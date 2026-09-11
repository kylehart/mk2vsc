"""Inverter parity: the units must agree outside Victron's documented per-unit list.

Runs against the real device files in fixtures/ plus synthetic files built from them.  The point is
that the CLASSIFICATION is right and that the guard can never go quiet: a grid-code or Virtual Switch
difference is expected and must not raise; a shared-battery difference must raise as an error; an
undocumented other difference must raise as a warning; and a file the check cannot judge must raise
ParityNotComparable rather than pass.
"""
import pytest

from mk2vsc import api
from mk2vsc.cli import main
from mk2vsc.fields import FIELDS, GRID_CODE_LOCKED
from mk2vsc.parity import (
    DC_LOW_SHUTDOWN_IDS,
    EXPECTED_PER_UNIT,
    SHARED_BATTERY_IDS,
    VIRTUAL_SWITCH_IDS,
    ParityMismatch,
    ParityNotComparable,
    check_parity,
    check_parity_bytes,
    parity_report_bytes,
)
from mk2vsc.sections import RvmsFile
from mk2vsc.units import N_SETTINGS, SECTION_DATA, unit_blocks
from mk2vsc.writer import set_settings

from .conftest import all_fixture_paths, corpus_paths, rel


# ----------------------------------------------------------------------------- helpers

def _device_pairs():
    """Device-form corpus fixtures that hold a comparable set of inverter blocks.

    ``corpus_paths()`` excludes ``fixtures/synthetic/`` (see tests/conftest.py): those files are built from
    corpus blocks to exercise the single-unit and three-phase shapes, so they are deliberately not pairs and
    would break the two-block assumptions the helpers below make."""
    out = []
    for p in corpus_paths():
        try:
            cfg = api.load(p)
        except Exception:
            continue
        if parity_report_bytes(cfg.data).comparable:
            out.append(p)
    return out


def _agreeing_pair():
    """A fixture whose units agree outside the exception list (needed for exit-0 cases)."""
    for p in _device_pairs():
        if parity_report_bytes(open(p, "rb").read()).ok:
            return p
    pytest.skip("no fixture whose pair agrees outside the exception list")


def _mismatching_pair():
    """A fixture with a shared-battery disagreement (the corpus holds one: System A, 2026-07-20)."""
    for p in _device_pairs():
        rep = parity_report_bytes(open(p, "rb").read())
        if rep.errors:
            return p
    pytest.skip("no fixture with a shared-battery disagreement")


def _one_sided(base: bytes, field: str, value) -> bytes:
    serial = parity_report_bytes(base).serials[0]
    out, _ = set_settings(base, [(serial, field, value)])
    return out


def _with_blocks(data: bytes, n: int) -> bytes:
    """Rebuild ``data`` with exactly ``n`` inverter blocks (drop from the end, or duplicate the last
    under a fresh placeholder serial so the copy is a distinct unit)."""
    f = RvmsFile.parse(data)
    data_secs = [s for s in f.sections if s.name == SECTION_DATA]
    other = [s for s in f.sections if s.name != SECTION_DATA]
    assert len(data_secs) == 2, "helper expects a two-block source"
    keep = data_secs[:n]
    k = 0
    while len(keep) < n:
        src = data_secs[-1]
        old = unit_blocks(f)[-1].serial.encode()
        new = f"HQ0000A9{k:03d}".encode()
        k += 1
        payload = src.payload.replace(old, new)
        keep.append(type(src)(start=src.start, name=src.name, next_ptr=src.next_ptr,
                              payload=payload, stored_checksum=src.stored_checksum, raw=src.raw))
    secs = other + keep
    return RvmsFile(magic_raw=f.magic_raw, sections=secs, length=f.length).rebuild().to_bytes()


