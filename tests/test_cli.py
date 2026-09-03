import json
import os

from rvms.cli import main
from tests.conftest import FIXTURES

BARE = os.path.join(FIXTURES, "guava", "guava_2026-07-20_download_bare_deviceform_1.rvms")
BAD = os.path.join(FIXTURES, "guava", "guava_2026-06-18_experiment_bare_deviceform_1.rvms")
A = os.path.join(FIXTURES, "mango", "mango_2026-07-24_download_bare_deviceform_1.rvms")
B = os.path.join(FIXTURES, "mango", "mango_2026-07-24_download_bare_deviceform_2.rvms")


def test_validate(capsys):
    assert main(["validate", BARE]) == 0
    assert main(["validate", BAD]) == 1
    out = capsys.readouterr().out
    assert "BAD" in out and "OK" in out


def test_info_and_decode_json(capsys):
    assert main(["info", BARE]) == 0
    capsys.readouterr()
    assert main(["decode", BARE, "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["all_checksums_ok"] and len(d["units"]) == 2
    assert d["units"][0]["settings"][2]["name"] == "absorption_V"


def test_diff_exit_codes(capsys):
    assert main(["diff", A, B]) == 0          # bookkeeping only
    assert main(["diff", A, BARE]) == 2       # different systems -> content


def test_set_qualify_roundtrip(tmp_path, capsys):
    out = str(tmp_path / "edited.rvms")
    assert main(["set", BARE, out, "absorption_V=56.8", "float_V=54.0"]) == 0
    intent = tmp_path / "intent.json"
    intent.write_text(json.dumps({"settings": {"absorption_V": 56.8, "float_V": 54.0}}))
    assert main(["qualify", out, "--intent", str(intent)]) == 0
    assert main(["qualify", BARE, "--intent", str(intent)]) == 1
    assert main(["set", BARE, out, "vs_param52=1"]) == 1
    assert "REFUSED" in capsys.readouterr().err


def test_fix_and_fields_and_census(tmp_path, capsys):
    out = str(tmp_path / "fixed.rvms")
    assert main(["fix", BAD, out]) == 0
    assert main(["validate", out]) == 0
    assert main(["fields"]) == 0
    assert main(["census", BARE, BAD]) == 0
    text = capsys.readouterr().out
    assert "BAD" in text and "ok " in text
