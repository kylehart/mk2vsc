import os
import shutil

import pytest

import mk2vsc
from mk2vsc import WriteRefused
from tests.conftest import FIXTURES

BARE = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_1.rvms")
REDL = os.path.join(FIXTURES, "system_a", "system_a_2026-07-20_download_bare_deviceform_2.rvms")


def test_load_read_aliases_and_ids():
    cfg = mk2vsc.load(BARE)
    assert cfg.valid and cfg.form == "device"
    assert cfg.serials == ["HQ2414AXENJ", "HQ2414U6FVN"]
    u = cfg["HQ2414U6FVN"]
    assert u["absorption"] == u["absorption_V"] == u[2] == u["2"] == 56.0
    assert u["ac_limit"] == 50.0 and u.raw("ac_limit") == 500
    assert u.get("nonsense") is None
    assert cfg.value("absorption") == {"HQ2414AXENJ": 57.6, "HQ2414U6FVN": 56.0}
    assert not cfg.agree("absorption") and cfg.agree("inverter_output_V")
    assert "no assistant" in u.assistant
    assert "absorption_V" in u.as_dict() and "param85" not in u.as_dict()


def test_set_save_verify_check(tmp_path):
    src = tmp_path / "download.rvms"
    shutil.copyfile(BARE, src)
    cfg = mk2vsc.load(str(src))
    edits = cfg.set("absorption", 56.8)
    assert sorted(e.serial for e in edits) == ["HQ2414AXENJ", "HQ2414U6FVN"]
    cfg.set_many({"float": 54.0})
    assert cfg.value("absorption") == {"HQ2414AXENJ": 56.8, "HQ2414U6FVN": 56.8}
    with pytest.raises(WriteRefused):
        cfg.save(str(src))                       # never the input
    out = cfg.save()
    assert out.endswith("download.edited.rvms") and os.path.exists(out)
    with pytest.raises(WriteRefused):
        cfg.save()                               # exists
    cfg.save(overwrite=True)
    ok, res = cfg.check(absorption=56.8, float=54.0)
    assert ok, res
    ok, _ = mk2vsc.load(BARE).check(absorption=56.8)
    assert not ok
    # the archived real re-download after this very edit
    ok, text = mk2vsc.verify(out, REDL)
    assert ok and "VERIFIED" in text
    assert cfg.diff(mk2vsc.load(REDL)).only_bookkeeping


def test_refusals_surface_through_the_facade():
    cfg = mk2vsc.load(BARE)
    with pytest.raises(WriteRefused):
        cfg.set("absorption", 5.68)
    with pytest.raises(WriteRefused):
        cfg.set("vs_load_above_for_s", 1)
    with pytest.raises(KeyError):
        cfg.set("vs_soc_pct", 20)
    with pytest.raises(KeyError):
        cfg.set("absorbtion", 56.8)
    assert cfg.edits == []


def test_summary_text():
    s = mk2vsc.load(BARE).summary()
    assert "Charger" in s and "Absorption voltage" in s and "inverters differ" in s and "Legend" in s
    assert "param85" not in s and "param85" in mk2vsc.load(BARE).summary(include_unknown=True)


def test_loads_bytes():
    cfg = mk2vsc.loads(open(BARE, "rb").read())
    assert cfg.path is None and cfg.valid
    with pytest.raises(ValueError):
        cfg.save()
