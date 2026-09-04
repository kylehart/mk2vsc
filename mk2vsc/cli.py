"""
mk2vsc: Victron VEConfigure .rvms files without VEConfigure.

Start here (one file downloaded from VRM > Device list > Remote VEConfigure):

    mk2vsc show     download.rvms                        what is in it, per inverter, in plain labels
    mk2vsc edit     download.rvms absorption=56.8 float=54.0
                                                         writes download.edited.rvms; upload THAT through VRM
    mk2vsc verify   download.edited.rvms redownload.rvms  after the upload: did the device take exactly your change?
    mk2vsc check    redownload.rvms --expect absorption=56.8 float=54.0
                                                         values as intended, and equal on both inverters

More:

    mk2vsc diff      A B                 what differs between any two files, by inverter serial
    mk2vsc history   FILE...             dated change log mined from a folder of old downloads
    mk2vsc census    FILE...             the report to paste into an issue: does the format model hold on your file?
    mk2vsc validate  FILE...             structure and checksums only
    mk2vsc fields                        the settings table with confidence levels and aliases
    mk2vsc experimental ...              assistant (ESS) injection experiments; read docs/ESS_INJECTION.md first

Nothing here uploads to a device. Field names accept aliases (absorption, float, charge_current, ac_limit,
low_shutdown, vs_entry, vs_return, capacity ...), full names, or VE.Bus setting IDs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .sections import RvmsFile, RvmsParseError
from .units import unit_blocks
from .fields import FIELDS, ALIASES, lookup, CONFIRMED, HIGH
from .writer import WriteRefused
from .diff import diff_files, render as render_diff
from .qualify import Intent, qualify_file, render as render_qual
from .assistants import parse_assistant_area, grid_code_words
from .history import load_snapshots, changes as history_changes, render as render_history
from . import api


def _fail(msg: str, rc: int = 1) -> int:
    print(msg, file=sys.stderr)
    return rc


def _parse_value(field_name: str, text: str):
    t = text.strip()
    try:
        if t.lower().startswith("0x"):
            return int(t, 16)
        if t.lstrip("-").isdigit():
            return int(t)
        return float(t)
    except ValueError:
        raise ValueError(f"{field_name}: {text!r} is not a number")


def _assignments(items):
    out = {}
    for kv in items:
        if "=" not in kv:
            raise ValueError(f"expected FIELD=VALUE, got {kv!r}")
        k, v = kv.split("=", 1)
        fld = lookup(k)               # KeyError with a helpful message on unknown names
        out[fld.name] = _parse_value(fld.name, v)
    return out


# ----------------------------------------------------------------------------- first-use verbs
def cmd_show(a):
    rc = 0
    for p in a.files:
        try:
            cfg = api.load(p)
        except (RvmsParseError, OSError) as e:
            rc = 1
            print(f"{p}: {e}", file=sys.stderr)
            continue
        if a.json:
            from .decode import decode_bytes
            print(json.dumps(decode_bytes(cfg.data, include_unknown=a.all), indent=1, default=str))
        else:
            print(cfg.summary(include_unknown=a.all))
            if len(a.files) > 1:
                print()
    return rc


def cmd_edit(a):
    try:
        changes = _assignments(a.assignments)
    except (KeyError, ValueError) as e:
        return _fail(f"error: {e}", 2)
    try:
        cfg = api.load(a.file)
    except (RvmsParseError, OSError) as e:
        return _fail(f"{a.file}: {e}")
    try:
        edits = cfg.set_many(changes, serial=a.serial, allow_unverified=a.allow_unverified,
                             allow_out_of_range=a.allow_out_of_range)
        out = cfg.save(a.output, overwrite=a.overwrite)
    except (WriteRefused, KeyError, ValueError) as e:
        return _fail(f"REFUSED: {e}")
    for e in edits:
        d = e.as_dict()
        same = " (unchanged)" if d["old"] == d["new"] else ""
        print(f"  {d['serial']}  {d['field']:28s} {d['old']} -> {d['new']} {d['unit']}{same}")
    print(f"\nwrote {out}")
    print("verified: only those bytes and their section checksums changed; the input file is untouched.\n")
    print("Next:")
    print(f"  1. VRM > Device list > Remote VEConfigure > Upload: {os.path.basename(out)}")
    print("  2. Download again from the same page.")
    print(f"  3. mk2vsc verify {out} <the new download>")
    return 0


def cmd_verify(a):
    try:
        ok, text = api.verify(a.prepared, a.redownload)
    except (RvmsParseError, OSError, ValueError) as e:
        return _fail(f"cannot verify: {e}")
    print(text)
    return 0 if ok else 2


def cmd_check(a):
    try:
        expect = _assignments(a.expect or [])
    except (KeyError, ValueError) as e:
        return _fail(f"error: {e}", 2)
    if a.intent:
        try:
            intent = Intent.load(a.intent)
        except (OSError, ValueError) as e:
            return _fail(f"cannot load intent {a.intent}: {e}", 2)
        intent.settings.update(expect)
    else:
        intent = Intent(settings=expect, require_agreement=not a.no_agreement)
    if not intent.settings:
        print("note: no expected values given; checking structure and inverter agreement only "
              "(add --expect field=value ... or --intent file.json)")
    rc = 0
    for p in a.files:
        try:
            ok, res = qualify_file(p, intent)
        except KeyError as e:
            return _fail(f"{p}: {e}", 2)
        print(render_qual(ok, res, p))
        rc |= 0 if ok else 1
    return rc


def cmd_diff(a):
    try:
        d = diff_files(a.a, a.b)
    except (RvmsParseError, OSError, ValueError) as e:
        return _fail(f"cannot diff: {e}")
    print(json.dumps(d.as_dict(), indent=1) if a.json else render_diff(d))
    return 0 if (d.identical or d.only_bookkeeping) else 2


# ----------------------------------------------------------------------------- tools
def cmd_validate(a):
    rc = 0
    for p in a.files:
        try:
            f = RvmsFile.load(p)
        except (RvmsParseError, OSError) as e:
            rc = 1
            print(f"BAD {p}: {e}")
            continue
        for name, start, stored, computed, ok in f.checksum_report():
            if not ok or a.verbose:
                print(f"{'OK ' if ok else 'BAD'} {p} {name}@0x{start:x} stored={stored:08x} computed={computed:08x}")
            if not ok:
                rc = 1
        if f.all_checksums_ok:
            print(f"OK  {p}  ({len(f.sections)} sections, {len(f.unit_sections)} inverters)")
    return rc


def cmd_fields(a):
    alias_of = {v: k for k, v in ALIASES.items()}
    if a.by_tab:
        return _fields_by_tab(alias_of)
    print(f"{'id':>3} {'offset':>7} {'name':28s} {'alias':16s} {'unit':6s} {'conf':9s} {'label':34s} in VEConfigure")
    for f in FIELDS:
        if f.confidence not in (CONFIRMED, HIGH) and not a.all:
            continue
        where = f.ui.path if f.ui else ""
        print(f"{f.id:3d} +0x{f.offset:03x} {f.name:28s} {alias_of.get(f.name, ''):16s} {f.unit:6s} {f.confidence:9s} {f.label:34s} {where}")
    if not a.all:
        print("(CONFIRMED and HIGH fields only; --all lists every named setting; --by-tab lays them out as VEConfigure does)")
    return 0


def _fields_by_tab(alias_of):
    """The settings laid out as VEConfigure's tabs and groups, with the mk2vsc name to edit each one."""
    from .fields import BY_ID
    from .ui import by_tab, TAB_LABEL, DERIVED, UNPLACED
    by_eprom = {f.eprom: f for f in FIELDS}
    for tab, groups in by_tab().items():
        if not groups:
            continue
        print(f"{TAB_LABEL[tab]}")
        for group, items in groups.items():
            print(f"  {group}")
            for key, ui in items:
                if key.startswith("setting "):
                    sid, bit = int(key.split()[1]), int(key.split()[3])
                    how = f"{BY_ID[sid].name} bit {bit}" + (" (ticked = bit clear)" if ui.inverted else "")
                    conf = BY_ID[sid].confidence
                else:
                    f = by_eprom[key]
                    how = f.name + (f"  alias {alias_of[f.name]}" if f.name in alias_of else "")
                    conf = f.confidence
                cert = "" if ui.certainty == "confirmed" else f"  [{ui.certainty} placement]"
                print(f"    {ui.label:60s} {how:44s} {conf}{cert}")
        for t, g, label, formula in DERIVED:
            if t == tab:
                print(f"    {label:60s} computed: {formula}")
        for t, g, label in UNPLACED:
            if t == tab:
                print(f"  {g}\n    {label:60s} no setting known")
    print("\nPlacement observed on VEConfigure 1.33 (talas9/rvsc-tools, MIT); 'probable' = name match not yet exercised.")
    return 0


