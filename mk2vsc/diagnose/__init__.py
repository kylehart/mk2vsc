"""
``mk2vsc diagnose``: configuration problems read from the settings themselves, with the evidence, a proposed
fix the user may take or leave, a corrected file built through the writer's guards, and a manual change
sheet for typing the same change into VEConfigure.

    from mk2vsc.diagnose import diagnose_files, apply_fixes, sheet_rows
    rep = diagnose_files(["download.rvms"])          # Report; rep.as_dict() is report_version 1 JSON
    fr = rep.files[0]
    out, intent = apply_fixes(data, fr, accept=[f.id for f in fr.findings if f.rule == "D1"],
                              values={"absorption_V": 56.8, "float_V": 54.0, "dc_low_shutdown_V": 48.0})
    rows = sheet_rows(fr, intent)

Rules live in ``mk2vsc/diagnose/rules``, one module each; docs/DIAGNOSE.md lists them with their evidence.
"""
from .report import Report, FileReport, Finding, Question, REPORT_VERSION
from .engine import diagnose_bytes, diagnose_files
from .fix import apply_fixes, plan_edits, FixRefused
from .sheet import sheet_rows, render_sheet
from .render import render
from .rules import load_rules

__all__ = ["Report", "FileReport", "Finding", "Question", "REPORT_VERSION", "diagnose_bytes", "diagnose_files",
           "apply_fixes", "plan_edits", "FixRefused", "sheet_rows", "render_sheet", "render", "load_rules"]