def _truncate_last_block(data: bytes, keep_bytes: int = 120) -> bytes:
    """Cut the last inverter block's payload so it cannot hold the 192-word settings array while the
    file still parses (pointers and checksums are recomputed)."""
    f = RvmsFile.parse(data)
    payloads = [s.payload for s in f.sections]
    idx = max(i for i, s in enumerate(f.sections) if s.name == SECTION_DATA)
    payloads[idx] = payloads[idx][:keep_bytes]
    return f.rebuild(payloads).to_bytes()


# ----------------------------------------------------------------------------- corpus-wide

def test_every_comparable_fixture_compares_all_192_registers():
    pairs = _device_pairs()
    assert pairs, "expected at least one comparable pair in fixtures/"
    for p in pairs:
        rep = parity_report_bytes(open(p, "rb").read())
        assert rep.checked == 192, f"{rel(p)}: compared {rep.checked} settings, expected 192"
        assert rep.units == 2, f"{rel(p)}: every real fixture is a pair"
        rep.render()   # must not raise


def test_report_form_never_raises_on_any_fixture():
    for p in all_fixture_paths():
        parity_report_bytes(open(p, "rb").read())          # malformed fixtures included


def test_raise_can_be_disabled():
    for p in _device_pairs():
        rep = check_parity(p, raise_on_mismatch=False)
        assert rep.comparable


def test_agreeing_pair_is_ok_and_does_not_raise():
    p = _agreeing_pair()
    rep = check_parity(p)
    assert rep.ok


def test_corpus_holds_a_real_mismatch_and_it_raises():
    """The corpus contains a genuine commissioning disagreement; the eager check must raise on it."""
    p = _mismatching_pair()
    with pytest.raises(ParityMismatch) as exc:
        check_parity(p)
    assert exc.value.report.errors


# ----------------------------------------------------------------------------- the three classes

def test_grid_code_difference_is_expected_and_the_corpus_exercises_it():
    """Grid code is per unit: 81 and 128-191 differing must classify 'expected'.  The corpus does
    hold grid-code differences, so this is not vacuous -- assert that too."""
    seen = 0
    for p in _device_pairs():
        for d in parity_report_bytes(open(p, "rb").read()).differences:
            if d.setting_id == 81 or 128 <= d.setting_id <= 191:
                seen += 1
                assert d.expected and d.severity == "expected", f"{rel(p)}: setting {d.setting_id}"
    assert seen > 0, "expected the corpus to contain at least one grid-code difference"


@pytest.mark.parametrize("field,value,sid", [("53", 6, 53), ("11", 48.6, 11)])
def test_one_sided_per_unit_setting_is_expected_and_does_not_raise(field, value, sid):
    """A Virtual Switch timer (53) or DC low shutdown (11) written to ONE unit is documented per-unit:
    it must classify 'expected' and the eager check must NOT raise because of it."""
    p = _agreeing_pair()
    one_sided = _one_sided(open(p, "rb").read(), field, value)
    rep = check_parity_bytes(one_sided)                       # must not raise
    d = next(x for x in rep.differences if x.setting_id == sid)
    assert d.expected and d.severity == "expected"
    assert rep.ok


def test_shared_battery_difference_raises_as_error():
    """Absorption on one unit only (the S-4 condition): everyone charges ONE pack, so this must raise."""
    p = _agreeing_pair()
    one_sided = _one_sided(open(p, "rb").read(), "absorption", 57.2)
    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(one_sided)
    rep = exc.value.report
    bad = next(d for d in rep.errors if d.setting_id == 2)
    assert bad.severity == "error"
    assert "SHARED battery" in bad.describe()
    assert len(bad.values) == 2


def test_undocumented_difference_is_a_warning_and_still_raises():
    """A register outside both the exception list and the shared-battery set -- charge
    characteristic (10) -- classifies 'warning' and STILL raises: undocumented is not excused."""
    assert 10 not in EXPECTED_PER_UNIT and 10 not in SHARED_BATTERY_IDS
    p = _agreeing_pair()
    base = open(p, "rb").read()
    cur = parity_report_bytes(base)
    serial = cur.serials[0]
    one_sided, _ = set_settings(base, [(serial, "10", 2)], allow_unverified=True)
    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(one_sided)
    d = next(x for x in exc.value.report.unexpected if x.setting_id == 10)
    assert d.severity == "warning"
    assert "not a documented per-unit setting" in d.describe()


