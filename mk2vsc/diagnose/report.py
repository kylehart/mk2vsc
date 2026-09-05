"""Report records: the contract between the engine, the CLI text, and any consumer of ``--json`` (``report_version`` 1)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from ..fields import CONFIDENCE_ORDER

REPORT_VERSION = 1
SEVERITIES = ("BLOCKS", "DEGRADES", "FRAGILE", "INFO")
DEVICE_CONFIRMED, VENDOR_DOCUMENTED, INFERRED = "device-confirmed", "vendor-documented", "inferred"
CONF_ORDER = list(CONFIDENCE_ORDER)

QUESTIONS: Dict[str, str] = {
    "chemistry": "What battery chemistry is on this system, lithium or lead-acid? (Inferred lithium when any inverter "
                 "carries the LithiumBattery flag; otherwise state it: --assume chemistry=lithium)",
    "shared_battery": "Are the inverters in this file on one shared battery? (D2 applies only then; a shared bank wants "
                      "identical charger settings.)",
    "ess_intended": "Is ESS intended on this system? (An assistant on one inverter of a pair is a fault if yes, a "
                    "half-finished removal if no.)",
}


def weakest(confidences: List[str]) -> str:
    """The lowest decode confidence among the fields a finding read."""
    if not confidences:
        return "UNKNOWN"
    return max(confidences, key=lambda c: CONF_ORDER.index(c) if c in CONF_ORDER else len(CONF_ORDER))


@dataclass
class Finding:
    id: str
    rule: str
    title: str
    severity: str
    decode_confidence: str
    evidence_class: str
    serials: List[str]
    evidence: List[dict]
    message: str
    fix: Optional[dict] = None
    conditional: List[str] = field(default_factory=list)
    file: str = ""
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Question:
    id: str
    text: str
    affects: List[str]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileReport:
    name: str
    status: str
    message: str
    serials: List[str]
    editable: bool
    refusal_reason: str
    nominal_voltage: Optional[int]
    chemistry: str
    chemistry_source: str
    unverified_format: bool
    assumptions: Dict[str, object] = field(default_factory=dict)   # the answers that were stated (chemistry, shared_battery, ess_intended)
    findings: List[Finding] = field(default_factory=list)
    questions: List[Question] = field(default_factory=list)
    _ctx: object = field(default=None, repr=False, compare=False)

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "message": self.message, "serials": self.serials,
                "editable": self.editable, "refusal_reason": self.refusal_reason, "nominal_voltage": self.nominal_voltage,
                "chemistry": self.chemistry, "chemistry_source": self.chemistry_source,
                "unverified_format": self.unverified_format, "assumptions": self.assumptions}


@dataclass
class Report:
    files: List[FileReport]
    intent: Optional[dict] = None

    @property
    def findings(self) -> List[Finding]:
        return [f for fr in self.files for f in fr.findings]

    @property
    def questions(self) -> List[Question]:
        seen: Dict[str, Question] = {}
        for fr in self.files:
            for q in fr.questions:
                if q.id in seen:
                    seen[q.id].affects = sorted(set(seen[q.id].affects) | set(q.affects))
                else:
                    seen[q.id] = Question(q.id, q.text, list(q.affects))
        return list(seen.values())

    def as_dict(self) -> dict:
        d = {"report_version": REPORT_VERSION,
             "files": [fr.as_dict() for fr in self.files],
             "findings": [f.as_dict() for f in self.findings],
             "questions": [q.as_dict() for q in self.questions]}
        if self.intent is not None:
            d["intent"] = self.intent
        return d
