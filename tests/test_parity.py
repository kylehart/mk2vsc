"""Inverter parity: the pair must agree outside Victron's documented per-unit list.

Runs against the real device files in fixtures/.  The point of these tests is not that a particular
fixture happens to disagree today, but that the CLASSIFICATION is right: a grid-code or Virtual
Switch difference is expected and must not raise, while a difference in a setting acting on the
shared battery must raise and must be reported as a probable commissioning error.
"""
import pytest

from mk2vsc import api
from mk2vsc.parity import (
    EXPECTED_PER_UNIT,
    ParityMismatch,
    check_parity,
    check_parity_bytes,
    parity_report_bytes,
)
from mk2vsc.writer import set_settings

from .conftest import all_fixture_paths, rel


def _device_pairs():
    """Device-form fixtures that hold exactly two inverter blocks."""
    out = []
    for p in all_fixture_paths():
        try:
            cfg = api.load(p)
        except Exception:
            continue
        rep = parity_report_bytes(cfg.data)
        if rep.comparable:
            out.append(p)
    return out


def test_every_comparable_fixture_reports_without_crashing():
    pairs = _device_pairs()
    assert pairs, "expected at least one comparable pair in fixtures/"
    for p in pairs:
        rep = parity_report_bytes(open(p, "rb").read())
        assert rep.checked == 192, f"{rel(p)}: compared {rep.checked} settings, expected 192"
        assert len(rep.serials) == 2
        rep.render()   # must not raise


def test_report_form_never_raises():
    """parity_report_bytes is the non-raising door; callers that want it must get it."""
    for p in _device_pairs():
        parity_report_bytes(open(p, "rb").read())          # no exception, whatever it finds


def test_raise_on_mismatch_can_be_disabled():
    for p in _device_pairs():
        rep = check_parity(p, raise_on_mismatch=False)     # explicit opt-out
        assert rep.comparable


def test_identical_blocks_are_ok():
    """A file whose two blocks agree everywhere must pass and must not raise."""
    clean = [p for p in _device_pairs() if parity_report_bytes(open(p, "rb").read()).ok]
    assert clean, "expected at least one fixture whose pair agrees outside the exception list"
    for p in clean:
        rep = check_parity(p)                              # must not raise
        assert rep.ok


def test_grid_code_difference_is_expected_not_a_finding():
    """Victron configures grid code per unit, so 81 and 128-191 differing must not raise."""
    for p in _device_pairs():
        rep = parity_report_bytes(open(p, "rb").read())
        for d in rep.differences:
            if d.setting_id in (81,) or 128 <= d.setting_id <= 191:
                assert d.expected, f"{rel(p)}: setting {d.setting_id} should be expected per-unit"
                assert d.severity == "expected"


def test_shared_battery_difference_raises_and_is_an_error():
    """Absorption on one inverter only: both charge ONE pack, so this must raise."""
    p = _device_pairs()[0]
    base = open(p, "rb").read()
    before = parity_report_bytes(base)
    serial = before.serials[0]

    # Write absorption to ONE inverter by serial, exactly the S-4 condition.
    target = serial
    one_sided, _ = set_settings(base, [(target, "absorption", 57.2)])

    with pytest.raises(ParityMismatch) as exc:
        check_parity_bytes(one_sided)

    rep = exc.value.report
    assert not rep.ok
    ids = {d.setting_id for d in rep.errors}
    assert 2 in ids, "absorption (setting 2) should be flagged as a shared-battery error"
    bad = next(d for d in rep.errors if d.setting_id == 2)
    assert bad.severity == "error"
    assert "SHARED battery" in bad.describe()
    assert target in bad.values


def test_exception_carries_the_report():
    """A caller that catches must be able to act without re-reading the file."""
    p = _device_pairs()[0]
    base = open(p, "rb").read()
    target = parity_report_bytes(base).serials[0]
    one_sided, _ = set_settings(base, [(target, "float", 53.9)])
    try:
        check_parity_bytes(one_sided)
    except ParityMismatch as exc:
        assert exc.report.serials
        assert exc.report.unexpected
        assert "float" in str(exc)
    else:
        pytest.fail("expected ParityMismatch")


def test_unnamed_settings_are_still_compared():
    """Not having a label for a register is not a reason to stay silent about a disagreement."""
    p = _device_pairs()[0]
    rep = parity_report_bytes(open(p, "rb").read())
    assert rep.checked == 192, "parity must cover all 192 registers, named or not"


def test_single_block_file_is_not_comparable():
    """A file without a pair reports 'not comparable' rather than pretending to pass."""
    for p in all_fixture_paths():
        try:
            data = open(p, "rb").read()
            rep = parity_report_bytes(data)
        except Exception:
            continue
        if not rep.comparable:
            assert rep.reason
            assert not rep.differences
            return


def test_exception_list_matches_the_documented_set():
    """Guard the exception list: it encodes Victron's documentation, not our convenience."""
    assert 81 in EXPECTED_PER_UNIT                     # grid code
    assert all(i in EXPECTED_PER_UNIT for i in range(128, 192))
    assert 11 in EXPECTED_PER_UNIT and 12 in EXPECTED_PER_UNIT     # DC low shutdown
    assert 53 in EXPECTED_PER_UNIT and 70 in EXPECTED_PER_UNIT     # Virtual Switch
    # Charge parameters act on the shared battery and are NOT per-unit:
    for sid in (2, 3, 4, 64, 65):
        assert sid not in EXPECTED_PER_UNIT, f"setting {sid} must not be excused from parity"
