import os

import pytest

from rvms.sections import RvmsFile
from rvms.units import units_by_serial
from rvms.writer import set_settings, WriteRefused
from rvms.diff import diff_bytes

BARE = "guava/guava_2026-07-20_download_bare_deviceform_1.rvms"
ESS = "guava/guava_2026-08-13_download_ess_deviceform_1.rvms"
UPLOAD = "papaya/papaya_2026-07-21_gui-export_ess_uploadform_1.rvms"


def test_edit_then_revert_reproduces_original_byte_for_byte(good_files):
    data = good_files[BARE]
    serial = sorted(units_by_serial(RvmsFile.parse(data)))[0]
    orig_abs = units_by_serial(RvmsFile.parse(data))[serial].setting(2) / 100
    out, edits = set_settings(data, [(serial, "absorption_V", 57.6)])
    assert len(edits) == 1 and edits[0].new_raw == 5760
    assert units_by_serial(RvmsFile.parse(out))[serial].setting(2) == 5760
    back, _ = set_settings(out, [(serial, "absorption_V", orig_abs)])
    assert back == data


def test_edit_all_inverters_changes_only_intended_bytes(good_files):
    data = good_files[BARE]
    out, edits = set_settings(data, [(None, "float_V", 54.2), (None, "absorption_V", 56.8)])
    assert len(out) == len(data)
    d = diff_bytes(data, out)
    assert not d.only_bookkeeping
    for u in d.units:
        assert {s["id"] for s in u.settings} <= {2, 3}
        assert u.header == [] and u.assistant == 0
        assert len(u.bookkeeping) == 4  # checksum trailer only; no timestamp/pointer change


def test_edit_works_on_ess_blocks_and_leaves_assistant_untouched(good_files):
    data = good_files[ESS]
    out, _ = set_settings(data, [(None, "float_V", 54.1)])
    a, b = RvmsFile.parse(data), RvmsFile.parse(out)
    for ua, ub in zip(units_by_serial(a).values(), units_by_serial(b).values()):
        assert ua.assistant_area == ub.assistant_area
    assert len(out) == len(data) and b.all_checksums_ok


def test_refuses_unverified_field_without_override(good_files):
    data = good_files[BARE]
    with pytest.raises(WriteRefused):
        set_settings(data, [(None, "vs_param52", 1000)])
    out, edits = set_settings(data, [(None, "vs_param52", 1000)], allow_unverified=True)
    assert edits[0].new_raw == 1000


def test_refuses_flag_registers_unknown_serial_and_bad_values(good_files):
    data = good_files[BARE]
    with pytest.raises(WriteRefused):
        set_settings(data, [(None, "flags0", 1)])
    with pytest.raises(WriteRefused):
        set_settings(data, [("HQ0000000000", "float_V", 54.0)])
    with pytest.raises((WriteRefused, ValueError)):
        set_settings(data, [(None, "float_V", 700.0)])
    with pytest.raises(KeyError):
        set_settings(data, [(None, "vs_soc_pct", 20)])   # retracted field


def test_refuses_upload_form_and_corrupt_input(good_files):
    with pytest.raises(WriteRefused):
        set_settings(good_files[UPLOAD], [(None, "float_V", 54.0)])
    corrupt = bytearray(good_files[BARE])
    corrupt[0x1060] ^= 0xFF
    with pytest.raises(WriteRefused):
        set_settings(bytes(corrupt), [(None, "float_V", 54.0)])


def test_legacy_field_names_still_resolve(good_files):
    out, edits = set_settings(good_files[BARE], [(None, "vs_return_V", 52.5), (None, "vs_entry_V", 51.0)])
    assert {e.field.id for e in edits} == {58, 54}


def test_reproduces_the_archived_prepared_files(good_files, manifest):
    """Regression: for each change-control record that has baseline + prepared + re-download, the
    prepared file must be reproducible from the baseline with this writer (same edit, same bytes)."""
    # baseline -> prepared pairs known from the change records (2026-07-20 charge-profile corrections)
    pairs = [
        ("guava/guava_2026-07-20_download_bare_deviceform_1.rvms", "guava/guava_2026-07-20_prepared_bare_deviceform_1.rvms",
         [(None, "absorption_V", 56.8), (None, "float_V", 54.0)]),
        ("mango/mango_2026-07-20_download_bare_deviceform_1.rvms", "mango/mango_2026-07-20_prepared_bare_deviceform_1.rvms",
         [(None, "absorption_V", 56.8), (None, "float_V", 54.0)]),
    ]
    for base, prepared, changes in pairs:
        if base not in good_files or prepared not in good_files:
            pytest.skip("fixture missing")
        out, _ = set_settings(good_files[base], changes)
        assert out == good_files[prepared], f"{prepared} is not baseline+edits"
