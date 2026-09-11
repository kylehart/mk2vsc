"""
Single-unit and three-phase file shapes, on the synthetic fixtures under fixtures/synthetic/ (built from corpus
blocks by tools/gen_synthetic_fixtures.py) and on corpus blocks with one header byte altered.

What these tests prove is the container and layout model on those shapes: block count, checksums, alignment
against the file's own schema, byte-exact round trip, the per-slot phase/unit bytes, the 24-bit firmware
number, the assistant flag's high nibble, the writer on a one-block file, and that the pair rules D2/E2 are
reported not applicable on one unit rather than firing or crashing.  The same checks are run on real files
outside the repository with tools/validate_dir.py (docs/QA.md).
"""
import json
import os
import shutil
import struct

import pytest

import mk2vsc
from mk2vsc.sections import RvmsFile, SECTION_INFO
from mk2vsc.units import (unit_blocks, units_by_serial, OFF_FIRMWARE, OFF_ASSISTANT_FLAG, OFF_SLOT_A, OFF_SLOT_B,
                          PREFIX_LEN, FIRMWARE_MASK, PHASE_LABELS)
from mk2vsc.schema import schema_of, firmware_of_schema, firmware_word_of_schema
from mk2vsc.align import check as align_check
from mk2vsc.census import census_text
from mk2vsc.decode import decode_bytes
from mk2vsc.diff import diff_bytes
from mk2vsc.writer import set_settings
from mk2vsc.diagnose import diagnose_bytes, render, Report
from mk2vsc.cli import main
from tests.conftest import FIXTURES

SYN = os.path.join(FIXTURES, "synthetic")
SINGLE = os.path.join(SYN, "system_a_2026-07-20_synthetic_bare_deviceform_1.rvsc")
THREE = os.path.join(SYN, "system_a_2026-09-03_synthetic_ess_deviceform_1.rvms")
SIX = os.path.join(SYN, "system_a_2026-09-03_synthetic_ess_deviceform_2.rvms")
SINGLE_SOURCE = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_1.rvms")
THREE_SOURCE = os.path.join(FIXTURES, "system_a", "system_a_2026-09-03_download_ess_deviceform_1.rvms")


def _read(p):
    with open(p, "rb") as fh:
        return fh.read()


# ------------------------------------------------------------------ the generator reproduces the files on disk
def test_synthetic_fixtures_are_what_the_generator_builds():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", os.path.join(os.path.dirname(FIXTURES), "tools", "gen_synthetic_fixtures.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    built = gen.build()
    assert set(built) == {os.path.relpath(p, FIXTURES).replace(os.sep, "/") for p in (SINGLE, THREE, SIX)}
    for rel, data in built.items():
        assert _read(os.path.join(FIXTURES, rel)) == data, rel


# ------------------------------------------------------------------ every synthetic file: container, schema, alignment
def test_synthetic_file_parses_validates_aligns_and_round_trips(synthetic_path):
    data = _read(synthetic_path)
    f = RvmsFile.parse(data)
    assert f.all_checksums_ok and f.to_bytes() == data and f.rebuild().to_bytes() == data
    assert f.sections[-1].next_ptr == len(data)
    sch = schema_of(f)
    units = unit_blocks(f)
    assert len(units) in (1, 3, 6)
    for u in units:
        assert align_check(u, sch).ok and not u.is_upload_form and u.firmware_version == 2729560 and u.firmware_word_high_byte == 0
    assert len(units_by_serial(f)) == len(units)
    text, ok = census_text(data, os.path.basename(synthetic_path))
    assert ok and f"{len(units)} inverter(s)" in text and "alignment OK" in text


# ------------------------------------------------------------------ single unit
def test_single_unit_is_the_byte_prefix_of_its_source():
    single, src = _read(SINGLE), _read(SINGLE_SOURCE)
    orig = RvmsFile.parse(src)
    assert single == src[: orig.unit_sections[1].start]
    f = RvmsFile.parse(single)
    assert [s.name for s in f.sections] == [b"Mk2vscInfo", SECTION_INFO, b"BareSettingData"]
    u = unit_blocks(f)[0]
    assert u.is_last and u.serial == "HQ0000A0001" and u.slot == (0, 0) and u.phase_summary == "L1, unit 0"
    assert u.raw == unit_blocks(orig)[0].raw


