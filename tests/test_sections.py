"""
Structure and integrity claims, checked against every good fixture.

If you add a file from a different system, firmware, or VEConfigure version and one of these fails,
that is the interesting result: open an issue with the file.
"""
import struct

import pytest

from rvms.sections import RvmsFile, RvmsParseError, sum32_le, MAGIC, SECTION_MK2, SECTION_INFO, SECTION_DATA, scan_unit_blocks


def test_every_good_file_parses_and_validates(good_path):
    f = RvmsFile.load(good_path)
    assert [s.name for s in f.sections][:2] == [SECTION_MK2, SECTION_INFO]
    assert all(s.name == SECTION_DATA for s in f.sections[2:])
    assert len(f.unit_sections) == 2, "corpus files are all two-inverter systems"
    assert f.all_checksums_ok, f.checksum_report()


def test_pointer_chain_is_contiguous_and_ends_at_eof(good_path):
    f = RvmsFile.load(good_path)
    pos = len(f.magic_raw)
    for s in f.sections:
        assert s.start == pos
        assert s.next_ptr == s.end
        pos = s.next_ptr
    assert pos == f.length


def test_round_trip_is_byte_exact(good_path):
    data = open(good_path, "rb").read()
    f = RvmsFile.parse(data)
    assert f.to_bytes() == data
    # rebuilding with unchanged payloads must reproduce pointers and checksums exactly
    assert f.rebuild().to_bytes() == data


def test_checksum_is_plain_word_sum_with_no_constant(good_path):
    """The historical formula sum32(block[2:]) + 0x6142000F is the same thing as sum32 from the length prefix."""
    data = open(good_path, "rb").read()
    f = RvmsFile.parse(data)
    for s in f.unit_sections:
        blk = data[s.name_start: s.checksum_offset]           # 'B'... up to the trailer
        legacy = (sum32_le(blk, 2, len(blk)) + 0x6142000F) & 0xFFFFFFFF
        assert legacy == s.computed_checksum == s.stored_checksum
        assert struct.unpack("<I", b"\x0f\x00Ba")[0] == 0x6142000F


def test_header_sections_are_constant_across_corpus(good_files):
    mk = {RvmsFile.parse(d).section(SECTION_MK2).raw for d in good_files.values()}
    info = {RvmsFile.parse(d).section(SECTION_INFO).payload for d in good_files.values()}
    assert len(mk) == 1, "Mk2vscInfo section identical in every file (format version 1.33)"
    assert len(info) == 1, "BareSettingInfo payload identical in every file (it is a template, not per-unit data)"
    d = next(iter(good_files.values()))
    mkp = RvmsFile.parse(d).section(SECTION_MK2).payload
    assert mkp[:4] == b"\x01\x00\x00\x00"
    assert mkp[4:6] == b"\x04\x00" and mkp[6:10] == b"1.33"


def test_known_bad_files_are_detected(bad_path):
    data = open(bad_path, "rb").read()
    try:
        f = RvmsFile.parse(data)
    except RvmsParseError:
        return  # broken pointer chain: correct outcome
    assert not f.all_checksums_ok, "a KNOWN_BAD file parsed AND validated -- update KNOWN_BAD or investigate"


def test_forensic_scan_agrees_with_parser(good_path):
    data = open(good_path, "rb").read()
    f = RvmsFile.parse(data)
    spans = scan_unit_blocks(data)
    assert [s for s, _ in spans] == [u.name_start for u in f.unit_sections]


def test_parse_rejects_garbage():
    with pytest.raises(RvmsParseError):
        RvmsFile.parse(b"\x1d\x00" + b"x" * 40)
    with pytest.raises(RvmsParseError):
        RvmsFile.parse(b"\x1d\x00" + MAGIC + b"\x05\x00hello\xff\xff\xff\xff")


def test_sum32_partial_word_padding():
    assert sum32_le(b"\x01\x00\x00\x00\x02") == 3
    assert sum32_le(b"\xff\xff\xff\xff\x01\x00\x00\x00") == 0  # wraps mod 2**32