def test_exception_carries_the_report():
    p = _agreeing_pair()
    one_sided = _one_sided(open(p, "rb").read(), "float", 53.9)
    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(one_sided)
    assert exc.value.report.serials
    assert exc.value.report.unexpected
    assert "float" in str(exc.value)


# ----------------------------------------------------------------------------- not comparable: fail closed

def test_one_block_file_is_not_comparable_and_raises():
    p = _agreeing_pair()
    one = _with_blocks(open(p, "rb").read(), 1)
    rep = parity_report_bytes(one)
    assert not rep.comparable and "only 1 inverter block" in rep.reason
    assert not rep.ok, "not checked must never read as OK"
    with pytest.raises(ParityNotComparable):
        check_parity_bytes(one)


def test_three_block_file_is_compared_across_all_units():
    """N > 2 is written to be checked, not refused.  A duplicated block under a placeholder serial
    agrees with its source, so the synthetic three-unit file compares clean; a one-sided write to the
    third unit must then surface with all three values listed.  (Synthetic only: no three-phase
    system has been read with this tool -- docs/PARITY.md.)"""
    p = _agreeing_pair()
    three = _with_blocks(open(p, "rb").read(), 3)
    rep = check_parity_bytes(three)
    assert rep.comparable and rep.units == 3 and rep.checked == 192
    assert "3 units" in rep.render()
    third = rep.serials[-1]
    skewed, _ = set_settings(three, [(third, "absorption", 57.2)])
    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(skewed)
    d = next(x for x in exc.value.report.errors if x.setting_id == 2)
    assert set(d.values) == set(rep.serials), "every unit's value must be listed"


def test_block_short_into_the_checksum_trailer_is_not_comparable():
    """A block short by only a few bytes still ends with its 4-byte checksum, so a naive length
    check accepts it and the last reads take checksum bytes as settings 190/191 -- which are on the
    per-unit exception list, so two equally damaged blocks could report ok=True.  Guard that."""
    p = _agreeing_pair()
    base = open(p, "rb").read()
    f = RvmsFile.parse(base)
    idx = max(i for i, sec in enumerate(f.sections) if sec.name == SECTION_DATA)
    payloads = [sec.payload for sec in f.sections]

    # Trim so the block keeps its checksum trailer but loses the last settings word.  Without the
    # +4 reservation this file compares "fine": the reads fall into the checksum, and the affected
    # ids (190, 191) are on the per-unit exception list, so ok would be True.
    def trimmed(k):
        pay = list(payloads)
        pay[idx] = pay[idx][:len(pay[idx]) - k]
        return f.rebuild(pay).to_bytes()

    short = trimmed(6)
    # Since #64 the parser itself refuses a BareSettingData payload this short (SectionTooShort), so
    # the block never reaches parity's own length guard.  Either way the contract that matters holds:
    # the file is NOT comparable and NOT ok, and the eager check raises rather than passing quietly.
    rep = parity_report_bytes(short)
    assert not rep.comparable, "a block whose settings run into the checksum must not be compared"
    assert not rep.ok
    with pytest.raises(ParityNotComparable):
        check_parity_bytes(short)

    # A block that is merely tight (full array plus full trailer) is still compared: the guard must
    # reserve the checksum without refusing legitimate files.
    assert parity_report_bytes(trimmed(4)).comparable


