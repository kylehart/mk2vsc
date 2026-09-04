"""
One module per rule.  A rule is a ``Rule`` record plus a ``run(ctx) -> List[Finding]`` function that reads
values through the ``FileContext`` and writes evidence records the report contract can carry.

Two confidences travel with every finding: the **decode confidence** of the weakest field it read (from the
settings table), and the **evidence class** of the behavioural claim: ``device-confirmed`` (a before/after on
hardware), ``vendor-documented`` (a Victron citation) or ``inferred`` (a corpus or forensic pattern).  Decode
certainty does not transfer to behaviour.

Each rule names the corpus fixture that triggers it; tests/test_diagnose.py checks that fixture and counts
the rule's hits over the whole device-form corpus.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from ..context import FileContext
from ..report import Finding


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    evidence_class: str
    description: str
    fixture: str                      # a corpus file that triggers it
    run: Callable[[FileContext], List[Finding]]


def load_rules() -> List[Rule]:
    from . import d1, d2, c1, v1, v2, e1, e2
    return [m.RULE for m in (d1, d2, c1, v1, v2, e1, e2)]
