"""Run every rule over a file and assemble the report."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from .context import build_context, FileContext
from .report import Finding, Question, FileReport, Report, QUESTIONS, SEVERITIES
from .rules import load_rules

UNVERIFIED_NOTE = "unverified on single-unit .rvsc files: no such file is in the fixture corpus yet"


def _p3(ctx: FileContext) -> Finding:
    return Finding(id="P3", rule="P3", title="Upload-form file offered as device state", severity="INFO",
                   decode_confidence="CONFIRMED", evidence_class="device-confirmed", serials=ctx.serials,
                   evidence=[{"serial": s, "field": "form", "label": "block form", "unit": "", "raw": "upload", "value": "upload form",
                              "schema_min": None, "schema_max": None, "schema_default": None, "confidence": "CONFIRMED",
                              "vote": "16-byte GUI export blob at +0x45"} for s in ctx.serials],
                   message=ctx.message, fix=None)


def diagnose_bytes(data: bytes, name: str = "<bytes>", assume: Optional[Dict[str, str]] = None) -> FileReport:
    ctx = build_context(data, name=name, assume=assume)
    fr = FileReport(name=name, status=ctx.status, message=ctx.message, serials=ctx.serials, editable=ctx.editable,
                    refusal_reason=ctx.refusal_reason, nominal_voltage=ctx.nominal, chemistry=ctx.chemistry,
                    chemistry_source=ctx.chemistry_source, unverified_format=ctx.unverified_format, _ctx=ctx)
    if ctx.status == "upload_form":
        fr.findings = [_p3(ctx)]
    elif ctx.status == "ok":
        for rule in load_rules():
            fr.findings.extend(rule.run(ctx))
    order = {s: i for i, s in enumerate(SEVERITIES)}
    fr.findings.sort(key=lambda f: (order.get(f.severity, 9), f.rule, f.serials))
    for f in fr.findings:
        f.file = name
        if ctx.unverified_format:
            f.note = UNVERIFIED_NOTE
    asked: Dict[str, List[str]] = {}
    for f in fr.findings:
        for q in f.conditional:
            asked.setdefault(q, []).append(f.id)
    fr.questions = [Question(q, QUESTIONS[q], ids) for q, ids in asked.items()]
    return fr


def diagnose_files(paths: List[str], assume: Optional[Dict[str, str]] = None) -> Report:
    files = []
    for p in paths:
        try:
            with open(p, "rb") as fh:
                data = fh.read()
        except OSError as e:
            files.append(FileReport(name=os.path.basename(p), status="unparseable", message=str(e), serials=[], editable=False,
                                    refusal_reason=str(e), nominal_voltage=None, chemistry="unknown", chemistry_source="unknown",
                                    unverified_format=p.lower().endswith(".rvsc")))
            continue
        files.append(diagnose_bytes(data, name=os.path.basename(p), assume=assume))
    return Report(files=files)
