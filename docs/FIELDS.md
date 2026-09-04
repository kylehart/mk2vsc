# The settings table

Each `BareSettingData` block carries a flat array of 190 little-endian u16 values starting at block
offset +0x59 (device form; +0x63 in the GUI's upload form, see `docs/FORMAT.md` §4). Entry *n* of that
array is **VE.Bus setting ID n** as documented by the community MK2/MK3 protocol reference,
[xcellsior/ve-bus-programming](https://github.com/xcellsior/ve-bus-programming) (`FINDINGS.md`,
"Persistent Settings IDs 0-255"). The IDs, scales and flag bits below marked `xcellsior` come from that
reference; the evidence that the file's array *is* that table is ours.

Names for settings 0 to 65 and the flag bits are Victron's own, from the public document "Interfacing
with VE.Bus products, MK2 Protocol 3.14" (section 7.3.13, Setting and Variable IDs; Victron Energy,
victronenergy.com/upload/documents). That document also defines `CommandGetSettingInfo`, whose
scale/offset/default/min/max reply is exactly the per-setting record stored in `BareSettingInfo`
(display value = scale x (raw + offset), scale = Sc if Sc > 0 else 1/(-Sc)). Settings above 65 are not in
that document; their names here are ours, and their confidence says so.

The table is generated from `mk2vsc/fields.py` by `tools/gen_fields_table.py`. Regenerate it after any
change to the code; the code is the source of truth.

## How the mapping was found

Two values were pinned early, independently of any reference: absorption voltage at +0x5d and float
voltage at +0x5f, confirmed by editing them, uploading through VRM, and reading them back on live
systems. When we later compared the array against the reference's setting IDs, those two sit exactly
where IDs 2 and 3 would if ID 0 started at +0x59. Reading the rest of the array under that assumption
across all 162 blocks of the well-formed corpus gave values that only make sense if the mapping is right:

| ID | reads | meaning under the reference | why that is convincing |
|---:|---|---|---|
| 5 | 120 on every device-form block | inverter output voltage, volts | these are 120 V units; upload-form blocks read 120 at +10 |
| 6 | 500 | AC input 1 current limit, /10 A | 50.0 A matches the installation |
| 4 | 35 | charge current, A | one deliberate installer limit on all eight inverters |
| 11, 12 | 4850, 200 | DC low shutdown 48.50 V, restart offset 2.00 V | a sane LFP floor and a 2 V restart band, fleet-wide |
| 64, 65 | 200/300, 190/196 | battery capacity Ah; SoC at bulk end × 0.5 % | 2 and 3 battery modules of 100 Ah; the reference says "190 = 95 % for LiFePO4" |
| 73 | 6300 | a voltage threshold | 63.00 V is the DC over-voltage protection level in our alarm history |
| 81 | 0 or 1 | grid code active | 0 on every bare download, 1 on every GUI-authored ESS block |
| 88 | 5200 | solar & wind priority voltage | its high byte, 0x14 = 20, sits at +0x10a; see the Virtual Switch section |

No single line is proof; the pattern is. `tests/test_claims.py` re-checks each row on every fixture.

## Confidence vocabulary

| Level | Meaning | What it permits |
|---|---|---|
| CONFIRMED | we wrote it, uploaded it, read it back on hardware, or matched it to a VEConfigure screen | edit with `mk2vsc edit` |
| HIGH | reference ID and scale give a physically sensible value on every corpus block, tied to a known property of the installation | edit with `mk2vsc edit` (you are still the first to write it) |
| MEDIUM | reference ID exists; scale or meaning not checked against our systems | read; edit only with `--i-know-this-is-unverified` |
| LOW | plausible meaning from context only | read |
| UNKNOWN | observed values recorded, meaning unknown | read |

Flag registers (IDs 0 and 1) are never edited by the writer regardless of level; we have not toggled a bit
on hardware.

## The device's own schema

The `BareSettingInfo` section is a table of one 10-byte record per setting: `i16 scale | i16 offset |
u16 default | u16 min | u16 max`. The engineering value of a raw u16 is `(raw + offset) / |scale|` for a
negative scale (a divisor) and `(raw + offset) * scale` for a positive one (a unit such as 15 minutes).
`mk2vsc.schema` reads it, the last column of the table below shows it, and the writer refuses any raw
value outside the device's own min/max. 189 of the 190 settings in the corpus lie inside their range; the
exception is the flags register, whose "max" (0x6ffc) is the mask of settable bits.