def cmd_history(a):
    snaps, skipped = load_snapshots(a.files)
    chs = history_changes(snaps)
    if a.json:
        print(json.dumps([{"system": c.system, "serial": c.serial, "what": c.what, "old": c.old, "new": c.new,
                           "confidence": c.confidence, "after": c.after.when, "before": c.before.when,
                           "file_after": c.after.path, "file_before": c.before.path} for c in chs], indent=1, default=str))
    else:
        print(render_history(snaps, chs, skipped))
    return 0


def cmd_census(a):
    """The report we ask contributors for: everything needed to judge whether the format model holds on
    a file, without the file itself.  One block per file; safe to paste into an issue."""
    from .schema import schema_of, firmware_of_schema
    from .fields import BY_ID
    rc = 0
    for p in a.files:
        try:
            f = RvmsFile.load(p)
        except (RvmsParseError, OSError) as e:
            rc = 1
            print(f"{os.path.basename(p)}: PARSE FAILED: {e}")
            continue
        cks = "OK" if f.all_checksums_ok else "INVALID"
        try:
            mk = f.section(b"Mk2vscInfo").payload
            version = mk[6: 6 + int.from_bytes(mk[4:6], "little")].decode()
        except Exception:  # noqa: BLE001
            version = "?"
        try:
            sch = schema_of(f)
            info_fw = firmware_of_schema(f.section(b"BareSettingInfo").payload)
            schema_txt = f"parsed ({len(sch)} records, firmware {info_fw})"
        except Exception as e:  # noqa: BLE001
            sch = None
            schema_txt = f"NOT PARSED ({e})"
        units = unit_blocks(f)
        print(f"{os.path.basename(p)}: {f.length} bytes, {len(f.sections)} sections, checksums {cks}, "
              f"format {version}, schema {schema_txt}, {len(units)} inverter(s)")
        for u in units:
            asst = parse_assistant_area(u)
            gcw = grid_code_words(u)
            in_range = ""
            if sch is not None:
                from .align import check as align_check
                al = align_check(u, sch)
                in_range = ", " + al.summary
                if not al.ok:
                    rc = 1
            when = u.save_datetime.isoformat() if u.save_datetime else "?"
            print(f"  {u.serial}: block {len(u.raw)} B, flag {u.assistant_flag:02x}, form {'upload' if u.is_upload_form else 'device'}, "
                  f"firmware {u.firmware_version}, saved {when}, assistant: {asst['summary']}; {gcw['summary']}{in_range}")
            keys = [2, 3, 4, 5, 6, 11, 54, 58, 62, 64, 65]
            cells = []
            for k in keys:
                fld = BY_ID[k]
                v = fld.decode(u.setting(k))
                cells.append(f"{fld.name}={v:g}{fld.unit}" if isinstance(v, float) else f"{fld.name}={v}{fld.unit}")
            print("    " + "  ".join(cells))
        if not f.all_checksums_ok or sch is None or len(units) == 0:
            rc = 1
    if rc == 0 and not a.quiet:
        print("\nTo report: paste this output into a GitHub issue together with what the values SHOULD be "
              "(as VEConfigure or VRM shows them). https://github.com/kylehart/mk2vsc/issues/new/choose")
    return rc


