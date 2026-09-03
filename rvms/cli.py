"""
Command-line interface.

    rvms info      FILE...                 one-screen summary (structure, inverters, confirmed settings)
    rvms validate  FILE...                 checksum + structure check; exit 1 on any failure
    rvms decode    FILE [--json] [--all]   every setting with label/confidence
    rvms diff      A B [--json]            by-serial comparison; says whether only bookkeeping changed
    rvms set       IN OUT [--serial S] FIELD=VALUE ...      guarded edit (never uploads)
    rvms qualify   FILE... --intent intent.json             check against intended values
    rvms fix       IN OUT                  recompute every checksum (forensic use only)
    rvms fields                            print the settings table
    rvms census    FILE...                 one line per file (block lengths, flags, form, assistant kind)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .sections import RvmsFile, RvmsParseError
from .units import unit_blocks
from .decode import decode_file, brief
from .diff import diff_files, render as render_diff
from .writer import set_settings_file, WriteRefused
from .qualify import Intent, qualify_file, render as render_qual
from .fields import FIELDS
from .assistants import parse_assistant_area


def _load(path):
    try:
        return RvmsFile.load(path)
    except (RvmsParseError, OSError) as e:
        print(f"{path}: {e}", file=sys.stderr)
        return None


def cmd_info(a):
    rc = 0
    for p in a.files:
        try:
            print(f"== {p}")
            print(brief(decode_file(p)))
        except Exception as e:  # noqa: BLE001
            rc = 1
            print(f"  ERROR {e}")
    return rc


def cmd_validate(a):
    rc = 0
    for p in a.files:
        f = _load(p)
        if f is None:
            rc = 1
            continue
        for name, start, stored, computed, ok in f.checksum_report():
            if not ok or a.verbose:
                print(f"{'OK ' if ok else 'BAD'} {p} {name}@0x{start:x} stored={stored:08x} computed={computed:08x}")
            if not ok:
                rc = 1
        if f.all_checksums_ok:
            print(f"OK  {p}  ({len(f.sections)} sections, {len(f.unit_sections)} inverters)")
    return rc


def cmd_decode(a):
    d = decode_file(a.file, include_unknown=a.all)
    if a.json:
        print(json.dumps(d, indent=1, default=str))
    else:
        print(brief(d))
        for u in d["units"]:
            print(f"\n{u['serial']}: all named settings")
            for s in u["settings"]:
                if s.get("name") or a.all:
                    v = s.get("value", s["raw"])
                    print(f"  {s['id']:3d} {s['offset']} {s.get('name') or '-':30s} raw={s['raw']:6d} value={v!s:>9} "
                          f"{s.get('unit','')} [{s['confidence']}]")
    return 0


def cmd_diff(a):
    d = diff_files(a.a, a.b)
    print(json.dumps(d.as_dict(), indent=1) if a.json else render_diff(d))
    return 0 if (d.identical or d.only_bookkeeping) else 2


def cmd_set(a):
    changes = []
    for kv in a.assignments:
        if "=" not in kv:
            print(f"bad assignment {kv!r}; expected FIELD=VALUE", file=sys.stderr)
            return 2
        k, v = kv.split("=", 1)
        try:
            val = float(v)
        except ValueError:
            val = int(v, 0)
        changes.append((a.serial, k, val))
    try:
        edits = set_settings_file(a.inp, a.out, changes, allow_unverified=a.i_know_this_is_unverified)
    except (WriteRefused, KeyError, ValueError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    for e in edits:
        d = e.as_dict()
        print(f"{d['serial']}  {d['field']}  {d['old']} -> {d['new']} {d['unit']}  ({d['block_offset']} / file {d['file_offset']})")
    print(f"wrote {a.out}; verified: only the listed bytes and their section checksums changed")
    return 0


def cmd_qualify(a):
    intent = Intent.load(a.intent) if a.intent else Intent(settings={})
    rc = 0
    for p in a.files:
        ok, res = qualify_file(p, intent)
        print(render_qual(ok, res, p))
        rc |= 0 if ok else 1
    return rc


def cmd_fix(a):
    f = _load(a.inp)
    if f is None:
        return 1
    out = f.fixed().to_bytes()
    with open(a.out, "wb") as fh:
        fh.write(out)
    changed = sum(1 for s in f.sections if not s.checksum_ok)
    print(f"wrote {a.out}: {changed} checksum(s) recomputed")
    return 0


def cmd_fields(a):
    print(f"{'id':>3} {'offset':>7} {'name':30s} {'scale':>5} {'unit':6s} {'conf':9s} label")
    for f in FIELDS:
        print(f"{f.id:3d} +0x{f.offset:03x} {f.name:30s} {f.scale:>5g} {f.unit:6s} {f.confidence:9s} {f.label}")
    return 0


def cmd_census(a):
    for p in a.files:
        f = _load(p)
        if f is None:
            continue
        cells = []
        for u in unit_blocks(f):
            asst = parse_assistant_area(u)
            cells.append(f"{u.serial}:{u.length:#x}:{u.assistant_flag:02x}:{'U' if u.is_upload_form else 'd'}:{asst['kind']}")
        print(f"{f.length:6d} {'ok ' if f.all_checksums_ok else 'BAD'} | {' '.join(cells)} | {p}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rvms", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info"); s.add_argument("files", nargs="+"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("validate"); s.add_argument("files", nargs="+"); s.add_argument("-v", "--verbose", action="store_true"); s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("decode"); s.add_argument("file"); s.add_argument("--json", action="store_true"); s.add_argument("--all", action="store_true", help="include unknown settings"); s.set_defaults(fn=cmd_decode)
    s = sub.add_parser("diff"); s.add_argument("a"); s.add_argument("b"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_diff)
    s = sub.add_parser("set"); s.add_argument("inp"); s.add_argument("out"); s.add_argument("--serial", default=None, help="edit one inverter only (default: all)")
    s.add_argument("--i-know-this-is-unverified", action="store_true", help="allow MEDIUM/LOW/UNKNOWN fields")
    s.add_argument("assignments", nargs="+", metavar="FIELD=VALUE"); s.set_defaults(fn=cmd_set)
    s = sub.add_parser("qualify"); s.add_argument("files", nargs="+"); s.add_argument("--intent", help="intent JSON"); s.set_defaults(fn=cmd_qualify)
    s = sub.add_parser("fix"); s.add_argument("inp"); s.add_argument("out"); s.set_defaults(fn=cmd_fix)
    s = sub.add_parser("fields"); s.set_defaults(fn=cmd_fields)
    s = sub.add_parser("census"); s.add_argument("files", nargs="+"); s.set_defaults(fn=cmd_census)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
