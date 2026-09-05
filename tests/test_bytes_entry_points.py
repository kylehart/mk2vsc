"""``census_text``, ``verify_bytes`` and ``history.snapshots_from_bytes``: the path-taking verbs on bytes already in hand."""
import os

from mk2vsc.api import verify, verify_bytes
from mk2vsc.census import census_text
from mk2vsc.history import load_snapshots, snapshots_from_bytes
from tests.conftest import FIXTURES

A1 = "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"
A2 = "system_a/system_a_2026-08-12_download_bare_deviceform_1.rvms"


def test_census_text_matches_the_cli(good_files, capsys):
    from mk2vsc.cli import main
    p = os.path.join(FIXTURES, A1)
    assert main(["census", p, "-q"]) == 0
    text, ok = census_text(good_files[A1], os.path.basename(p))
    assert ok and capsys.readouterr().out.strip() == text


def test_census_text_reports_a_bad_file():
    text, ok = census_text(b"junk", "junk.rvms")
    assert not ok and text.startswith("junk.rvms: PARSE FAILED")


def test_verify_bytes_matches_verify(good_files):
    p1, p2 = os.path.join(FIXTURES, A1), os.path.join(FIXTURES, A2)
    assert verify_bytes(good_files[A1], good_files[A1]) == verify(p1, p1)
    assert verify_bytes(good_files[A1], good_files[A2]) == verify(p1, p2)
    assert verify_bytes(good_files[A1], good_files[A1])[0] is True
    assert verify_bytes(good_files[A1], good_files[A2])[0] is False


def test_snapshots_from_bytes_matches_load_snapshots(good_files):
    paths = [os.path.join(FIXTURES, A2), os.path.join(FIXTURES, A1)]
    from_paths, skipped_p = load_snapshots(paths)
    from_bytes, skipped_b = snapshots_from_bytes([(paths[0], good_files[A2]), (paths[1], good_files[A1])])
    assert skipped_p == skipped_b == []
    assert [(s.path, s.timestamp, s.serials) for s in from_paths] == [(s.path, s.timestamp, s.serials) for s in from_bytes]
    snaps, skipped = snapshots_from_bytes([("junk.rvms", b"junk"), ("a.rvms", good_files[A1])])
    assert [s.path for s in snaps] == ["a.rvms"] and skipped[0][0] == "junk.rvms"
