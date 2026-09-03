"""
Shared fixtures.  Every test in this suite runs against the real device files in ``fixtures/``
(see fixtures/manifest.json and docs/FIXTURES.md).  Three files there are deliberately malformed and are
listed in KNOWN_BAD with the reason; tests assert that they *fail* the way the device rejected them.
"""
import glob
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")

# file -> why it is malformed (these are kept on purpose as negative controls)
KNOWN_BAD = {
    "guava/guava_2026-06-18_experiment_bare_deviceform_1.rvms":
        "deliberately stale checksums (June 2026 probe of whether the device validates the trailer)",
    "guava/guava_2026-07-21_prepared_ess_uploadform_1.rvms":
        "v1 graft: upload-form block transplanted into a device-form file; pointer chain broken (never uploaded)",
    "papaya/papaya_2026-07-20_prepared_ess_deviceform_1.rvms":
        "v4 of the 2026-07-20 ESS-load-both attempt: last pointer points inside the file (rejected mk2vsc-49)",
}


def all_fixture_paths():
    return sorted(glob.glob(os.path.join(FIXTURES, "*", "*.rvms")))


def rel(p):
    return os.path.relpath(p, FIXTURES)


@pytest.fixture(scope="session")
def manifest():
    with open(os.path.join(FIXTURES, "manifest.json")) as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def good_paths():
    return [p for p in all_fixture_paths() if rel(p) not in KNOWN_BAD]


@pytest.fixture(scope="session")
def good_files(good_paths):
    return {rel(p): open(p, "rb").read() for p in good_paths}


def pytest_generate_tests(metafunc):
    if "good_path" in metafunc.fixturenames:
        paths = [p for p in all_fixture_paths() if rel(p) not in KNOWN_BAD]
        metafunc.parametrize("good_path", paths, ids=[rel(p) for p in paths])
    if "bad_path" in metafunc.fixturenames:
        paths = [p for p in all_fixture_paths() if rel(p) in KNOWN_BAD]
        metafunc.parametrize("bad_path", paths, ids=[rel(p) for p in paths])
