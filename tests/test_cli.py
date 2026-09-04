import json
import os
import shutil

import pytest

from mk2vsc.cli import main
from tests.conftest import FIXTURES

BARE = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_1.rvms")   # 56.0/57.6 mismatch
BAD = os.path.join(FIXTURES, "system_a", "system_a_2026-06-18_experiment_bare_deviceform_1.rvms")
A = os.path.join(FIXTURES, "system_b", "system_b_2026-07-24_download_bare_deviceform_1.rvms")
B = os.path.join(FIXTURES, "system_b", "system_b_2026-07-24_download_bare_deviceform_2.rvms")


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    assert "Start here" in capsys.readouterr().out


def test_show_default_and_all_and_json(capsys):
    assert main(["show", BARE]) == 0
    out = capsys.readouterr().out
    assert "UBatAbsorption" in out and "inverters differ" in out and "Charger" in out
    assert "info_id0" not in out
    assert main(["show", BARE, "--all"]) == 0
    assert "info_id0" in capsys.readouterr().out
    assert main(["show", BARE, "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["all_checksums_ok"] and len(d["units"]) == 2


def test_edit_writes_next_to_input_and_never_overwrites(tmp_path, capsys):
    src = tmp_path / "download.rvms"
    shutil.copyfile(BARE, src)
    assert main(["edit", str(src), "absorption=56.8", "float=54.0"]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out and "download.edited.rvms" in out and "Next:" in out
    edited = tmp_path / "download.edited.rvms"
    assert edited.exists() and src.read_bytes() == open(BARE, "rb").read()
    # second run refuses to clobber the edited file unless told to
    assert main(["edit", str(src), "absorption=56.8"]) == 1
    assert "exists" in capsys.readouterr().err
    assert main(["edit", str(src), "absorption=56.8", "--overwrite"]) == 0
    # explicit output path, one inverter, numeric id
    out2 = tmp_path / "one.rvms"
    assert main(["edit", str(src), "3=54.1", "--serial", "HQ0000A0001", "-o", str(out2)]) == 0
    assert "HQ0000A0001" in capsys.readouterr().out and out2.exists()


def test_edit_refusals(tmp_path, capsys):
    src = tmp_path / "d.rvms"
    shutil.copyfile(BARE, src)
    assert main(["edit", str(src), "absorbtion=56.8"]) == 2          # typo: unknown field
    assert "unknown field" in capsys.readouterr().err
    assert main(["edit", str(src), "absorption=5.68"]) == 1           # implausible
    err = capsys.readouterr().err
    assert "plausible" in err or "outside the device" in err
    assert main(["edit", str(src), "fs_ubat_start_V=57.72"]) == 1           # low confidence
    assert "allow_unverified" in capsys.readouterr().err
    assert main(["edit", str(src), "absorption=abc"]) == 2
    assert main(["edit", str(src), "absorption"]) == 2


def test_verify_and_check_loop(tmp_path, capsys):
    src = tmp_path / "download.rvms"
    shutil.copyfile(BARE, src)
    assert main(["edit", str(src), "absorption=56.8", "float=54.0"]) == 0
    edited = str(tmp_path / "download.edited.rvms")
    capsys.readouterr()
    # the "re-download" is simulated by the edited file itself (identical) and by the archived real re-download
    assert main(["verify", edited, edited]) == 0
    assert "VERIFIED" in capsys.readouterr().out
    assert main(["verify", edited, BARE]) == 2
    assert "NOT VERIFIED" in capsys.readouterr().out
    assert main(["check", edited, "--expect", "absorption=56.8", "float=54.0"]) == 0
    assert main(["check", BARE, "--expect", "absorption=56.8"]) == 1
    assert main(["check", BARE]) == 1                    # agreement alone fails on the mismatched file
    assert "no expected values" in capsys.readouterr().out
    assert main(["check", BARE, "--no-agreement"]) == 0
    assert main(["check", BARE, "--expect", "nonsense=1"]) == 2


def test_verify_on_the_real_post_upload_pair(capsys):
    """The 2026-07-20 System A change: prepared file vs the device's re-download."""
    prepared = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_prepared_bare_deviceform_1.rvms")
    redl = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_2.rvms")
    rc = main(["verify", prepared, redl])
    out = capsys.readouterr().out
    assert rc == 0 and "VERIFIED" in out, out


def test_diff_validate_fields_census_history(capsys):
    assert main(["diff", A, B]) == 0
    assert main(["diff", A, BARE]) == 2
    assert main(["validate", BARE]) == 0
    assert main(["validate", BAD]) == 1
    assert main(["fields"]) == 0
    out = capsys.readouterr().out
    assert "absorption" in out and "info_id0" not in out
    assert main(["fields", "--all"]) == 0
    assert "info_id0" in capsys.readouterr().out
    assert main(["census", BARE]) == 0
    out = capsys.readouterr().out
    assert "schema parsed" in out and "alignment OK" in out and "absorption_V=" in out and "To report" in out
    assert main(["census", BAD]) == 1
    assert main(["history", A, B]) == 0


# ---------------------------------------------------------------- diagnose
C0618 = os.path.join(FIXTURES, "system_c", "system_c_2026-06-18_download_bare_deviceform_1.rvms")


def test_diagnose_text_and_json(capsys):
    assert main(["diagnose", BARE]) == 0
    out = capsys.readouterr().out
    assert "[DEGRADES] D1" in out and "[DEGRADES] D2" in out and "evidence device-confirmed" in out
    assert "Questions the file cannot answer" in out and "shared_battery" in out
    assert main(["diagnose", BARE, "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["report_version"] == 1 and d["files"][0]["status"] == "ok" and any(f["rule"] == "D1" for f in d["findings"])


def test_diagnose_assume_resolves_conditionals(capsys):
    assert main(["diagnose", C0618]) == 0
    assert "conditional on: chemistry" in capsys.readouterr().out
    assert main(["diagnose", C0618, "--assume", "chemistry=lithium"]) == 0
    assert "conditional on: chemistry" not in capsys.readouterr().out


def test_diagnose_fix_requires_accept_then_writes_corrected_file_and_sheet(tmp_path, capsys):
    src = tmp_path / "download.rvms"
    shutil.copyfile(BARE, src)
    assert main(["diagnose", str(src), "--fix"]) == 2
    assert "--accept" in capsys.readouterr().err
    assert main(["diagnose", str(src), "--fix", "--accept", "D1:HQ0000A0002"]) == 0
    out = capsys.readouterr().out
    assert "Manual change sheet" in out and "Charger" in out and "wrote" in out and "download.corrected.rvms" in out
    corrected = tmp_path / "download.corrected.rvms"
    assert corrected.exists() and (tmp_path / "download.corrected.rvms.intent.json").exists()
    assert src.read_bytes() == open(BARE, "rb").read()
    intent = json.loads((tmp_path / "download.corrected.rvms.intent.json").read_text())
    assert any(e["field"] == "absorption_V" for e in intent["edits"]) and intent["bit_edits"]
    # the corrected file diagnoses clean of D1 on that unit, and verify against itself is trivially fine
    assert main(["diagnose", str(corrected)]) == 0
    assert "D1" not in capsys.readouterr().out.split("Questions")[0].replace("Phase 0 rules (D1", "")
    assert main(["diagnose", str(src), "--fix", "--accept", "D1:HQ0000A0002"]) == 1      # exists, no --overwrite
    assert "exists" in capsys.readouterr().err


def test_diagnose_values_fix_and_sheet_only(tmp_path, capsys):
    src = tmp_path / "c.rvms"
    shutil.copyfile(C0618, src)
    assert main(["diagnose", str(src), "--fix", "--accept", "D1:HQ0000C0001", "--assume", "chemistry=lithium"]) == 1
    assert "enter a value" in capsys.readouterr().err
    assert main(["diagnose", str(src), "--sheet", "--accept", "D1:HQ0000C0001", "--assume", "chemistry=lithium",
                 "--set", "absorption=56.8", "float=54.0", "low_shutdown=48.0"]) == 0
    out = capsys.readouterr().out
    assert "Manual change sheet" in out and "56.8 V" in out and "ticked" in out
    assert not (tmp_path / "c.corrected.rvms").exists()


def test_diagnose_upload_form_and_junk(tmp_path, capsys):
    up = os.path.join(FIXTURES, "system_c", "system_c_2026-07-21_gui-export_ess_uploadform_1.rvms")
    assert main(["diagnose", up]) == 1
    assert "status upload_form" in capsys.readouterr().out
    junk = tmp_path / "x.rvsc"
    junk.write_bytes(b"\x00" * 50)
    assert main(["diagnose", str(junk)]) == 1
    assert ".rvsc" in capsys.readouterr().out
