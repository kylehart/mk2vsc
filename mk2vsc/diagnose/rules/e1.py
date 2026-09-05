"""E1: the empty assistant stub a failed by-file install leaves behind."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, DEVICE_CONFIRMED

TEXT = ("By file: `mk2vsc assistant reinstall` builds an upload-form file from an earlier download of the same system "
        "that carries the assistant on every inverter; uploading it resets the VE.Bus (docs/ASSISTANTS.md section 8). "
        "Without such a download: re-author the assistant in VEConfigure. Settings edits are refused on this file until then.")


def run(ctx: FileContext) -> List[Finding]:
    out = []
    for s in ctx.serials:
        a = ctx.assistant[s]
        if not a["stub"]:
            continue
        out.append(Finding(id=f"E1:{s}", rule="E1", title="Failed by-file assistant install (empty stub)", severity="BLOCKS",
                           decode_confidence="CONFIRMED", evidence_class=DEVICE_CONFIRMED, serials=[s],
                           evidence=[{"serial": s, "field": "assistant_area", "label": "assistant area", "unit": "", "raw": a["tail_hex"],
                                      "value": a["summary"], "schema_min": None, "schema_max": None, "schema_default": None,
                                      "confidence": "CONFIRMED", "vote": "stub signature 40 00 a7 fe"}],
                           message=f"{s}: the assistant area holds the 64-byte empty container a by-file install leaves when the "
                                   f"device stores the file but never starts the assistant. The inverter runs without its "
                                   f"assistant. {TEXT}",
                           fix={"kind": "gui", "text": TEXT, "lacks": [s]}))
    return out


RULE = Rule("E1", "Failed by-file assistant install (empty stub)", DEVICE_CONFIRMED,
            "The `40 00 a7 fe` container signature in the assistant area. Known signature from four corpus downloads "
            "(Systems A and B, 2026-07-24 and 08-12); the writer refuses such files.",
            "system_a/system_a_2026-08-12_download_stub_deviceform_1.rvms", run)
