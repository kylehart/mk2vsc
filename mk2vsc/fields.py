"""
The settings table: what each u16 in the per-inverter settings array means, and how sure we are.

Every ``BareSettingData`` block carries a flat array of 192 little-endian u16 values starting at
block offset +0x59 (device form).  Entry *n* of that array is VE.Bus **setting ID n** as documented by
the community MK2/MK3 protocol work (github.com/xcellsior/ve-bus-programming, "Persistent Settings
IDs 0-255").  We established the mapping by noticing that the two fields we had confirmed
independently (absorption at +0x5d, float at +0x5f) sit exactly where setting IDs 2 and 3 land,
then checking the rest of the array against that reference across the whole corpus (170 blocks in 85 well-formed files):

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
    raw_offset: int = 0          # added to the raw value before scaling (the device schema's offset word)
    period: bool = False         # value = scale / raw (a period stored where a frequency is shown)

    @property
    def eprom(self) -> str:
        """VEConfigure's internal identifier for this setting (see EPROM_NAMES)."""
        return EPROM_NAMES[self.id] if self.id < len(EPROM_NAMES) else ""

    @property
    def ui(self):
        """Where this setting appears in VEConfigure (tab, group, label), or None; see mk2vsc.ui."""
        from .ui import ui_for_setting
        return ui_for_setting(self.eprom)

    @property
    def offset(self) -> int:
        """Device-form block offset (add 10 for upload-form blocks)."""
        return 0x59 + 2 * self.id

    def decode(self, raw: int):
        if self.period:
            return round(self.scale / raw, 4) if raw else 0
        v = raw + self.raw_offset
        return v / self.scale if self.scale != 1.0 else v

    def encode(self, value) -> int:
        if self.period:
            raw = int(round(self.scale / value))
        else:
            raw = int(round(value * self.scale)) - self.raw_offset
        if not 0 <= raw <= 0xFFFF:
            raise ValueError(f"{self.name}: {value} does not fit in u16 after scaling")
        return raw


