"""
The experimental ESS-injection code is tested against the archived files it produced in August 2026,
so a reader can see exactly what was uploaded and reproduce it.  None of these files produced a running
system; see docs/ESS_INJECTION.md.
"""
import pytest

from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks, units_by_serial
from mk2vsc.experimental import graft, GraftRefused, to_upload_form, compare_per_slot, TransformRefused
from mk2vsc.assistants import parse_assistant_area
from mk2vsc.diff import diff_bytes

TEMPLATE = "papaya/papaya_2026-07-24_download_ess_deviceform_1.rvms"          # GUI-installed ESS, device form
ROB_EXPORT = "papaya/papaya_2026-07-21_gui-export_ess_uploadform_1.rvms"       # the GUI export that installed it
GUAVA_BASE = "guava/guava_2026-08-12_download_bare_deviceform_4.rvms"          # the bare download v3 was built from
GUAVA_V3 = "guava/guava_2026-08-12_prepared_ess_deviceform_2.rvms"             # v3 graft (accepted -> stub)
SA_BASE = "sugar_apple/sugar_apple_2026-08-13_download_bare_deviceform_1.rvms"  # the fresh bare download of 2026-08-13
SA_FULL = "sugar_apple/sugar_apple_2026-08-13_prepared_ess_deviceform_1.rvms"  # one-shot graft + install state
GUAVA_UPLOAD_V2 = "guava/guava_2026-08-13_prepared_ess_uploadform_1.rvms"      # accepted by the device
GUAVA_ESS_T18 = "guava/guava_2026-08-13_download_ess_deviceform_7.rvms"        # device form the v2 was built from


def test_graft_reproduces_the_archived_v3_file(good_files):
    out, checks = graft(good_files[GUAVA_BASE], good_files[TEMPLATE])
    assert all(checks.values())
    assert out == good_files[GUAVA_V3], "v3 graft is not reproducible from its baseline + template"


def test_graft_with_install_state_reproduces_the_sugar_apple_one_shot(good_files):
    base = good_files[SA_BASE]
    out, checks = graft(base, good_files[TEMPLATE], install_state=True)
    assert all(checks.values())
    if out != good_files[SA_FULL]:
        d = diff_bytes(out, good_files[SA_FULL])
        pytest.fail("Sugar Apple one-shot graft not reproduced: " + str(d.as_dict()["units"]))


def test_graft_output_has_template_records_and_target_identity(good_files):
    out, _ = graft(good_files[GUAVA_BASE], good_files[TEMPLATE])
    fo = RvmsFile.parse(out)
    assert fo.all_checksums_ok
    us = units_by_serial(fo)
    assert set(us) == set(units_by_serial(RvmsFile.parse(good_files[GUAVA_BASE])))
    lengths = sorted(r["length"] for u in us.values() for r in parse_assistant_area(u)["records"])
    assert lengths == [704, 1152]


def test_graft_refuses_wrong_inputs(good_files):
    with pytest.raises(GraftRefused):
        graft(good_files[TEMPLATE], good_files[TEMPLATE])              # baseline already has an assistant
    with pytest.raises(GraftRefused):
        graft(good_files[GUAVA_BASE], good_files[ROB_EXPORT])          # template in upload form


def test_upload_form_transform_reproduces_the_gui_export(good_files):
    """The self-test that justified uploading a transformed file: transform(device download of Papaya after
    the GUI install, reference = the GUI export) must equal the export per block, pointers/checksum aside."""
    out = to_upload_form(good_files[TEMPLATE], reference=good_files[ROB_EXPORT])
    diffs = compare_per_slot(out, good_files[ROB_EXPORT])
    assert all(not d for d in diffs.values()), diffs


def test_upload_form_transform_without_reference_matches_compaction(good_files):
    out = to_upload_form(good_files[TEMPLATE], timestamp=1_784_000_000)
    ref = good_files[ROB_EXPORT]
    ou = {u.slot: u for u in unit_blocks(RvmsFile.parse(out))}
    ru = {u.slot: u for u in unit_blocks(RvmsFile.parse(ref))}
    for slot in ou:
        assert ou[slot].is_upload_form and ou[slot].settings() == ru[slot].settings()
        a, b = parse_assistant_area(ou[slot]), parse_assistant_area(ru[slot])
        assert [r["length"] for r in a["records"]] == [r["length"] for r in b["records"]], (slot, a, b)
    d = diff_bytes(out, ref)
    assert all(u.settings == [] for u in d.units)


def test_upload_form_transform_reproduces_the_accepted_guava_v2(good_files):
    """Guava_ESS_UPLOADFORM_v2 was built from Tunnel-18 with the reference compaction and fresh stamps; the
    device accepted it.  Reproduce it with the same stamps."""
    v2 = good_files[GUAVA_UPLOAD_V2]
    v2u = unit_blocks(RvmsFile.parse(v2))
    export_ts = max(u.export_timestamp for u in v2u)
    out = to_upload_form(good_files[GUAVA_ESS_T18], timestamp=export_ts)
    diffs = compare_per_slot(out, v2)
    assert all(not d for d in diffs.values()), diffs


def test_upload_form_transform_refuses_bare_and_upload_inputs(good_files):
    with pytest.raises(TransformRefused):
        to_upload_form(good_files[GUAVA_BASE])
    with pytest.raises(TransformRefused):
        to_upload_form(good_files[ROB_EXPORT])


def test_cli_experimental_requires_acknowledgement(tmp_path, capsys):
    import os
    from mk2vsc.cli import main
    from tests.conftest import FIXTURES
    base = os.path.join(FIXTURES, GUAVA_BASE); tpl = os.path.join(FIXTURES, TEMPLATE)
    out = str(tmp_path / "g.rvms")
    assert main(["experimental", "graft", base, tpl, out]) == 2
    assert main(["experimental", "graft", base, tpl, out, "--i-accept-the-risk"]) == 0
    assert open(out, "rb").read() == open(os.path.join(FIXTURES, GUAVA_V3), "rb").read()
