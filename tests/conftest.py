"""
Shared fixtures.  Every corpus test in this suite runs against the real device files in ``fixtures/``
(see fixtures/manifest.json and docs/FIXTURES.md).  Three files there are deliberately malformed and are
listed in KNOWN_BAD with the reason; tests assert that they *fail* the way the device rejected them.

``fixtures/synthetic/`` holds files built from corpus blocks (single-unit and three-phase shapes; see
tools/gen_synthetic_fixtures.py).  They are in the manifest and are exercised by tests/test_topologies.py,
but they are not part of ``good_files`` / ``good_path``: an Observed claim is checked on device files only.
"""
import glob
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")

# file -> why it is malformed (these are kept on purpose as negative controls)
KNOWN_BAD = {
    "system_a/system_a_2026-06-18_experiment_bare_deviceform_1.rvms":
        "deliberately stale checksums (June 2026 probe of whether the device validates the trailer)",
    "system_a/system_a_2026-07-21_prepared_ess_uploadform_1.rvms":
        "v1 graft: upload-form block transplanted into a device-form file; pointer chain broken (never uploaded)",
    "system_c/system_c_2026-07-20_prepared_ess_deviceform_1.rvms":
        "v4 of the 2026-07-20 ESS-load-both attempt: last pointer points inside the file (rejected mk2vsc-49)",
}


SYNTHETIC_DIR = "synthetic"


def all_fixture_paths():
    return sorted(glob.glob(os.path.join(FIXTURES, "*", "*.rvms")) + glob.glob(os.path.join(FIXTURES, "*", "*.rvsc")))


def is_synthetic(p):
    return rel(p).startswith(SYNTHETIC_DIR + "/")


def corpus_paths():
    """Real device files that are well formed: every fixture except KNOWN_BAD and the synthetic ones."""
    return [p for p in all_fixture_paths() if rel(p) not in KNOWN_BAD and not is_synthetic(p)]


def rel(p):
    """Fixture key with forward slashes on every OS (the Windows CI run used backslashes and missed KNOWN_BAD)."""
    return os.path.relpath(p, FIXTURES).replace(os.sep, "/")


@pytest.fixture(scope="session")
def manifest():
    with open(os.path.join(FIXTURES, "manifest.json")) as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def good_paths():
    return corpus_paths()


@pytest.fixture(scope="session")
def synthetic_paths():
    return [p for p in all_fixture_paths() if is_synthetic(p)]


@pytest.fixture(scope="session")
def good_files(good_paths):
    return {rel(p): open(p, "rb").read() for p in good_paths}


def pytest_generate_tests(metafunc):
    if "good_path" in metafunc.fixturenames:
        paths = corpus_paths()
        metafunc.parametrize("good_path", paths, ids=[rel(p) for p in paths])
    if "synthetic_path" in metafunc.fixturenames:
        paths = [p for p in all_fixture_paths() if is_synthetic(p)]
        metafunc.parametrize("synthetic_path", paths, ids=[rel(p) for p in paths])
    if "bad_path" in metafunc.fixturenames:
        paths = [p for p in all_fixture_paths() if rel(p) in KNOWN_BAD]
        metafunc.parametrize("bad_path", paths, ids=[rel(p) for p in paths])