# VEConfigure's own identifier for every setting index, from the Delphi RTTI symbol table of the
# VEConfig.exe binary as extracted and published by talas9/rvsc-tools (MIT, 2026; core/settings.json,
# validated against two independent tables in the binary with zero mismatches over 192 entries).
# Index n here is VE.Bus setting ID n.  A name is an identity, not a meaning: "NotDefinedYet" and
# "GridSettingsInt" say what the vendor calls the slot, nothing more.
EPROM_NAMES = ["EPROM_FlagsWord0", "EPROM_FlagsWord1", "EPROM_UBatAbs", "EPROM_UBatFloat", "EPROM_IBatBulk", "EPROM_UInvSetpoint", "EPROM_IMainsLimit", "EPROM_EqualiseQuarters", "EPROM_FloatDays", "EPROM_AbsorptionHours", "EPROM_ChargeCharacteristic", "EPROM_UBat2Low", "EPROM_UBat2LowMargin", "EPROM_NrOfSlaves", "EPROM_SpecialThreePhase", "EPROM_vsUsage", "EPROM_vsonIInvHigh", "EPROM_vsonUBatHigh", "EPROM_vsonUBatLow", "EPROM_vstonIInvHigh", "EPROM_vstonUBatHigh", "EPROM_vstonUBatLow", "EPROM_vstonNotCharging", "EPROM_vstonFanOn", "EPROM_vstonTemperatureAlarm", "EPROM_vstonLowBatteryAlarm", "EPROM_vstonOverloadAlarm", "EPROM_vstonUBatRippleAlarm", "EPROM_vsoffIInvLow", "EPROM_vsoffUBatHigh", "EPROM_vsoffUBatLow", "EPROM_vstoffIInvLow", "EPROM_vstoffUBatHigh", "EPROM_vstoffUBatLow", "EPROM_vstoffCharging", "EPROM_vstoffFanOff", "EPROM_vstoffChargeBulkFinished", "EPROM_vstoffNoVSOnCondition", "EPROM_vstoffNoACInput", "EPROM_vstoffTemperatureAlarm", "EPROM_vstoffLowBatteryAlarm", "EPROM_vstoffOverloadAlarm", "EPROM_vstoffUBatRippleAlarm", "EPROM_vsMinimumOnTime", "EPROM_UMains2LowForFine", "EPROM_UMains2LowForFineHysterese", "EPROM_UMains2High", "EPROM_UMains2HighHysterese", "EPROM_AssistBoostFactor", "EPROM_IMainsLimitAC1", "EPROM_IInv2AES", "EPROM_IInvAESHysterese", "EPROM_vs2onILoadHigh", "EPROM_vs2tonILoadHigh", "EPROM_vs2onUBatLow", "EPROM_vs2tonUBatLow", "EPROM_vs2offILoadLow", "EPROM_vs2toffILoadLow", "EPROM_vs2offUBat", "EPROM_vs2toffUBat", "EPROM_FlagsWord2", "EPROM_FlagsWord3", "EPROM_vsInverterPeriodTime", "EPROM_UBatLowPreAlarmOffset", "EPROM_BatteryCapacity", "EPROM_ChargePercentageResetValueForBatteryMonitor", "EPROM_fsUBatStart", "EPROM_fsUBatStartDelay", "EPROM_fsUBatStop", "EPROM_fsUBatStopDelay", "EPROM_vs2StartOnSOC", "EPROM_vllTempCompensation", "EPROM_ChargeEfficiency", "EPROM_IInvLimitDuringAssist", "EPROM_AbsToFloatSOCReset", "EPROM_IBatForStopAbsorption", "EPROM_InvertRedundancy", "EPROM_ExpectedPresenceFlags0", "EPROM_ExpectedPresenceFlags2", "EPROM_RelativePhaseInfo", "EPROM_MyShortID", "EPROM_GridCode", "EPROM_PermanentFlags0", "EPROM_SOCStopInvert", "EPROM_SOCStartInvert", "EPROM_InfoID0", "EPROM_TBatStopCharge", "EPROM_TempCompensationSlope", "EPROM_UBatDontCharge", "EPROM_CurrentSensorFactor", "EPROM_NotDefinedYet37", "EPROM_NotDefinedYet36", "EPROM_NotDefinedYet35", "EPROM_NotDefinedYet34", "EPROM_NotDefinedYet33", "EPROM_NotDefinedYet32", "EPROM_NotDefinedYet31", "EPROM_NotDefinedYet30", "EPROM_NotDefinedYet29", "EPROM_NotDefinedYet28", "EPROM_NotDefinedYet27", "EPROM_NotDefinedYet26", "EPROM_NotDefinedYet25", "EPROM_NotDefinedYet24", "EPROM_NotDefinedYet23", "EPROM_NotDefinedYet22", "EPROM_NotDefinedYet21", "EPROM_NotDefinedYet20", "EPROM_NotDefinedYet19", "EPROM_NotDefinedYet18", "EPROM_NotDefinedYet17", "EPROM_NotDefinedYet16", "EPROM_NotDefinedYet15", "EPROM_NotDefinedYet14", "EPROM_NotDefinedYet13", "EPROM_NotDefinedYet12", "EPROM_NotDefinedYet11", "EPROM_NotDefinedYet10", "EPROM_NotDefinedYet9", "EPROM_NotDefinedYet8", "EPROM_NotDefinedYet7", "EPROM_NotDefinedYet6", "EPROM_NotDefinedYet5", "EPROM_NotDefinedYet4", "EPROM_NotDefinedYet3", "EPROM_NotDefinedYet2", "EPROM_NotDefinedYet1", "EPROM_NotDefinedYet0", "EPROM_GridSettingsValidCheckerA", "EPROM_GridSettingsInt0", "EPROM_GridSettingsInt1", "EPROM_GridSettingsInt2", "EPROM_GridSettingsInt3", "EPROM_GridSettingsInt4", "EPROM_GridSettingsInt5", "EPROM_GridSettingsInt6", "EPROM_GridSettingsInt7", "EPROM_GridSettingsInt8", "EPROM_GridSettingsInt9", "EPROM_GridSettingsInt10", "EPROM_GridSettingsInt11", "EPROM_GridSettingsInt12", "EPROM_GridSettingsInt13", "EPROM_GridSettingsInt14", "EPROM_GridSettingsInt15", "EPROM_GridSettingsInt16", "EPROM_GridSettingsInt17", "EPROM_GridSettingsInt18", "EPROM_GridSettingsInt19", "EPROM_GridSettingsInt20", "EPROM_GridSettingsInt21", "EPROM_GridSettingsInt22", "EPROM_GridSettingsInt23", "EPROM_GridSettingsInt24", "EPROM_GridSettingsInt25", "EPROM_GridSettingsInt26", "EPROM_GridSettingsInt27", "EPROM_GridSettingsInt28", "EPROM_GridSettingsInt29", "EPROM_GridSettingsInt30", "EPROM_GridSettingsInt31", "EPROM_GridSettingsInt32", "EPROM_GridSettingsInt33", "EPROM_GridSettingsInt34", "EPROM_GridSettingsInt35", "EPROM_GridSettingsInt36", "EPROM_GridSettingsInt37", "EPROM_GridSettingsInt38", "EPROM_GridSettingsInt39", "EPROM_GridSettingsInt40", "EPROM_GridSettingsInt41", "EPROM_GridSettingsInt42", "EPROM_GridSettingsInt43", "EPROM_GridSettingsInt44", "EPROM_GridSettingsInt45", "EPROM_GridSettingsInt46", "EPROM_GridSettingsInt47", "EPROM_GridSettingsInt48", "EPROM_GridSettingsInt49", "EPROM_GridSettingsInt50", "EPROM_GridSettingsInt51", "EPROM_GridSettingsInt52", "EPROM_GridSettingsInt53", "EPROM_GridSettingsInt54", "EPROM_GridSettingsInt55", "EPROM_GridSettingsInt56", "EPROM_GridSettingsInt57", "EPROM_GridSettingsInt58", "EPROM_GridSettingsInt59", "EPROM_GridSettingsInt60", "EPROM_GeneralGridSettingsInt", "EPROM_GridSettingsValidCheckerB"]