def test_single_unit_census_show_verify_and_check(capsys):
    single = _read(SINGLE)
    cfg = mk2vsc.loads(single)
    assert cfg.valid and cfg.serials == ["HQ0000A0001"] and cfg.form == "device"
    assert cfg["HQ0000A0001"]["absorption"] == 56.0
    text, ok = census_text(single, "one.rvsc")
    assert ok and "1 inverter(s)" in text and "phase L1, unit 0" in text
    ok, report = mk2vsc.api.verify_bytes(single, single)
    assert ok and "VERIFIED" in report
    d = diff_bytes(single, single)
    assert d.identical
    ok, res = cfg.check(absorption=56.0, float=54.0)
    assert ok, res
    assert main(["show", SINGLE]) == 0
    out = capsys.readouterr().out
    assert "1 inverter(s)" in out and "phase L1, unit 0" in out and "alignment OK" in out
    assert main(["validate", SINGLE]) == 0 and main(["check", SINGLE]) == 0 and main(["census", SINGLE]) == 0
    capsys.readouterr()
    assert main(["show", SINGLE, "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert len(j["units"]) == 1 and j["units"][0]["phase"] == "L1" and j["units"][0]["unit_index"] == 0


def test_single_unit_diagnose_runs_the_block_rules_and_reports_pair_rules_not_applicable(capsys):
    fr = diagnose_bytes(_read(SINGLE), name="one.rvsc")
    assert fr.status == "ok" and fr.serials == ["HQ0000A0001"] and fr.chemistry == "lithium"
    assert not [f for f in fr.findings if f.rule in ("D2", "E2")]
    assert set(fr.not_applicable) == {"D2", "E2"}
    assert all("needs 2 or more inverters; this file has 1" == why for why in fr.not_applicable.values())
    d = Report(files=[fr]).as_dict()
    assert d["report_version"] == 1 and d["files"][0]["not_applicable"] == fr.not_applicable
    assert "not applicable: D2 (needs 2 or more inverters; this file has 1); E2 (" in render(Report(files=[fr]))
    assert main(["diagnose", SINGLE]) == 0
    assert "not applicable: D2" in capsys.readouterr().out
    # a pair does not report anything as not applicable
    pair = diagnose_bytes(_read(SINGLE_SOURCE), name="pair.rvms")
    assert pair.status == "ok" and pair.not_applicable == {} and any(f.rule == "D2" for f in pair.findings)


def test_single_unit_writer_edit_changes_only_the_intended_bytes(tmp_path, capsys):
    single = _read(SINGLE)
    out, edits = set_settings(single, [(None, "absorption_V", 56.8), (None, "float_V", 54.1)])
    assert len(out) == len(single) and len(edits) == 2
    f = RvmsFile.parse(out)
    assert f.all_checksums_ok
    u = unit_blocks(f)[0]
    assert u.setting(2) == 5680 and u.setting(3) == 5410
    changed = {i for i in range(len(out)) if out[i] != single[i]}
    allowed = set()
    for e in edits:
        allowed |= {e.offset_in_file, e.offset_in_file + 1}
    ck = f.unit_sections[0].checksum_offset
    allowed |= {ck, ck + 1, ck + 2, ck + 3}
    assert changed <= allowed and changed >= {e.offset_in_file for e in edits}
    # revert reproduces the fixture byte for byte
    back, _ = set_settings(out, [(None, "absorption_V", 56.0), (None, "float_V", 54.0)])
    assert back == single
    # the CLI keeps the extension: FILE.edited.rvsc next to the input
    src = tmp_path / "download.rvsc"
    shutil.copyfile(SINGLE, src)
    assert main(["edit", str(src), "absorption=56.8"]) == 0
    assert "download.edited.rvsc" in capsys.readouterr().out and (tmp_path / "download.edited.rvsc").exists()
    assert main(["verify", str(tmp_path / "download.edited.rvsc"), str(src)]) == 2       # a real change: not bookkeeping


# ------------------------------------------------------------------ three-phase
@pytest.mark.parametrize("path,n", [(THREE, 3), (SIX, 6)])
def test_three_phase_slot_bytes_decode_per_unit(path, n, capsys):
    f = RvmsFile.parse(_read(path))
    units = unit_blocks(f)
    assert len(units) == n
    for i, u in enumerate(units):
        phase = i % 3
        assert u.slot == (4 * phase, i) and u.unit_index == i and u.phase_byte == 4 * phase
        assert u.phase_label == ("L1", "L2", "L3")[phase]
        assert u.assistant_flag == 0xE8 + phase and u.has_assistant_flag and (u.assistant_flag & 0x0F) == 8 + phase
        assert u.serial == f"HQ0000A{3 + i:04d}"
    text, ok = census_text(_read(path), "three.rvms")
    assert ok and "flag e9, phase L2, unit 1" in text and "flag ea, phase L3, unit 2" in text
    assert main(["show", path]) == 0
    out = capsys.readouterr().out
    assert f"{n} inverter(s)" in out and "phase L2, unit 1" in out and "phase L3, unit 2" in out
    j = decode_bytes(_read(path))
    assert [u["phase"] for u in j["units"]][:3] == ["L1", "L2", "L3"] and [u["unit_index"] for u in j["units"]] == list(range(n))


def test_three_phase_diagnose_runs_every_rule(capsys):
    for path in (THREE, SIX):
        fr = diagnose_bytes(_read(path), name=os.path.basename(path))
        assert fr.status == "ok" and fr.not_applicable == {} and fr.findings == [] and len(fr.serials) in (3, 6)
        assert fr.editable
    assert main(["diagnose", THREE]) == 0
    out = capsys.readouterr().out
    assert "3 inverter(s)" in out and "no findings" in out and "not applicable" not in out


def test_e2_on_more_than_two_inverters_says_the_by_file_remedy_is_untested_there():
    """E2 fires per block, so it reaches three-phase files; `mk2vsc assistant` was derived from two-inverter
    systems, so the message must not send a six-unit operator down an untested by-file path."""
    from mk2vsc.assistants import parse_assistant_area
    f = RvmsFile.parse(_read(THREE))
    payloads = []
    for i, s_ in enumerate(f.sections):
        p_ = bytearray(s_.payload)
        if s_.is_unit and i == len(f.sections) - 1:        # strip the last block's records: some have, one lacks
            area_off = 0x59 + 2 * 192 - PREFIX_LEN
            p_[area_off:] = b"\x00\x00\xff\x00\x0b"
            p_[OFF_ASSISTANT_FLAG - PREFIX_LEN] = 0xF8
        payloads.append(bytes(p_))
    data = f.rebuild(payloads).to_bytes()
    kinds = [parse_assistant_area(u)["kind"] for u in unit_blocks(RvmsFile.parse(data))]
    assert kinds.count("records") == 2 and "none" in kinds, kinds
    fr = diagnose_bytes(data, name="three.rvms", assume={"ess_intended": "yes"})
    e2 = [x for x in fr.findings if x.rule == "E2"]
    assert len(e2) == 1 and "more than two inverters" in e2[0].message
    assert "never run on one like yours" in e2[0].message and "of the pair" not in e2[0].message
    # the two-inverter case keeps the pair wording and carries no caveat
    pair = diagnose_bytes(_read(os.path.join(FIXTURES, "system_c", "system_c_2026-07-20_download_half-ess_deviceform_1.rvms")),
                          name="c.rvms", assume={"ess_intended": "yes"})
    pe2 = [x for x in pair.findings if x.rule == "E2"]
    assert len(pe2) == 1 and "a parallel pair" in pe2[0].message and "more than two inverters" not in pe2[0].message


def test_three_phase_clones_carry_the_source_block_apart_from_slot_bytes_and_serial():
    src = units_by_serial(RvmsFile.parse(_read(THREE_SOURCE)))["HQ0000A0001"]
    for u in unit_blocks(RvmsFile.parse(_read(THREE))):
        a, b = bytearray(u.raw), bytearray(src.raw)
        for off in (0x0F, 0x10, 0x11, 0x12, 0x35, 0x36, 0x37):     # next pointer (position), slot bytes
            a[off] = b[off] = 0
        a[0x3A: 0x45] = b[0x3A: 0x45] = b"\x00" * 11
        assert a[: -4] == b[: -4], u.serial          # everything but the checksum
        assert u.assistant_area == src.assistant_area and u.settings() == src.settings()


# ------------------------------------------------------------------ the firmware word's high byte (docs/FORMAT.md 3.3)
def _with_firmware_high_byte(data: bytes, high: int) -> bytes:
    """Every block's firmware word and the schema header's word with bits 24..31 set to ``high``; checksums rebuilt."""
    f = RvmsFile.parse(data)
    payloads = []
    for s in f.sections:
        p = bytearray(s.payload)
        if s.name == SECTION_INFO:
            p[7] = high
        elif s.is_unit:
            p[OFF_FIRMWARE + 3 - PREFIX_LEN] = high
        payloads.append(bytes(p))
    return f.rebuild(payloads).to_bytes()


def test_firmware_number_is_the_low_24_bits_of_the_word(good_files):
    src = good_files["system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"]
    data = _with_firmware_high_byte(src, 0xC7)
    f = RvmsFile.parse(data)
    assert f.all_checksums_ok and len(data) == len(src)
    info = f.section(SECTION_INFO).payload
    assert firmware_word_of_schema(info) == 0xC7000000 | 2729560 and firmware_of_schema(info) == 2729560
    for u in unit_blocks(f):
        assert u.firmware_word == 0xC7000000 | 2729560 and u.firmware_version == 2729560 and u.firmware_word_high_byte == 0xC7
        assert align_check(u, schema_of(f)).ok, "the settings array is untouched: alignment does not depend on the word"
        assert u.summary()["firmware"] == 2729560 and u.summary()["firmware_word_high_byte"] == 0xC7
    text, ok = census_text(data, "hb.rvms")
    assert ok and "firmware 2729560 (word high byte 0xc7)" in text and "3341293528" not in text
    assert "(word high byte 0xc7)" in mk2vsc.loads(data).summary(), "`show` carries the note too"
    assert all(u.summary()["assistant_present"] is u.has_assistant_flag for u in unit_blocks(f))
    assert "schema parsed (192 records, firmware 2729560 (word high byte 0xc7))" in text
    # the corpus text is unchanged: no note when the high byte is zero
    plain, _ = census_text(src, "hb.rvms")
    assert "high byte" not in plain and "firmware 2729560," in plain
    assert FIRMWARE_MASK == 0xFFFFFF and 9_999_999 < 2 ** 24
    d = diff_bytes(src, data)
    assert not d.only_bookkeeping and all(not ud.settings for ud in d.units), "a header byte, never a setting"


def test_assistant_flag_is_read_by_its_high_nibble(good_files):
    src = good_files["system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"]
    f = RvmsFile.parse(src)
    for flag, expect in ((0xF0, False), (0xE0, True), (0xE8, True), (0xEA, True), (0xF4, False), (0xE5, True)):
        payloads = []
        for s in f.sections:
            p = bytearray(s.payload)
            if s.is_unit:
                p[OFF_ASSISTANT_FLAG - PREFIX_LEN] = flag
            payloads.append(bytes(p))
        for u in unit_blocks(f.rebuild(payloads)):
            assert u.has_assistant_flag is expect and u.assistant_flag == flag


def test_records_imply_the_assistant_flag_but_not_the_converse(good_files):
    """The one direction of the flag/area relation that holds on the corpus, and the counterexamples that
    kill the converse.  tools/validate_dir.py scores exactly this; `has_assistant_flag` is not evidence of
    records (stub, container and empty areas sit behind an `e` nibble too)."""
    from mk2vsc.assistants import parse_assistant_area
    records = converse_counterexamples = 0
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            kind = parse_assistant_area(u)["kind"]
            if kind == "records":
                records += 1
                assert u.has_assistant_flag, (name, u.serial, hex(u.assistant_flag))
            elif u.has_assistant_flag:
                converse_counterexamples += 1          # e nibble, no records: stub / container / none
    assert records >= 40 and converse_counterexamples >= 6, (records, converse_counterexamples)


def test_slot_is_the_phase_and_unit_bytes(good_files):
    """`slot` keys the blocks in upload_form and the graft; it must stay the same two bytes the named
    properties read, or those two representations drift."""
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            assert u.slot == (u.phase_byte, u.unit_index) == (u.raw[0x35], u.raw[0x37]), name


def test_phase_labels_cover_the_observed_values_and_nothing_else():
    assert PHASE_LABELS == {0x00: "L1", 0x04: "L2", 0x08: "L3", 0x86: "L2 (split-phase)"}
    f = RvmsFile.parse(_read(SINGLE_SOURCE))
    assert sorted(u.phase_label for u in unit_blocks(f)) == ["L1", "L2 (split-phase)"]
    assert sorted(u.unit_index for u in unit_blocks(f)) == [0, 1]


# ------------------------------------------------------------------ tools/validate_dir.py: aggregate counts only
def _validate_dir(path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("vd", os.path.join(os.path.dirname(FIXTURES), "tools", "validate_dir.py"))
    vd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd)
    rc = vd.main([path])
    return rc, capsys.readouterr().out


def test_validate_dir_prints_aggregates_and_nothing_identifying(capsys):
    rc, out = _validate_dir(SYN, capsys)
    assert "3 files, 10 inverter blocks" in out and "HQ0000" not in out and "system_a" not in out and "2026-" not in out
    assert "1      1" in out and "3      1" in out and "6      1" in out          # by unit count
    for check in ("parse", "checksums", "round_trip", "layout", "schema_192", "alignment", "census", "records_imply_assistant_flag"):
        assert any(line.startswith(check) and line.split()[1:] == ["3", "0", "0"] for line in out.splitlines()), check
    # the single-unit fixture keeps the pair's flag byte f4 (it is a byte prefix); real single-unit files carry
    # low nibble 0, so the phase-model check fails on it by construction and the exit status says so
    assert any(line.startswith("phase_model") and line.split()[1:] == ["2", "1", "0"] for line in out.splitlines())
    assert rc == 1
    rc, out = _validate_dir(os.path.join(FIXTURES, "system_d"), capsys)
    assert rc == 0 and "20 files" in out and "HQ0000" not in out
    assert any(line.startswith("phase_model") and line.split()[1:] == ["0", "0", "20"] for line in out.splitlines()), "pairs are not scored"
    assert any(line.startswith("alignment") and line.split()[1:] == ["20", "0", "0"] for line in out.splitlines())
    # every well-formed corpus block satisfies the records=>flag rule; only the KNOWN_BAD negatives fail, at parse
    assert any(line.startswith("records_imply_assistant_flag") and line.split()[1:] == ["20", "0", "0"] for line in out.splitlines())


def _vd_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vd", os.path.join(os.path.dirname(FIXTURES), "tools", "validate_dir.py"))
    vd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd)
    return vd


def test_validate_dir_failure_paths_and_exit_codes(tmp_path, capsys):
    vd = _vd_module()
    # a deliberately broken fixture: the checks that depend on parsing report False, and the run exits 1
    d = tmp_path / "bad"
    d.mkdir()
    shutil.copyfile(os.path.join(FIXTURES, "system_a", "system_a_2026-07-21_prepared_ess_uploadform_1.rvms"), d / "a.rvms")
    assert vd.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "1 files" in out and "HQ0000" not in out and "a.rvms" not in out
    for check in ("parse", "layout", "schema_192", "records_imply_assistant_flag"):
        assert any(line.startswith(check) and line.split()[1:] == ["0", "1", "0"] for line in out.splitlines()), check
    # a stale-checksum file parses: checksums fail, the container checks still pass
    d2 = tmp_path / "stale"
    d2.mkdir()
    shutil.copyfile(os.path.join(FIXTURES, "system_a", "system_a_2026-06-18_experiment_bare_deviceform_1.rvms"), d2 / "b.rvms")
    assert vd.main([str(d2)]) == 1
    out = capsys.readouterr().out
    assert any(line.startswith("checksums") and line.split()[1:] == ["0", "1", "0"] for line in out.splitlines())
    assert any(line.startswith("parse") and line.split()[1:] == ["1", "0", "0"] for line in out.splitlines())
    # no files, and a bad argument
    empty = tmp_path / "empty"
    empty.mkdir()
    assert vd.main([str(empty)]) == 1
    assert "no .rvsc/.rvms files" in capsys.readouterr().out
    assert vd.main([]) == 2 and vd.main([str(tmp_path / "nope")]) == 2
    capsys.readouterr()
    # --markdown renders the same counts as pipe tables
    assert vd.main([os.path.join(FIXTURES, "synthetic"), "--markdown"]) == 1
    md = capsys.readouterr().out
    assert "| units | files |" in md and "| parse | 3 | 0 | 0 |" in md and "HQ0000" not in md


def test_validate_dir_never_prints_a_version_string_from_the_file(tmp_path, capsys):
    """The Mk2vscInfo version is free text inside someone else's file. An unrecognised value is bucketed, so
    nothing the file's author wrote can reach a table that is meant to carry no per-file detail."""
    vd = _vd_module()
    data = _read(SINGLE)
    f = RvmsFile.parse(data)
    payloads = [s_.payload for s_ in f.sections]
    payloads[0] = b"\x01\x00\x00\x00" + struct.pack("<H", 11) + b"SITE-ALPHA1"
    d = tmp_path / "v"
    d.mkdir()
    (d / "x.rvsc").write_bytes(f.rebuild(payloads).to_bytes())
    assert vd.check_file((d / "x.rvsc").read_bytes())["format"] == "other (not printed)"
    vd.main([str(d)])
    out = capsys.readouterr().out
    assert "SITE-ALPHA1" not in out and "other (not printed)" in out
    assert vd.KNOWN_FORMATS == ("1.3", "1.30", "1.31", "1.32", "1.33")


def test_validate_dir_phase_model_requires_a_contiguous_unique_index_set(tmp_path, capsys):
    """Per-block phase arithmetic alone passes a file whose three blocks all claim to be unit 0."""
    vd = _vd_module()
    f = RvmsFile.parse(_read(THREE))
    assert vd.check_file(_read(THREE))["phase_model"] is True
    payloads = []
    for s_ in f.sections:
        p_ = bytearray(s_.payload)
        if s_.is_unit:
            p_[OFF_SLOT_A - PREFIX_LEN] = 0            # every block: phase L1, unit 0
            p_[OFF_SLOT_B - PREFIX_LEN] = 0
            p_[OFF_ASSISTANT_FLAG - PREFIX_LEN] = 0xE8
        payloads.append(bytes(p_))
    d = tmp_path / "dup"
    d.mkdir()
    (d / "x.rvms").write_bytes(f.rebuild(payloads).to_bytes())
    assert vd.check_file((d / "x.rvms").read_bytes())["phase_model"] is False
    assert vd.main([str(d)]) == 1
    capsys.readouterr()


def test_validate_dir_strict_makes_a_value_finding_set_the_exit_status(tmp_path, capsys):
    """Alignment is a finding about a value, not the format model, so on its own it is reported without
    failing the run; --strict is the CI caller's switch. (A file mutated far enough to misalign also makes
    `diagnose` report `misaligned`, so this uses the one real file in the QA set that aligns badly on its
    own terms: here that state is simulated by scoring the checks directly.)"""
    vd = _vd_module()
    f = RvmsFile.parse(_read(THREE))                   # a file whose other checks all pass
    payloads = []
    for s_ in f.sections:
        p_ = bytearray(s_.payload)
        if s_.is_unit:
            off = 0x59 - PREFIX_LEN + 2 * 2           # setting 2 (absorption), well outside its schema range
            p_[off: off + 2] = (65535).to_bytes(2, "little")
        payloads.append(bytes(p_))
    d = tmp_path / "al"
    d.mkdir()
    (d / "x.rvms").write_bytes(f.rebuild(payloads).to_bytes())
    r = vd.check_file((d / "x.rvms").read_bytes())
    assert r["alignment"] is False and r["parse"] is True and r["checksums"] is True
    assert r["records_imply_assistant_flag"] and r["phase_model"] and r["round_trip"], "the container is sound"
    # the real QA-set file that fails alignment is an upload-form GUI save whose diagnose status is
    # upload_form, so only the two value checks fail there and the run stays green by default
    real = dict(r, census=False, diagnose_ok_or_upload_form=True, diagnose_status="upload_form")
    lenient = [c for c in vd.CHECKS if c not in ("alignment", "census")]
    assert all(real[c] for c in lenient), "a value finding must not look like a format-model failure"
    assert vd.main([str(d), "--strict"]) == 1          # strict: every failed check counts
    out = capsys.readouterr().out
    assert "--strict makes that set the exit status" not in out
    assert vd.main([str(d)]) == 1                      # this mutant also misaligns diagnose, so it still fails
    assert "--strict makes that set the exit status" in capsys.readouterr().out
