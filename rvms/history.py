"""
Mine a library of archived downloads for configuration changes.

Given any set of ``.rvms`` files, group them by system (the set of inverter serials), order each group
by the save timestamp stored in the file, and report every setting that differs between consecutive
downloads, per inverter.  This turns a folder of old downloads into a dated change log.

Caveat that must travel with every result: a download's timestamp is an UPPER bound on when the change
happened.  A setting that differs between two consecutive downloads changed somewhere in between; the
tool reports the interval, never a point.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .sections import RvmsFile, RvmsParseError
from .units import unit_blocks, units_by_serial
from .fields import BY_ID
from .assistants import parse_assistant_area


@dataclass
class Snapshot:
    path: str
    timestamp: int
    serials: Tuple[str, ...]
    file: RvmsFile

    @property
    def when(self) -> str:
        return _dt.datetime.fromtimestamp(self.timestamp, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass
class Change:
    system: Tuple[str, ...]
    serial: str
    what: str
    old: object
    new: object
    confidence: str
    after: Snapshot
    before: Snapshot

    def line(self) -> str:
        return (f"{self.before.when} .. {self.after.when}  {self.serial}  {self.what}: {self.old} -> {self.new}"
                f"  [{self.confidence}]  ({self.before.path.split('/')[-1]} -> {self.after.path.split('/')[-1]})")


def load_snapshots(paths: List[str]) -> Tuple[List[Snapshot], List[Tuple[str, str]]]:
    snaps, skipped = [], []
    for p in paths:
        try:
            f = RvmsFile.load(p)
        except (RvmsParseError, OSError) as e:
            skipped.append((p, str(e)))
            continue
        units = unit_blocks(f)
        if not units:
            skipped.append((p, "no unit blocks"))
            continue
        ts = max(u.save_timestamp for u in units)
        snaps.append(Snapshot(p, ts, tuple(sorted(u.serial for u in units)), f))
    return snaps, skipped


def changes(snaps: List[Snapshot]) -> List[Change]:
    by_system: Dict[Tuple[str, ...], List[Snapshot]] = {}
    for s in snaps:
        by_system.setdefault(s.serials, []).append(s)
    out: List[Change] = []
    for system, seq in by_system.items():
        seq.sort(key=lambda s: (s.timestamp, s.path))
        for a, b in zip(seq, seq[1:]):
            ua, ub = units_by_serial(a.file), units_by_serial(b.file)
            for serial in system:
                x, y = ua[serial], ub[serial]
                sx, sy = x.settings(), y.settings()
                for sid, (p, q) in enumerate(zip(sx, sy)):
                    if p != q:
                        f = BY_ID.get(sid)
                        out.append(Change(system, serial, f.name if f else f"setting_{sid}",
                                          f.decode(p) if f else p, f.decode(q) if f else q,
                                          f.confidence if f else "UNKNOWN", b, a))
                ka, kb = parse_assistant_area(x)["summary"], parse_assistant_area(y)["summary"]
                if ka != kb:
                    out.append(Change(system, serial, "assistant", ka, kb, "structure", b, a))
    return out


def render(snaps: List[Snapshot], chs: List[Change], skipped) -> str:
    lines = [f"{len(snaps)} snapshots, {len({s.serials for s in snaps})} system(s); "
             f"{len(chs)} change(s).  Intervals are [previous download .. this download]; "
             f"download time is an upper bound on when a change happened."]
    for p, why in skipped:
        lines.append(f"  skipped {p}: {why}")
    for c in chs:
        lines.append("  " + c.line())
    return "\n".join(lines)
