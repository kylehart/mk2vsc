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
    assert main(["edit", str(src), "3=54.1", "--serial", "HQ2414U6FVN", "-o", str(out2)]) == 0
    assert "HQ2414U6FVN" in capsys.readouterr().out and out2.exists()


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
    assert "schema parsed" in out and "settings in schema range 190/190" in out and "absorption_V=" in out and "To report" in out
    assert main(["census", BAD]) == 1
    assert main(["history", A, B]) == 0