def test_same_settings_different_firmware_is_not_parity():
    """Victron requires every unit on the same firmware.  Settings can agree word for word while the
    versions differ, so a settings-only check would wrongly report parity OK."""
    p = _agreeing_pair()
    base = open(p, "rb").read()
    f = RvmsFile.parse(base)
    blocks = unit_blocks(f)
    assert len({b.firmware_version for b in blocks}) == 1, "fixture should start on one firmware"
    off = blocks[-1].firmware_offset if hasattr(blocks[-1], "firmware_offset") else None
    data = bytearray(base)
    # bump the last block's firmware word in place, then rebuild checksums
    sec = [sec for sec in f.sections if sec.name == SECTION_DATA][-1]
    payloads = [x.payload for x in f.sections]
    idx = f.sections.index(sec)
    pay = bytearray(payloads[idx])
    fw_rel = blocks[-1].firmware_version
    # locate the firmware bytes inside the payload by value (u32 little-endian)
    import struct
    needle = struct.pack("<I", fw_rel)
    at = pay.find(needle)
    assert at >= 0, "firmware word not found in the block payload"
    struct.pack_into("<I", pay, at, fw_rel + 1)
    payloads[idx] = bytes(pay)
    skewed = f.rebuild(payloads).to_bytes()

    rep = parity_report_bytes(skewed)
    assert rep.comparable and not rep.differences, "settings must still agree; only firmware differs"
    assert rep.firmware_disagrees
    assert not rep.ok, "same settings + different firmware is NOT parity"
    assert "firmware" in rep.render()
    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(skewed)
    assert "firmware" in str(exc.value)


def test_truncated_block_is_not_comparable_not_a_crash():
    p = _agreeing_pair()
    short = _truncate_last_block(open(p, "rb").read())
    rep = parity_report_bytes(short)
    # The report form never raises, whether the refusal comes from the parser (SectionTooShort,
    # added in #64) or from parity's own length guard.
    assert not rep.comparable and not rep.ok
    assert rep.reason
    with pytest.raises(ParityNotComparable):
        check_parity_bytes(short)


def test_unparseable_file_is_not_comparable():
    rep = parity_report_bytes(b"\x00\x01garbage")
    assert not rep.comparable and "could not be parsed" in rep.reason
    assert not rep.ok


# ----------------------------------------------------------------------------- the exception list

def test_exception_list_is_exactly_the_documented_set():
    """Guard the list against typos: it must equal grid code + every vs_ field + DC low shutdown,
    and must not excuse any shared-battery setting."""
    vs_from_fields = {f.id for f in FIELDS if f.name.startswith("vs_")}
    assert VIRTUAL_SWITCH_IDS == vs_from_fields
    assert DC_LOW_SHUTDOWN_IDS == {11, 12}
    assert EXPECTED_PER_UNIT == frozenset(GRID_CODE_LOCKED) | vs_from_fields | {11, 12}
    assert not (EXPECTED_PER_UNIT & SHARED_BATTERY_IDS)
    for sid in (2, 3, 4, 64, 65):
        assert sid not in EXPECTED_PER_UNIT


# ----------------------------------------------------------------------------- CLI

def test_cli_parity_exit_codes(tmp_path, capsys):
    good = _agreeing_pair()
    bad = _mismatching_pair()
    assert main(["parity", good]) == 0
    assert "parity OK" in capsys.readouterr().out
    assert main(["parity", bad]) == 2
    assert "commissioning error" in capsys.readouterr().out
    missing = str(tmp_path / "nope.rvms")
    assert main(["parity", missing]) == 1
    capsys.readouterr()
    # a mismatch wins over a read error in either order
    assert main(["parity", bad, missing]) == 2
    assert main(["parity", missing, bad]) == 2
    out = capsys.readouterr().out
    assert out.count(":") >= 2, "multi-file output prefixes each report with its path"
    # not comparable is a failure, not a pass
    one = tmp_path / "one.rvms"
    one.write_bytes(_with_blocks(open(good, "rb").read(), 1))
    assert main(["parity", str(one)]) == 1
    assert "NOT CHECKED" in capsys.readouterr().out


def test_cli_show_keeps_exit_0_and_prints_parity(capsys):
    bad = _mismatching_pair()
    assert main(["show", bad]) == 0                          # display command: exit unchanged
    out = capsys.readouterr().out
    assert "parity:" in out and "commissioning error" in out