What the schema settles on its own: the durations in the Virtual Switch block are `raw - 1` (in seconds
or minutes), charge efficiency is `(raw + 1) / 256`, setting 62 is the output frequency stored as a period
(41667 / 2500 = 16.667 ms = 60 Hz, range 45 to 65 Hz), settings 63 and 71 are signed values centred on
32768, settings 70 and 74 are percentages at the half-percent scale, and setting 81 is a 0 to 32 index
rather than a flag. What it does not give is names: scale and range narrow a setting's identity, they do
not name it.

## The Virtual Switch relay mode (IDs 15 to 43)

Setting 15 (`vsUsage`) selects what the Virtual Switch does: 0 not used, 1 controls the relay, 2 ignores
the AC input. Settings 16 to 43 are the relay-mode conditions: on-levels (16 to 18), on-times (19 to
27), off-levels (28 to 30), off-times (31 to 42) and a minimum on time (43), all named by Victron. Our
systems use the ignore-AC mode, so these hold defaults.

## The Virtual Switch ignore-AC mode (IDs 52 to 59, 70)

Victron calls these the vs2 settings. The "Virtual switch > Ignore AC input" tab holds eight values, a SoC
threshold and a drop-down:

| IDs | Tab field | Storage |
|---|---|---|
| 70 | do not ignore AC when SoC lower than | x0.5 %, MEDIUM: not in Victron's document; 25 % on every configured block, the value the installer set fleet-wide |
| 52, 53 | do not ignore AC when load higher than ... W for ... s | current in 0.01 A (HIGH); seconds = raw - 1 (MEDIUM) |
| 54, 55 | do not ignore AC when Udc lower than ... V for ... s | volts x100 (CONFIRMED); seconds = raw - 1 (MEDIUM) |
| 56, 57 | ignore AC when load lower than ... W for ... min | current in 0.01 A (HIGH); minutes = raw - 1 (MEDIUM) |
| 58, 59 | ignore AC when Udc higher than ... V for ... min | volts x100 (CONFIRMED); minutes = raw - 1 (MEDIUM) |

The load thresholds are stored as current, not watts: the tab showed 1000 W and 750 W on a 120 V inverter,
and the download from the same period holds 833 and 625, which are 8.33 A and 6.25 A. Every load value in
the corpus is a round number of watts at 120 V (1750 = 2100 W, 1250 = 1500 W, 1208 = 1450 W). To set a
threshold in watts, divide by the inverter output voltage: `mk2vsc edit f.rvms vs_load_high=17.5` is
2100 W on a 120 V system.

The four durations (53, 55, 57, 59) sit next to their thresholds. The device schema gives them offset -1:
the value is `raw - 1`, in seconds for 53 and 55 (unit 1/60 minute) and minutes for 57 and 59. Current
blocks read 3 s / 20 s / 1 min / 1 min, and 20 s and 1 min are the values on the tab. Settings 16 to 18 and
28 to 30 hold a second copy of load-high / Udc-high / Udc-low values with the same scales; probably the
same conditions for another context.

## The flag registers (IDs 0, 1, 60, 61)

Victron numbers the flags 0 to 63 across four registers: Flags[0..15] are the bits of setting 0,
[16..31] of setting 1, [32..47] of setting 60, [48..63] of setting 61. From the MK2 document:

| Flag | Bit of | Meaning when set |
|---|---|---|
| 0, 1 | setting 0 | MultiPhaseSystem, MultiPhaseLeader |
| 2 | setting 0 | 60 Hz |
| 3 / 7 | setting 0 | Disable wave check (the "UPS function" option), bit 7 must be its inverse |
| 4 | setting 0 | DoNotStopAfter10HrBulk |
| 5 | setting 0 | AssistEnabled (PowerAssist) |
| 6, 8 | setting 0 | DisableCharge, DisableAES |
| 11 | setting 0 | EnableReducedFloat |
| 13, 14, 15 | setting 0 | Disable ground relay, Weak AC input, Remote overrules AC2 |
| 16 to 26 | setting 1 bits 0 to 10 | Virtual Switch relay-mode alarm conditions (vsonBulkProtection ... vsInvert) |
| 27, 28 | setting 1 bits 11, 12 | Accept wide input frequency, Dynamic current limiter |
| 29, 30, 31 | setting 1 bits 13 to 15 | Tubular plate traction curve, Remote overrules AC1, Low power shutdown in AES |
| 32, 33, 34 | setting 60 bits 0 to 2 | vs2offWhenAC1Available, vs2Invert, vsSetInverterPeriodTime |

Bits 9, 10 and 12 of setting 0 are "not promoted options"; Victron warns that changing them can damage
the device. The schema's max for each flag register is the mask of bits the firmware supports. The
writer does not edit flag registers.

