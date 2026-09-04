import glob
import os

from mk2vsc.history import load_snapshots, changes
from tests.conftest import FIXTURES


def test_history_finds_the_documented_system_a_changes():
    """System A device downloads: the 2026-07-20 charge correction (absorption 56.0/57.6 -> 56.8 both,
    float 55.2 -> 54.0) and the 2026-09-02 post-service state (56.8 on both, ESS records present)."""
    paths = sorted(glob.glob(os.path.join(FIXTURES, "system_a", "*_download_*.rvms")))
    snaps, skipped = load_snapshots(paths)
    assert not skipped
    chs = changes(snaps)
    assert len({s.serials for s in snaps}) == 1
    abs_changes = [c for c in chs if c.what == "absorption_V"]
    assert any(c.old == 57.6 and c.new == 56.8 for c in abs_changes)
    assert any(c.old == 56.0 and c.new == 56.8 for c in abs_changes)
    assert any(c.what == "assistant" and "records" in str(c.new) for c in chs)
    # every change is an interval whose end is after its start
    assert all(c.after.timestamp >= c.before.timestamp for c in chs)


def test_history_groups_systems_by_serial_set():
    paths = sorted(glob.glob(os.path.join(FIXTURES, "*", "*_download_*.rvms")))
    snaps, _ = load_snapshots(paths)
    assert len({s.serials for s in snaps}) == 4
