"""Settings 190/191 are the grid-code / LOM words, not an assistant-record header (xcellsior FINDINGS 7.4)."""
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


def test_lom_words_take_only_the_bench_values(good_files):
    """Every block reads 190 in {0xffff, 0xfff5} and 191 in {0xffff, 0x0000, 0xff00, 0x0001, 0x0101}."""
    seen = collections.Counter()
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            w = grid_code_words(u)
            assert w["w190"] in (0xFFFF, 0xFFF5), (name, u.serial, w)
            assert w["w191"] in (0xFFFF, 0x0000, 0xFF00, 0x0001, 0x0101), (name, u.serial, w)
            seen[w["state"]] += 1
    assert seen["never"] and seen["lom_b"] and seen["no_lom"] and seen["residual"], seen
    assert not seen["other"], seen


def test_grid_code_blocks_carry_lom_words_and_bare_never_coded_blocks_do_not(good_files, manifest):
    """Device downloads only: hand-prepared files in the corpus stamped setting 81 without the LOM words."""
    by_file = {e["file"]: e for e in manifest["entries"]}
    for name, data in good_files.items():
        if by_file[name]["origin"] != "download":
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            w = grid_code_words(u)
            if w["grid_code"] == 1:
                assert w["w190"] == 0xFFF5 and w["w191"] in (0x0001, 0x0101), (name, u.serial, w)
                assert w["w128"] & 0x00FF == w["w191"] & 0x00FF or w["w128"] == 0xFF01, (name, u.serial, w)
            if w["state"] == "never":
                assert w["w128"] == 0xFFFF and u.setting(81) == 0


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
