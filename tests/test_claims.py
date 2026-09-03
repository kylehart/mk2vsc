"""
Every claim in docs/FIELDS.md and units.py that can be checked against the corpus, checked against
the corpus.  These are the tests that make the field table trustworthy; when they fail on a new file
the *table* is what needs revising.
"""
import collections
import datetime as dt

from rvms.sections import RvmsFile
from rvms.units import unit_blocks, units_by_serial, N_SETTINGS
from rvms.fields import BY_ID, FIELDS, CONFIRMED, HIGH, UNKNOWN


def _units(good_files):
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            yield name, u


def test_serial_sits_at_0x3a_and_firmware_at_0x1b(good_files):
    for name, u in _units(good_files):
        assert u.raw[0x3A:0x3C] == b"HQ", name
        assert len(u.serial) == 11
        assert u.firmware_version == 2729560, f"{name}: firmware word differs -- new firmware in corpus?"
        assert u.u32(0x13) == 3


def test_two_blocks_per_file_have_distinct_serials_and_slots(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    for name, data in good_files.items():
        f = RvmsFile.parse(data)
        if by_file[name]["origin"] == "prepared":
            continue  # some archived v1 grafts are known-defective (both blocks slot (0,0)); device output never is
        by = units_by_serial(f)
        assert len(by) == 2, name
        slots = {u.slot for u in by.values()}
        assert len(slots) == 2, f"{name}: slot bytes (+0x35,+0x37) must differ between the pair"


def test_assistant_flag_values(good_files):
    seen = collections.Counter(u.assistant_flag for _, u in _units(good_files))
    assert set(seen) <= {0xF4, 0xF5, 0xE4, 0xE5}, seen
    for name, u in _units(good_files):
        # low nibble encodes the slot: x4 pairs with slot (00,00), x5 with (86,01)
        assert (u.assistant_flag & 0x0F) == (4 if u.slot == (0, 0) else 5), (name, u.slot, u.assistant_flag)


def test_upload_form_shift_puts_settings_at_0x63(good_files):
    n_upload = 0
    for name, u in _units(good_files):
        if u.is_upload_form:
            n_upload += 1
            assert u.settings_offset == 0x63
            assert u.raw[0x45:0x51] == bytes.fromhex("010008004a3981804e93d70c"), "constant 12-byte GUI blob prefix"
        else:
            assert u.settings_offset == 0x59
            assert u.raw[0x45:0x4F] == b"\x00" * 10
        assert u.setting(5) == 120, f"{name}: inverter output voltage not 120 -- offset model wrong for this block"
    assert n_upload >= 4, "corpus should contain upload-form blocks (GUI exports)"


def test_save_timestamp_is_a_plausible_unix_time(good_files):
    lo, hi = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc), dt.datetime(2026, 12, 31, tzinfo=dt.timezone.utc)
    for name, u in _units(good_files):
        t = u.save_datetime
        assert t is not None and lo <= t <= hi, (name, u.save_timestamp)


def test_confirmed_and_high_fields_decode_to_sensible_values(good_files):
    for name, u in _units(good_files):
        if u.assistant_area[:4] == b"\x40\x00\xa7\xfe" or u.setting(2) == 0:
            continue  # stub-installed blocks carry zeroed settings; recorded, not sensible
        abs_v, flt_v = u.setting(2) / 100, u.setting(3) / 100
        assert 40 <= abs_v <= 60 and 40 <= flt_v <= 60, (name, abs_v, flt_v)
        assert flt_v <= abs_v + 0.01, f"{name}: float above absorption"
        assert u.setting(4) in (35,), name                 # charge current, installer-set
        assert u.setting(6) == 500, name                   # 50.0 A input limit
        assert 30 <= u.setting(11) / 100 <= 52, name       # DC low shutdown
        assert u.setting(12) in (200, 640), name           # restart offset 2.0 / 6.4 V
        assert 45 <= u.setting(54) / 100 <= 55, name       # VS entry
        assert 50 <= u.setting(58) / 100 <= 65, name       # VS return (64.00 = unreachable, real bug)
        assert u.setting(64) in (0, 200, 300), name        # Ah
        assert u.setting(65) in (170, 190, 196), name      # 85/95/98 %
        assert u.setting(73) == 6300, name
        assert u.setting(81) in (0, 1), name
        assert u.setting(88) == 5200, name


def test_grid_code_flag_tracks_gui_authored_ess(good_files, manifest):
    """Setting 81 is 0 on every bare download and 1 on every block whose assistant was installed via the GUI."""
    by_file = {e["file"]: e for e in manifest["entries"]}
    for name, u in _units(good_files):
        e = by_file[name]
        if e["state"] == "bare" and e["origin"] == "download":
            assert u.setting(81) == 0, name
        if e["origin"] == "gui-export" and u.has_assistant_flag:
            assert u.setting(81) == 1, name


def test_retracted_vs_soc_field_is_the_high_byte_of_setting_88(good_files):
    for name, u in _units(good_files):
        if u.setting(88) == 5200:
            assert u.raw[u.setting_offset(88) + 1] == 0x14 == 20


def test_settings_region_128_to_189_is_unprogrammed_on_bare_blocks(good_files):
    for name, u in _units(good_files):
        if not u.has_assistant_flag:
            assert all(v == 0xFFFF for v in u.settings()[129:N_SETTINGS]), name


def test_field_table_is_consistent():
    ids = [f.id for f in FIELDS]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    for f in FIELDS:
        assert f.offset == 0x59 + 2 * f.id
        assert f.confidence in ("CONFIRMED", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
        if f.confidence in (CONFIRMED, HIGH):
            assert f.evidence, f"{f.name}: a CONFIRMED/HIGH field must state its evidence"
        if f.confidence == UNKNOWN:
            assert f.observed, f"{f.name}: an UNKNOWN field must at least record observed values"
