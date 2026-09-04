"""
What the rules know about one file before any rule runs.

A ``FileContext`` is built once per input: parse, checksums, blocks by serial, the device schema, the nominal
voltage read from that schema, the battery chemistry (stated by the user, else inferred from the LithiumBattery
flag on any block of the shared battery, else unknown), the assistant state per block, and whether the writer
would accept the file at all (``editable`` plus the writer's own refusal reason).  Rules read values through it
so every finding's evidence carries raw, decoded, schema min/max/default and the field's decode confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..sections import RvmsFile, RvmsParseError
from ..units import UnitBlock, units_by_serial
from ..schema import schema_of, nominal_voltage, SettingInfo
from ..fields import lookup, Field, BY_NAME
from ..assistants import parse_assistant_area
from ..align import check as align_check
from ..writer import WriteRefused, preflight

STATUSES = ("ok", "unparseable", "checksum_invalid", "duplicate_serial", "upload_form", "no_schema", "misaligned")
LITHIUM_FIELD, LITHIUM_BIT = "flags2", 4
STORAGE_FIELD, STORAGE_BIT = "flags0", 11

RVSC_NOTE = ("If this is a single-unit .rvsc saved by VEConfigure on a PC: that format is not supported yet. "
             "mk2vsc reads the .rvms that VRM's Remote VEConfigure downloads; no .rvsc fixture is in hand "
             "(github.com/kylehart/mk2vsc/issues/14). If you can share one, it names the layout for everyone.")


@dataclass
class FileContext:
    name: str
    data: bytes
    status: str = "ok"
    message: str = ""
    file: Optional[RvmsFile] = None
    units: Dict[str, UnitBlock] = field(default_factory=dict)
    schema: Optional[List[SettingInfo]] = None
    nominal: Optional[int] = None
    chemistry: str = "unknown"            # lithium | lead-acid | unknown
    chemistry_source: str = "unknown"     # stated | flag:<serial> | unknown
    assume: Dict[str, str] = field(default_factory=dict)
    editable: bool = False
    refusal_reason: str = ""
    unverified_format: bool = False
    assistant: Dict[str, dict] = field(default_factory=dict)
    memo: Dict[object, object] = field(default_factory=dict)   # per-file cache for rules (D1 votes)

    # ------------------------------------------------------------- values
    @property
    def serials(self) -> List[str]:
        return sorted(self.units)

    def raw(self, serial: str, name) -> int:
        return self.units[serial].setting(lookup(name).id)

    def value(self, serial: str, name):
        f = lookup(name)
        return f.decode(self.raw(serial, name))

    def info(self, name) -> SettingInfo:
        return self.schema[lookup(name).id]

    def bit(self, serial: str, name, bit: int) -> bool:
        return bool((self.raw(serial, name) >> bit) & 1)

    def lithium_flag(self, serial: str) -> bool:
        return self.bit(serial, LITHIUM_FIELD, LITHIUM_BIT)

    def at_default(self, serial: str, name) -> bool:
        return self.raw(serial, name) == self.info(name).default

    def at_min(self, serial: str, name) -> bool:
        return self.raw(serial, name) == self.info(name).min

    def evidence(self, serial: str, name, vote: str = "") -> dict:
        """One evidence record: raw, decoded, schema min/max/default, all in the field's engineering units."""
        f: Field = lookup(name)
        r = self.info(name)
        raw = self.raw(serial, name)
        dec = (lambda x: x) if f.bits else f.decode
        return {"serial": serial, "field": f.name, "label": f.label, "unit": f.unit, "raw": raw, "value": dec(raw),
                "schema_min": dec(r.min), "schema_max": dec(r.max), "schema_default": dec(r.default),
                "confidence": f.confidence, "vote": vote}

    def needs_value(self, serial: str, name) -> dict:
        f: Field = lookup(name)
        r = self.info(name)
        return {"serial": serial, "field": f.name, "unit": f.unit, "current": f.decode(self.raw(serial, name)),
                "schema_min": f.decode(r.min), "schema_max": f.decode(r.max), "schema_default": f.decode(r.default)}


def is_rvsc(name: str) -> bool:
    return name.lower().endswith(".rvsc")


def build_context(data: bytes, name: str = "<bytes>", assume: Optional[Dict[str, str]] = None) -> FileContext:
    ctx = FileContext(name=name, data=data, assume=dict(assume or {}))
    ctx.unverified_format = is_rvsc(name)
    try:
        f = RvmsFile.parse(data)
    except RvmsParseError as e:
        ctx.status, ctx.message = "unparseable", f"not a readable .rvms: {e}"
        if ctx.unverified_format or b"VEConfig" in data[:64]:
            ctx.message += " " + RVSC_NOTE
        return ctx
    ctx.file = f
    if not f.all_checksums_ok:
        bad = [n for n, *_, ok in f.checksum_report() if not ok]
        ctx.status, ctx.message = "checksum_invalid", f"section checksums invalid in {bad}; the values may not be the device's"
        return ctx
    try:
        ctx.units = units_by_serial(f)
    except ValueError as e:
        ctx.status, ctx.message = "duplicate_serial", str(e)
        return ctx
    if not ctx.units:
        ctx.status, ctx.message = "no_schema", "no inverter block (BareSettingData) in the file"
        return ctx
    ctx.assistant = {s: parse_assistant_area(u) for s, u in ctx.units.items()}
    if any(u.is_upload_form for u in ctx.units.values()):
        ctx.status = "upload_form"
        ctx.message = ("this is a GUI export (upload form), not a device download: it says what someone prepared to "
                       "upload, not what the inverters hold. Diagnose a fresh Remote VEConfigure download instead.")
        return ctx
    try:
        ctx.schema = schema_of(f)
        ctx.nominal = nominal_voltage(ctx.schema)
    except (KeyError, ValueError) as e:
        ctx.status, ctx.message = "no_schema", f"device schema (BareSettingInfo) not usable: {e}"
        return ctx
    for s, u in ctx.units.items():
        al = align_check(u, ctx.schema)
        if not al.ok:
            ctx.status, ctx.message = "misaligned", f"{s}: {al.summary}; values decoded from this block cannot be trusted"
            return ctx
    # chemistry: stated beats inferred; one lithium flag on a shared battery settles the pair
    stated = ctx.assume.get("chemistry")
    if stated in ("lithium", "lead-acid"):
        ctx.chemistry, ctx.chemistry_source = stated, "stated"
    else:
        flagged = [s for s in ctx.serials if ctx.lithium_flag(s)]
        if flagged:
            ctx.chemistry, ctx.chemistry_source = "lithium", f"flag:{','.join(flagged)}"
    # would the writer take this file?  Same guards, same words, on the state already parsed above.
    try:
        preflight(ctx.units, ctx.schema)
        ctx.editable = True
    except WriteRefused as e:
        ctx.editable, ctx.refusal_reason = False, str(e)
    return ctx
