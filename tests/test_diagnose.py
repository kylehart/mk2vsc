"""`mk2vsc diagnose`: the rule engine, its Phase 0 rules, the report contract, fixes and the change sheet.

Every rule has at least one corpus fixture that triggers it and one that does not; the precision test at
the end counts hits over the whole device-form corpus so a rule that starts firing everywhere is caught."""
import json
import os

import pytest

from mk2vsc.sections import RvmsFile
from mk2vsc.units import units_by_serial
from tests.conftest import FIXTURES

A_0720 = "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"      # A0002 lead-acid profile, A0001 lithium; 56.0 vs 57.6
A_0813 = "system_a/system_a_2026-08-13_download_ess_deviceform_1.rvms"       # A0002 lithium flag set, voltages still 57.6/55.2
A_STUB = "system_a/system_a_2026-08-12_download_stub_deviceform_1.rvms"      # both blocks carry the failed-install stub
C_0618 = "system_c/system_c_2026-06-18_download_bare_deviceform_1.rvms"      # both lead-acid; C0001 absorption = float = 48.0
C_HALF = "system_c/system_c_2026-07-20_download_half-ess_deviceform_1.rvms"  # assistant on one inverter only
C_MIS = "system_c/system_c_2026-07-20_download_half-ess_deviceform_6.rvms"   # absorption = float = 48.00 V (limits test file)
C_UPLOAD = "system_c/system_c_2026-07-21_gui-export_ess_uploadform_1.rvms"
B_CLEAN = "system_b/system_b_2026-08-12_download_ess_deviceform_1.rvms"      # a healthy lithium pair


def run(good_files, key, **assume):
    from mk2vsc.diagnose import diagnose_bytes
    return diagnose_bytes(good_files[key], name=os.path.basename(key), assume=assume or None)


def by_rule(rep, rule):
    return [f for f in rep.findings if f.rule == rule]


# ------------------------------------------------------------------------------------ D1
def test_d1_fires_on_the_lead_acid_unit_and_copies_from_its_healthy_pair(good_files):
    rep = run(good_files, A_0720)
    d1 = by_rule(rep, "D1")
    assert [f.serials for f in d1] == [["HQ0000A0002"]]
    f = d1[0]
    assert f.severity in ("BLOCKS", "DEGRADES") and f.evidence_class == "device-confirmed"
    assert not f.conditional, "the pair's lithium flag on unit 1 settles the chemistry"
    votes = {e["field"] for e in f.evidence}
    assert {"flags2", "charge_characteristic", "flags0"} <= votes
    assert f.fix["kind"] == "copy" and f.fix["source"] == "HQ0000A0001" and "HQ0000A0002" in f.fix["targets"]
    assert any(b["field"] == "flags2" and b["bit"] == 4 and b["set"] for b in f.fix["bit_edits"])


def test_d1_with_no_healthy_pair_needs_values_and_asks_the_chemistry(good_files):
    rep = run(good_files, C_0618)
    d1 = by_rule(rep, "D1")
    assert {tuple(f.serials) for f in d1} == {("HQ0000C0001",), ("HQ0000C0002",)}
    for f in d1:
        assert f.conditional == ["chemistry"], "both flags clear and nothing stated: chemistry unknown"
        assert f.fix["kind"] == "values"
        assert {v["field"] for v in f.fix["needs_value"]} >= {"absorption_V", "float_V", "dc_low_shutdown_V"}
    blocks = [f for f in d1 if f.serials == ["HQ0000C0001"]][0]
    assert blocks.severity == "BLOCKS", "absorption at the schema minimum will not charge a lithium bank"
    assert any("chemistry" == q.id for q in rep.questions)
    rep2 = run(good_files, C_0618, chemistry="lithium")
    assert all(not f.conditional for f in by_rule(rep2, "D1"))


def test_d1_reports_the_half_fix_lithium_flag_set_but_voltages_at_lead_acid_defaults(good_files):
    rep = run(good_files, A_0813)
    d1 = by_rule(rep, "D1")
    assert [f.serials for f in d1] == [["HQ0000A0002"]]
    assert d1[0].severity == "DEGRADES"
    assert {e["field"] for e in d1[0].evidence} >= {"absorption_V", "float_V"}
    assert not any("flags2" == e["field"] for e in d1[0].evidence), "the flag is set; it is not a vote here"


def test_d1_is_silent_on_a_healthy_lithium_pair(good_files):
    assert by_rule(run(good_files, B_CLEAN), "D1") == []


