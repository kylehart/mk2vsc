import collections

from rvms.sections import RvmsFile
from rvms.units import unit_blocks
from rvms.assistants import parse_assistant_area


def test_bare_blocks_have_the_empty_header(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            a = parse_assistant_area(u)
            if not u.has_assistant_flag:
                assert a["kind"] in ("none", "container"), (name, u.serial, a)
                assert not any(r["length"] for r in a["records"] if r["marker"] == "f5ff")
                if "free" in a:
                    assert a["free_plus_used"] == 2816 + 6, (name, a)   # 6 = the empty header itself


def test_free_space_counter_on_stub_blocks(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    for name, data in good_files.items():
        if by_file[name]["state"] != "stub":
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            a = parse_assistant_area(u)
            assert a["records"][0]["length"] == 64 and a["free_plus_used"] == 2816 + 6, (name, a)


def test_gui_installed_ess_has_704_and_1152_byte_records(good_files, manifest):
    """Every device download of a GUI-authored ESS install carries exactly two records per system,
    one 704 B and one 1152 B (one per inverter), never a stub."""
    by_file = {e["file"]: e for e in manifest["entries"]}
    seen = 0
    for name, data in good_files.items():
        e = by_file[name]
        if e["origin"] != "download" or e["state"] != "ess":
            continue
        lengths = []
        for u in unit_blocks(RvmsFile.parse(data)):
            a = parse_assistant_area(u)
            assert a["kind"] == "records" and not a["stub"], (name, u.serial, a)
            lengths += [r["length"] for r in a["records"]]
        assert sorted(lengths) == [704, 1152], (name, lengths)
        seen += 1
    assert seen >= 5


def test_record_bodies_are_the_same_template_across_systems(good_files, manifest):
    """The 1152-byte body is byte-identical on every system; the 704-byte body differs only in one flag byte."""
    by_file = {e["file"]: e for e in manifest["entries"]}
    bodies = collections.defaultdict(set)
    for name, data in good_files.items():
        e = by_file[name]
        if e["origin"] != "download" or e["state"] != "ess":
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            for r in parse_assistant_area(u)["records"]:
                bodies[r["length"]].add(r["body_sha8"])
    assert len(bodies[1152]) == 1, bodies
    assert len(bodies[704]) <= 2, bodies


def test_stub_signature_detected(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    n = 0
    for name, data in good_files.items():
        if by_file[name]["state"] != "stub":
            continue
        for u in unit_blocks(RvmsFile.parse(data)):
            a = parse_assistant_area(u)
            assert a["kind"] == "stub" and u.has_assistant_flag, (name, a)
            n += 1
    assert n == 6, "three stub downloads x two inverters"


def test_record_length_beyond_area_is_reported_as_malformed(good_files):
    """A hand-built 2026-07-20 file carries an f5ff header whose length exceeds the area."""
    name = "papaya/papaya_2026-07-20_prepared_half-ess_deviceform_4.rvms"
    kinds = [parse_assistant_area(u)["kind"] for u in unit_blocks(RvmsFile.parse(good_files[name]))]
    assert "malformed" in kinds, kinds
