from rvms.diff import diff_bytes, render

# Two consecutive downloads of the same system with no configuration change (Mango, 2026-07-24).
# The two blocks SWAPPED file position between these downloads.
A = "mango/mango_2026-07-24_download_bare_deviceform_1.rvms"
B = "mango/mango_2026-07-24_download_bare_deviceform_2.rvms"
STUB = "mango/mango_2026-07-24_download_stub_deviceform_1.rvms"


def test_consecutive_downloads_differ_only_in_bookkeeping(good_files):
    d = diff_bytes(good_files[A], good_files[B])
    assert not d.identical
    assert d.only_bookkeeping, render(d)
    for u in d.units:
        n = u.length_a - 2 if u.length_a in (484,) else u.length_a   # raw length (see UnitBlock.length)
        allowed = {0x0F, 0x10, 0x4F, 0x50, 0x51, 0x52}
        assert all(o in allowed or o >= 470 for o in u.bookkeeping), u.bookkeeping


def test_block_order_swap_is_invisible_when_comparing_by_serial(good_files):
    """Among the Mango bare downloads there is a pair whose two blocks swapped file position."""
    from rvms.sections import RvmsFile
    from rvms.units import unit_blocks
    mango = {k: v for k, v in good_files.items() if k.startswith("mango/") and "download_bare" in k}
    orders = {k: [u.serial for u in unit_blocks(RvmsFile.parse(v))] for k, v in mango.items()}
    swapped = [(a, b) for a in orders for b in orders if a < b and orders[a] == orders[b][::-1]]
    assert swapped, "corpus should contain a swapped-order pair"
    hits = 0
    for a, b in swapped:
        if len(good_files[a]) != len(good_files[b]):
            continue  # the two June 2026 legacy-layout files are a different length
        naive = sum(1 for x, y in zip(good_files[a], good_files[b]) if x != y)
        d = diff_bytes(good_files[a], good_files[b])
        if d.only_bookkeeping:
            assert naive > 20, "positional diff should be misleading when block order swapped"
            hits += 1
    assert hits >= 1, "expected at least one swapped-order pair that differs only in bookkeeping"


def test_stub_download_is_reported_as_content_change(good_files):
    d = diff_bytes(good_files[B], good_files[STUB])
    assert not d.only_bookkeeping
    for u in d.units:
        assert u.length_a != u.length_b
        assert "assistant" in u.note


def test_identical(good_files):
    d = diff_bytes(good_files[A], good_files[A])
    assert d.identical and render(d) == "identical"


def test_cross_form_diff_compares_settings_by_id(good_files):
    dev = "papaya/papaya_2026-07-21_download_ess_deviceform_1.rvms"   # device download after Rob's install
    up = "papaya/papaya_2026-07-21_gui-export_ess_uploadform_1.rvms"    # the GUI export that was uploaded
    if dev not in good_files or up not in good_files:
        return
    d = diff_bytes(good_files[up], good_files[dev])
    for u in d.units:
        assert u.form_a == "upload" and u.form_b == "device"
        assert u.settings == [], "GUI export and the device's re-download must agree on every setting"