XC = "xcellsior/ve-bus-programming FINDINGS.md"
RT = "VEConfigure identifier table (talas9/rvsc-tools, from VEConfig.exe RTTI)"
MK2 = "Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13"   # public PDF
SCH = "device schema (BareSettingInfo = CommandGetSettingInfo records)"

# Flag bits.  Victron numbers flags 0..63: Flags[0..15] are bits of setting 0, [16..31] of setting 1,
# [32..47] of setting 60, [48..63] of setting 61.  Bit meanings are the SET state.
FLAGS0_BITS = {0: "MultiPhaseSystem", 1: "MultiPhaseLeader", 2: "60 Hz", 3: "Disable wave check (UPS function off)",
               4: "DoNotStopAfter10HrBulk", 5: "AssistEnabled (PowerAssist)", 6: "DisableCharge",
               7: "inverse of bit 3", 8: "DisableAES", 9: "not promoted", 10: "not promoted",
               11: "EnableReducedFloat (storage mode, per the Victron doc; xcellsior reads the bit as adaptive charge. On every GUI- or device-authored block here bit 11 is set exactly when charge_characteristic = 3, so the corpus cannot separate the two readings)", 12: "not promoted", 13: "Disable ground relay", 14: "Weak AC input",
               15: "Remote overrules AC2"}
FLAGS1_BITS = {0: "vsonBulkProtection", 1: "vsonTemperaturePreAlarm", 2: "vsonLowBatteryPreAlarm",
               3: "vsonOverloadPreAlarm", 4: "vsonUBatRipplePreAlarm", 5: "vsoffTemperaturePreAlarm",
               6: "vsoffLowBatteryPreAlarm", 7: "vsoffOverloadPreAlarm", 8: "vsoffUBatRipplePreAlarm",
               9: "vsonWhenGeneralFailure", 10: "vsInvert", 11: "Accept wide input frequency",
               12: "Dynamic current limiter", 13: "Tubular plate traction battery curve",
               14: "Remote overrules AC1", 15: "Low power shutdown in AES"}
FLAGS2_BITS = {0: "vs2offWhenAC1Available", 1: "vs2Invert", 2: "vsSetInverterPeriodTime", 3: "vsInverterPeriodTimeOnUBat",
               4: "LithiumBattery", 5: "AllowEnableFeedIn", 6: "AllowIMainsHigherThanMaxRelayCurrent",
               7: "ConfiguredForVEBusBMS", 8: "DisableVSense", 9: "PreferRenewableEnergy"}   # 3-9 from VEConfigure identifiers (talas9/rvsc-tools)


def _f(id, name, label, scale=1, unit="", conf=UNKNOWN, desc="", ev="", obs="", src="", **kw):
    return Field(id, name, label, scale, unit, conf, desc, ev, obs, src, **kw)


def _vs_level(id, name, victron, what, obs, scale=100, unit="V", conf=HIGH):
    return _f(id, name, f"{victron}", scale, unit, conf,
              f"Virtual Switch (relay mode, settings 15 to 43): {what}.", f"{MK2}: {victron}; {SCH}.", obs, "mk2")


def _vs_time(id, name, victron, what, obs, unit="s"):
    long = "minutes" if unit == "min" else "seconds (1/60 minute units)"
    return _f(id, name, f"{victron}", 1, unit, HIGH,
              f"Virtual Switch (relay mode): {what}, {long}, raw - 1.", f"{MK2}: {victron} (Time); {SCH}: offset -1.",
              obs, "mk2", raw_offset=-1)


