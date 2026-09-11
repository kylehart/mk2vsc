"""
Files whose sections parse but whose payloads are shorter than the layout mk2vsc reads, and the one-block
file the container code does read.

The short files are built here from our own grammar (``Section.build``), not copied from any other project.
Their shape follows the single-unit ``.rvsc`` files other tools describe: one ``BareSettingData`` block, and
a ``BareSettingInfo`` shorter than the 192-record schema.  Every entry point must refuse them as
``SectionTooShort`` (a ``RvmsParseError``), naming the section and both byte counts, never with a traceback.

The one-block file is a corpus fixture with its second block removed through ``RvmsFile.rebuild``: it
parses with one inverter, validates, aligns, and round-trips.  Because a section's pointer is the absolute
start of the next section, the first block's pointer already equals its own end, so the one-block file is
byte-for-byte the prefix of the two-block file up to the second block: no pointer or checksum changes.
That is the container-level claim for single-unit files; the layout claim (whether a device-written
``.rvsc`` is that shape) is Unknown.
"""
import os
import struct

import pytest

import mk2vsc
from mk2vsc.sections import RvmsFile, Section, RvmsParseError, SectionTooShort, MAGIC, SECTION_MK2, SECTION_INFO, SECTION_DATA
from mk2vsc.units import unit_blocks, check_layout, MIN_PAYLOAD_DEVICE
from mk2vsc.schema import parse_schema, schema_of, SCHEMA_LEN, HEADER_LEN, RECORD_LEN
from mk2vsc.align import check as align_check
from mk2vsc.census import census_text
from mk2vsc.qualify import qualify_bytes, Intent
from mk2vsc.history import snapshots_from_bytes
from mk2vsc.diagnose import diagnose_bytes
from mk2vsc.cli import main
from tests.conftest import FIXTURES

BARE = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_1.rvms")
MK2_PAYLOAD = b"\x01\x00\x00\x00\x04\x001.33"


def build_file(parts):
    """A file from ``[(name, payload)]`` in our grammar: magic, then sections with contiguous pointers and fresh
    checksums, the last pointer equal to the file length (the same arithmetic as ``RvmsFile.rebuild``)."""
    magic = struct.pack("<H", len(MAGIC)) + MAGIC
    pos, out = len(magic), []
    for name, payload in parts:
        size = 2 + len(name) + 4 + len(payload) + 4
        out.append(Section.build(name, pos + size, payload, pos).raw)
        pos += size
    return magic + b"".join(out)


def one_block(data: bytes) -> bytes:
    """``data`` with its second ``BareSettingData`` removed: pointers and checksums recomputed by the container code."""
    f = RvmsFile.parse(data)
    assert len(f.unit_sections) == 2
    keep = [s for s in f.sections if not s.is_unit] + [f.unit_sections[0]]
    return RvmsFile(magic_raw=f.magic_raw, sections=keep, length=0).rebuild().to_bytes()


@pytest.fixture(scope="module")
def corpus():
    data = open(BARE, "rb").read()
    f = RvmsFile.parse(data)
    return data, f.section(SECTION_INFO).payload, f.unit_sections[0].payload


# ------------------------------------------------------------------ the short shapes
SHORT_INFO_LEN = 71          # a BareSettingInfo of the size a single-unit tool fixture carries: 6 whole records
SHORT_DATA_LEN = 22          # a BareSettingData payload far short of the 192-entry settings array


def short_block_file(corpus):
    _, info, _ = corpus
    return build_file([(SECTION_MK2, MK2_PAYLOAD), (SECTION_INFO, info), (SECTION_DATA, bytes(SHORT_DATA_LEN))])


def short_schema_file(corpus):
    _, info, block = corpus
    return build_file([(SECTION_MK2, MK2_PAYLOAD), (SECTION_INFO, info[:SHORT_INFO_LEN]), (SECTION_DATA, block)])


def both_short_file(corpus):
    _, info, _ = corpus
    return build_file([(SECTION_MK2, MK2_PAYLOAD), (SECTION_INFO, info[:SHORT_INFO_LEN]), (SECTION_DATA, bytes(SHORT_DATA_LEN))])


SHAPES = [
    ("short_block", short_block_file, "BareSettingData", SHORT_DATA_LEN, MIN_PAYLOAD_DEVICE),
    ("short_schema", short_schema_file, "BareSettingInfo", SHORT_INFO_LEN, SCHEMA_LEN),
    ("both_short", both_short_file, "BareSettingInfo", SHORT_INFO_LEN, SCHEMA_LEN),   # the schema is checked first
]


@pytest.fixture(params=SHAPES, ids=[s[0] for s in SHAPES])
def short(request, corpus):
    _, build, section, found, needed = request.param
    return build(corpus), section, found, needed


def _expect(exc: SectionTooShort, section: str, found: int, needed: int):
    msg = str(exc)
    assert isinstance(exc, RvmsParseError)
    assert exc.section.startswith(section) and exc.found == found and exc.needed == needed
    assert section in msg and f"is {found} bytes" in msg and f"at least {needed}" in msg
    assert "tool or firmware version mk2vsc has not seen" in msg
    assert "docs/ERRORS.md" in msg


