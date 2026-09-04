"""
The one-object API.  Everything a first-time user needs, without knowing setting IDs or section layout::

    import mk2vsc
    cfg = mk2vsc.load("download.rvms")
    cfg.units                      # {"HQ2414U6FVN": <Unit>, "HQ2414AXENJ": <Unit>}
    cfg["HQ2414U6FVN"]["absorption"]          # 56.0   (volts)
    cfg.set("absorption", 56.8)               # every inverter (a shared battery wants them equal)
    cfg.set("float", 54.0, serial="HQ2414U6FVN")
    out = cfg.save()                          # writes download.edited.rvms, never overwrites the input
    cfg.check(absorption=56.8, float=54.0)    # (ok, [(level, message), ...])
    mk2vsc.verify("download.edited.rvms", "redownload.rvms")   # after the VRM upload + re-download

Field names accept the short aliases in ``mk2vsc.fields.ALIASES`` (absorption, float, charge_current,
ac_limit, low_shutdown, vs_entry, vs_return, capacity ...), the full names from the settings table, or
a numeric VE.Bus setting ID.  The lower-level modules (sections, units, writer, diff, qualify) remain
available for anything this facade does not cover.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .sections import RvmsFile
from .units import UnitBlock, units_by_serial
from .fields import lookup, FIELDS, Field, CONFIRMED, HIGH, MEDIUM, ALIASES
from .writer import set_settings, WriteRefused, Edit
from .diff import diff_bytes, FileDiff, render as render_diff
from .qualify import Intent, qualify_bytes
from .assistants import parse_assistant_area

# Human grouping for `show`.  Field names are those in fields.py.
GROUPS: List[Tuple[str, List[str]]] = [
    ("Charger", ["absorption_V", "float_V", "charge_current_A", "charge_characteristic", "repeated_absorption_time",
                 "repeated_absorption_interval", "max_absorption_time", "charge_efficiency"]),
    ("Inverter / AC input", ["inverter_output_V", "output_frequency_Hz", "ac1_input_limit_A", "ac2_input_limit_A", "dc_low_shutdown_V",
                             "dc_low_restart_offset_V"]),
    ("Battery monitor", ["battery_capacity_Ah", "soc_at_bulk_end_pct"]),
    ("Virtual Switch (ignore AC input)", ["vs_dont_ignore_load_above_A", "vs_load_above_for_s", "vs_ignore_load_below_A",
                                          "vs_load_below_for_min", "vs_ignore_ac_below_V", "vs_udc_below_for_s",
                                          "vs_dont_ignore_soc_below_pct", "vs_accept_battery_above_V", "vs_udc_above_for_min",
                                          "aes_low_current_limit_A", "aes_current_hysteresis_A"]),
    ("Grid / ESS related", ["grid_code", "grid_settings_valid_checker_a", "flags2", "ubat_dont_charge_V",
                            "inverter_current_limit_during_assist_A"]),
    ("Flag registers", ["flags0", "flags1", "flags2"]),
]
_GROUPED = {n for _, names in GROUPS for n in names}


class Unit:
    """Read-only view of one inverter's settings, by field name, alias, or ID."""

    def __init__(self, block: UnitBlock):
        self._b = block
        self.serial = block.serial

    def __getitem__(self, key) -> object:
        f = lookup(key)
        return f.decode(self._b.setting(f.id))

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def raw(self, key) -> int:
        return self._b.setting(lookup(key).id)

    @property
    def block(self) -> UnitBlock:
        return self._b

    @property
    def assistant(self) -> str:
        return parse_assistant_area(self._b)["summary"]

    @property
    def form(self) -> str:
        return "upload" if self._b.is_upload_form else "device"

    def as_dict(self, include_unknown: bool = False) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for f in FIELDS:
            if f.id >= 190:
                continue
            if f.confidence in (CONFIRMED, HIGH, MEDIUM) or include_unknown:
                out[f.name] = f.decode(self._b.setting(f.id))
        return out

    def __repr__(self) -> str:
        return f"<Unit {self.serial} absorption={self.get('absorption')} float={self.get('float')} assistant={self.assistant!r}>"