# ------------------------------------------------------------------------------------ D2
def test_d2_names_the_disagreeing_fields_and_picks_the_source_only_when_one_block_passes_d1(good_files):
    rep = run(good_files, A_0720)
    d2 = by_rule(rep, "D2")
    assert len(d2) == 1
    f = d2[0]
    assert {e["field"] for e in f.evidence} >= {"absorption_V", "float_V", "flags2"}
    assert f.fix["kind"] == "copy" and f.fix["source"] == "HQ0000A0001"
    assert "shared_battery" in f.conditional
    rep = run(good_files, C_0618)                     # both blocks fail D1: no automatic source
    d2 = by_rule(rep, "D2")
    assert len(d2) == 1 and d2[0].fix["source"] is None and set(d2[0].fix["candidates"]) == {"HQ0000C0001", "HQ0000C0002"}


def test_d2_is_silent_when_the_pair_agrees(good_files):
    assert by_rule(run(good_files, B_CLEAN), "D2") == []


# ------------------------------------------------------------------------------------ C1
def test_c1_is_a_thin_adapter_over_limits(good_files):
    rep = run(good_files, C_MIS)
    c1 = by_rule(rep, "C1")
    assert {(f.serials[0], f.evidence[0]["field"]) for f in c1} == {("HQ0000C0001", "absorption_V"), ("HQ0000C0001", "float_V")}
    assert all(f.fix["kind"] == "values" and f.evidence_class == "inferred" for f in c1)
    assert by_rule(run(good_files, B_CLEAN), "C1") == []


# ------------------------------------------------------------------------------------ V1 / V2
def test_v1_low_shutdown_at_schema_default_needs_a_lithium_chemistry(good_files):
    rep = run(good_files, C_0618)
    v1 = by_rule(rep, "V1")
    assert len(v1) == 2 and all(f.conditional == ["chemistry"] for f in v1)
    rep = run(good_files, C_0618, chemistry="lithium")
    v1 = by_rule(rep, "V1")
    assert len(v1) == 2 and all(not f.conditional and f.severity == "FRAGILE" for f in v1)
    assert all(e["value"] == 37.2 and e["schema_default"] == 37.2 for f in v1 for e in f.evidence)
    assert by_rule(run(good_files, B_CLEAN, chemistry="lithium"), "V1") == []


def test_v2_vs_return_at_the_unreachable_default(good_files):
    rep = run(good_files, C_0618)
    v2 = by_rule(rep, "V2")
    assert len(v2) == 2 and all(f.severity == "FRAGILE" and f.evidence_class == "inferred" for f in v2)
    assert all(e["value"] == 64.0 for f in v2 for e in f.evidence if e["field"] == "vs_accept_battery_above_V")
    assert by_rule(run(good_files, A_0720), "V2") == [], "52.5 V return below absorption is reachable"


# ------------------------------------------------------------------------------------ E1 / E2 / P3
def test_e1_stub_blocks_and_makes_the_file_uneditable(good_files):
    rep = run(good_files, A_STUB)
    e1 = by_rule(rep, "E1")
    assert len(e1) == 2 and all(f.severity == "BLOCKS" and f.fix["kind"] == "gui" for f in e1)
    assert rep.status == "ok" and rep.editable is False and "STUB" in rep.refusal_reason
    assert "assistant reinstall" in e1[0].fix["text"]


def test_e2_names_the_inverter_that_lacks_the_assistant(good_files):
    rep = run(good_files, C_HALF)
    e2 = by_rule(rep, "E2")
    assert len(e2) == 1 and e2[0].conditional == ["ess_intended"]
    assert len(e2[0].fix["lacks"]) == 1 and e2[0].fix["lacks"][0] in ("HQ0000C0001", "HQ0000C0002")
    assert by_rule(run(good_files, B_CLEAN), "E2") == []


def test_p3_upload_form_is_refused_as_device_state(good_files):
    rep = run(good_files, C_UPLOAD)
    assert rep.status == "upload_form" and rep.editable is False
    assert [f.rule for f in rep.findings] == ["P3"]


# ------------------------------------------------------------------------------------ file status
def test_unparseable_bytes_and_the_rvsc_spike():
    from mk2vsc.diagnose import diagnose_bytes
    rep = diagnose_bytes(b"\x00" * 64, name="junk.rvms")
    assert rep.status == "unparseable" and rep.findings == [] and rep.editable is False
    rep = diagnose_bytes(b"\x1d\x00VEConfig setting section fil\x00" + b"\x00" * 40, name="local.rvsc")
    assert rep.status == "unparseable" and ".rvsc" in rep.message and "fixture" in rep.message


def test_rvsc_extension_marks_every_finding_unverified(good_files):
    from mk2vsc.diagnose import diagnose_bytes
    rep = diagnose_bytes(good_files[A_0720], name="local.rvsc")
    assert rep.findings and all("unverified on single-unit" in f.note for f in rep.findings)


