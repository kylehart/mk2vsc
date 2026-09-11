#!/usr/bin/env python3
"""Run mk2vsc's structural checks over every .rvsc/.rvms in a directory and print aggregate counts only.

    python tools/validate_dir.py <dir> [--markdown]

This is how files that cannot enter the repository (other people's systems, files without publication
consent) are exercised: point it at a private folder and paste the tables, which carry no file name, serial,
site name, timestamp or full firmware number, into an issue or docs/QA.md.  Nothing is written.

Per file: parse, checksums, byte-exact round trip, layout (SectionTooShort), schema (192 records), alignment
of every block against the file's own schema, census verdict, diagnose status, the assistant flag's high nibble
against the presence of assistant records, and the phase/unit byte model (+0x35 = 4 * (+0x37 mod 3) and flag
low nibble = 8 + +0x35 / 4 on files with three or more units; all zero on one unit).  Firmware is reported by
family (the first two digits of the block's seven-digit number: 19/20 old microcontroller, 26/27 new), whether
the word's high byte is set, and whether the schema header's firmware number differs from the blocks'.

Exit status 1 when parse, checksums, round trip, layout, schema, the flag nibble or the phase model fail on any
file.  An alignment or census failure is a finding about a value in the file (census names the setting), not a
failure of the tool, and does not set the exit status.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from mk2vsc.sections import RvmsFile, RvmsParseError, SECTION_INFO       # noqa: E402
from mk2vsc.units import unit_blocks, check_layout                       # noqa: E402
from mk2vsc.schema import schema_of, firmware_of_schema, firmware_word_of_schema   # noqa: E402
from mk2vsc.align import check as align_check                            # noqa: E402
from mk2vsc.assistants import parse_assistant_area                       # noqa: E402
from mk2vsc.census import census_text                                    # noqa: E402
from mk2vsc.diagnose import diagnose_bytes                               # noqa: E402

CHECKS = ["parse", "checksums", "round_trip", "layout", "schema_192", "alignment", "census", "diagnose_ok_or_upload_form",
          "flag_nibble_vs_records", "phase_model"]


def check_file(data: bytes) -> dict:
    """One dict of facts and pass/fail booleans for a file; nothing identifying."""
    r = {"units": None, "format": "?", "form": "?", "fw_family": "?", "fw_high_byte_set": False, "fw_schema_differs": False,
         "assistant_records": False, "grid_code_set": False, "diagnose_status": "-"}
    r.update({c: False for c in CHECKS})
    try:
        f = RvmsFile.parse(data)
    except RvmsParseError:
        return r
    r["parse"] = True
    r["checksums"] = f.all_checksums_ok
    r["round_trip"] = f.to_bytes() == data
    try:
        mk = f.section(b"Mk2vscInfo").payload
        r["format"] = mk[6: 6 + int.from_bytes(mk[4:6], "little")].decode()
    except Exception:  # noqa: BLE001
        pass
    try:
        check_layout(f)
        r["layout"] = True
    except RvmsParseError:
        return r
    units = unit_blocks(f)
    r["units"] = len(units)
    r["form"] = "upload" if any(u.is_upload_form for u in units) else "device"
    try:
        sch = schema_of(f)
        r["schema_192"] = len(sch) == 192
        info = f.section(SECTION_INFO).payload
        fw = firmware_of_schema(info)
        r["fw_family"] = "/".join(sorted({str(u.firmware_version)[:2] for u in units}))
        r["fw_high_byte_set"] = bool(firmware_word_of_schema(info) >> 24) or any(u.firmware_word_high_byte for u in units)
        r["fw_schema_differs"] = any(u.firmware_version != fw for u in units)
        r["alignment"] = all(align_check(u, sch).ok for u in units)
    except Exception:  # noqa: BLE001
        sch = None
    areas = [parse_assistant_area(u) for u in units]
    r["assistant_records"] = any(a["kind"] == "records" for a in areas)
    r["grid_code_set"] = any(u.setting(81) != 0 for u in units)
    r["flag_nibble_vs_records"] = all(u.has_assistant_flag == (a["kind"] == "records") for u, a in zip(units, areas))
    if len(units) == 1:
        u = units[0]
        r["phase_model"] = u.slot == (0, 0) and (u.assistant_flag & 0x0F) == 0
    elif len(units) >= 3:
        r["phase_model"] = all(u.phase_byte == 4 * (u.unit_index % 3) and (u.assistant_flag & 0x0F) == 8 + u.phase_byte // 4
                               for u in units)
    else:
        r["phase_model"] = None            # two-unit files: two patterns seen (00/86 split-phase, 00/00 parallel); not scored
    r["census"] = census_text(data, "file")[1]
    fr = diagnose_bytes(data, name="file" + (".rvsc" if len(units) == 1 else ".rvms"))
    r["diagnose_status"] = fr.status
    r["diagnose_ok_or_upload_form"] = fr.status in ("ok", "upload_form")
    return r


def _table(title, rows, markdown):
    out = [f"{title}"]
    if markdown:
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + "|".join("---" for _ in rows[0]) + "|")
        out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows[1:]]
    else:
        widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
        out += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in rows]
    return "\n".join(out)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    markdown = "--markdown" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1 or not os.path.isdir(args[0]):
        print(__doc__)
        return 2
    paths = sorted(p for p in os.listdir(args[0]) if p.lower().endswith((".rvsc", ".rvms")))
    results = []
    for name in paths:
        with open(os.path.join(args[0], name), "rb") as fh:
            results.append(check_file(fh.read()))
    n = len(results)
    if n == 0:
        print("no .rvsc/.rvms files in that directory")
        return 1
    print(f"{n} files, {sum(r['units'] or 0 for r in results)} inverter blocks (aggregate only; no names, serials or timestamps)\n")

    def count(key, fmt=str):
        c = collections.Counter(fmt(r[key]) for r in results)
        return [[key, "files"]] + [[k, v] for k, v in sorted(c.items())]

    print(_table("By unit count", count("units"), markdown)); print()
    print(_table("By format version (Mk2vscInfo)", count("format"), markdown)); print()
    print(_table("By firmware family (first two digits of the block firmware number)", count("fw_family"), markdown)); print()
    print(_table("By form", count("form"), markdown)); print()
    facts = [["fact", "files"],
             ["assistant records present", sum(r["assistant_records"] for r in results)],
             ["grid code set (setting 81 != 0)", sum(r["grid_code_set"] for r in results)],
             ["firmware word high byte set", sum(r["fw_high_byte_set"] for r in results)],
             ["schema firmware differs from block firmware", sum(r["fw_schema_differs"] for r in results)],
             ["diagnose status ok", sum(r["diagnose_status"] == "ok" for r in results)],
             ["diagnose status upload_form", sum(r["diagnose_status"] == "upload_form" for r in results)],
             ["diagnose status other", sum(r["diagnose_status"] not in ("ok", "upload_form") for r in results)]]
    print(_table("Facts", facts, markdown)); print()
    rows = [["check", "pass", "fail", "n/a"]]
    for c in CHECKS:
        vals = [r[c] for r in results]
        rows.append([c, sum(v is True for v in vals), sum(v is False for v in vals), sum(v is None for v in vals)])
    print(_table("Checks (pass / fail / not applicable)", rows, markdown))
    failed = any(r[c] is False for r in results for c in CHECKS if c not in ("alignment", "census"))
    align_fail = sum(r["alignment"] is False for r in results)
    if align_fail:
        print(f"\nnote: alignment failed on {align_fail} file(s): a value outside its schema range; `mk2vsc census` on that file names the setting")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
