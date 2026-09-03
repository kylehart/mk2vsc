import hashlib
import os

from tests.conftest import FIXTURES, all_fixture_paths, rel


def test_manifest_matches_files(manifest):
    listed = {e["file"]: e for e in manifest["entries"]}
    on_disk = {rel(p): p for p in all_fixture_paths()}
    assert set(listed) == set(on_disk), (set(listed) ^ set(on_disk))
    for name, e in listed.items():
        data = open(on_disk[name], "rb").read()
        assert hashlib.sha256(data).hexdigest() == e["sha256"], name
        assert len(data) == e["size"], name
        assert e["state"] in ("bare", "ess", "half-ess", "stub")
        assert e["form"] in ("deviceform", "uploadform")
        assert e["origin"] in ("download", "prepared", "gui-export", "experiment")


def test_no_duplicate_content(manifest):
    shas = [e["sha256"] for e in manifest["entries"]]
    assert len(shas) == len(set(shas))