FIELDS: List[Field] = [
    _f(0, "flags0", "Flags0", 1, "bitmask", HIGH,
       "Bit register of on/off options; see the bit table. The schema's max (0x6ffc) is the mask of settable bits.",
       f"{MK2} 7.3.13.3 flag table (bits 0-15).", "0x81f4 (most), 0x89f4, 0x89b4, 0x817c, 0x81b4", "mk2", bits=FLAGS0_BITS),
    _f(1, "flags1", "Flags1", 1, "bitmask", HIGH,
       "Bit register: Virtual Switch relay-mode alarm conditions (bits 0-10) and general options (bits 11-15).",
       f"{MK2} flag table (bits 16-31).", "0x4dfe on every device-form block", "mk2", bits=FLAGS1_BITS),
    _f(2, "absorption_V", "UBatAbsorption", 100, "V", CONFIRMED,
       "Charger absorption voltage. With a CAN-bus BMS and DVCC active the BMS charge-voltage limit overrides it.",
       f"Written by us on four systems via Remote VEConfigure and read back; {MK2}: UBatAbsorption; schema 48.00 to 64.00 V.",
       "5600, 5650, 5680, 5760 (also 4800 on a mis-commissioned unit)", "ours + mk2", lo=40.0, hi=66.0),
    _f(3, "float_V", "UBatFloat", 100, "V", CONFIRMED, "Charger float voltage.",
       f"Written by us (54.0 -> 54.1 V on two inverters, uploaded, read back); {MK2}: UBatFloat.",
       "5400, 5410, 5420, 5520", "ours + mk2", lo=40.0, hi=66.0),
    _f(4, "charge_current_A", "IBatBulk", 1, "A", HIGH, "Maximum battery charge current.",
       f"{MK2}: IBatBulk; schema 0 to 35 A on this model.", "35", "mk2", lo=0, hi=300),
    _f(5, "inverter_output_V", "UInvSetpoint", 1, "V", HIGH, "Nominal AC output voltage.",
       f"{MK2}: UInvSetpoint; schema 95 to 128 V; 120 on every block.", "120", "mk2", lo=100, hi=250),
    _f(6, "ac1_input_limit_A", "IMainsLimit (AC1)", 10, "A", HIGH,
       "AC input 1 current limit (the persistent value; the GX can override at runtime).",
       f"{MK2}: IMainsLimit (AC1), 0.1 A units; schema 1.0 to 100.0 A.", "500", "mk2", lo=0, hi=200),
    _f(7, "repeated_absorption_time_min", "Repeated Absorption Time", 1, "min", HIGH,
       "Duration of the periodic re-absorption, in minutes (raw x 15).", f"{MK2}; schema scale 15, 1 to 96 (15 min to 24 h).",
       "2, 4", "mk2"),
    _f(8, "repeated_absorption_interval_min", "Repeated Absorption Interval", 1, "min", HIGH,
       "Interval between re-absorptions, in minutes (raw x 360, i.e. 6-hour steps; VEConfigure shows days = minutes / 1440).", f"{MK2}; schema scale 360, 1 to 180.",
       "4, 28", "mk2"),
    _f(9, "max_absorption_time_min", "(Maximum) Absorption duration", 1, "min", HIGH,
       "Maximum absorption time, in minutes (raw x 60).", f"{MK2}; schema scale 60, 1 to 24 h.", "1, 8", "mk2"),
    _f(10, "charge_characteristic", "Charge characteristic", 1, "enum", HIGH,
       "Charge curve: 1 = Fixed, 2 = Adaptive, 3 = Adaptive + BatterySafe (VEConfigure's option text). Our lithium systems read 1.",
       f"{MK2}; option text from VEConfigure via {RT}.", "1, 3", "mk2 + rtti"),
    _f(11, "dc_low_shutdown_V", "UBatLowLimit for Inverter", 100, "V", HIGH,
       "Battery voltage at which the inverter shuts down.", f"{MK2}; schema 37.20 to 52.00 V.", "4850, 3720, 4800", "mk2", lo=36.0, hi=56.0),
    _f(12, "dc_low_restart_offset_V", "UBatLow hysteresis for Inverter", 100, "V", HIGH,
       "Hysteresis above the low limit before the inverter restarts.", f"{MK2}; schema 1.00 to 24.00 V.", "200, 640", "mk2", lo=0.0, hi=12.0),
    _f(13, "number_of_slaves", "Number of slaves connected", 1, "", HIGH, "Number of slave units in a parallel set.",
       f"{MK2}; schema unused on this model; 0.", "0", "mk2"),
    _f(14, "three_phase_setting", "Special three phase setting", 1, "enum", HIGH,
       "0 = 3 phase, 1 = split phase 180, 2 = 2-leg 3-phase 120.", f"{MK2}; schema unused on this model; 0.", "0", "mk2"),
    _f(15, "vs_usage", "vsUsage", 1, "enum", HIGH,
       "Virtual Switch usage: 0 do not use, 1 drive the aux relay, 2 ignore AC input, 3 dedicated ignore AC input, "
       "4 dedicated generator control, 5 relay + dedicated ignore AC, 6 ignore AC input (VS off = ignore). Our systems read 3.",
       f"{MK2} (0 to 2); options 3 to 6 from VEConfigure's UI via {RT}.", "0, 1, 3", "mk2 + rtti"),
    # Virtual Switch, relay mode (15 to 43): documented names; values on our systems are defaults.
    _vs_level(16, "vs_on_inverter_current_high_A", "vsonIInvHigh", "on when inverter current higher than (0.01 A; VEConfigure shows watts = A x output voltage)", "2125", scale=100, unit="A"),
    _vs_level(17, "vs_on_ubat_high_V", "vsonUBatHigh", "on when battery voltage higher than (relay mode; 6400 is the schema default and is unchanged on every block, as is 4700 for 18; xcellsior reads 17 as a 64 V over-voltage threshold)", "6400"),
    _vs_level(18, "vs_on_ubat_low_V", "vsonUBatLow", "on when battery voltage lower than", "4700"),
    _vs_time(19, "vs_ton_inverter_current_high", "vstonIInvHigh", "time for vsonIInvHigh", "0"),
    _vs_time(20, "vs_ton_ubat_high", "vstonUBatHigh", "time for vsonUBatHigh", "0"),
    _vs_time(21, "vs_ton_ubat_low", "vstonUBatLow", "time for vsonUBatLow", "0"),
    _vs_time(22, "vs_ton_not_charging", "vstonNotCharging", "on after not charging for", "0"),
    _vs_time(23, "vs_ton_fan_on", "vstonFanOn", "on after fan on for", "0"),
    _vs_time(24, "vs_ton_temperature_alarm", "vstonTemperatureAlarm", "on after temperature alarm for", "2"),
    _vs_time(25, "vs_ton_low_battery_alarm", "vstonLowBatteryAlarm", "on after low battery alarm for", "2"),
    _vs_time(26, "vs_ton_overload_alarm", "vstonOverloadAlarm", "on after overload alarm for", "2"),
    _vs_time(27, "vs_ton_ubat_ripple_alarm", "vstonUBatRippleAlarm", "on after ripple alarm for", "2"),
    _vs_level(28, "vs_off_inverter_current_low_A", "vsoffIInvLow", "off when inverter current lower than (0.01 A; VEConfigure shows watts = A x output voltage)", "531", scale=100, unit="A"),
    _vs_level(29, "vs_off_ubat_high_V", "vsoffUBatHigh", "off when battery voltage higher than", "6400"),
    _vs_level(30, "vs_off_ubat_low_V", "vsoffUBatLow", "off when battery voltage lower than", "4700"),
    _vs_time(31, "vs_toff_inverter_current_low", "vstoffIInvLow", "time for vsoffIInvLow", "0"),
    _vs_time(32, "vs_toff_ubat_high", "vstoffUBatHigh", "time for vsoffUBatHigh", "0"),
    _vs_time(33, "vs_toff_ubat_low", "vstoffUBatLow", "time for vsoffUBatLow", "0"),
    _vs_time(34, "vs_toff_charging", "vstoffCharging", "off after charging for", "0"),
    _vs_time(35, "vs_toff_fan_off", "vstoffFanOff", "off after fan off for", "0"),
    _vs_time(36, "vs_toff_bulk_finished", "vstoffChargeBulkFinished", "off after bulk finished for", "0", unit="min"),
    _vs_time(37, "vs_toff_no_on_condition", "vstoffNoVSOnCondition", "off after no on-condition for", "1", unit="min"),
    _vs_time(38, "vs_toff_no_ac_input", "vstoffNoACInput", "off after no AC input for", "0"),
    _vs_time(39, "vs_toff_temperature_alarm", "vstoffTemperatureAlarm", "off after temperature alarm cleared for", "0"),
    _vs_time(40, "vs_toff_low_battery_alarm", "vstoffLowBatteryAlarm", "off after low battery alarm cleared for", "0"),
    _vs_time(41, "vs_toff_overload_alarm", "vstoffOverloadAlarm", "off after overload alarm cleared for", "0"),
    _vs_time(42, "vs_toff_ubat_ripple_alarm", "vstoffUBatRippleAlarm", "off after ripple alarm cleared for", "0"),
    _f(43, "vs_minimum_on_time", "vsMinimumOnTime", 1, "min", HIGH, "Virtual Switch (relay mode): minimum on time, minutes; 0 = no minimum.",
       f"{MK2}; schema 0 to 1200, offset 0.", "0", "mk2"),
    _f(44, "mains_lowest_acceptable_V", "Lowest acceptable UMains", 1, "V", HIGH, "Lowest AC input voltage accepted.",
       f"{MK2}; 90 V here.", "90", "mk2"),
    _f(45, "mains_low_hysteresis_V", "Hysteresis for parameter 44", 1, "V", HIGH, "Hysteresis on the low mains limit.", MK2, "7", "mk2"),
    _f(46, "mains_highest_acceptable_V", "Highest acceptable UMains", 1, "V", HIGH,
       "Highest AC input voltage accepted; stored minus 100 (raw 40 = 140 V, schema 120 to 140 V).",
       f"{MK2}; {SCH}: offset +100.", "40", "mk2", raw_offset=100),
    _f(47, "mains_high_hysteresis_V", "Hysteresis for parameter 46", 1, "V", HIGH, "Hysteresis on the high mains limit.", MK2, "5", "mk2"),
    _f(48, "assist_current_boost_factor", "Assist current boost factor", 16, "", HIGH,
       "PowerAssist boost factor: raw / 16 (32 = 2.0; schema 0.25 to 3.5).", f"{MK2}; {SCH}: scale -16.", "32", "mk2"),
    _f(49, "ac2_input_limit_A", "IMainsLimit (AC2)", 10, "A", HIGH, "AC input 2 current limit (Quattro).",
       f"{MK2}; schema unused on this MultiPlus.", "0", "mk2"),
    _f(50, "aes_low_current_limit_A", "Low current limit for switching to AES", 100, "A", HIGH,
       "AC load current below which the inverter enters AES (search/low-power mode). VEConfigure shows watts; the conversion from the stored amps is not established here.", f"{MK2}; schema /100, 0.21 to 2.55 A, default 0.60.", "60", "mk2"),
    _f(51, "aes_current_hysteresis_A", "Hysteresis on AES current limit", 100, "A", HIGH,
       "AES leaves when current exceeds settings 50 + 51.", f"{MK2}; schema /100, default 0.40.", "40", "mk2"),
    # Virtual Switch, ignore-AC-input mode (vs2, settings 52 to 59)
    _f(52, "vs_dont_ignore_load_above_A", "vs2onILoadHigh", 100, "A", HIGH,
       "Ignore-AC mode: do not ignore the AC input when the AC load current is higher than this (VEConfigure shows watts: W = A x output voltage).",
       f"{MK2}: vs2onILoadHigh (Level); the tab's 1000 W on a 120 V inverter = 8.33 A = raw 833 in the same-period download.",
       "833, 1250, 1750, 2125", "mk2 + ours", lo=0, hi=100),
    _f(53, "vs_load_above_for_s", "vs2onILoadHigh (time)", 1, "s", HIGH, "Duration for the load-high condition, seconds (raw - 1).",
       f"{MK2}: vs2onILoadHigh Time; {SCH}: offset -1, 1/60 min units.", "0, 4, 6", "mk2", lo=0, hi=254, raw_offset=-1),
    _f(54, "vs_ignore_ac_below_V", "vs2onUBatLow", 100, "V", CONFIRMED,
       "Ignore-AC mode: do not ignore the AC input when the battery voltage is lower than this.",
       f"Matched to the VEConfigure tab (51.40 V), written by us; {MK2}: vs2onUBatLow.", "5100, 4700", "ours + mk2"),
    _f(55, "vs_udc_below_for_s", "vs2onUBatLow (time)", 1, "s", HIGH, "Duration for the Udc-low condition, seconds (raw - 1).",
       f"{MK2}: vs2onUBatLow Time; schema offset -1; raw 21 = 20 s, the value on the tab.", "0, 6, 21", "mk2", lo=0, hi=254, raw_offset=-1),
    _f(56, "vs_ignore_load_below_A", "vs2offILoadLow", 100, "A", HIGH,
       "Ignore-AC mode: ignore the AC input again when the AC load current is lower than this.",
       f"{MK2}: vs2offILoadLow; 750 W on the tab = 6.25 A = raw 625.", "531, 625, 833, 1500", "mk2 + ours", lo=0, hi=100),
    _f(57, "vs_load_below_for_min", "vs2offILoadLow (time)", 1, "min", HIGH, "Duration for the load-low condition, minutes (raw - 1).",
       f"{MK2}; schema offset -1; raw 2 = 1 min.", "0, 2", "mk2", lo=0, hi=254, raw_offset=-1),
    _f(58, "vs_accept_battery_above_V", "vs2offUBatHigh", 100, "V", CONFIRMED,
       "Ignore-AC mode: ignore the AC input again when the battery voltage is higher than this. Victron: if the high byte "
       "is 0, low byte 0 means 'when bulk finished' and 1 'when absorption finished' instead of a voltage. A value the "
       "battery cannot reach (64.00 V on a 48 V LFP) makes grid pass-through permanent.",
       f"Tab match (53.00 V), written by us; {MK2}: vs2offUBatHigh.", "5250, 5300, 5450, 6400", "ours + mk2"),
    _f(59, "vs_udc_above_for_min", "vs2offUBatHigh (time)", 1, "min", HIGH, "Duration for the Udc-high condition, minutes (raw - 1).",
       f"{MK2}; schema offset -1; raw 2 = 1 min.", "0, 2", "mk2", lo=0, hi=254, raw_offset=-1),
    _f(60, "flags2", "Flags2", 1, "bitmask", HIGH, "Bit register; bits 0 to 2 named by Victron (MK2 flags 32 to 34), bits 3 to 9 by VEConfigure identifiers (talas9/rvsc-tools); see the bit table. Schema max 1022.",
       f"{MK2} flags 32-34 (bits 0 to 2); {RT} (bits 3 to 9).", "0, 16, 48", "mk2 + rtti", bits=FLAGS2_BITS),
    _f(61, "flags3", "Flags3", 1, "bitmask", HIGH, "Bit register; no documented bits.", f"{MK2}: Flags3.", "0", "mk2", bits={}),
    _f(62, "output_frequency_Hz", "vsInverterPeriodTime", 2_500_000, "Hz", HIGH,
       "Inverter output frequency, stored as the period in 1/2500 ms: 41667 = 16.667 ms = 60 Hz (Hz = 2500000 / raw). Applied when Flags2 bit 2 (vsSetInverterPeriodTime) is set.",
       f"{MK2}: vsInverterPeriodTime; schema range 45 to 65 Hz.", "41667, 41666", "mk2", lo=45, hi=65, period=True),
    _f(63, "ubat_low_prealarm_offset_V", "UBat low pre-alarm offset", 100, "V", HIGH,
       "Signed offset added to (UBatLowLimit + hysteresis) to set the low-battery pre-alarm level; stored with 0x8000 added.",
       f"{MK2}: 'this offset can be positive or negative; 0x8000 is added'.", "32668 (-1.00 V), 32768 (0)", "mk2", raw_offset=-32768),
    _f(64, "battery_capacity_Ah", "Battery capacity", 1, "Ah", HIGH, "Capacity for the built-in battery monitor; 0 disables it.",
       f"{MK2}; 200 / 300 Ah match the installed modules.", "200, 300, 0", "mk2"),
    _f(65, "soc_at_bulk_end_pct", "SoC when bulk finished", 2, "%", HIGH,
       "State of charge the built-in monitor assumes when the charge state changes from bulk to absorption.",
       f"{MK2}; schema /2, 30 to 100 %.", "170, 190, 196", "mk2"),
    # Beyond 65 Victron's public document stops.  Identifiers come from VEConfigure's own symbol table (RT);
    # scales and ranges from the device schema; meanings inferred from the identifier and marked as such.
    _f(66, "fs_ubat_start_V", "fsUBatStart", 100, "V", MEDIUM, "Battery voltage at which the 'fs' function starts (57.72 V here; the prefix is not expanded in any public source).", f"{RT}; {SCH}: 0 to 70.00 V.", "5772", "rtti + schema"),
    _f(67, "fs_ubat_start_delay_s", "fsUBatStartDelay", 1, "s", MEDIUM, "Delay for fsUBatStart, seconds (raw - 1).", f"{RT}; {SCH}: 1/60 min, offset -1.", "3", "rtti + schema", raw_offset=-1),
    _f(68, "fs_ubat_stop_V", "fsUBatStop", 100, "V", MEDIUM, "Battery voltage at which the 'fs' function stops (54.00 V here).", f"{RT}; {SCH}.", "5400", "rtti + schema"),
    _f(69, "fs_ubat_stop_delay_s", "fsUBatStopDelay", 1, "s", MEDIUM, "Delay for fsUBatStop, seconds (raw - 1).", f"{RT}; {SCH}.", "3", "rtti + schema", raw_offset=-1),
    _f(70, "vs_dont_ignore_soc_below_pct", "vs2StartOnSOC", 2, "%", HIGH,
       "Ignore-AC mode battery condition on state of charge: do not ignore the AC input when SoC is below this.",
       f"{RT}: vs2StartOnSOC; {SCH}: /2, 0 to 100 %. 25 % on every configured block, the fleet-wide setpoint the installer's note describes.",
       "50, 0", "rtti + schema + installer note", lo=0, hi=100),
    _f(71, "vll_temp_compensation", "vllTempCompensation", 1, "", LOW, "Signed value centred on 32768 (schema +/-800); 0 here. Meaning of 'vll' unknown.", f"{RT}; {SCH}.", "32768", "rtti + schema", raw_offset=-32768),
    _f(72, "charge_efficiency", "ChargeEfficiency", 256, "", HIGH, "Battery charge efficiency as a fraction (raw + 1)/256: 255 = 1.000, 242 = 0.949.", f"{RT}; {SCH}: scale -256, offset +1.", "250, 242, 255", "rtti + schema", raw_offset=1),
    _f(73, "inverter_current_limit_during_assist_A", "IInvLimitDuringAssist", 100, "A", HIGH, "Inverter current limit while PowerAssist is active: 63.00 A on every block.", f"{RT}; {SCH}: /100, 8.03 to 106.00.", "6300", "rtti + schema"),
    _f(74, "abs_to_float_soc_reset_pct", "AbsToFloatSOCReset", 2, "%", HIGH, "SoC the battery monitor is set to when the charger goes from absorption to float (100 % here; schema 30 to 100 %, default 85 %).", f"{RT}; {SCH}.", "200", "rtti + schema"),
    _f(75, "ibat_for_stop_absorption", "IBatForStopAbsorption", 1, "", LOW, "Battery current at which absorption stops (schema unused on this model).", f"{RT}.", "0", "rtti"),
    _f(76, "invert_redundancy", "InvertRedundancy", 1, "", LOW, "", f"{RT}; schema unused here.", "0", "rtti"),
    _f(77, "expected_presence_flags0", "ExpectedPresenceFlags0", 1, "bitmask", LOW, "", f"{RT}; schema unused here.", "0", "rtti", bits={}),
    _f(78, "expected_presence_flags2", "ExpectedPresenceFlags2", 1, "bitmask", LOW, "", f"{RT}; schema unused here.", "0", "rtti", bits={}),
    _f(79, "relative_phase_info", "RelativePhaseInfo", 1, "", LOW, "", f"{RT}; schema unused here.", "0", "rtti"),
    _f(80, "my_short_id", "MyShortID", 1, "", LOW, "", f"{RT}; schema unused here.", "0", "rtti"),
    _f(81, "grid_code", "GridCode", 1, "enum", HIGH,
       "Country / grid code standard: 0 = none; a non-zero index selects a grid code, set with the dealer password in VEConfigure. Schema 0 to 32.",
       f"{RT}: GridCode; 0 on every bare block, 1 on every GUI-authored ESS block.", "0, 1", "rtti + ours"),
    _f(82, "permanent_flags0", "PermanentFlags0", 1, "bitmask", LOW, "Permanent flags; bit 0 = ShortCircuitIsFatal (VEConfigure identifier). 0 here.", f"{RT}; schema unused here.", "0", "rtti", bits={0: "ShortCircuitIsFatal"}),
    _f(83, "soc_stop_invert_pct", "SOCStopInvert", 2, "%", MEDIUM, "SoC at which inverting stops ('shut-down on SOC'); schema unused on this model.", f"{RT}.", "0", "rtti"),
    _f(84, "soc_start_invert_pct", "SOCStartInvert", 2, "%", MEDIUM, "SoC at which inverting restarts; schema unused on this model.", f"{RT}.", "0", "rtti"),
    _f(85, "info_id0", "InfoID0", 1, "", LOW, "Schema: scale 50, offset 1069, default 3000, min 2400; 65535 here.", f"{RT}; {SCH}.", "65535", "rtti + schema"),
    _f(86, "tbat_stop_charge", "TBatStopCharge", 1, "", LOW, "Battery temperature at which charging stops; schema unused here.", f"{RT}.", "0", "rtti"),
    _f(87, "temp_compensation_slope", "TempCompensationSlope", 12800, "", LOW, "Charge-voltage temperature compensation slope (schema /12800, 0 to 1536, default 829 = 0.0648). VEConfigure shows mV/degC; the relation between the stored fraction and that display is not established.", f"{RT}; {SCH}.", "829", "rtti + schema"),
    _f(88, "ubat_dont_charge_V", "UBatDontCharge", 100, "V", HIGH, "Battery voltage below which the charger does not charge (52.00 V here; VEConfigure shows it as the sustain voltage).", f"{RT}; {SCH}: 48.00 to 64.00 V; {XC} calls it the solar & wind priority voltage.", "5200", "rtti + schema"),
    _f(89, "current_sensor_factor", "CurrentSensorFactor", 1, "", LOW, "", f"{RT}; schema unused here.", "0", "rtti"),
    _f(128, "grid_settings_valid_checker_a", "GridSettingsValidCheckerA", 1, "", MEDIUM,
       "Grid-code word A. 0xffff on blocks that never had a grid code. On every GUI-authored ESS download it equals setting 191 on "
       "the same inverter: low byte 1, high byte 0 to 3 (0x0001, 0x0101, 0x0201, 0x0301); the two inverters of a pair may differ "
       "(System C: 1 and 0x0101; System D: 0x0201 and 0x0301) or match (System B: 1 and 1; System A: 0x0101 and 0x0101). On a single bench unit xcellsior reads 1 with LOM type B and 257 with no LOM detection. "
       "0 or 0xffff on bare blocks after a grid code was removed. Byte-grafted files (never started) show 128 != 191.",
       f"{RT}; xcellsior FINDINGS 7.4; corpus.", "65535, 1, 257, 65281, 0", "rtti + xcellsior + ours"),
    _f(190, "general_grid_settings_int", "GeneralGridSettingsInt", 1, "", MEDIUM,
       "Grid-code word B, firmware-managed (wire writes are silently dropped per xcellsior). 0xffff on blocks that never had a grid "
       "code; 0xfff5 on every grid-coded block here, including the 0x0101 ones (the bench reads 0xfff6 for those); 0xfff5 or 0xffff "
       "on bare blocks after a grid code was removed.",
       f"{RT}; xcellsior FINDINGS 7.4/9 (0xfff5 / 0xfff6); corpus.", "65535, 65525", "rtti + xcellsior + ours"),
    _f(191, "grid_settings_valid_checker_b", "GridSettingsValidCheckerB", 1, "", MEDIUM,
       "Grid-code word C. 0xffff on blocks that never had a grid code; equals setting 128 on every GUI-authored ESS download (low byte 1, "
       "high byte 0 to 3, per inverter; see 128); 0 or 0xff00 on bare blocks after a grid code was removed.",
       f"{RT}; xcellsior FINDINGS 7.4 (1 / 257 / residual 512); corpus.", "65535, 1, 257, 0, 65280", "rtti + xcellsior + ours"),
]
FIELDS += [_f(n, f"not_defined_yet_{127 - n}", EPROM_NAMES[n], 1, "", UNKNOWN, "Reserved slot; 0 on every block.", RT, "0", "rtti") for n in range(90, 128)]
FIELDS += [_f(n, f"grid_settings_int{n - 129}", EPROM_NAMES[n], 1, "", UNKNOWN, "Grid-code settings block, written by the grid-code step in VEConfigure; 0xffff on bare blocks.", RT, "65535", "rtti") for n in range(129, 190)]
FIELDS.sort(key=lambda f: f.id)

BY_ID: Dict[int, Field] = {f.id: f for f in FIELDS}
BY_NAME: Dict[str, Field] = {f.name: f for f in FIELDS}

# Fields the guarded writer will edit without an override.
EDITABLE = {f.name for f in FIELDS if f.confidence in (CONFIRMED, HIGH) and f.bits is None}

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
    "vs_load_high": "vs_dont_ignore_load_above_A",
    "vs_load_low": "vs_ignore_load_below_A",
    "vs_soc": "vs_dont_ignore_soc_below_pct",
    "frequency": "output_frequency_Hz",
    "capacity": "battery_capacity_Ah",
    "soc_bulk_end": "soc_at_bulk_end_pct",
    "grid_code": "grid_code",
    "repeated_absorption_time": "repeated_absorption_time_min",
    "repeated_absorption_interval": "repeated_absorption_interval_min",
    "max_absorption_time": "max_absorption_time_min",
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
