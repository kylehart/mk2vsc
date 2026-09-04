# The settings table

Each `BareSettingData` block carries a flat array of 190 little-endian u16 values starting at block
offset +0x59 (device form; +0x63 in the GUI's upload form, see `docs/FORMAT.md` §4). Entry *n* of that
array is **VE.Bus setting ID n** as documented by the community MK2/MK3 protocol reference,
[xcellsior/ve-bus-programming](https://github.com/xcellsior/ve-bus-programming) (`FINDINGS.md`,
"Persistent Settings IDs 0-255"). The IDs, scales and flag bits below marked `xcellsior` come from that
reference; the evidence that the file's array *is* that table is ours.

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

## The Virtual Switch block (IDs 50 to 59)

The "Virtual switch > Ignore AC input" tab in VEConfigure holds eight values and a drop-down. Settings 50
to 59 hold them in this layout:

| IDs | Tab field | Storage |
|---|---|---|
| 50 | ignore AC when SoC higher than (drop-down alternative) | x0.5 %, LOW: 60 = 30 % on every block, never seen on a screen |
| 51 | do not ignore AC when SoC lower than | x0.5 %, MEDIUM: 40 = 20.0 %, the value on the tab |
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

## The flag registers (IDs 0 and 1)

ID 0 reads 0x81f4 on most blocks and 0x89f4 / 0x89b4 on older ones. The difference is bit 11 (0x0800),
which the reference identifies as *adaptive charge curve (lead-acid) when set, fixed (LiFePO4) when
clear*. Every GUI ESS install in our corpus cleared it. For weeks we tracked this as "the 0x5a byte,
89 → 81", one of the install-state mysteries; it is the GUI switching a lithium system to a fixed charge
curve. ID 1 reads 0x4dfe on every device-form block; bits 11 and 12 (wide frequency range, dynamic current
limiter) are set.

## IDs 128–189

On every bare block these read 0xffff (unprogrammed). The GUI ESS install writes 1 or 0x0101 into 128
and 129 (the reference calls 128 "LOM configuration A"). In our files the assistant area begins at the
position of ID 190, so the array has 190 entries, not 256; whether 190/191 exist as settings on other
systems we cannot say.

## The table
| ID | Offset | Name | VEConfigure label | Type / scale | Unit | Confidence | Presumed usage | Evidence | Observed values | Device schema (default; min to max) |
|---:|:------:|------|-------------------|--------------|------|:----------:|----------------|----------|-----------------|-------------------------------------|
| 0 | +0x059 | `flags0` | Primary flags register | u16 bitmask | bitmask | HIGH | Bit register of on/off options. Known bits (from the MK2 protocol reference): bit 3 SET = UPS function DISABLED; bit 5 SET = PowerAssist enabled; bit 11 SET = adaptive (lead-acid) charge curve, CLEAR = fixed (LiFePO4); bit 14 SET = Weak AC. Bits: bit 3 = UPS function disabled; bit 5 = PowerAssist enabled; bit 11 = Adaptive charge curve (lead-acid); bit 14 = Weak AC input enabled. | Reference bit table. On our fleet the ESS installs performed in the GUI changed 0x89xx -> 0x81xx, i.e. cleared bit 11 (adaptive charge) -- consistent with the GUI switching the charge curve to fixed for a lithium battery, and consistent with the reference. Not yet toggled by us. | 0x81f4 (most), 0x89f4, 0x89b4, 0x817c, 0x81b4 | default 35252; 0 to 28668 |
| 1 | +0x05b | `flags1` | Secondary flags register | u16 bitmask | bitmask | HIGH | Second bit register. bit 11 SET = accept wide input frequency range; bit 12 SET = dynamic current limiter. Bits: bit 11 = Accept wide frequency range; bit 12 = Dynamic current limiter. | Reference bit table; value 0x4dfe on every device-form block. | 0x4dfe (device form), 0x6a5f/0x6a55/0x6a7e in a few grafted files | default 19966; 0 to 65535 |
| 2 | +0x05d | `absorption_V` | Absorption voltage | u16 / 100 | V | CONFIRMED | Charger absorption (bulk end) voltage. With a CAN-bus BMS and DVCC active the BMS charge-voltage limit overrides this; it is the fallback used when the BMS link is absent. | Written by the writer on four systems (2026-07-20) via Remote VEConfigure, read back correct on every inverter; matches VRM 'Absorption' and VEConfigure Charger tab. | 5600, 5650, 5680, 5760 (also 4800 on a mis-commissioned unit, 0 in stub blocks) | default 57.6; 48 to 64 |
| 3 | +0x05f | `float_V` | Float voltage | u16 / 100 | V | CONFIRMED | Charger float voltage (after absorption). | First live proof of the whole toolchain: float 54.0 -> 54.1 V on both inverters of one system, uploaded, 'Success', read back 54.1 (2026-07-20). Later edits confirmed again. | 5400, 5410, 5420, 5520 | default 55.2; 48 to 64 |
| 4 | +0x061 | `charge_current_A` | Charge current | u16 | A | HIGH | Maximum battery charge current from the charger. | Reference ID/scale; 35 on every device-form block (a deliberate installer limit, consistent across eight inverters). Not edited by us. | 35 | default 35; 0 to 35 |
| 5 | +0x063 | `inverter_output_V` | Inverter output voltage | u16 | V | HIGH | Nominal AC output voltage of the inverter. | Reference; 120 on every block (these are 120 V units). Upload-form blocks read it at +10. | 120 | default 120; 95 to 128 |
| 6 | +0x065 | `ac1_input_limit_A` | AC input 1 current limit | u16 / 10 | A | HIGH | Shore/grid input current limit for AC input 1 (the persistent value; the GX can override at runtime). | Reference; 500 = 50.0 A on every device-form block, matching the installation's breaker sizing. | 500 | default 50; 1 to 100 |
| 7 | +0x067 | `repeated_absorption_time` | Repeated absorption time | u16 |  | MEDIUM | Duration of a periodic re-absorption cycle (lead-acid curve). | Reference name only. | 2, 4 | default 4; 1 to 96 |
| 8 | +0x069 | `repeated_absorption_interval` | Repeated absorption interval | u16 |  | MEDIUM | Interval between periodic re-absorption cycles. | Reference name only. | 4, 28 | default 28; 1 to 180 |
| 9 | +0x06b | `max_absorption_time` | Maximum absorption time | u16 |  | MEDIUM | Absorption time limit; the reference notes '1 for LiFePO4 fixed'. | Reference. | 1, 8 | default 8; 1 to 24 |
| 10 | +0x06d | `charge_characteristic` | Charge characteristic | u16 | enum | MEDIUM | 0 = variable (adaptive), 1 = fixed, 2 = fixed + storage. | Reference enum; 1 on lithium systems here. | 1, 3 | default 3; 1 to 3 |
| 11 | +0x06f | `dc_low_shutdown_V` | DC input low shut-down | u16 / 100 | V | HIGH | Battery voltage at which the inverter shuts down (low-battery cutoff). | Reference ID/scale. Our differential decode saw this move 37.20 -> 48.50 V on two systems during the installer's 'properly configure' pass and it reads 48.50 on all current blocks; 48.5 V is a sane LFP floor. | 4850, 3720, 4800 | default 37.2; 37.2 to 52 |
| 12 | +0x071 | `dc_low_restart_offset_V` | DC input low restart offset | u16 / 100 | V | HIGH | Voltage above the shut-down level at which the inverter restarts. | Reference; 2.00 V fleet-wide. | 200, 640 | default 6.4; 1 to 24 |
| 13 | +0x073 | `unknown_13` |  | u16 |  | UNKNOWN |  |  | 0 | unused |
| 14 | +0x075 | `unknown_14` |  | u16 |  | UNKNOWN |  |  | 0 | unused |
| 15 | +0x077 | `unknown_toggle_15` | Unknown toggle | u16 | enum | LOW | An enumeration 0..6 (device schema: default 1, min 0, max 6). | Values track the installer's configuration pass (3 on configured, 1/0 on older). | 0, 1, 3 | default 1; 0 to 6 |
| 16 | +0x079 | `param16` |  | u16 |  | LOW | First of a repeated block (16-18 and 28-30) whose values equal the Virtual Switch load-high, Udc-high and Udc-low settings of an untouched system (2125 / 6400 / 4700 and 531 / 6400 / 4700): probably the same conditions for another context (second AC input, or defaults). |  | 2125 | default 2125; 0 to 9166 |
| 17 | +0x07b | `param17_V` |  | u16 / 100 | V? | LOW | Reads 64.00 -- voltage-like; possibly a DC high alarm/threshold. | Same value as ID 29 and as the unreachable 64.00 V VS-return threshold once set on two systems. | 6400 | default 64; 0 to 70 |
| 18 | +0x07d | `param18_V` |  | u16 / 100 | V? | LOW | Reads 47.00 -- voltage-like. | Same value as ID 30. | 4700 | default 47; 0 to 70 |
| 24 | +0x089 | `param24` |  | u16 |  | UNKNOWN |  |  | 2 | default 2; 0 to 255 |
| 25 | +0x08b | `param25` |  | u16 |  | UNKNOWN |  |  | 2 | default 2; 0 to 255 |
| 26 | +0x08d | `param26` |  | u16 |  | UNKNOWN |  |  | 2 | default 2; 0 to 255 |
| 27 | +0x08f | `param27` |  | u16 |  | UNKNOWN |  |  | 2 | default 2; 0 to 255 |
| 28 | +0x091 | `param28` |  | u16 |  | UNKNOWN | Second copy of the 16-18 block shape. |  | 531 | default 531; 0 to 9166 |
| 29 | +0x093 | `param29_V` |  | u16 / 100 | V? | LOW | Reads 64.00. |  | 6400 | default 64; 0 to 70 |
| 30 | +0x095 | `param30_V` |  | u16 / 100 | V? | LOW | Reads 47.00. |  | 4700 | default 47; 0 to 70 |
| 37 | +0x0a3 | `param37` |  | u16 |  | UNKNOWN |  |  | 1 | default 1; 0 to 1201 |
| 44 | +0x0b1 | `param44` |  | u16 |  | UNKNOWN |  |  | 90 | default 90; 90 to 120 |
| 45 | +0x0b3 | `param45` |  | u16 |  | UNKNOWN |  |  | 7 | default 7; 1 to 15 |
| 46 | +0x0b5 | `param46` |  | u16 |  | UNKNOWN |  |  | 40 | default 40; 20 to 40 |
| 47 | +0x0b7 | `param47` |  | u16 |  | UNKNOWN |  |  | 5 | default 5; 1 to 15 |
| 48 | +0x0b9 | `param48` |  | u16 |  | UNKNOWN |  |  | 32 | default 32; 4 to 56 |
| 49 | +0x0bb | `ac2_input_limit_A` | AC input 2 current limit | u16 / 10 | A | MEDIUM | Quattro only; 0 on MultiPlus. | Reference; 0 on all our MultiPlus blocks. | 0 | unused |
| 50 | +0x0bd | `vs_ignore_soc_above_pct` | VS: ignore AC input when SoC higher than | u16 / 2 | % | LOW | Alternative battery condition for returning to battery (the drop-down next to 'Udc higher than'). | Adjacent to the SoC-lower setting and identical (60 = 30 %) on every block; not seen on a screenshot. | 60 | default 30; 10.5 to 127.5 |
| 51 | +0x0bf | `vs_dont_ignore_soc_below_pct` | VS: do not ignore AC input when SoC lower than | u16 / 2 | % | MEDIUM | Battery condition for accepting the grid: SoC below this (x0.5 %, the scale setting 65 uses). | 40 = 20.0 % on every block, matching the 20.0 % shown on the VEConfigure tab; a single value, so the scale rests on one data point plus the setting-65 convention. | 40 | default 20; 20 to 127.5 |
| 52 | +0x0c1 | `vs_dont_ignore_load_above_A` | VS: do not ignore AC input when load higher than | u16 / 100 | A | HIGH | Load condition for accepting the grid: AC load above this current (VEConfigure shows watts; W = A x inverter output voltage, 120 V here). | The tab showed 1000 W while the same-period download held 833 = 8.33 A = 1000 W / 120 V; the 750 W field matched setting 56 the same way. Current values 1750 = 17.5 A = 2100 W. | 833, 1750, 2125 | default 21.25; 0 to 91.66 |
| 53 | +0x0c3 | `vs_load_above_for_s` | VS: ... for (seconds) | u16 | s | MEDIUM | Duration for the load-high condition, in seconds. | Device schema: offset -1, unit 1/60 minute; raw 4 = 3 s. Adjacent to setting 52. | 0, 4, 6 | default -1; -1 to 254 |
| 54 | +0x0c5 | `vs_ignore_ac_below_V` | VS: do not ignore AC input when Udc lower than | u16 / 100 | V | CONFIRMED | Battery condition for accepting the grid: DC voltage below this for the configured time. | Matched to the VEConfigure tab (51.40 V) and to the installer's note of lowering it to 51.0 at all sites; later GUI changes landed here; written by us. | 5100 (current), 4700 (old) | default 47; 0 to 70 |
| 55 | +0x0c7 | `vs_udc_below_for_s` | VS: ... for (seconds) | u16 | s | MEDIUM | Duration for the Udc-low condition, in seconds. | Device schema: offset -1; raw 21 = 20 s, the value on the VEConfigure tab. Adjacent to setting 54. | 0, 6, 21 | default -1; -1 to 254 |
| 56 | +0x0c9 | `vs_ignore_load_below_A` | VS: when accepting AC due to load, ignore AC when load lower than | u16 / 100 | A | HIGH | Load condition for returning to battery: AC load below this current (tab shows watts). | 750 W on the tab; 625 = 6.25 A = 750 W / 120 V in the same-period download. Current 1500 = 15 A = 1800 W. | 625, 1500, 531 | default 5.31; 0 to 91.66 |
| 57 | +0x0cb | `vs_load_below_for_min` | VS: ... for (minutes) | u16 | min | MEDIUM | Duration for the load-low condition, in minutes. | Device schema: offset -1; raw 2 = 1 min, the value on the tab. Adjacent to setting 56. | 0, 2 | default -1; -1 to 254 |
| 58 | +0x0cd | `vs_accept_battery_above_V` | VS: when accepting AC due to a battery condition, ignore AC when Udc higher than | u16 / 100 | V | CONFIRMED | Battery condition for returning to battery: DC voltage above this. A value the battery cannot reach (64.00 V on a 48 V LFP) makes grid pass-through permanent. | Tab match (53.00 V); the installer's per-site values (53.0 / 52.5) appear here; written by us. | 5250, 5300, 6400 (unreachable) | default 64; 0 to 70 |
| 59 | +0x0cf | `vs_udc_above_for_min` | VS: ... for (minutes) | u16 | min | MEDIUM | Duration for the Udc-high condition, in minutes. | Device schema: offset -1; raw 2 = 1 min, the value on the tab. Adjacent to setting 58. | 0, 2 | default -1; -1 to 254 |
| 60 | +0x0d1 | `solar_wind_priority_flags` | Solar & wind priority flags | u16 | bitmask | MEDIUM | Reference: bit 4 (16) = off, 528 = on. | Reference; 16 on bare blocks, 48 after GUI ESS install. | 16, 48, 0 | default 0; 0 to 1022 |
| 62 | +0x0d5 | `output_frequency_Hz` | Inverter output frequency | u16 / 2500 | Hz | HIGH | AC output frequency, stored as the period in units of 1/2500 ms: 41667 = 16.667 ms = 60 Hz. | Device schema: scale -2500, range 38461..55555 = 65 Hz down to 45 Hz, default 41666; every block reads 60.00 Hz. | 41667, 41666 | default 0.06; 0.065 to 0.045 |
| 63 | +0x0d7 | `signed_offset_63_V` |  | u16 / 100 | V | LOW | A signed voltage offset centred on 32768 (device schema: offset -32768, scale -100, range -37.20 to +48.00 V); 0.00 or -1.00 V here. | Schema only. | 32668, 32768 | default 0; -37.2 to 48 |
| 64 | +0x0d9 | `battery_capacity_Ah` | Battery capacity | u16 | Ah | HIGH | Capacity used by the inverter's built-in battery monitor; 0 disables the monitor. | Reference; 200 / 300 Ah match the installed EG4 module counts (2 x 100 Ah vs 3 x 100 Ah). | 200, 300, 0 | default 0; 0 to 65330 |
| 65 | +0x0db | `soc_at_bulk_end_pct` | SoC when bulk finished | u16 / 2 | % | HIGH | State of charge the built-in monitor assumes at the end of bulk (x0.5 %). | Reference: '190 = 95 % for LiFePO4'; we see 190 and 196 (98 %). | 190, 196, 170 | default 85; 30 to 100 |
| 66 | +0x0dd | `param66_V` |  | u16 / 100 | V? | LOW | 57.72 V -- voltage-like; possibly a second (lead-acid default) charge profile paired with 68. |  | 5772 | default 57.72; 0 to 70 |
| 67 | +0x0df | `param67` |  | u16 |  | LOW | Changed 04 -> 02 by the GUI ESS install on one inverter. |  | 3, 2, 4 | default 3; 1 to 255 |
| 68 | +0x0e1 | `param68_V` |  | u16 / 100 | V? | LOW | 54.00 V -- voltage-like, pairs with 66. |  | 5400 | default 54; 0 to 70 |
| 69 | +0x0e3 | `param69` |  | u16 |  | LOW | Changed 1c -> 04 by the GUI ESS install on one inverter. |  | 3, 4, 28 | default 3; 1 to 255 |
| 70 | +0x0e5 | `soc_pct_70` |  | u16 / 2 | % | LOW | A state-of-charge value (device schema: scale -2, 0..100 %); 25 % on configured blocks, the value the installer set fleet-wide as the reserve. | Schema scale; one value. | 50, 0 | default 0; 0 to 100 |
| 71 | +0x0e7 | `signed_offset_71` |  | u16 |  | LOW | A signed value centred on 32768 (schema range -800..+800); 0 here. | Schema only. | 32768 | default 0; -800 to 800 |
| 72 | +0x0e9 | `charge_efficiency` | Battery charge efficiency | u16 / 256 |  | MEDIUM | Fraction: (raw + 1) / 256. 255 = 1.000, 242 = 0.949 (the reference's 'about 95 % for LiFePO4'). | Device schema: scale -256, offset +1. | 250, 242, 255 | default 1; 0.00390625 to 1 |
| 73 | +0x0eb | `voltage_threshold_73_V` | Voltage threshold | u16 / 100 | V | MEDIUM | Reference calls it a voltage threshold that 'varies significantly'. Ours reads 63.00 V everywhere, the same value as the DC over-voltage protection trip we found in the alarm history. | Value coincidence with a known protection level; not toggled. | 6300 | default 63; 8.03 to 106 |
| 74 | +0x0ed | `soc_pct_74` |  | u16 / 2 | % | LOW | A state-of-charge value (schema: scale -2, 30..100 %, default 85 %); 100 % here. | Schema only. | 200 | default 85; 30 to 100 |
| 81 | +0x0fb | `grid_code_active` | Grid code | u16 | enum | HIGH | 0 = none; a non-zero value selects a grid code (country standard) set with the dealer password in VEConfigure. Device schema: 0..32, so an index into the grid-code list rather than a flag; 1 here. | Reference; 0 on every bare block, 1 on every GUI-authored ESS block. Part of the 'grid-code fingerprint' our failed grafts tried to stamp. | 0, 1 | default 0; 0 to 32 |
| 85 | +0x103 | `param85` |  | u16 |  | UNKNOWN |  | Schema: scale 50, offset 1069, default 3000, min 2400; 65535 here (disabled?). | 65535 | default 3000; 2400 to 65535 |
| 87 | +0x107 | `param87` |  | u16 |  | UNKNOWN |  | Schema: scale -12800, range 0..1536, default 829 (0.0648). | 829 | default 829; 0 to 1536 |
| 88 | +0x109 | `solar_wind_priority_V` | Solar & wind priority (sustain) voltage | u16 / 100 | V | MEDIUM | Reference: sustain voltage for solar & wind priority. | Reference; 52.00 V everywhere. The byte at +0x10a (which reads 20) is the high byte of this value (5200 = 0x1450), not a SoC threshold; the Virtual Switch SoC threshold is not located. | 5200 | default 52; 48 to 64 |
| 128 | +0x159 | `lom_config_a` | LOM configuration A | u16 |  | LOW | Loss-of-mains configuration (grid code related). 0xffff on bare blocks; the GUI ESS install writes 1 / 0x0101. | Reference name; observed transition. | 65535, 1, 257, 65281, 0 | default 48906; 0 to 65535 |

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
