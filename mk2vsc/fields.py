"""
The settings table: what each u16 in the per-inverter settings array means, and how sure we are.

Every ``BareSettingData`` block carries a flat array of 190 little-endian u16 values starting at
block offset +0x59 (device form).  Entry *n* of that array is VE.Bus **setting ID n** as documented by
the community MK2/MK3 protocol work (github.com/xcellsior/ve-bus-programming, "Persistent Settings
IDs 0-255").  We established the mapping by noticing that the two fields we had confirmed
independently (absorption at +0x5d, float at +0x5f) sit exactly where setting IDs 2 and 3 land,
then checking the rest of the array against that reference across the whole corpus (162 blocks in 81 well-formed files):

* ID 5 reads 120 in every device-form block (our inverters are 120 V units)
* ID 6 reads 500 = 50.0 A (AC input current limit, /10)
* ID 65 reads 190 or 196 = 95 % or 98 % (SoC at bulk end, x0.5) exactly as the reference predicts
* ID 81 (grid-code active) reads 0 in bare blocks and 1 in blocks with a grid code
* ID 73 reads 6300 = the 63.00 V protection threshold that appears in our alarm history

Confidence vocabulary (be honest, and be specific):

    CONFIRMED  written by our tool, applied to a live system through Remote VEConfigure, and read back;
               or matched to a VEConfigure screen showing the value.
    HIGH       reference ID + scale reproduce a value that is physically sensible on every corpus block
               and that we can tie to a known property of the installation.
    MEDIUM     reference ID exists but we have not verified the scale/meaning against the system.
    LOW        we can name a plausible meaning from context only.
    UNKNOWN    observed values are recorded; meaning unknown.

A CONFIRMED entry is safe to edit with the writer.  Everything else is safe to *read*; editing it means
you are the first person to test that offset on hardware.  The writer refuses to touch anything below
HIGH unless you pass ``--i-know-this-is-unverified``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

CONFIRMED, HIGH, MEDIUM, LOW, UNKNOWN = "CONFIRMED", "HIGH", "MEDIUM", "LOW", "UNKNOWN"


@dataclass(frozen=True)
class Field:
    id: int                      # VE.Bus setting ID == index in the settings array
    name: str                    # short machine name
    label: str                   # what VEConfigure calls it, where known
    scale: float = 1.0           # value = raw / scale
    unit: str = ""
    confidence: str = UNKNOWN
    description: str = ""        # what it does in a Victron system
    evidence: str = ""           # why we believe the mapping
    observed: str = ""           # values seen in the corpus
    source: str = ""             # 'xcellsior' (public MK2 protocol reference) / 'ours' / both
    bits: Optional[Dict[int, str]] = None   # for flag registers: bit -> meaning when SET
    lo: Optional[float] = None   # plausibility range in engineering units (48 V systems); writer refuses outside
    hi: Optional[float] = None

    @property
    def offset(self) -> int:
        """Device-form block offset (add 10 for upload-form blocks)."""
        return 0x59 + 2 * self.id

    def decode(self, raw: int):
        return raw / self.scale if self.scale != 1.0 else raw

    def encode(self, value) -> int:
        raw = int(round(value * self.scale))
        if not 0 <= raw <= 0xFFFF:
            raise ValueError(f"{self.name}: {value} does not fit in u16 after scaling")
        return raw


XC = "xcellsior/ve-bus-programming FINDINGS.md"

FIELDS: List[Field] = [
    Field(0, "flags0", "Primary flags register", 1, "bitmask", HIGH,
          "Bit register of on/off options. Known bits (from the MK2 protocol reference): "
          "bit 3 SET = UPS function DISABLED; bit 5 SET = PowerAssist enabled; "
          "bit 11 SET = adaptive (lead-acid) charge curve, CLEAR = fixed (LiFePO4); bit 14 SET = Weak AC.",
          "Reference bit table. On our fleet the ESS installs performed in the GUI changed 0x89xx -> 0x81xx, "
          "i.e. cleared bit 11 (adaptive charge) -- consistent with the GUI switching the charge curve to fixed "
          "for a lithium battery, and consistent with the reference. Not yet toggled by us.",
          "0x81f4 (most), 0x89f4, 0x89b4, 0x817c, 0x81b4",
          XC, bits={3: "UPS function disabled", 5: "PowerAssist enabled", 11: "Adaptive charge curve (lead-acid)",
                    14: "Weak AC input enabled"}),
    Field(1, "flags1", "Secondary flags register", 1, "bitmask", HIGH,
          "Second bit register. bit 11 SET = accept wide input frequency range; bit 12 SET = dynamic current limiter.",
          "Reference bit table; value 0x4dfe on every device-form block.",
          "0x4dfe (device form), 0x6a5f/0x6a55/0x6a7e in a few grafted files",
          XC, bits={11: "Accept wide frequency range", 12: "Dynamic current limiter"}),
    Field(2, "absorption_V", "Absorption voltage", 100, "V", CONFIRMED,
          "Charger absorption (bulk end) voltage. With a CAN-bus BMS and DVCC active the BMS charge-voltage limit "
          "overrides this; it is the fallback used when the BMS link is absent.",
          "Written by the writer on four systems (2026-07-20) via Remote VEConfigure, read back correct on every "
          "inverter; matches VRM 'Absorption' and VEConfigure Charger tab.",
          "5600, 5650, 5680, 5760 (also 4800 on a mis-commissioned unit, 0 in stub blocks)", "ours + " + XC, lo=40.0, hi=66.0),
    Field(3, "float_V", "Float voltage", 100, "V", CONFIRMED,
          "Charger float voltage (after absorption).",
          "First live proof of the whole toolchain: float 54.0 -> 54.1 V on both inverters of one system, "
          "uploaded, 'Success', read back 54.1 (2026-07-20). Later edits confirmed again.",
          "5400, 5410, 5420, 5520", "ours + " + XC, lo=40.0, hi=66.0),
    Field(4, "charge_current_A", "Charge current", 1, "A", HIGH,
          "Maximum battery charge current from the charger.",
          "Reference ID/scale; 35 on every device-form block (a deliberate installer limit, consistent across "
          "eight inverters). Not edited by us.", "35", XC, lo=0, hi=300),
    Field(5, "inverter_output_V", "Inverter output voltage", 1, "V", HIGH,
          "Nominal AC output voltage of the inverter.",
          "Reference; 120 on every block (these are 120 V units). Upload-form blocks read it at +10.", "120", XC, lo=100, hi=250),
    Field(6, "ac1_input_limit_A", "AC input 1 current limit", 10, "A", HIGH,
          "Shore/grid input current limit for AC input 1 (the persistent value; the GX can override at runtime).",
          "Reference; 500 = 50.0 A on every device-form block, matching the installation's breaker sizing.", "500", XC, lo=0, hi=200),
    Field(7, "repeated_absorption_time", "Repeated absorption time", 1, "", MEDIUM,
          "Duration of a periodic re-absorption cycle (lead-acid curve).", "Reference name only.", "2, 4", XC),
    Field(8, "repeated_absorption_interval", "Repeated absorption interval", 1, "", MEDIUM,
          "Interval between periodic re-absorption cycles.", "Reference name only.", "4, 28", XC),
    Field(9, "max_absorption_time", "Maximum absorption time", 1, "", MEDIUM,
          "Absorption time limit; the reference notes '1 for LiFePO4 fixed'.", "Reference.", "1, 8", XC),
    Field(10, "charge_characteristic", "Charge characteristic", 1, "enum", MEDIUM,
          "0 = variable (adaptive), 1 = fixed, 2 = fixed + storage.", "Reference enum; 1 on lithium systems here.",
          "1, 3", XC),
    Field(11, "dc_low_shutdown_V", "DC input low shut-down", 100, "V", HIGH,
          "Battery voltage at which the inverter shuts down (low-battery cutoff).",
          "Reference ID/scale. Our differential decode saw this move 37.20 -> 48.50 V on two systems during the "
          "installer's 'properly configure' pass and it reads 48.50 on all current blocks; 48.5 V is a sane LFP "
          "floor.", "4850, 3720, 4800", "ours + " + XC, lo=36.0, hi=56.0),
    Field(12, "dc_low_restart_offset_V", "DC input low restart offset", 100, "V", HIGH,
          "Voltage above the shut-down level at which the inverter restarts.",
          "Reference; 2.00 V fleet-wide.", "200, 640", XC, lo=0.0, hi=12.0),
    Field(13, "unknown_13", "", 1, "", UNKNOWN, "", "", "0"),
    Field(14, "unknown_14", "", 1, "", UNKNOWN, "", "", "0"),
    Field(15, "unknown_toggle_15", "Unknown toggle", 1, "", LOW,
          "The reference notes this 'differs between units'.",
          "Values track the installer's configuration pass (3 on configured, 1/0 on older).", "0, 1, 3", XC),
    Field(16, "param16", "", 1, "", UNKNOWN, "First of a repeated parameter block (16-18 / 28-30 have the same shape).",
          "", "2125"),
    Field(17, "param17_V", "", 100, "V?", LOW, "Reads 64.00 -- voltage-like; possibly a DC high alarm/threshold.",
          "Same value as ID 29 and as the unreachable 64.00 V VS-return threshold once set on two systems.", "6400"),
    Field(18, "param18_V", "", 100, "V?", LOW, "Reads 47.00 -- voltage-like.", "Same value as ID 30.", "4700"),
    Field(24, "param24", "", 1, "", UNKNOWN, "", "", "2"),
    Field(25, "param25", "", 1, "", UNKNOWN, "", "", "2"),
    Field(26, "param26", "", 1, "", UNKNOWN, "", "", "2"),
    Field(27, "param27", "", 1, "", UNKNOWN, "", "", "2"),
    Field(28, "param28", "", 1, "", UNKNOWN, "Second copy of the 16-18 block shape.", "", "531"),
    Field(29, "param29_V", "", 100, "V?", LOW, "Reads 64.00.", "", "6400"),
    Field(30, "param30_V", "", 100, "V?", LOW, "Reads 47.00.", "", "4700"),
    Field(37, "param37", "", 1, "", UNKNOWN, "", "", "1"),
    Field(44, "param44", "", 1, "", UNKNOWN, "", "", "90"),
    Field(45, "param45", "", 1, "", UNKNOWN, "", "", "7"),
    Field(46, "param46", "", 1, "", UNKNOWN, "", "", "40"),
    Field(47, "param47", "", 1, "", UNKNOWN, "", "", "5"),
    Field(48, "param48", "", 1, "", UNKNOWN, "", "", "32"),
    Field(49, "ac2_input_limit_A", "AC input 2 current limit", 10, "A", MEDIUM,
          "Quattro only; 0 on MultiPlus.", "Reference; 0 on all our MultiPlus blocks.", "0", XC),
    Field(50, "vs_param50", "Virtual Switch parameter", 1, "", LOW,
          "IDs 50-59 hold the Virtual Switch 'ignore AC input' parameters (the reference lists 50-59 as a "
          "parameter block). 60 and 40 look like time constants in seconds (1 min / 40 s).", "", "60"),
    Field(51, "vs_param51", "Virtual Switch parameter", 1, "", LOW, "", "", "40"),
    Field(52, "vs_param52", "Virtual Switch parameter", 1, "", LOW,
          "Moves with the VS thresholds across the installer's configuration pass (833/2125 -> 1750); "
          "scale unknown (volts x100, watts, or something else).", "", "1750, 2125, 833"),
    Field(53, "vs_param53", "Virtual Switch parameter", 1, "", LOW, "", "", "4, 0, 6"),
    Field(54, "vs_ignore_ac_below_V", "VS: do not ignore AC input when Udc lower than", 100, "V", CONFIRMED,
          "Virtual Switch 'Ignore AC input' battery condition: leave battery operation and accept the grid when "
          "DC voltage drops below this (for the configured time). Entry-to-passthrough threshold.",
          "Matched byte-for-byte to a VEConfigure Virtual Switch tab screenshot (51.40 V) and to the installer's "
          "note of lowering it to 51.0 at all sites; later GUI changes landed here. Written by us (rollback files).",
          "5100 (current), 4700 (old)", "ours", lo=40.0, hi=60.0),
    Field(55, "vs_param55", "Virtual Switch parameter", 1, "", LOW, "Time-like (20 s?).", "", "21, 6, 0"),
    Field(56, "vs_param56", "Virtual Switch parameter", 1, "", LOW, "Scale unknown.",
          "", "1500, 531, 625"),
    Field(57, "vs_param57", "Virtual Switch parameter", 1, "", LOW, "", "", "2, 0"),
    Field(58, "vs_accept_battery_above_V", "VS: ignore AC input again when Udc higher than", 100, "V", CONFIRMED,
          "Virtual Switch return condition: go back to battery (ignore AC) when DC voltage exceeds this. A value "
          "above what the battery can reach (64.00 V on a 48 V LFP) makes passthrough permanent -- the root cause "
          "of a 5.6-day stuck-on-grid episode on one system.",
          "Screenshot match (53.00 V); the installer's per-site values (53.0 / 52.5) appear here; edited by us.",
          "5250, 5300, 6400 (old, unreachable)", "ours", lo=40.0, hi=66.0),
    Field(59, "vs_param59", "Virtual Switch parameter", 1, "", LOW, "", "", "2, 0"),
    Field(60, "solar_wind_priority_flags", "Solar & wind priority flags", 1, "bitmask", MEDIUM,
          "Reference: bit 4 (16) = off, 528 = on.", "Reference; 16 on bare blocks, 48 after GUI ESS install.",
          "16, 48, 0", XC),
    Field(62, "param62", "", 1, "", UNKNOWN, "", "", "41667, 41666"),
    Field(63, "param63", "", 1, "", UNKNOWN, "", "", "32668, 32768"),
    Field(64, "battery_capacity_Ah", "Battery capacity", 1, "Ah", HIGH,
          "Capacity used by the inverter's built-in battery monitor; 0 disables the monitor.",
          "Reference; 200 / 300 Ah match the installed EG4 module counts (2 x 100 Ah vs 3 x 100 Ah).",
          "200, 300, 0", XC, lo=0, hi=10000),
    Field(65, "soc_at_bulk_end_pct", "SoC when bulk finished", 2, "%", HIGH,
          "State of charge the built-in monitor assumes at the end of bulk (x0.5 %).",
          "Reference: '190 = 95 % for LiFePO4'; we see 190 and 196 (98 %).", "190, 196, 170", XC, lo=0, hi=100),
    Field(66, "param66_V", "", 100, "V?", LOW, "57.72 V -- voltage-like; possibly a second (lead-acid default) "
          "charge profile paired with 68.", "", "5772"),
    Field(67, "param67", "", 1, "", LOW, "Changed 04 -> 02 by the GUI ESS install on one inverter.", "", "3, 2, 4"),
    Field(68, "param68_V", "", 100, "V?", LOW, "54.00 V -- voltage-like, pairs with 66.", "", "5400"),
    Field(69, "param69", "", 1, "", LOW, "Changed 1c -> 04 by the GUI ESS install on one inverter.", "", "3, 4, 28"),
    Field(70, "param70", "", 1, "", LOW, "0 -> 50 during the installer's configuration pass ('?flag_e5').", "",
          "50, 0"),
    Field(71, "param71", "", 1, "", UNKNOWN, "", "", "32768"),
    Field(72, "charge_efficiency", "Battery charge efficiency", 1, "", MEDIUM,
          "Reference: 242 is about 95 % for LiFePO4.", "Reference.", "250, 242, 255", XC),
    Field(73, "voltage_threshold_73_V", "Voltage threshold", 100, "V", MEDIUM,
          "Reference calls it a voltage threshold that 'varies significantly'. Ours reads 63.00 V everywhere, "
          "the same value as the DC over-voltage protection trip we found in the alarm history.",
          "Value coincidence with a known protection level; not toggled.", "6300", "ours + " + XC),
    Field(74, "param74", "", 1, "", UNKNOWN, "", "", "200"),
    Field(81, "grid_code_active", "Grid code active flag", 1, "flag", HIGH,
          "1 when a grid code (country standard) has been set with the dealer password in VEConfigure.",
          "Reference; 0 on every bare block, 1 on every GUI-authored ESS block. Part of the 'grid-code "
          "fingerprint' our failed grafts tried to stamp.", "0, 1", XC, lo=0, hi=1),
    Field(85, "param85", "", 1, "", UNKNOWN, "", "", "65535"),
    Field(87, "param87", "", 1, "", UNKNOWN, "", "", "829"),
    Field(88, "solar_wind_priority_V", "Solar & wind priority (sustain) voltage", 100, "V", MEDIUM,
          "Reference: sustain voltage for solar & wind priority.",
          "Reference; 52.00 V everywhere. The byte at +0x10a (which reads 20) is the high byte of this value "
          "(5200 = 0x1450), not a SoC threshold; the Virtual Switch SoC threshold is not located.", "5200", XC),
    Field(128, "lom_config_a", "LOM configuration A", 1, "", LOW,
          "Loss-of-mains configuration (grid code related). 0xffff on bare blocks; the GUI ESS install writes 1 / 0x0101.",
          "Reference name; observed transition.", "65535, 1, 257, 65281, 0", XC),
]

BY_ID: Dict[int, Field] = {f.id: f for f in FIELDS}
BY_NAME: Dict[str, Field] = {f.name: f for f in FIELDS}

# Fields the guarded writer will edit without an override.
EDITABLE = {f.name for f in FIELDS if f.confidence in (CONFIRMED, HIGH) and f.bits is None and f.id not in (0, 1)}

# Short aliases accepted everywhere a field name is (CLI, API).  Full names remain valid.
ALIASES = {
    "absorption": "absorption_V",
    "float": "float_V",
    "charge_current": "charge_current_A",
    "output_voltage": "inverter_output_V",
    "ac_limit": "ac1_input_limit_A",
    "ac2_limit": "ac2_input_limit_A",
    "low_shutdown": "dc_low_shutdown_V",
    "restart_offset": "dc_low_restart_offset_V",
    "vs_entry": "vs_ignore_ac_below_V",
    "vs_return": "vs_accept_battery_above_V",
    "capacity": "battery_capacity_Ah",
    "soc_bulk_end": "soc_at_bulk_end_pct",
    "grid_code": "grid_code_active",
}


def lookup(name_or_id) -> Field:
    """Resolve a field by full name, alias, or VE.Bus setting ID (int or digit string)."""
    if isinstance(name_or_id, Field):
        return name_or_id
    if isinstance(name_or_id, int):
        return BY_ID[name_or_id]
    key = str(name_or_id).strip()
    if key.isdigit():
        return BY_ID[int(key)]
    key = ALIASES.get(key, key)
    if key in BY_NAME:
        return BY_NAME[key]
    raise KeyError(f"unknown field {name_or_id!r}; run `mk2vsc fields` for the list (aliases: {', '.join(sorted(ALIASES))})")