# ------------------------------------------------------------------------------------ report contract
def test_report_json_v1_shape(good_files):
    from mk2vsc.diagnose import diagnose_files, Report
    rep = diagnose_files([os.path.join(FIXTURES, A_0720)])
    d = rep.as_dict()
    assert d["report_version"] == 1
    fl = d["files"][0]
    assert {"name", "status", "message", "serials", "editable", "refusal_reason", "nominal_voltage", "chemistry"} <= set(fl)
    f = d["findings"][0]
    assert {"id", "rule", "title", "severity", "decode_confidence", "evidence_class", "conditional", "serials",
            "evidence", "fix", "message", "file"} <= set(f)
    ev = f["evidence"][0]
    assert {"field", "raw", "value", "schema_min", "schema_max", "schema_default"} <= set(ev)
    assert {"id", "text", "affects"} <= set(d["questions"][0])
    json.dumps(d)                                      # serialisable as-is


# ------------------------------------------------------------------------------------ fixes and the sheet
def test_apply_d1_copy_fix_and_render_the_sheet(good_files):
    from mk2vsc.diagnose import diagnose_bytes, apply_fixes, sheet_rows
    data = good_files[A_0720]
    rep = diagnose_bytes(data, name="a.rvms")
    d1 = by_rule(rep, "D1")[0]
    out, intent = apply_fixes(data, rep, accept=[d1.id])
    u = units_by_serial(RvmsFile.parse(out))
    assert (u["HQ0000A0002"].setting(60) >> 4) & 1 == 1
    assert u["HQ0000A0002"].setting(2) == u["HQ0000A0001"].setting(2) == 5600
    assert u["HQ0000A0002"].setting(10) == 1
    assert any(i["field"] == "absorption_V" and i["serial"] == "HQ0000A0002" for i in intent["edits"])
    assert any(i["field"] == "flags2" and i["bit"] == 4 for i in intent["bit_edits"])
    rows = sheet_rows(rep, intent)
    assert rows and all({"serial", "tab", "label", "old", "new"} <= set(r) for r in rows)
    assert any("Charger" in r["tab"] for r in rows)
    assert any(r["tab"] == "(tab unknown)" or "›" in r["tab"] for r in rows)


def test_apply_values_fix_needs_the_values(good_files):
    from mk2vsc.diagnose import diagnose_bytes, apply_fixes, FixRefused
    data = good_files[C_0618]
    rep = diagnose_bytes(data, name="c.rvms", assume={"chemistry": "lithium"})
    d1 = [f for f in by_rule(rep, "D1") if f.serials == ["HQ0000C0001"]][0]
    with pytest.raises(FixRefused):
        apply_fixes(data, rep, accept=[d1.id])
    out, intent = apply_fixes(data, rep, accept=[d1.id],
                              values={"absorption_V": 56.8, "float_V": 54.0, "dc_low_shutdown_V": 48.0})
    u = units_by_serial(RvmsFile.parse(out))["HQ0000C0001"]
    assert u.setting(2) == 5680 and u.setting(3) == 5400 and u.setting(11) == 4800 and u.setting(10) == 1
    assert (u.setting(60) >> 4) & 1 == 1


def test_apply_refuses_a_d2_copy_without_a_source(good_files):
    from mk2vsc.diagnose import diagnose_bytes, apply_fixes, FixRefused
    data = good_files[C_0618]
    rep = diagnose_bytes(data, name="c.rvms")
    d2 = by_rule(rep, "D2")[0]
    with pytest.raises(FixRefused):
        apply_fixes(data, rep, accept=[d2.id])
    out, intent = apply_fixes(data, rep, accept=[d2.id], copy_from="HQ0000C0002")
    u = units_by_serial(RvmsFile.parse(out))
    assert u["HQ0000C0001"].setting(2) == u["HQ0000C0002"].setting(2)


# ------------------------------------------------------------------------------------ corpus precision
EXPECTED_HITS = {"D1": 48, "D2": 44, "C1": 14, "V1": 18, "V2": 11, "E1": 6, "E2": 10}   # 82 device-form files, 164 blocks


def test_corpus_precision_counts_and_quiet_systems(good_files):
    """Exact hit counts over the device-form corpus (regenerate by running this test after a fixture lands; the
    numbers are the rule's documented precision).  System D never triggers anything; System B never carries the
    lead-acid signature, the VS trap, or a range-edge value."""
    import collections
    from mk2vsc.diagnose import diagnose_bytes
    hits = collections.Counter()
    blocks = files = 0
    quiet = {"D1", "V1", "V2", "C1"}          # System B carries a stub download (E1) and a pair mismatch (D2)
    for key, data in good_files.items():
        fr = diagnose_bytes(data, name=os.path.basename(key))
        if fr.status != "ok":
            assert fr.status == "upload_form" and [f.rule for f in fr.findings] == ["P3"]
            continue
        files += 1
        blocks += len(fr.serials)
        for f in fr.findings:
            hits[f.rule] += 1
            if key.startswith("system_d/") or (key.startswith("system_b/") and f.rule in quiet):
                raise AssertionError(f"{f.rule} fired on {key} {f.serials}: {f.message[:120]}")
    assert (files, blocks) == (82, 164)
    assert dict(hits) == EXPECTED_HITS
