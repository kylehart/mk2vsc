import os

import pytest

from mk2vsc.sections import RvmsFile
from mk2vsc.units import units_by_serial
from mk2vsc.writer import set_settings, WriteRefused
from mk2vsc.diff import diff_bytes

BARE = "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"
ESS = "system_a/system_a_2026-08-13_download_ess_deviceform_1.rvms"
UPLOAD = "system_c/system_c_2026-07-21_gui-export_ess_uploadform_1.rvms"


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
        set_settings(data, [(None, "fs_ubat_start_V", 57.72)])
    out, edits = set_settings(data, [(None, "fs_ubat_start_V", 57.72)], allow_unverified=True)
    assert edits[0].new_raw == 5772


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


def test_aliases_resolve(good_files):
    out, edits = set_settings(good_files[BARE], [(None, "vs_return", 52.5), (None, "vs_entry", 51.0)])
    assert {e.field.id for e in edits} == {58, 54}


def test_reproduces_the_archived_prepared_files(good_files, manifest):
    """Regression: for each change-control record that has baseline + prepared + re-download, the
    prepared file must be reproducible from the baseline with this writer (same edit, same bytes)."""
    # baseline -> prepared pairs known from the change records (2026-07-20 charge-profile corrections)
    pairs = [
        ("system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms", "system_a/system_a_2026-07-20_prepared_bare_deviceform_1.rvms",
         [(None, "absorption_V", 56.8), (None, "float_V", 54.0)]),
        ("system_b/system_b_2026-07-20_download_bare_deviceform_1.rvms", "system_b/system_b_2026-07-20_prepared_bare_deviceform_1.rvms",
         [(None, "absorption_V", 56.8), (None, "float_V", 54.0)]),
    ]
    for base, prepared, changes in pairs:
        if base not in good_files or prepared not in good_files:
            pytest.skip("fixture missing")
        out, _ = set_settings(good_files[base], changes)
        assert out == good_files[prepared], f"{prepared} is not baseline+edits"


def test_refuses_implausible_voltages_and_float_above_absorption(good_files):
    data = good_files[BARE]
    with pytest.raises(WriteRefused):
        set_settings(data, [(None, "absorption_V", 5.68)])          # forgot the decimal place
    with pytest.raises(WriteRefused):
        set_settings(data, [(None, "float_V", 60.0), (None, "absorption_V", 50.0)])
    out, _ = set_settings(data, [(None, "absorption_V", 5.68)], allow_out_of_range=True)
    first = sorted(units_by_serial(RvmsFile.parse(out)))[0]
    assert units_by_serial(RvmsFile.parse(out))[first].setting(2) == 568


def test_refuses_stub_downloads(good_files):
    stub = "system_a/system_a_2026-08-12_download_stub_deviceform_1.rvms"
    with pytest.raises(WriteRefused):
        set_settings(good_files[stub], [(None, "float_V", 54.0)])


def test_refuses_fractional_value_for_integer_field(good_files):
    with pytest.raises(WriteRefused):
        set_settings(good_files[BARE], [(None, "charge_current_A", 35.7)])


# ---------------------------------------------------------------- plausibility bounds scale with nominal voltage
VOLT_IDS = (2, 3, 11, 12, 17, 18, 54, 58, 68, 88)   # every /100 V setting the writer or rules read