def test_short_files_are_well_formed_containers(short):
    """The sections and checksums are fine: what is wrong is the payload length, which only the layout knows."""
    data, *_ = short
    f = RvmsFile.parse(data)
    assert [s.name for s in f.sections] == [SECTION_MK2, SECTION_INFO, SECTION_DATA] and f.all_checksums_ok


def test_library_entry_points_raise_the_named_error(short):
    data, section, found, needed = short
    with pytest.raises(SectionTooShort) as ei:
        mk2vsc.loads(data)
    _expect(ei.value, section, found, needed)
    with pytest.raises(SectionTooShort) as ei:
        check_layout(RvmsFile.parse(data))
    _expect(ei.value, section, found, needed)


def test_schema_and_block_readers_raise_it_directly(corpus):
    _, info, _ = corpus
    with pytest.raises(SectionTooShort) as ei:
        parse_schema(info[:SHORT_INFO_LEN])
    _expect(ei.value, "BareSettingInfo", SHORT_INFO_LEN, SCHEMA_LEN)
    assert f"room for {(SHORT_INFO_LEN - HEADER_LEN) // RECORD_LEN} whole {RECORD_LEN}-byte records" in str(ei.value)
    with pytest.raises(SectionTooShort) as ei:
        unit_blocks(RvmsFile.parse(short_block_file(corpus)))
    _expect(ei.value, "BareSettingData", SHORT_DATA_LEN, MIN_PAYLOAD_DEVICE)
    assert "inverter block 0" in str(ei.value)


def test_report_entry_points_refuse_without_a_traceback(short):
    data, section, found, needed = short
    text, ok = census_text(data, "short.rvsc")
    assert not ok and text.startswith("short.rvsc: PARSE FAILED") and section in text and f"is {found} bytes" in text
    ok, results = qualify_bytes(data, Intent(settings={}))
    assert not ok and results[0][0] == "FAIL" and "not parseable" in results[0][1] and section in results[0][1]
    fr = diagnose_bytes(data, name="short.rvsc")
    assert fr.status == "unparseable" and section in fr.message and f"at least {needed}" in fr.message
    snaps, skipped = snapshots_from_bytes([("short.rvsc", data)])
    assert snaps == [] and skipped[0][0] == "short.rvsc" and section in skipped[0][1]


def test_cli_verbs_refuse_with_the_existing_exit_codes(short, tmp_path, capsys):
    data, section, found, needed = short
    p = str(tmp_path / "short.rvsc")
    open(p, "wb").write(data)
    assert main(["show", p]) == 1
    err = capsys.readouterr().err
    assert section in err and f"is {found} bytes" in err and f"at least {needed}" in err and "Traceback" not in err
    assert main(["show", p, "--json"]) == 1
    assert main(["census", p]) == 1
    assert "PARSE FAILED" in capsys.readouterr().out
    assert main(["check", p]) == 1
    assert "NOT QUALIFIED" in capsys.readouterr().out
    assert main(["verify", p, BARE]) == 1
    assert "cannot verify" in capsys.readouterr().err
    assert main(["verify", BARE, p]) == 1
    capsys.readouterr()
    assert main(["diagnose", p]) == 1
    assert "status unparseable" in capsys.readouterr().out
    assert main(["history", p, BARE]) == 0                     # skipped with the reason, like any unreadable file
    assert section in capsys.readouterr().out
    # validate is container and checksums only, on purpose: it still reports a well-formed short file as OK
    assert main(["validate", p]) == 0


# ------------------------------------------------------------------ the one-block file the container code reads
def test_one_block_file_parses_validates_and_aligns(corpus, tmp_path, capsys):
    data, _, _ = corpus
    single = one_block(data)
    f = RvmsFile.parse(single)
    assert len(f.unit_sections) == 1 and f.all_checksums_ok and f.to_bytes() == single
    assert f.sections[-1].next_ptr == len(single)
    # the first block's pointer was already its own end, so nothing was rewritten: the one-block file is the prefix
    orig = RvmsFile.parse(data)
    assert single == data[: orig.unit_sections[1].start]
    assert orig.unit_sections[0].raw == f.unit_sections[0].raw
    u = unit_blocks(f)[0]
    assert u.is_last and u.serial == unit_blocks(orig)[0].serial
    assert align_check(u, schema_of(f)).ok
    cfg = mk2vsc.loads(single)
    assert cfg.valid and len(cfg.serials) == 1
    text, ok = census_text(single, "one.rvms")
    assert ok and "1 inverter(s)" in text and "alignment OK" in text
    assert diagnose_bytes(single, name="one.rvms").status == "ok"
    p = str(tmp_path / "one.rvms")
    open(p, "wb").write(single)
    assert main(["show", p]) == 0
    assert "1 inverter(s)" in capsys.readouterr().out
    assert main(["validate", p]) == 0 and main(["check", p]) == 0