@dataclass
class Config:
    """A parsed file plus pending edits."""

    path: Optional[str]
    data: bytes
    edits: List[Edit] = field(default_factory=list)

    # ----------------------------------------------------------------- reading
    @property
    def file(self) -> RvmsFile:
        return RvmsFile.parse(self.data)

    @property
    def units(self) -> Dict[str, Unit]:
        return {s: Unit(u) for s, u in units_by_serial(self.file).items()}

    def __getitem__(self, serial: str) -> Unit:
        return self.units[serial]

    @property
    def serials(self) -> List[str]:
        return sorted(self.units)

    @property
    def valid(self) -> bool:
        return self.file.all_checksums_ok

    @property
    def form(self) -> str:
        forms = {u.form for u in self.units.values()}
        return forms.pop() if len(forms) == 1 else "mixed"

    def value(self, key) -> Dict[str, object]:
        """``{serial: value}`` for one field across all inverters."""
        return {s: u[key] for s, u in self.units.items()}

    def agree(self, key) -> bool:
        return len(set(self.value(key).values())) == 1

    # ----------------------------------------------------------------- editing
    def set(self, key, value, serial: Optional[str] = None, **kw) -> List[Edit]:
        """Change one setting on every inverter (default) or on one.  Raises WriteRefused on anything
        outside the proven-safe surface (unknown field, low confidence, implausible value, stub, upload form)."""
        out, edits = set_settings(self.data, [(serial, lookup(key).name, value)], **kw)
        self.data = out
        self.edits.extend(edits)
        return edits

    def set_many(self, changes: Dict[str, object], serial: Optional[str] = None, **kw) -> List[Edit]:
        out, edits = set_settings(self.data, [(serial, lookup(k).name, v) for k, v in changes.items()], **kw)
        self.data = out
        self.edits.extend(edits)
        return edits

    def save(self, path: Optional[str] = None, overwrite: bool = False) -> str:
        """Write the current bytes.  Default name: ``<input>.edited.rvms`` next to the input.  Refuses to
        overwrite the input file or any existing file unless ``overwrite=True``."""
        if path is None:
            if not self.path:
                raise ValueError("no input path; give save(path=...)")
            root, ext = os.path.splitext(self.path)
            path = f"{root}.edited{ext or '.rvms'}"
        if self.path and os.path.abspath(path) == os.path.abspath(self.path):
            raise WriteRefused("refusing to overwrite the input file; keep the download as your rollback")
        if os.path.exists(path) and not overwrite:
            raise WriteRefused(f"{path} exists; pass overwrite=True or choose another name")
        with open(path, "wb") as fh:
            fh.write(self.data)
        return path

    # ----------------------------------------------------------------- checking
    def check(self, agree: bool = True, serials: Optional[Iterable[str]] = None, **expect) -> Tuple[bool, List[Tuple[str, str]]]:
        """Structure + inverter agreement + expected values, e.g. ``cfg.check(absorption=56.8, float=54.0)``."""
        settings = {lookup(k).name: v for k, v in expect.items()}
        intent = Intent(settings=settings, serials=list(serials) if serials else None, require_agreement=agree)
        return qualify_bytes(self.data, intent)

    def diff(self, other: "Config") -> FileDiff:
        return diff_bytes(self.data, other.data)

    def summary(self, include_unknown: bool = False) -> str:
        return render_summary(self, include_unknown)


def load(path: str) -> Config:
    with open(path, "rb") as fh:
        data = fh.read()
    RvmsFile.parse(data)   # fail early with a clear parse error
    return Config(path=path, data=data)


def loads(data: bytes) -> Config:
    RvmsFile.parse(data)
    return Config(path=None, data=data)


def verify(prepared: str, redownload: str) -> Tuple[bool, str]:
    """After an upload: does the device's re-download match what you uploaded, apart from bookkeeping?"""
    d = diff_bytes(load(prepared).data, load(redownload).data)
    ok = d.identical or d.only_bookkeeping
    text = render_diff(d)
    if ok:
        text = "VERIFIED: the re-download carries your settings; only pointers, timestamps and checksums differ.\n" + text
    else:
        text = "NOT VERIFIED: the re-download differs in content. Read the lines below before trusting the system.\n" + text
    return ok, text


# ----------------------------------------------------------------------- rendering
def _fmt(f: Field, raw: int) -> str:
    v = f.decode(raw)
    if f.bits:
        on = [f.bits[b] for b in f.bits if raw & (1 << b)]
        return f"0x{raw:04x}" + (f"  ({'; '.join(on)})" if on else "")
    if isinstance(v, float):
        return f"{v:g} {f.unit}".strip()
    return f"{v} {f.unit}".strip()


def render_summary(cfg: Config, include_unknown: bool = False) -> str:
    f = cfg.file
    units = units_by_serial(f)
    lines = [f"{cfg.path or '<bytes>'}: {len(cfg.data)} bytes, {len(units)} inverter(s), form={cfg.form}, "
             f"checksums {'OK' if f.all_checksums_ok else 'INVALID'}"]
    serials = sorted(units)
    for s in serials:
        u = units[s]
        lines.append(f"  {s}: firmware {u.firmware_version}, saved {u.save_datetime.isoformat() if u.save_datetime else '?'}, "
                     f"assistant: {parse_assistant_area(u)['summary']}")
    conf_mark = {CONFIRMED: "", HIGH: "", MEDIUM: "  ?", "LOW": "  ??", "UNKNOWN": "  ???"}
    width = max(len(s) for s in serials)
    for title, names in GROUPS:
        rows = []
        for n in names:
            fld = lookup(n)
            if fld.confidence not in (CONFIRMED, HIGH, MEDIUM) and not include_unknown:
                continue
            vals = [_fmt(fld, units[s].setting(fld.id)) for s in serials]
            flag = "" if len(set(vals)) == 1 else "   <- inverters differ"
            label = fld.label if fld.label and fld.label != fld.name else ""
            rows.append(f"    {fld.name:28s} {label:34s} " + "  ".join(f"{v:>{max(width, 14)}}" for v in vals)
                        + conf_mark.get(fld.confidence, "") + flag)
        if rows:
            lines.append(f"  {title}")
            lines.extend(rows)
    if include_unknown:
        rest = [x for x in FIELDS if x.name not in _GROUPED and x.id < 190 and x.confidence != "UNKNOWN"]
        lines.append("  Other named settings (below HIGH confidence; reserved and grid-code slots omitted)")
        for fld in rest:
            vals = [_fmt(fld, units[s].setting(fld.id)) for s in serials]
            lines.append(f"    {fld.name:28s} {('id ' + str(fld.id)):34s} " + "  ".join(f"{v:>{max(width, 14)}}" for v in vals)
                        + conf_mark.get(fld.confidence, ""))
    lines.append("  Legend: ? = MEDIUM confidence, ?? = LOW, ??? = UNKNOWN; no mark = CONFIRMED/HIGH. "
                 "Names are what `mk2vsc edit` takes; `--all` shows every setting.")
    return "\n".join(lines)