def cmd_experimental(a):
    if not a.i_accept_the_risk:
        return _fail("experimental commands have never produced a running ESS system and have disrupted live systems; "
                     "read docs/ESS_INJECTION.md, then pass --i-accept-the-risk", 2)
    from .experimental import graft, to_upload_form, GraftRefused, TransformRefused
    try:
        if a.what == "graft":
            out, checks = graft(open(a.baseline, "rb").read(), open(a.template, "rb").read(),
                                install_state=a.install_state, capacity_ah=a.capacity_ah)
            for k, v in checks.items():
                print(f"  {k}: {v}")
        else:
            ref = open(a.reference, "rb").read() if a.reference else None
            out = to_upload_form(open(a.device, "rb").read(), reference=ref)
        with open(a.out, "wb") as fh:
            fh.write(out)
        print(f"wrote {a.out} ({len(out)} bytes). EXPERIMENTAL: see docs/ESS_INJECTION.md before uploading.")
        return 0
    except (GraftRefused, TransformRefused, RvmsParseError, OSError) as e:
        return _fail(f"REFUSED: {e}")


# ----------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mk2vsc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    s = sub.add_parser("show", help="what is in a file, per inverter, in plain labels")
    s.add_argument("files", nargs="+", metavar="FILE")
    s.add_argument("--all", action="store_true", help="include low-confidence and unknown settings")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("edit", help="change settings; writes FILE.edited.rvms (never overwrites the input)")
    s.add_argument("file", metavar="FILE")
    s.add_argument("assignments", nargs="+", metavar="FIELD=VALUE")
    s.add_argument("-o", "--output", help="output path (default: <FILE>.edited.rvms)")
    s.add_argument("--serial", help="edit one inverter only (default: all, as a shared battery needs)")
    s.add_argument("--overwrite", action="store_true", help="allow replacing an existing output file")
    s.add_argument("--allow-unverified", action="store_true", help="edit MEDIUM/LOW/UNKNOWN fields (you are the first to try)")
    s.add_argument("--allow-out-of-range", action="store_true", help="skip the plausibility and float<=absorption checks")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("verify", help="after uploading: does the re-download carry exactly your change?")
    s.add_argument("prepared", metavar="PREPARED")
    s.add_argument("redownload", metavar="REDOWNLOAD")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("check", help="values as intended and equal on every inverter; exit 1 if not")
    s.add_argument("files", nargs="+", metavar="FILE")
    s.add_argument("--expect", nargs="+", metavar="FIELD=VALUE", help="expected values")
    s.add_argument("--intent", help="JSON intent file (advanced; see docs/CHANGE_CONTROL.md)")
    s.add_argument("--no-agreement", action="store_true", help="do not require the inverters to agree")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("diff", help="what differs between two files, compared by inverter serial")
    s.add_argument("a"); s.add_argument("b"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("history", help="dated change log from a folder of old downloads")
    s.add_argument("files", nargs="+", metavar="FILE"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_history)

    s = sub.add_parser("validate", help="structure and checksums only")
    s.add_argument("files", nargs="+", metavar="FILE"); s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("fields", help="the settings table: names, aliases, confidence")
    s.add_argument("--all", action="store_true", help="include MEDIUM/LOW/UNKNOWN entries")
    s.add_argument("--by-tab", action="store_true", help="lay the settings out as VEConfigure's tabs and groups")
    s.set_defaults(fn=cmd_fields)

    s = sub.add_parser("census", help="the self-check report to paste into an issue: structure, schema, inverters, key values")
    s.add_argument("files", nargs="+", metavar="FILE"); s.add_argument("-q", "--quiet", action="store_true", help="omit the reporting hint")
    s.set_defaults(fn=cmd_census)

    x = sub.add_parser("experimental", help="assistant-injection experiments (docs/ESS_INJECTION.md)")
    xs = x.add_subparsers(dest="what", required=True)
    g = xs.add_parser("graft"); g.add_argument("baseline"); g.add_argument("template"); g.add_argument("out")
    g.add_argument("--install-state", action="store_true"); g.add_argument("--capacity-ah", type=int, default=None)
    g.add_argument("--i-accept-the-risk", action="store_true"); g.set_defaults(fn=cmd_experimental)
    t = xs.add_parser("to-upload-form"); t.add_argument("device"); t.add_argument("out"); t.add_argument("--reference")
    t.add_argument("--i-accept-the-risk", action="store_true"); t.set_defaults(fn=cmd_experimental)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