def make_24v_twin(data: bytes) -> bytes:
    """A synthetic 24 V file: halve the schema range and the stored value of every /100 V setting, keep
    everything else, recompute checksums.  Alignment still passes because value and range move together."""
    import struct
    from mk2vsc.schema import HEADER_LEN, RECORD_LEN
    from mk2vsc.sections import SECTION_INFO, SECTION_DATA
    f = RvmsFile.parse(data)
    payloads = []
    for s in f.sections:
        pl = bytearray(s.payload)
        if s.name == SECTION_INFO:
            for sid in VOLT_IDS:
                o = HEADER_LEN + RECORD_LEN * sid
                sc, off, d, mn, mx = struct.unpack_from("<hhHHH", pl, o)
                struct.pack_into("<hhHHH", pl, o, sc, off, d // 2, mn // 2, mx // 2)
        elif s.name == SECTION_DATA:
            u = [x for x in units_by_serial(f).values() if x.section is s][0]
            for sid in VOLT_IDS:
                o = u.setting_offset(sid) - (len(s.name) + 4)
                v = struct.unpack_from("<H", pl, o)[0]
                struct.pack_into("<H", pl, o, v // 2)
        payloads.append(bytes(pl))
    return f.rebuild(payloads).to_bytes()


def test_24v_twin_accepts_24v_absorption_and_refuses_48v_values(good_files):
    twin = make_24v_twin(good_files[BARE])
    out, edits = set_settings(twin, [(None, "absorption_V", 28.4), (None, "float_V", 27.0)])
    assert {e.new_raw for e in edits} == {2840, 2700}
    with pytest.raises(WriteRefused) as ei:
        set_settings(twin, [(None, "absorption_V", 57.6)])
    # the schema range (24.00 to 32.00 V on the twin) refuses first; the scaled plausibility bound is the backstop
    assert "24.0..32.0 V" in str(ei.value) or "24 V system" in str(ei.value)


def test_48v_file_still_refuses_a_24v_absorption(good_files):
    with pytest.raises(WriteRefused) as ei:
        set_settings(good_files[BARE], [(None, "absorption_V", 28.4)], allow_out_of_range=False)
    assert "48 V system" in str(ei.value) or "outside the device's own range" in str(ei.value)


# ---------------------------------------------------------------- bit-level writes (decision 2: qualified bits only)
def test_set_lithium_bit_changes_exactly_one_bit_on_the_target_block(good_files):
    from mk2vsc.writer import set_bits
    data = good_files[BARE]
    units = units_by_serial(RvmsFile.parse(data))
    off = [s for s, u in units.items() if not (u.setting(60) >> 4) & 1]
    assert off == ["HQ0000A0002"], "the 2026-07-20 System A download has the lithium flag clear on unit 2 only"
    out, edits = set_bits(data, [("HQ0000A0002", "flags2", 4, True)])
    assert len(edits) == 1 and edits[0].bit == 4
    assert edits[0].new_raw == edits[0].old_raw | 0x10
    new_units = units_by_serial(RvmsFile.parse(out))
    assert new_units["HQ0000A0002"].setting(60) == units["HQ0000A0002"].setting(60) | 0x10
    assert new_units["HQ0000A0001"].setting(60) == units["HQ0000A0001"].setting(60)
    d = diff_bytes(data, out)
    for u in d.units:
        assert {s["id"] for s in u.settings} <= {60}
    # clearing it again reproduces the input byte for byte
    back, _ = set_bits(out, [("HQ0000A0002", "flags2", 4, False)])
    assert back == data


def test_set_bits_on_every_inverter_is_a_no_op_where_already_set(good_files):
    from mk2vsc.writer import set_bits
    data = good_files[BARE]
    out, edits = set_bits(data, [(None, "flags2", 4, True)])
    assert len(edits) == 2
    changed = [e for e in edits if e.old_raw != e.new_raw]
    assert [e.serial for e in changed] == ["HQ0000A0002"]


def test_set_bits_refuses_unqualified_bits_non_flag_fields_and_unsettable_bits(good_files):
    from mk2vsc.writer import set_bits
    data = good_files[BARE]
    with pytest.raises(WriteRefused) as ei:
        set_bits(data, [(None, "flags0", 11, False)])          # storage mode / adaptive: three published meanings
    assert "qualif" in str(ei.value)
    with pytest.raises(WriteRefused):
        set_bits(data, [(None, "absorption_V", 0, True)])       # not a flag register
    with pytest.raises(WriteRefused) as ei:
        set_bits(data, [(None, "flags0", 15, False)], allow_unqualified=True)   # bit 15 is outside the 0x6ffc settable mask
    assert "settable" in str(ei.value)
    out, edits = set_bits(data, [(None, "flags0", 11, False)], allow_unqualified=True)
    assert all(not (e.new_raw >> 11) & 1 for e in edits)