## IDs 128–189

On every bare block these read 0xffff (unprogrammed). The GUI ESS install writes 1 or 0x0101 into 128
and 129 (the reference calls 128 "LOM configuration A"). In our files the assistant area begins at the
position of ID 190, so the array has 190 entries, not 256; whether 190/191 exist as settings on other
systems we cannot say.

## The table
| ID | Offset | Name | VEConfigure label | Type / scale | Unit | Confidence | Presumed usage | Evidence | Observed values | Device schema (default; min to max) |
|---:|:------:|------|-------------------|--------------|------|:----------:|----------------|----------|-----------------|-------------------------------------|
| 0 | +0x059 | `flags0` | Flags0 | u16 bitmask | bitmask | HIGH | Bit register of on/off options; see the bit table. The schema's max (0x6ffc) is the mask of settable bits. Bits: bit 0 = MultiPhaseSystem; bit 1 = MultiPhaseLeader; bit 2 = 60 Hz; bit 3 = Disable wave check (UPS function off); bit 4 = DoNotStopAfter10HrBulk; bit 5 = AssistEnabled (PowerAssist); bit 6 = DisableCharge; bit 7 = inverse of bit 3; bit 8 = DisableAES; bit 9 = not promoted; bit 10 = not promoted; bit 11 = EnableReducedFloat; bit 12 = not promoted; bit 13 = Disable ground relay; bit 14 = Weak AC input; bit 15 = Remote overrules AC2. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13 7.3.13.3 flag table (bits 0-15). | 0x81f4 (most), 0x89f4, 0x89b4, 0x817c, 0x81b4 | default 35252; 0 to 28668 |
| 1 | +0x05b | `flags1` | Flags1 | u16 bitmask | bitmask | HIGH | Bit register: Virtual Switch relay-mode alarm conditions (bits 0-10) and general options (bits 11-15). Bits: bit 0 = vsonBulkProtection; bit 1 = vsonTemperaturePreAlarm; bit 2 = vsonLowBatteryPreAlarm; bit 3 = vsonOverloadPreAlarm; bit 4 = vsonUBatRipplePreAlarm; bit 5 = vsoffTemperaturePreAlarm; bit 6 = vsoffLowBatteryPreAlarm; bit 7 = vsoffOverloadPreAlarm; bit 8 = vsoffUBatRipplePreAlarm; bit 9 = vsonWhenGeneralFailure; bit 10 = vsInvert; bit 11 = Accept wide input frequency; bit 12 = Dynamic current limiter; bit 13 = Tubular plate traction battery curve; bit 14 = Remote overrules AC1; bit 15 = Low power shutdown in AES. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13 flag table (bits 16-31). | 0x4dfe on every device-form block | default 19966; 0 to 65535 |
| 2 | +0x05d | `absorption_V` | UBatAbsorption | u16 / 100 | V | CONFIRMED | Charger absorption voltage. With a CAN-bus BMS and DVCC active the BMS charge-voltage limit overrides it. | Written by us on four systems via Remote VEConfigure and read back; Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: UBatAbsorption; schema 48.00 to 64.00 V. | 5600, 5650, 5680, 5760 (also 4800 on a mis-commissioned unit) | default 57.6; 48 to 64 |
| 3 | +0x05f | `float_V` | UBatFloat | u16 / 100 | V | CONFIRMED | Charger float voltage. | Written by us (54.0 -> 54.1 V on two inverters, uploaded, read back); Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: UBatFloat. | 5400, 5410, 5420, 5520 | default 55.2; 48 to 64 |
| 4 | +0x061 | `charge_current_A` | IBatBulk | u16 | A | HIGH | Maximum battery charge current. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: IBatBulk; schema 0 to 35 A on this model. | 35 | default 35; 0 to 35 |
| 5 | +0x063 | `inverter_output_V` | UInvSetpoint | u16 | V | HIGH | Nominal AC output voltage. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: UInvSetpoint; schema 95 to 128 V; 120 on every block. | 120 | default 120; 95 to 128 |
| 6 | +0x065 | `ac1_input_limit_A` | IMainsLimit (AC1) | u16 / 10 | A | HIGH | AC input 1 current limit (the persistent value; the GX can override at runtime). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: IMainsLimit (AC1), 0.1 A units; schema 1.0 to 100.0 A. | 500 | default 50; 1 to 100 |
| 7 | +0x067 | `repeated_absorption_time_min` | Repeated Absorption Time | u16 | min | HIGH | Duration of the periodic re-absorption, in minutes (raw x 15). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema scale 15, 1 to 96 (15 min to 24 h). | 2, 4 | default 4; 1 to 96 |
| 8 | +0x069 | `repeated_absorption_interval_min` | Repeated Absorption Interval | u16 | min | HIGH | Interval between re-absorptions, in minutes (raw x 360, i.e. 6-hour steps). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema scale 360, 1 to 180. | 4, 28 | default 28; 1 to 180 |
| 9 | +0x06b | `max_absorption_time_min` | (Maximum) Absorption duration | u16 | min | HIGH | Maximum absorption time, in minutes (raw x 60). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema scale 60, 1 to 24 h. | 1, 8 | default 8; 1 to 24 |
| 10 | +0x06d | `charge_characteristic` | Charge characteristic | u16 | enum | HIGH | Charge curve selector (schema 1 to 3, default 3). The community reference reads 0 = variable, 1 = fixed, 2 = fixed + storage; our lithium systems read 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; enum values from xcellsior/ve-bus-programming FINDINGS.md. | 1, 3 | default 3; 1 to 3 |
| 11 | +0x06f | `dc_low_shutdown_V` | UBatLowLimit for Inverter | u16 / 100 | V | HIGH | Battery voltage at which the inverter shuts down. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema 37.20 to 52.00 V. | 4850, 3720, 4800 | default 37.2; 37.2 to 52 |
| 12 | +0x071 | `dc_low_restart_offset_V` | UBatLow hysteresis for Inverter | u16 / 100 | V | HIGH | Hysteresis above the low limit before the inverter restarts. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema 1.00 to 24.00 V. | 200, 640 | default 6.4; 1 to 24 |
| 13 | +0x073 | `number_of_slaves` | Number of slaves connected | u16 |  | HIGH | Number of slave units in a parallel set. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema unused on this model; 0. | 0 | unused |
| 14 | +0x075 | `three_phase_setting` | Special three phase setting | u16 | enum | HIGH | 0 = 3 phase, 1 = split phase 180, 2 = 2-leg 3-phase 120. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema unused on this model; 0. | 0 | unused |
| 15 | +0x077 | `vs_usage` | vsUsage | u16 | enum | HIGH | Virtual Switch usage: 0 = not used, 1 = VS controls the relay, 2 = VS ignores the AC input. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema 0 to 6. Reads 3 on our configured systems, 0 or 1 on older blocks. | 0, 1, 3 | default 1; 0 to 6 |
| 16 | +0x079 | `vs_on_inverter_current_high_A` | vsonIInvHigh | u16 / 100 | A | HIGH | Virtual Switch (relay mode, settings 15 to 43): on when inverter current higher than (0.01 A). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsonIInvHigh; device schema (BareSettingInfo = CommandGetSettingInfo records). | 2125 | default 21.25; 0 to 91.66 |
| 17 | +0x07b | `vs_on_ubat_high_V` | vsonUBatHigh | u16 / 100 | V | HIGH | Virtual Switch (relay mode, settings 15 to 43): on when battery voltage higher than. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsonUBatHigh; device schema (BareSettingInfo = CommandGetSettingInfo records). | 6400 | default 64; 0 to 70 |
| 18 | +0x07d | `vs_on_ubat_low_V` | vsonUBatLow | u16 / 100 | V | HIGH | Virtual Switch (relay mode, settings 15 to 43): on when battery voltage lower than. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsonUBatLow; device schema (BareSettingInfo = CommandGetSettingInfo records). | 4700 | default 47; 0 to 70 |
| 19 | +0x07f | `vs_ton_inverter_current_high` | vstonIInvHigh | u16 | s | HIGH | Virtual Switch (relay mode): time for vsonIInvHigh, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonIInvHigh (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 20 | +0x081 | `vs_ton_ubat_high` | vstonUBatHigh | u16 | s | HIGH | Virtual Switch (relay mode): time for vsonUBatHigh, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonUBatHigh (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 21 | +0x083 | `vs_ton_ubat_low` | vstonUBatLow | u16 | s | HIGH | Virtual Switch (relay mode): time for vsonUBatLow, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonUBatLow (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 22 | +0x085 | `vs_ton_not_charging` | vstonNotCharging | u16 | s | HIGH | Virtual Switch (relay mode): on after not charging for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonNotCharging (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 23 | +0x087 | `vs_ton_fan_on` | vstonFanOn | u16 | s | HIGH | Virtual Switch (relay mode): on after fan on for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonFanOn (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 24 | +0x089 | `vs_ton_temperature_alarm` | vstonTemperatureAlarm | u16 | s | HIGH | Virtual Switch (relay mode): on after temperature alarm for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonTemperatureAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 2 | default 1; -1 to 254 |
| 25 | +0x08b | `vs_ton_low_battery_alarm` | vstonLowBatteryAlarm | u16 | s | HIGH | Virtual Switch (relay mode): on after low battery alarm for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonLowBatteryAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 2 | default 1; -1 to 254 |
| 26 | +0x08d | `vs_ton_overload_alarm` | vstonOverloadAlarm | u16 | s | HIGH | Virtual Switch (relay mode): on after overload alarm for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonOverloadAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 2 | default 1; -1 to 254 |
| 27 | +0x08f | `vs_ton_ubat_ripple_alarm` | vstonUBatRippleAlarm | u16 | s | HIGH | Virtual Switch (relay mode): on after ripple alarm for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstonUBatRippleAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 2 | default 1; -1 to 254 |
| 28 | +0x091 | `vs_off_inverter_current_low_A` | vsoffIInvLow | u16 / 100 | A | HIGH | Virtual Switch (relay mode, settings 15 to 43): off when inverter current lower than (0.01 A). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsoffIInvLow; device schema (BareSettingInfo = CommandGetSettingInfo records). | 531 | default 5.31; 0 to 91.66 |
| 29 | +0x093 | `vs_off_ubat_high_V` | vsoffUBatHigh | u16 / 100 | V | HIGH | Virtual Switch (relay mode, settings 15 to 43): off when battery voltage higher than. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsoffUBatHigh; device schema (BareSettingInfo = CommandGetSettingInfo records). | 6400 | default 64; 0 to 70 |
| 30 | +0x095 | `vs_off_ubat_low_V` | vsoffUBatLow | u16 / 100 | V | HIGH | Virtual Switch (relay mode, settings 15 to 43): off when battery voltage lower than. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsoffUBatLow; device schema (BareSettingInfo = CommandGetSettingInfo records). | 4700 | default 47; 0 to 70 |
| 31 | +0x097 | `vs_toff_inverter_current_low` | vstoffIInvLow | u16 | s | HIGH | Virtual Switch (relay mode): time for vsoffIInvLow, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffIInvLow (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 32 | +0x099 | `vs_toff_ubat_high` | vstoffUBatHigh | u16 | s | HIGH | Virtual Switch (relay mode): time for vsoffUBatHigh, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffUBatHigh (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 33 | +0x09b | `vs_toff_ubat_low` | vstoffUBatLow | u16 | s | HIGH | Virtual Switch (relay mode): time for vsoffUBatLow, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffUBatLow (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 34 | +0x09d | `vs_toff_charging` | vstoffCharging | u16 | s | HIGH | Virtual Switch (relay mode): off after charging for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffCharging (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 35 | +0x09f | `vs_toff_fan_off` | vstoffFanOff | u16 | s | HIGH | Virtual Switch (relay mode): off after fan off for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffFanOff (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 36 | +0x0a1 | `vs_toff_bulk_finished` | vstoffChargeBulkFinished | u16 | min | HIGH | Virtual Switch (relay mode): off after bulk finished for, minutes, raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffChargeBulkFinished (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 1200 |
| 37 | +0x0a3 | `vs_toff_no_on_condition` | vstoffNoVSOnCondition | u16 | min | HIGH | Virtual Switch (relay mode): off after no on-condition for, minutes, raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffNoVSOnCondition (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 1 | default 0; -1 to 1200 |
| 38 | +0x0a5 | `vs_toff_no_ac_input` | vstoffNoACInput | u16 | s | HIGH | Virtual Switch (relay mode): off after no AC input for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffNoACInput (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 39 | +0x0a7 | `vs_toff_temperature_alarm` | vstoffTemperatureAlarm | u16 | s | HIGH | Virtual Switch (relay mode): off after temperature alarm cleared for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffTemperatureAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 40 | +0x0a9 | `vs_toff_low_battery_alarm` | vstoffLowBatteryAlarm | u16 | s | HIGH | Virtual Switch (relay mode): off after low battery alarm cleared for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffLowBatteryAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 41 | +0x0ab | `vs_toff_overload_alarm` | vstoffOverloadAlarm | u16 | s | HIGH | Virtual Switch (relay mode): off after overload alarm cleared for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffOverloadAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 42 | +0x0ad | `vs_toff_ubat_ripple_alarm` | vstoffUBatRippleAlarm | u16 | s | HIGH | Virtual Switch (relay mode): off after ripple alarm cleared for, seconds (1/60 minute units), raw - 1. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vstoffUBatRippleAlarm (Time); device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1. | 0 | default -1; -1 to 254 |
| 43 | +0x0af | `vs_minimum_on_time` | vsMinimumOnTime | u16 | min | HIGH | Virtual Switch (relay mode): minimum on time, minutes; 0 = no minimum. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema 0 to 1200, offset 0. | 0 | default 0; 0 to 1200 |
| 44 | +0x0b1 | `mains_lowest_acceptable_V` | Lowest acceptable UMains | u16 | V | HIGH | Lowest AC input voltage accepted. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; 90 V here. | 90 | default 90; 90 to 120 |
| 45 | +0x0b3 | `mains_low_hysteresis_V` | Hysteresis for parameter 44 | u16 | V | HIGH | Hysteresis on the low mains limit. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13 | 7 | default 7; 1 to 15 |
| 46 | +0x0b5 | `mains_highest_acceptable_V` | Highest acceptable UMains | u16 | V | HIGH | Highest AC input voltage accepted; stored minus 100 (raw 40 = 140 V, schema 120 to 140 V). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; device schema (BareSettingInfo = CommandGetSettingInfo records): offset +100. | 40 | default 140; 120 to 140 |
| 47 | +0x0b7 | `mains_high_hysteresis_V` | Hysteresis for parameter 46 | u16 | V | HIGH | Hysteresis on the high mains limit. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13 | 5 | default 5; 1 to 15 |
| 48 | +0x0b9 | `assist_current_boost_factor` | Assist current boost factor | u16 / 16 |  | HIGH | PowerAssist boost factor: raw / 16 (32 = 2.0; schema 0.25 to 3.5). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; device schema (BareSettingInfo = CommandGetSettingInfo records): scale -16. | 32 | default 2; 0.25 to 3.5 |
| 49 | +0x0bb | `ac2_input_limit_A` | IMainsLimit (AC2) | u16 / 10 | A | HIGH | AC input 2 current limit (Quattro). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema unused on this MultiPlus. | 0 | unused |
| 50 | +0x0bd | `aes_low_current_limit_A` | Low current limit for switching to AES | u16 / 100 | A | HIGH | AC load current below which the inverter enters AES (search/low-power mode). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema /100, 0.21 to 2.55 A, default 0.60. | 60 | default 0.6; 0.21 to 2.55 |
| 51 | +0x0bf | `aes_current_hysteresis_A` | Hysteresis on AES current limit | u16 / 100 | A | HIGH | AES leaves when current exceeds settings 50 + 51. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema /100, default 0.40. | 40 | default 0.4; 0.4 to 2.55 |
| 52 | +0x0c1 | `vs_dont_ignore_load_above_A` | vs2onILoadHigh | u16 / 100 | A | HIGH | Ignore-AC mode: do not ignore the AC input when the AC load current is higher than this (VEConfigure shows watts: W = A x output voltage). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2onILoadHigh (Level); the tab's 1000 W on a 120 V inverter = 8.33 A = raw 833 in the same-period download. | 833, 1250, 1750, 2125 | default 21.25; 0 to 91.66 |
| 53 | +0x0c3 | `vs_load_above_for_s` | vs2onILoadHigh (time) | u16 | s | HIGH | Duration for the load-high condition, seconds (raw - 1). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2onILoadHigh Time; device schema (BareSettingInfo = CommandGetSettingInfo records): offset -1, 1/60 min units. | 0, 4, 6 | default -1; -1 to 254 |
| 54 | +0x0c5 | `vs_ignore_ac_below_V` | vs2onUBatLow | u16 / 100 | V | CONFIRMED | Ignore-AC mode: do not ignore the AC input when the battery voltage is lower than this. | Matched to the VEConfigure tab (51.40 V), written by us; Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2onUBatLow. | 5100, 4700 | default 47; 0 to 70 |
| 55 | +0x0c7 | `vs_udc_below_for_s` | vs2onUBatLow (time) | u16 | s | HIGH | Duration for the Udc-low condition, seconds (raw - 1). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2onUBatLow Time; schema offset -1; raw 21 = 20 s, the value on the tab. | 0, 6, 21 | default -1; -1 to 254 |
| 56 | +0x0c9 | `vs_ignore_load_below_A` | vs2offILoadLow | u16 / 100 | A | HIGH | Ignore-AC mode: ignore the AC input again when the AC load current is lower than this. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2offILoadLow; 750 W on the tab = 6.25 A = raw 625. | 531, 625, 833, 1500 | default 5.31; 0 to 91.66 |
| 57 | +0x0cb | `vs_load_below_for_min` | vs2offILoadLow (time) | u16 | min | HIGH | Duration for the load-low condition, minutes (raw - 1). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema offset -1; raw 2 = 1 min. | 0, 2 | default -1; -1 to 254 |
| 58 | +0x0cd | `vs_accept_battery_above_V` | vs2offUBatHigh | u16 / 100 | V | CONFIRMED | Ignore-AC mode: ignore the AC input again when the battery voltage is higher than this. Victron: if the high byte is 0, low byte 0 means 'when bulk finished' and 1 'when absorption finished' instead of a voltage. A value the battery cannot reach (64.00 V on a 48 V LFP) makes grid pass-through permanent. | Tab match (53.00 V), written by us; Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vs2offUBatHigh. | 5250, 5300, 5450, 6400 | default 64; 0 to 70 |
| 59 | +0x0cf | `vs_udc_above_for_min` | vs2offUBatHigh (time) | u16 | min | HIGH | Duration for the Udc-high condition, minutes (raw - 1). | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema offset -1; raw 2 = 1 min. | 0, 2 | default -1; -1 to 254 |
| 60 | +0x0d1 | `flags2` | Flags2 | u16 bitmask | bitmask | HIGH | Bit register: vs2offWhenAC1Available (bit 0), vs2Invert (bit 1), vsSetInverterPeriodTime (bit 2). Schema max 1022. Bits: bit 0 = vs2offWhenAC1Available; bit 1 = vs2Invert; bit 2 = vsSetInverterPeriodTime. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13 flags 32-34. | 0, 16, 48 | default 0; 0 to 1022 |
| 61 | +0x0d3 | `flags3` | Flags3 | u16 | bitmask | HIGH | Bit register; no documented bits. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: Flags3. | 0 | default 0; 0 to 0 |
| 62 | +0x0d5 | `output_frequency_Hz` | vsInverterPeriodTime | u16 / 2500 | Hz | HIGH | Inverter output frequency, stored as the period in 1/2500 ms: 41667 = 16.667 ms = 60 Hz. Applied when Flags2 bit 2 (vsSetInverterPeriodTime) is set. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: vsInverterPeriodTime; schema range 45 to 65 Hz. | 41667, 41666 | default 0.06; 0.065 to 0.045 |
| 63 | +0x0d7 | `ubat_low_prealarm_offset_V` | UBat low pre-alarm offset | u16 / 100 | V | HIGH | Signed offset added to (UBatLowLimit + hysteresis) to set the low-battery pre-alarm level; stored with 0x8000 added. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13: 'this offset can be positive or negative; 0x8000 is added'. | 32668 (-1.00 V), 32768 (0) | default 0; -37.2 to 48 |
| 64 | +0x0d9 | `battery_capacity_Ah` | Battery capacity | u16 | Ah | HIGH | Capacity for the built-in battery monitor; 0 disables it. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; 200 / 300 Ah match the installed modules. | 200, 300, 0 | default 0; 0 to 65330 |
| 65 | +0x0db | `soc_at_bulk_end_pct` | SoC when bulk finished | u16 / 2 | % | HIGH | State of charge the built-in monitor assumes when the charge state changes from bulk to absorption. | Victron 'Interfacing with VE.Bus products - MK2 Protocol 3.14' section 7.3.13; schema /2, 30 to 100 %. | 170, 190, 196 | default 85; 30 to 100 |
| 66 | +0x0dd | `param66_V` |  | u16 / 100 | V | LOW | 57.72 V, schema range 0 to 70.00 V; paired with 68 (54.00 V) and durations 67/69. Probably a second charge-voltage pair. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 5772 | default 57.72; 0 to 70 |
| 67 | +0x0df | `param67_time_s` |  | u16 | s | LOW | A duration in seconds (schema 1/60 min, offset -1) next to 66; 2 s here. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 3 | default 2; 0 to 254 |
| 68 | +0x0e1 | `param68_V` |  | u16 / 100 | V | LOW | 54.00 V, pairs with 66. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 5400 | default 54; 0 to 70 |
| 69 | +0x0e3 | `param69_time_s` |  | u16 | s | LOW | A duration in seconds next to 68; 2 s here. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 3 | default 2; 0 to 254 |
| 70 | +0x0e5 | `vs_dont_ignore_soc_below_pct` | VS: do not ignore AC input when SoC lower than | u16 / 2 | % | MEDIUM | Ignore-AC mode battery condition on state of charge (not in Victron's 3.14 document, which predates it). | device schema (BareSettingInfo = CommandGetSettingInfo records): /2, 0 to 100 %. 25 % on every configured block, the fleet-wide SoC setpoint the installer's note describes; the tab captured before that change showed 20.0 %. | 50, 0 | default 0; 0 to 100 |
| 71 | +0x0e7 | `signed_offset_71` |  | u16 |  | LOW | A signed value centred on 32768 (schema +/-800); 0 here. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 32768 | default 0; -800 to 800 |
| 72 | +0x0e9 | `charge_efficiency` | Battery charge efficiency | u16 / 256 |  | MEDIUM | Fraction (raw + 1)/256: 255 = 1.000, 242 = 0.949. | device schema (BareSettingInfo = CommandGetSettingInfo records): scale -256, offset +1; name from xcellsior/ve-bus-programming FINDINGS.md. | 250, 242, 255 | default 1; 0.00390625 to 1 |
| 73 | +0x0eb | `voltage_threshold_73_V` |  | u16 / 100 | V | MEDIUM | A voltage threshold; 63.00 V on every block, the DC over-voltage level in our alarm history. | device schema (BareSettingInfo = CommandGetSettingInfo records): 8.03 to 106.00 V; xcellsior/ve-bus-programming FINDINGS.md lists it as a voltage threshold. | 6300 | default 63; 8.03 to 106 |
| 74 | +0x0ed | `soc_pct_74` |  | u16 / 2 | % | LOW | A percentage at the half-percent scale (schema 30 to 100 %, default 85 %); 100 % here. | device schema (BareSettingInfo = CommandGetSettingInfo records) | 200 | default 85; 30 to 100 |
| 81 | +0x0fb | `grid_code` | Grid code | u16 | enum | HIGH | 0 = none; a non-zero value selects a grid code (country standard), set with the dealer password in VEConfigure. Schema 0 to 32. | 0 on every bare block, 1 on every GUI-authored ESS block. | 0, 1 | default 0; 0 to 32 |
| 85 | +0x103 | `param85` |  | u16 |  | UNKNOWN |  | Schema: scale 50, offset 1069, default 3000, min 2400; 65535 here. | 65535 | default 3000; 2400 to 65535 |
| 87 | +0x107 | `param87` |  | u16 |  | UNKNOWN |  | Schema: scale -12800, 0 to 1536, default 829. | 829 | default 829; 0 to 1536 |
| 88 | +0x109 | `solar_wind_priority_V` | Sustain voltage | u16 / 100 | V | MEDIUM | 52.00 V on every block; the community reference calls it the solar & wind priority (sustain) voltage. | xcellsior/ve-bus-programming FINDINGS.md; device schema (BareSettingInfo = CommandGetSettingInfo records): 48.00 to 64.00 V. | 5200 | default 52; 48 to 64 |
| 128 | +0x159 | `lom_config_a` | LOM configuration A | u16 |  | LOW | Loss-of-mains configuration (grid code related). 0xffff on bare blocks; the GUI ESS install writes 1 or 0x0101. | xcellsior/ve-bus-programming FINDINGS.md; observed transition. | 65535, 1, 257, 65281, 0 | default 48906; 0 to 65535 |

IDs not listed read zero on every block (19–23, 31–36, 38–43, 61, 75–80, 82–84, 86, 89–127) or
0xffff (129–189 on bare blocks); they are omitted from the table but visible with `mk2vsc show --all`.

## How to add or promote a field

The differential method is what produced everything above; it needs no Windows and no source.

1. **Bracket one change.** Download the file, make exactly one change in VEConfigure (or have your
   installer make it), download again. `mk2vsc diff before.rvms after.rvms` names the setting IDs that
   moved. One change at a time, or you cannot tell which is which.
2. **Look for lockstep.** A real setting changed by an installer's "configure properly" pass moves on
   both inverters of a pair at once and converges to the same standard value across systems. Timestamps,
   pointers and checksums move on every save and are never settings (`mk2vsc.units.VOLATILE_DEVICE`).
3. **Anchor to a screen.** One screenshot of the VEConfigure tab showing the value turns a candidate into
   a CONFIRMED entry in seconds; it is how the Virtual Switch thresholds were pinned.
4. **Check the scale on the corpus.** A voltage should decode to a voltage on every block, not just yours.
   `tests/test_claims.py::test_confirmed_and_high_fields_decode_to_sensible_values` is where such a
   check belongs.
5. **Write it down with its evidence.** Add a `Field` to `mk2vsc/fields.py` with `evidence` and `observed`
   filled in, regenerate this table, and say what you did not verify. A field promoted without evidence
   will be demoted in review.

Things that cannot be found this way: fields that never vary across the files you hold (grid code, phase
count, AC input current limit on a fleet where they are all the same). Those need either a screenshot or
a deliberate change.
