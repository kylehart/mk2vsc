"""The at-the-edge-of-range check and the alignment line in `show` / `check`."""
import glob

from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks
from mk2vsc.schema import schema_of
from mk2vsc.limits import at_limits
from mk2vsc import api
from mk2vsc.qualify import Intent, qualify_file

MISCOMMISSIONED = "fixtures/system_c/system_c_2026-07-20_download_half-ess_deviceform_6.rvms"   # absorption = float = 48.00 V


def _hits(path_or_bytes):
    f = RvmsFile.parse(path_or_bytes) if isinstance(path_or_bytes, bytes) else RvmsFile.load(path_or_bytes)
    sch = schema_of(f)
    return {u.serial: at_limits(u, sch) for u in unit_blocks(f)}


def test_the_48v_file_is_flagged_on_absorption_and_float_only():
    hits = _hits(MISCOMMISSIONED)
    flagged = {s: sorted(h.field.name for h in hs) for s, hs in hits.items() if hs}
    assert flagged, "expected at least one block at the schema minimum"
    for names in flagged.values():
        assert names == ["absorption_V", "float_V"]
    for hs in hits.values():
        for h in hs:
            assert h.edge == "minimum" and h.value == 48.0 and h.default in (57.6, 55.2)
            assert "at minimum of allowed range (48 V; default" in h.message


def test_the_rule_is_quiet_on_most_of_the_corpus(good_files):
    """A naive raw==min/max rule fires on every block (timers default to 0, charge current to its max).
    The narrowed rule fires only on blocks carrying a non-default extreme physical value."""
    flagged_blocks = total = 0
    names = set()
    for data in good_files.values():
        for serial, hs in _hits(data).items():
            total += 1
            if hs:
                flagged_blocks += 1
                names.update(h.field.name for h in hs)
    assert total > 100
    assert flagged_blocks < total / 10
    assert names <= {"absorption_V", "float_V"}


def test_show_carries_alignment_and_limit_notes():
    text = api.load(MISCOMMISSIONED).summary()
    assert "alignment OK" in text
    assert "<- at minimum of allowed range (48 V; default 57.6 V)" in text
    assert "Self-checks:" in text


def test_check_reports_alignment_pass_and_limit_warning():
    ok, res = qualify_file(MISCOMMISSIONED, Intent(settings={}, require_agreement=False))
    levels = {(l, m.split(":")[1].split()[0] if ":" in m else m) for l, m in res}
    assert any(l == "PASS" and "alignment OK" in m for l, m in res)
    assert any(l == "WARN" and "absorption_V at minimum of allowed range" in m for l, m in res)


def test_check_fails_on_a_misaligned_block(good_files, tmp_path):
    """Shift one inverter's settings array by two bytes: checksums are repaired, structure is fine, and
    only the alignment self-check notices."""
    f = RvmsFile.parse(good_files[MISCOMMISSIONED.split("fixtures/")[1]])
    u = unit_blocks(f)[0]
    idx = f.sections.index(u.section)
    payloads = [s.payload for s in f.sections]
    pl = bytearray(payloads[idx])
    o = u.settings_offset - (len(u.section.name) + 4)   # settings_offset counts from the name start; payload begins after name + pointer
    pl[o:o + 380] = pl[o + 2:o + 380] + pl[o:o + 2]
    payloads[idx] = bytes(pl)
    out = tmp_path / "shifted.rvms"
    out.write_bytes(f.rebuild(payloads).to_bytes())
    ok, res = qualify_file(str(out), Intent(settings={}, require_agreement=False))
    assert not ok
    assert any(l == "FAIL" and "ALIGNMENT SUSPECT" in m for l, m in res)
