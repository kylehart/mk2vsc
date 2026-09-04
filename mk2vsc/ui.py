"""
Where each setting appears in VEConfigure 3: tab, group and field label.

This is the layer a manual change sheet needs ("Charger tab, Charge curve group, Absorption voltage") and
the layer a viewer uses to lay settings out the way the vendor tool does.  The placement table was
observed against VEConfigure 1.33 on a MultiPlus 24/1200/25-16 (firmware 2667558) and published by
talas9/rvsc-tools (MIT, ``core/settings.json`` ``ui_field_coverage`` and ``flags``); it is keyed here by
VEConfigure's own identifiers (``EPROM_*`` for numeric settings, ``EBIT_*`` for flag bits) so it never
depends on an index.  Note when comparing with that project's viewer: it numbers settings from 1, so its
"idx 7" is VE.Bus setting ID 6 here.

Certainty is theirs: ``confirmed`` = the identifier and the GUI field were tied by a differential export or
a unit match; ``probable`` = a name match not yet exercised.  Two GUI fields we could place from Victron's
MK2 protocol document where that table had none are marked ``source="mk2"``.

Kinds: ``number`` (a scaled u16), ``bool`` (one flag bit; ``inverted`` means the box is ticked when the bit
is clear), ``enum`` (option text in ``ENUMS``).  ``UI.unit`` is what the GUI DISPLAYS, not the stored
quantity: the Virtual Switch load fields show watts where the file holds 0.01 A (W = A x output voltage),
the repeated-absorption interval shows days where the file holds minutes, and the temperature-compensation
slope shows mV/degC where the file holds a /12800 fraction.  ``Field.unit`` and ``Field.description`` are
the stored quantity.

AC input numbering: VEConfigure's identifiers count AC inputs from 0 (``RemoteOverrulesAC0``, ``AC1``);
Victron's MK2 document and this project's field names count from 1 (``IMainsLimit`` = AC1 = setting 6,
``Remote overrules AC1`` = setting 1 bit 14, ``AC2`` = setting 0 bit 15).  So VEConfigure's AC0 is MK2's AC1.

Two sources besides talas9's table: ``source="mk2"`` for the two boxes placed from Victron's MK2 document
plus xcellsior's toggle-and-diff (the tab and group still come from talas9's layout); ``source="ours"`` for
the ignore-AC tab, matched to a VEConfigure screenshot of one of our systems (docs/FIELDS.md, the vs2
section).  talas9's unit was not in ignore-AC mode, so their table places settings 54/55/58/59 under
"VS options"; ours is the layout that tab shows when the mode is selected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

TABS: List[Tuple[str, str]] = [("general", "General"), ("grid", "Grid"), ("inverter", "Inverter"), ("charger", "Charger"),
                               ("virtual_switch", "Virtual switch"), ("assistants", "Assistants"), ("advanced", "Advanced")]
TAB_LABEL = dict(TABS)


@dataclass(frozen=True)
class UI:
    tab: str
    group: str
    label: str
    kind: str                 # number | bool | enum
    unit: str = ""
    certainty: str = "confirmed"   # confirmed | probable (talas9's vocabulary)
    inverted: bool = False    # bool kind: GUI box ticked when the bit is CLEAR
    note: str = ""
    source: str = "rvsc-tools"

    @property
    def path(self) -> str:
        return f"{TAB_LABEL.get(self.tab, self.tab)} › {self.group} › {self.label}"


def _n(tab, group, label, unit="", cert="confirmed", note="", source="rvsc-tools"):
    return UI(tab, group, label, "number", unit, cert, note=note, source=source)


def _e(tab, group, label, cert="confirmed", note=""):
    return UI(tab, group, label, "enum", "", cert, note=note)


def _b(tab, group, label, cert="confirmed", inverted=False, note="", source="rvsc-tools"):
    return UI(tab, group, label, "bool", "", cert, inverted, note, source)


# Numeric and enum settings, by VEConfigure identifier.
UI_BY_EPROM: Dict[str, UI] = {
    "EPROM_IMainsLimit": _n("general", "Shore limit", "AC input current limit", "A"),
    "EPROM_ChargePercentageResetValueForBatteryMonitor": _n("general", "Enable battery monitor", "State of charge when Bulk finished", "%"),
    "EPROM_BatteryCapacity": _n("general", "Enable battery monitor", "Battery capacity", "Ah"),
    "EPROM_ChargeEfficiency": _n("general", "Enable battery monitor", "Charge efficiency"),
    "EPROM_GridCode": _e("grid", "Grid code selection", "Country / grid code standard", "probable", "range 0-32 vs 23 listed options"),
    "EPROM_UMains2LowForFine": _n("grid", "Transfer switch", "AC low disconnect", "V", "probable"),
    "EPROM_UMains2High": _n("grid", "Transfer switch", "AC high disconnect", "V", "probable"),
    "EPROM_UInvSetpoint": _n("inverter", "General", "Inverter output voltage", "V"),
    "EPROM_UBat2Low": _n("inverter", "General", "DC input low shut-down", "V"),
    "EPROM_AssistBoostFactor": _n("inverter", "PowerAssist", "Assist current boost factor"),
    "EPROM_SOCStopInvert": _n("inverter", "shut-down on SOC", "SOC low shut-down", "%", "probable"),
    "EPROM_SOCStartInvert": _n("inverter", "shut-down on SOC", "SOC low restart", "%", "probable"),
    "EPROM_IInv2AES": _n("inverter", "enable AES", "Start AES when load lower than", "W", "probable"),
    "EPROM_ChargeCharacteristic": _e("charger", "Charge curve", "Charge curve"),
    "EPROM_UBatAbs": _n("charger", "Charge curve", "Absorption voltage", "V"),
    "EPROM_UBatFloat": _n("charger", "Charge curve", "Float voltage", "V"),
    "EPROM_IBatBulk": _n("charger", "Charge curve", "Charge current", "A"),
    "EPROM_EqualiseQuarters": _n("charger", "Absorption timing", "Repeated absorption time", "Hr", "probable", "numeric match, name conflict"),
    "EPROM_FloatDays": _n("charger", "Absorption timing", "Repeated absorption interval", "Days", "probable", "numeric match, name conflict"),
    "EPROM_AbsorptionHours": _n("charger", "Absorption timing", "Maximum absorption time", "Hr", note="labelled 'Absorption time' when Lithium batteries is ticked"),
    "EPROM_TempCompensationSlope": _n("charger", "Temperature / Lithium", "Temperature compensation", "mV/degC"),
    "EPROM_TBatStopCharge": _n("charger", "Temperature / Lithium", "Stop charger below", "degC"),
    "EPROM_vsUsage": _e("virtual_switch", "Usage", "Specify virtual switch usage"),
    "EPROM_vsonIInvHigh": _n("virtual_switch", "A: Set VS ON", "when load higher than", "W", "probable"),
    "EPROM_vstonIInvHigh": _n("virtual_switch", "A: Set VS ON", "when load higher than - duration", "s", "probable"),
    "EPROM_vsonUBatLow": _n("virtual_switch", "A: Set VS ON", "when Udc lower than", "V", "probable"),
    "EPROM_vstonUBatLow": _n("virtual_switch", "A: Set VS ON", "when Udc lower than - duration", "s", "probable"),
    "EPROM_vsonUBatHigh": _n("virtual_switch", "A: Set VS ON", "when Udc higher than", "V", "probable"),
    "EPROM_vstonUBatHigh": _n("virtual_switch", "A: Set VS ON", "when Udc higher than - duration", "s", "probable"),
    "EPROM_vstonNotCharging": _n("virtual_switch", "A: Set VS ON", "when not charging for", "s", "probable"),
    "EPROM_vstonFanOn": _n("virtual_switch", "A: Set VS ON", "when fan on for", "s", "probable"),
    "EPROM_vstonTemperatureAlarm": _n("virtual_switch", "A: Set VS ON", "Temperature pre-alarm (VS ON delay)", "s", "probable"),
    "EPROM_vstonLowBatteryAlarm": _n("virtual_switch", "A: Set VS ON", "Low-battery pre-alarm (VS ON delay)", "s", "probable"),
    "EPROM_vstonOverloadAlarm": _n("virtual_switch", "A: Set VS ON", "Overload pre-alarm (VS ON delay)", "s", "probable"),
    "EPROM_vstonUBatRippleAlarm": _n("virtual_switch", "A: Set VS ON", "Udc ripple pre-alarm (VS ON delay)", "s", "probable"),
    "EPROM_vsoffIInvLow": _n("virtual_switch", "B: Set VS OFF", "when load lower than", "W", "probable"),
    "EPROM_vstoffIInvLow": _n("virtual_switch", "B: Set VS OFF", "when load lower than - duration", "s", "probable"),
    "EPROM_vsoffUBatLow": _n("virtual_switch", "B: Set VS OFF", "when Udc lower than", "V", "probable"),
    "EPROM_vstoffUBatLow": _n("virtual_switch", "B: Set VS OFF", "when Udc lower than - duration", "s", "probable"),
    "EPROM_vsoffUBatHigh": _n("virtual_switch", "B: Set VS OFF", "when Udc higher than", "V", "probable"),
    "EPROM_vstoffUBatHigh": _n("virtual_switch", "B: Set VS OFF", "when Udc higher than - duration", "s", "probable"),
    "EPROM_vstoffCharging": _n("virtual_switch", "B: Set VS OFF", "when charging for", "s", "probable"),
    "EPROM_vstoffFanOff": _n("virtual_switch", "B: Set VS OFF", "when fan off for", "s", "probable"),
    "EPROM_vstoffChargeBulkFinished": _n("virtual_switch", "B: Set VS OFF", "when bulk charge finished for", "min"),
    "EPROM_vstoffNoVSOnCondition": _n("virtual_switch", "B: Set VS OFF", "when no VS ON condition for", "min"),
    "EPROM_vstoffNoACInput": _n("virtual_switch", "B: Set VS OFF", "when no AC input for", "s", "probable"),
    "EPROM_vstoffTemperatureAlarm": _n("virtual_switch", "B: Set VS OFF", "Temperature pre-alarm (VS OFF delay)", "s", "probable"),
    "EPROM_vstoffLowBatteryAlarm": _n("virtual_switch", "B: Set VS OFF", "Low-battery pre-alarm (VS OFF delay)", "s", "probable"),
    "EPROM_vstoffOverloadAlarm": _n("virtual_switch", "B: Set VS OFF", "Overload pre-alarm (VS OFF delay)", "s", "probable"),
    "EPROM_vstoffUBatRippleAlarm": _n("virtual_switch", "B: Set VS OFF", "Udc ripple pre-alarm (VS OFF delay)", "s", "probable"),
    "EPROM_vsMinimumOnTime": _n("virtual_switch", "VS options", "Do not switch off within N minutes from switch on", "min"),
    "EPROM_vsInverterPeriodTime": _n("virtual_switch", "VS options", "Make period time", "ms"),
    # Ignore AC input tab (vs2 settings), matched to a VEConfigure screenshot of one of our systems in that mode.
    "EPROM_vs2onILoadHigh": _n("virtual_switch", "Ignore AC input", "Do not ignore AC input when load higher than", "W", source="ours"),
    "EPROM_vs2tonILoadHigh": _n("virtual_switch", "Ignore AC input", "Do not ignore AC input when load higher than - for", "s", source="ours"),
    "EPROM_vs2onUBatLow": _n("virtual_switch", "Ignore AC input", "Do not ignore AC input when Udc lower than", "V", source="ours",
                             note="talas9's table (unit not in ignore-AC mode) shows this under VS options"),
    "EPROM_vs2tonUBatLow": _n("virtual_switch", "Ignore AC input", "Do not ignore AC input when Udc lower than - for", "s", source="ours"),
    "EPROM_vs2StartOnSOC": _n("virtual_switch", "Ignore AC input", "Do not ignore AC input when state of charge lower than", "%", source="ours"),
    "EPROM_vs2offILoadLow": _n("virtual_switch", "Ignore AC input", "When accepting AC due to load, ignore AC when load lower than", "W", source="ours"),
    "EPROM_vs2toffILoadLow": _n("virtual_switch", "Ignore AC input", "When accepting AC due to load, ignore AC when load lower than - for", "min", source="ours"),
    "EPROM_vs2offUBat": _n("virtual_switch", "Ignore AC input", "When accepting AC due to a battery condition, ignore AC when Udc higher than", "V", source="ours",
                           note="talas9's table shows this under VS options, unit s for the duration; the tab in ignore-AC mode shows minutes"),
    "EPROM_vs2toffUBat": _n("virtual_switch", "Ignore AC input", "When accepting AC due to a battery condition, ignore AC when Udc higher than - for", "min", source="ours"),
    "EPROM_UBatDontCharge": _n("advanced", "limit internal charger to prioritize other energy sources", "Sustain voltage", "V"),
}

# Flag bits, by (setting ID, bit).  Setting 0 = FlagsWord0, 1 = FlagsWord1, 60 = FlagsWord2, 82 = PermanentFlags0.
UI_BITS: Dict[Tuple[int, int], UI] = {
    (0, 2): UI("general", "System frequency", "System frequency", "enum", note="50Hz / 60Hz; set = 60 Hz"),
    (0, 3): _b("grid", "Transfer switch", "UPS function", inverted=True, source="mk2",
               note="Victron MK2 doc flag 3 = disable wave check; xcellsior FINDINGS 7.1 toggle-and-diff: set = UPS off; tab/group from talas9's layout"),
    (0, 4): _b("charger", "Charger enable", "Stop after excessive bulk", "probable", inverted=True),
    (0, 5): _b("inverter", "PowerAssist", "PowerAssist"),
    (0, 6): _b("charger", "Charger enable", "Enable charger", inverted=True),
    (0, 8): _b("inverter", "enable AES", "enable AES", "probable", inverted=True),
    (0, 11): _b("charger", "Storage / Equalization", "Storage mode"),
    (0, 13): _b("inverter", "General", "Ground relay", "probable", inverted=True),
    (0, 14): _b("charger", "Charger enable", "Weak AC input"),
    (0, 15): _b("general", "Shore limit", "Overruled by remote", "probable", note="VEConfigure AC1 = MK2 AC2; the box on a single-input unit drives one of this and setting 1 bit 14"),
    (1, 0): _b("virtual_switch", "A: Set VS ON", "set VS on when bulk protection is activated (charger stopped after 10Hr bulk)"),
    (1, 1): _b("virtual_switch", "A: Set VS ON", "Temperature pre-alarm (VS ON condition)"),
    (1, 2): _b("virtual_switch", "A: Set VS ON", "Low-battery pre-alarm (VS ON condition)"),
    (1, 3): _b("virtual_switch", "A: Set VS ON", "Overload pre-alarm (VS ON condition)"),
    (1, 4): _b("virtual_switch", "A: Set VS ON", "Udc ripple pre-alarm (VS ON condition)"),
    (1, 5): _b("virtual_switch", "B: Set VS OFF", "Temperature pre-alarm (VS OFF condition)"),
    (1, 6): _b("virtual_switch", "B: Set VS OFF", "Low-battery pre-alarm (VS OFF condition)"),
    (1, 7): _b("virtual_switch", "B: Set VS OFF", "Overload pre-alarm (VS OFF condition)"),
    (1, 8): _b("virtual_switch", "B: Set VS OFF", "Udc ripple pre-alarm (VS OFF condition)"),
    (1, 9): _b("virtual_switch", "A: Set VS ON", "set VS on when general system failure occurs"),
    (1, 10): _b("virtual_switch", "Usage", "Invert virtual switch usage"),
    (1, 11): _b("grid", "Transfer switch", "Accept wide input frequency range (45-65 Hz)"),
    (1, 12): _b("general", "Other", "Dynamic current limiter", source="mk2", note="Victron MK2 doc flag 28; xcellsior FINDINGS 7.2 bit 12 confirmed; VEConfigure identifier AdjustMainsLimitForMechanicalGeneratorDelay; tab/group from talas9's layout"),
    (1, 13): _b("charger", "Storage / Equalization", "Use equalization (tubular plate traction battery curve)"),
    (1, 14): _b("general", "Shore limit", "Overruled by remote", "probable", note="VEConfigure AC0 = MK2 AC1; twin of setting 0 bit 15"),
    (60, 2): _b("virtual_switch", "VS options", "Change inverter period time when virtual switch is on"),
    (60, 3): _b("virtual_switch", "VS options", "Change inverter period time on Udc"),
    (60, 4): _b("charger", "Charger enable", "Lithium batteries"),
    (60, 7): _b("charger", "Charger enable", "Configured for VE.Bus BMS"),
    (60, 8): _b("charger", "Charger enable", "Disable VSense (for diagnostic purposes)"),
    (60, 9): _b("advanced", "limit internal charger to prioritize other energy sources", "limit internal charger to prioritize other energy sources", "probable"),
    (82, 0): _b("inverter", "General", "Do not restart after short-circuit (VDE 2510-2 safety)", "probable"),
}

# VEConfigure identifiers for flag bits not in Victron's MK2 document (setting 60 = FlagsWord2, 82 = PermanentFlags0).
EBIT_NAMES: Dict[Tuple[int, int], str] = {
    (60, 0): "vs2offWhenAC1Available", (60, 1): "vs2Invert", (60, 2): "vsSetInverterPeriodTime",
    (60, 3): "vsInverterPeriodTimeOnUBat", (60, 4): "LithiumBattery", (60, 5): "AllowEnableFeedIn",
    (60, 6): "AllowIMainsHigherThanMaxRelayCurrent", (60, 7): "ConfiguredForVEBusBMS", (60, 8): "DisableVSense",
    (60, 9): "PreferRenewableEnergy", (82, 0): "ShortCircuitIsFatal",
}

# GUI fields the GUI computes from other settings (no setting of their own); formula in VE.Bus setting IDs.
DERIVED: List[Tuple[str, str, str, str]] = [
    ("grid", "Transfer switch", "AC low connect", "setting 44 + setting 45"),
    ("grid", "Transfer switch", "AC high connect", "setting 46 - setting 47"),
    ("inverter", "General", "DC input low restart", "setting 11 + setting 12"),
    ("inverter", "General", "DC input low pre-alarm", "setting 11 + setting 12 + setting 63"),
    ("inverter", "enable AES", "Stop AES when load ... higher than start level", "setting 50 + setting 51"),
    ("charger", "Temperature / Lithium", "Max absorption voltage (computed)", "no formula recorded"),
    ("virtual_switch", "VS options", "Frequency (computed)", "2500000 / setting 62"),
]

# GUI fields for which no setting or bit is known (talas9 'unmapped'); a census pair that toggles one of
# these would place it.
UNPLACED: List[Tuple[str, str, str]] = [
    ("general", "Enable battery monitor", "Enable battery monitor"),
    ("inverter", "shut-down on SOC", "shut-down on SOC"),
    ("inverter", "enable AES", "AES type"),
    ("charger", "Battery configuration", "Battery type (which of the 7 lead-acid or 2 lithium options)"),
    ("charger", "Temperature / Lithium", "Enable stop charger below"),
    ("assistants", "Assistants", "Loaded assistants (the assistant area, not a setting)"),
]

# Option text VEConfigure 1.33 shows for the enum settings (talas9; the grid-code list is that build's).
ENUMS: Dict[str, Dict[int, str]] = {
    "EPROM_ChargeCharacteristic": {1: "Fixed", 2: "Adaptive", 3: "Adaptive+BatterySafe"},
    "EPROM_vsUsage": {0: "Do not use VS", 1: "drive multifunctional (aux.) relay: VS on=open; VS off=close",
                      2: "ignore AC input: VS on=ignore; VS off=do not ignore", 3: "dedicated ignore AC input",
                      4: "dedicated generator control", 5: "drive aux. relay (VS on=open) + dedicated ignore AC input",
                      6: "ignore AC input (VS on=ignore) + dedicated generator control"},
    "EPROM_GridCode": {0: "None: (feeding energy from DC to grid not allowed)", 1: "Other: not compliant to any grid code standard",
                       2: "Australia A: AS/NZS 4777.2:2020+A1+A2 stand alone app. M", 3: "Australia B: AS/NZS 4777.2:2020+A1+A2 stand alone app. M",
                       4: "Australia C: AS/NZS 4777.2:2020+A1+A2 stand alone app. M", 5: "Australia: AS/NZS 4777.2:2015",
                       6: "Austria: TOR-Erzeuger A V1.1:2019-12", 7: "Belgium: C10/11 ed. 2.1:2019-09", 8: "Czech: Czech 2024 PPDS type A1/A2",
                       9: "Denmark: DK1, Western Denmark (Technical regulation 3.3.1)", 10: "Denmark: DK2, Eastern Denmark (Technical regulation 3.3.1)",
                       11: "Europe: EN50549-1:2019", 12: "France: VDE V 0126-1-1 VFR 2019", 13: "Germany: VDE-AR-N 4105:2018-11, external NS protection",
                       14: "Italy: CEI 0-21, 2014-09 and CEI 0-21;V1, 2014-12", 15: "New Zealand: AS/NZS 4777.2:2020+A1+A2 stand alone app. M",
                       16: "New Zealand: AS/NZS 4777.2:2015", 17: "Northern Ireland: G99/NI April 2019",
                       18: "Poland: Commission Regulation (EU) 2016/631; Wymogi ogolnego stosowania 18-12-2018; zasady wykorzysta certyfikatow v.1.2 (26/04/2021)",
                       19: "South Africa: NRS 097-2-1:2017", 20: "Spain: RD 1699/2011 | UNE 206007-1:2013IN", 21: "UK: G99/1 Amendment 8",
                       22: "UK: G98/1 Amendment 6 (16A max.)"},
}


def ui_for_setting(eprom: str) -> Optional[UI]:
    return UI_BY_EPROM.get(eprom)


def ui_for_bit(setting_id: int, bit: int) -> Optional[UI]:
    return UI_BITS.get((setting_id, bit))


def by_tab() -> Dict[str, Dict[str, List[Tuple[str, UI]]]]:
    """{tab: {group: [(key, UI), ...]}} in VEConfigure's tab order; key is the EPROM name or 'setting N bit B'."""
    out: Dict[str, Dict[str, List[Tuple[str, UI]]]] = {t: {} for t, _ in TABS}
    for k, u in UI_BY_EPROM.items():
        out[u.tab].setdefault(u.group, []).append((k, u))
    for (sid, bit), u in UI_BITS.items():
        out[u.tab].setdefault(u.group, []).append((f"setting {sid} bit {bit}", u))
    return out
