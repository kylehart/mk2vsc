"""Settings 190/191 are grid-code words in the settings array, not an assistant-record header."""
import collections

from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks, N_SETTINGS
from mk2vsc.assistants import grid_code_words, parse_assistant_area


def test_settings_array_has_192_entries_and_the_area_starts_after_191(good_files):
    assert N_SETTINGS == 192
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            assert u.assistant_area_offset == u.settings_offset + 384
            assert len(u.settings()) == 192


def test_grid_code_words_take_only_the_observed_values(good_files):
    seen = collections.Counter()
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            w = grid_code_words(u)
            assert w["w190"] in (0xFFFF, 0xFFF5), (name, u.serial, w)
            assert w["w191"] in (0xFFFF, 0x0000, 0xFF00, 0x0001, 0x0101), (name, u.serial, w)
            seen[w["state"]] += 1
    assert seen["never"] and seen["set"] and seen["residual"], seen


GUI_AUTHORED = [   # ESS installs authored in VEConfigure by the installer and running (docs/ESS_INJECTION.md section 1)
    "system_b/system_b_2026-08-12_download_ess_deviceform_1.rvms",
    "system_c/system_c_2026-07-24_download_ess_deviceform_1.rvms",
    "system_a/system_a_2026-09-03_download_ess_deviceform_1.rvms",
]
GRAFTED = [        # our byte-grafted installs, stored by the device and never started
    "system_a/system_a_2026-08-13_download_ess_deviceform_1.rvms",
    "system_d/system_d_2026-08-13_download_ess_deviceform_1.rvms",
]


def test_on_gui_authored_downloads_128_equals_191_per_inverter(good_files):
    """128 == 191 on each inverter; the pair may differ (System C) or match (Systems A, B); 190 is 0xfff5 throughout."""
    per_system = {}
    for name in GUI_AUTHORED:
        vals = set()
        for u in unit_blocks(RvmsFile.parse(good_files[name])):
            w = grid_code_words(u)
            assert w["grid_code"] == 1 and w["w190"] == 0xFFF5 and w["words_agree"], (name, u.serial, w)
            assert w["w191"] in (0x0001, 0x0101)
            vals.add(w["w191"])
        per_system[name.split("/")[0]] = vals
    assert per_system == {"system_b": {0x0001}, "system_c": {0x0001, 0x0101}, "system_a": {0x0101}}, per_system


def test_grafted_installs_show_128_and_191_disagreeing_on_one_inverter(good_files):
    for name in GRAFTED:
        agree = [grid_code_words(u)["words_agree"] for u in unit_blocks(RvmsFile.parse(good_files[name]))]
        assert sorted(agree) == [False, True], (name, agree)


def test_never_coded_blocks_read_ffff_in_all_three_words(good_files):
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            w = grid_code_words(u)
            if w["state"] == "never":
                assert (w["w128"], w["w190"], w["w191"]) == (0xFFFF, 0xFFFF, 0xFFFF) and u.setting(81) == 0


OUR_BIT11_GRAFTS = {   # bit 11 set with a fixed curve: authored by our graft tooling, stored by the device; not GUI evidence
    "system_a/system_a_2026-08-12_prepared_ess_deviceform_3.rvms",
    "system_a/system_a_2026-08-13_download_ess_deviceform_2.rvms",
    "system_a/system_a_2026-08-13_download_ess_deviceform_3.rvms",
}


def test_flags0_bit11_tracks_the_charge_curve_on_every_authored_block(good_files):
    """Victron names setting 0 bit 11 EnableReducedFloat (storage mode); xcellsior reads it as adaptive charge.
    On every GUI- or device-authored block bit 11 is set exactly when charge_characteristic = 3, so the corpus
    cannot separate the two readings. The only exceptions are three blocks our own grafts produced."""
    both = collections.Counter()
    for name, data in good_files.items():
        if name in OUR_BIT11_GRAFTS:
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            both[((u.setting(0) >> 11) & 1, u.setting(10))] += 1
    assert set(both) == {(1, 3), (0, 1)}, both


def test_setting_17_is_the_relay_mode_default_on_every_block(good_files):
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            assert u.setting(17) == 6400 and u.setting(18) == 4700


def test_gui_ess_record_lengths_unchanged_under_the_new_model(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    lengths = collections.Counter()
    for name, data in good_files.items():
        e = by_file[name]
        if e["origin"] != "download" or e["state"] != "ess":
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            a = parse_assistant_area(u)
            assert a["kind"] == "records"
            lengths[a["records"][0]["length"]] += 1
    assert set(lengths) == {704, 1152}, lengths
