# The settings table

Each `BareSettingData` block carries a flat array of 190 little-endian u16 values starting at block
offset +0x59 (device form; +0x63 in the GUI's upload form, see `docs/FORMAT.md` §4). Entry *n* of that
array is **VE.Bus setting ID n** as documented by the community MK2/MK3 protocol reference,
[xcellsior/ve-bus-programming](https://github.com/xcellsior/ve-bus-programming) (`FINDINGS.md`,
"Persistent Settings IDs 0-255"). The IDs, scales and flag bits below marked `xcellsior` come from that
reference; the evidence that the file's array *is* that table is ours.

The table is generated from `rvms/fields.py` by `tools/gen_fields_table.py`. Regenerate it after any
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
| 11, 12 | 4850, 200 | DC low shutdown 48.50 V, restart offset 2.00 V | earlier differential decode had labelled these "?vs_restart" and "?field_71" |
| 64, 65 | 200/300, 190/196 | battery capacity Ah; SoC at bulk end × 0.5 % | 2 and 3 battery modules of 100 Ah; the reference says "190 = 95 % for LiFePO4" |
| 73 | 6300 | a voltage threshold | 63.00 V is the DC over-voltage protection level in our alarm history |
| 81 | 0 or 1 | grid code active | 0 on every bare download, 1 on every GUI-authored ESS block |
| 88 | 5200 | solar & wind priority voltage | and see the retraction below |

No single line is proof; the pattern is. `tests/test_claims.py` re-checks each row on every fixture.

## Confidence vocabulary

| Level | Meaning | What it permits |
|---|---|---|
| CONFIRMED | we wrote it, uploaded it, read it back on hardware, or matched it to a VEConfigure screen | edit with `rvms set` |
| HIGH | reference ID and scale give a physically sensible value on every corpus block, tied to a known property of the installation | edit with `rvms set` (you are still the first to write it) |
| MEDIUM | reference ID exists; scale or meaning not checked against our systems | read; edit only with `--i-know-this-is-unverified` |
| LOW | plausible meaning from context only | read |
| UNKNOWN | observed values recorded, meaning unknown | read |

Flag registers (IDs 0 and 1) are never edited by the writer regardless of level; we have not toggled a bit
on hardware.

## A retraction: there is no "VS SoC threshold" at +0x10a

Our early notes listed a Virtual Switch SoC threshold of 20 % at block offset +0x10a, "confirmed" because
every system read 20 there and the installer's screenshot showed a 20 % SoC condition. Under the
setting-ID mapping +0x10a is the **high byte of setting 88**, which reads 5200 (0x1450) on every block;
0x14 is 20. A coincidence that survived a month. The Virtual Switch SoC threshold is **not located**. The
old field name `vs_soc_pct` is retained in `rvms.fields.LEGACY_NAMES` only so that it raises a clear
error.

## The Virtual Switch block (IDs 50–59)

The reference lists 50–59 as a parameter block. Two of them are CONFIRMED against a VEConfigure
"Virtual Switch → Ignore AC input" screenshot from the installer:

* the screen showed *do not ignore AC input when Udc lower than 51.40 V for 20 s* and *ignore AC input
  again when Udc higher than 53.00 V for 1 min*; the array held 5140 at ID 54 and 5300 at ID 58 on that
  system at that time, and the installer's later per-site values (51.00; 52.50 / 53.00) appeared at the
  same IDs. A 64.00 V value at ID 58 on two systems was the unreachable return threshold behind a 5.6-day
  stuck-on-grid episode.
* the same screen showed load conditions of *1000 W for 1 s* and *750 W for 1 min*. We have **not**
  located those. IDs 50 (60), 51 (40), 52 (1750 / 2125 / 833), 53 (4 / 6 / 0), 55 (21 / 6 / 0), 56 (1500 / 625 / 531),
  57 and 59 (2 / 0) are the candidates; 52 and 56 move together with the thresholds across the
  installer's configuration passes and may be watts, tenths of seconds, or something else. Earlier notes
  read them as 17.50 V and 15.00 V; that is no better supported.

## The flag registers (IDs 0 and 1)

ID 0 reads 0x81f4 on most blocks and 0x89f4 / 0x89b4 on older ones. The difference is bit 11 (0x0800),
which the reference identifies as *adaptive charge curve (lead-acid) when set, fixed (LiFePO4) when
clear*. Every GUI ESS install in our corpus cleared it. For weeks we tracked this as "the 0x5a byte,
89 → 81", one of the install-state mysteries; it is the GUI switching a lithium system to a fixed charge
curve. ID 1 reads 0x4dfe on every device-form block; bits 11 and 12 (wide frequency range, dynamic current
limiter) are set. Earlier tooling mistook the bytes `fe 4d` at this position for a "device descriptor
marker" and built a check on it.

## IDs 128–189

On every bare block these read 0xffff (unprogrammed). The GUI ESS install writes 1 or 0x0101 into 128
and 129 (the reference calls 128 "LOM configuration A"). In our files the assistant area begins at the
position of ID 190, so the array has 190 entries, not 256; whether 190/191 exist as settings on other
systems we cannot say.

## The table
| ID | Offset | Name | VEConfigure label | Type / scale | Unit | Confidence | Presumed usage | Evidence | Observed values |
|---:|:------:|------|-------------------|--------------|------|:----------:|----------------|----------|-----------------|
| 0 | +0x059 | `flags0` | Primary flags register | u16 bitmask | bitmask | HIGH | Bit register of on/off options. Known bits (from the MK2 protocol reference): bit 3 SET = UPS function DISABLED; bit 5 SET = PowerAssist enabled; bit 11 SET = adaptive (lead-acid) charge curve, CLEAR = fixed (LiFePO4); bit 14 SET = Weak AC. Bits: bit 3 = UPS function disabled; bit 5 = PowerAssist enabled; bit 11 = Adaptive charge curve (lead-acid); bit 14 = Weak AC input enabled. | Reference bit table. On our fleet the ESS installs performed in the GUI changed 0x89xx -> 0x81xx, i.e. cleared bit 11 (adaptive charge) -- consistent with the GUI switching the charge curve to fixed for a lithium battery, and consistent with the reference. Not yet toggled by us. | 0x81f4 (most), 0x89f4, 0x89b4, 0x817c, 0x81b4 |
| 1 | +0x05b | `flags1` | Secondary flags register | u16 bitmask | bitmask | HIGH | Second bit register. bit 11 SET = accept wide input frequency range; bit 12 SET = dynamic current limiter. Bits: bit 11 = Accept wide frequency range; bit 12 = Dynamic current limiter. | Reference bit table; value 0x4dfe on 202/214 blocks. Earlier tooling mistook the bytes 'fe 4d' here for a 'device descriptor marker'. | 0x4dfe (device form), 0x6a5f/0x6a55/0x6a7e in a few grafted files |
| 2 | +0x05d | `absorption_V` | Absorption voltage | u16 / 100 | V | CONFIRMED | Charger absorption (bulk end) voltage. With a CAN-bus BMS and DVCC active the BMS charge-voltage limit overrides this; it is the fallback used when the BMS link is absent. | Written by rvms_writer on four systems (2026-07-20) via Remote VEConfigure, read back correct on every inverter; matches VRM 'Absorption' and VEConfigure Charger tab. | 5600, 5650, 5680, 5760 (also 4800 on a mis-commissioned unit, 0 in stub blocks) |
| 3 | +0x05f | `float_V` | Float voltage | u16 / 100 | V | CONFIRMED | Charger float voltage (after absorption). | First live proof of the whole toolchain: float 54.0 -> 54.1 V on both inverters of one system, uploaded, 'Success', read back 54.1 (2026-07-20). Later edits confirmed again. | 5400, 5410, 5420, 5520 |
| 4 | +0x061 | `charge_current_A` | Charge current | u16 | A | HIGH | Maximum battery charge current from the charger. | Reference ID/scale; 35 on every device-form block (a deliberate installer limit, consistent across eight inverters). Not edited by us. | 35 |
| 5 | +0x063 | `inverter_output_V` | Inverter output voltage | u16 | V | HIGH | Nominal AC output voltage of the inverter. | Reference; 120 on 202/214 blocks (these are 120 V units). Upload-form blocks read it at +10. | 120 |
| 6 | +0x065 | `ac1_input_limit_A` | AC input 1 current limit | u16 / 10 | A | HIGH | Shore/grid input current limit for AC input 1 (the persistent value; the GX can override at runtime). | Reference; 500 = 50.0 A on every device-form block, matching the installation's breaker sizing. | 500 |
| 7 | +0x067 | `repeated_absorption_time` | Repeated absorption time | u16 |  | MEDIUM | Duration of a periodic re-absorption cycle (lead-acid curve). | Reference name only. | 2, 4 |
| 8 | +0x069 | `repeated_absorption_interval` | Repeated absorption interval | u16 |  | MEDIUM | Interval between periodic re-absorption cycles. | Reference name only. | 4, 28 |
| 9 | +0x06b | `max_absorption_time` | Maximum absorption time | u16 |  | MEDIUM | Absorption time limit; the reference notes '1 for LiFePO4 fixed'. | Reference. | 1, 8 |
| 10 | +0x06d | `charge_characteristic` | Charge characteristic | u16 | enum | MEDIUM | 0 = variable (adaptive), 1 = fixed, 2 = fixed + storage. | Reference enum; 1 on lithium systems here. | 1, 3 |
| 11 | +0x06f | `dc_low_shutdown_V` | DC input low shut-down | u16 / 100 | V | HIGH | Battery voltage at which the inverter shuts down (low-battery cutoff). | Reference ID/scale. Our differential decode saw this move 37.20 -> 48.50 V on two systems during the installer's 'properly configure' pass and it reads 48.50 on all current blocks; 48.5 V is a sane LFP floor. Labelled '?vs_restart_or_sustain_V' in earlier notes. | 4850, 3720, 4800 |
| 12 | +0x071 | `dc_low_restart_offset_V` | DC input low restart offset | u16 / 100 | V | HIGH | Voltage above the shut-down level at which the inverter restarts. | Reference; 2.00 V fleet-wide (was '?field_71' in earlier notes). | 200, 640 |
| 13 | +0x073 | `unknown_13` |  | u16 |  | UNKNOWN |  |  | 0 |
| 14 | +0x075 | `unknown_14` |  | u16 |  | UNKNOWN |  |  | 0 |
| 15 | +0x077 | `unknown_toggle_15` | Unknown toggle | u16 |  | LOW | The reference notes this 'differs between units'. | Values track the installer's configuration pass (3 on configured, 1/0 on older). | 0, 1, 3 |
| 16 | +0x079 | `param16` |  | u16 |  | UNKNOWN | First of a repeated parameter block (16-18 / 28-30 have the same shape). |  | 2125 |
| 17 | +0x07b | `param17_V` |  | u16 / 100 | V? | LOW | Reads 64.00 -- voltage-like; possibly a DC high alarm/threshold. | Same value as ID 29 and as the unreachable 64.00 V VS-return threshold once set on two systems. | 6400 |
| 18 | +0x07d | `param18_V` |  | u16 / 100 | V? | LOW | Reads 47.00 -- voltage-like. | Same value as ID 30. | 4700 |
| 24 | +0x089 | `param24` |  | u16 |  | UNKNOWN |  |  | 2 |
| 25 | +0x08b | `param25` |  | u16 |  | UNKNOWN |  |  | 2 |
| 26 | +0x08d | `param26` |  | u16 |  | UNKNOWN |  |  | 2 |
| 27 | +0x08f | `param27` |  | u16 |  | UNKNOWN |  |  | 2 |
| 28 | +0x091 | `param28` |  | u16 |  | UNKNOWN | Second copy of the 16-18 block shape. |  | 531 |
| 29 | +0x093 | `param29_V` |  | u16 / 100 | V? | LOW | Reads 64.00. |  | 6400 |
| 30 | +0x095 | `param30_V` |  | u16 / 100 | V? | LOW | Reads 47.00. |  | 4700 |
| 37 | +0x0a3 | `param37` |  | u16 |  | UNKNOWN |  |  | 1 |
| 44 | +0x0b1 | `param44` |  | u16 |  | UNKNOWN |  |  | 90 |
| 45 | +0x0b3 | `param45` |  | u16 |  | UNKNOWN |  |  | 7 |
| 46 | +0x0b5 | `param46` |  | u16 |  | UNKNOWN |  |  | 40 |
| 47 | +0x0b7 | `param47` |  | u16 |  | UNKNOWN |  |  | 5 |
| 48 | +0x0b9 | `param48` |  | u16 |  | UNKNOWN |  |  | 32 |
| 49 | +0x0bb | `ac2_input_limit_A` | AC input 2 current limit | u16 / 10 | A | MEDIUM | Quattro only; 0 on MultiPlus. | Reference; 0 on all our MultiPlus blocks. | 0 |
| 50 | +0x0bd | `vs_param50` | Virtual Switch parameter | u16 |  | LOW | IDs 50-59 hold the Virtual Switch 'ignore AC input' parameters (the reference lists 50-59 as a parameter block). 60 and 40 look like time constants in seconds (1 min / 40 s). |  | 60 |
| 51 | +0x0bf | `vs_param51` | Virtual Switch parameter | u16 |  | LOW |  |  | 40 |
| 52 | +0x0c1 | `vs_param52` | Virtual Switch parameter | u16 |  | LOW | Moves with the VS thresholds across the installer's config pass (833/2125 -> 1750). Earlier notes read it as 17.5 V; watts or a different scale are as plausible. |  | 1750, 2125, 833 |
| 53 | +0x0c3 | `vs_param53` | Virtual Switch parameter | u16 |  | LOW |  |  | 4, 0, 6 |
| 54 | +0x0c5 | `vs_ignore_ac_below_V` | VS: do not ignore AC input when Udc lower than | u16 / 100 | V | CONFIRMED | Virtual Switch 'Ignore AC input' battery condition: leave battery operation and accept the grid when DC voltage drops below this (for the configured time). Entry-to-passthrough threshold. | Matched byte-for-byte to a VEConfigure Virtual Switch tab screenshot (51.40 V) and to the installer's note of lowering it to 51.0 at all sites; later GUI changes landed here. Written by us (rollback files). | 5100 (current), 4700 (old) |
| 55 | +0x0c7 | `vs_param55` | Virtual Switch parameter | u16 |  | LOW | Time-like (20 s?). |  | 21, 6, 0 |
| 56 | +0x0c9 | `vs_param56` | Virtual Switch parameter | u16 |  | LOW | Earlier notes read 15.00 V; unverified. |  | 1500, 531, 625 |
| 57 | +0x0cb | `vs_param57` | Virtual Switch parameter | u16 |  | LOW |  |  | 2, 0 |
| 58 | +0x0cd | `vs_accept_battery_above_V` | VS: ignore AC input again when Udc higher than | u16 / 100 | V | CONFIRMED | Virtual Switch return condition: go back to battery (ignore AC) when DC voltage exceeds this. A value above what the battery can reach (64.00 V on a 48 V LFP) makes passthrough permanent -- the root cause of a 5.6-day stuck-on-grid episode on one system. | Screenshot match (53.00 V); the installer's per-site values (53.0 / 52.5) appear here; edited by us. | 5250, 5300, 6400 (old, unreachable) |
| 59 | +0x0cf | `vs_param59` | Virtual Switch parameter | u16 |  | LOW |  |  | 2, 0 |
| 60 | +0x0d1 | `solar_wind_priority_flags` | Solar & wind priority flags | u16 | bitmask | MEDIUM | Reference: bit 4 (16) = off, 528 = on. | Reference; 16 on bare blocks, 48 after GUI ESS install. | 16, 48, 0 |
| 62 | +0x0d5 | `param62` |  | u16 |  | UNKNOWN |  |  | 41667, 41666 |
| 63 | +0x0d7 | `param63` |  | u16 |  | UNKNOWN |  |  | 32668, 32768 |
| 64 | +0x0d9 | `battery_capacity_Ah` | Battery capacity | u16 | Ah | HIGH | Capacity used by the inverter's built-in battery monitor; 0 disables the monitor. | Reference; 200 / 300 Ah match the installed EG4 module counts (2 x 100 Ah vs 3 x 100 Ah). | 200, 300, 0 |
| 65 | +0x0db | `soc_at_bulk_end_pct` | SoC when bulk finished | u16 / 2 | % | HIGH | State of charge the built-in monitor assumes at the end of bulk (x0.5 %). | Reference: '190 = 95 % for LiFePO4'; we see 190 and 196 (98 %) -- the one-byte difference between systems that puzzled us for a week ('+0xdb be vs c4'). | 190, 196, 170 |
| 66 | +0x0dd | `param66_V` |  | u16 / 100 | V? | LOW | 57.72 V -- voltage-like; possibly a second (lead-acid default) charge profile paired with 68. |  | 5772 |
| 67 | +0x0df | `param67` |  | u16 |  | LOW | Changed 04 -> 02 by the GUI ESS install on one inverter. |  | 3, 2, 4 |
| 68 | +0x0e1 | `param68_V` |  | u16 / 100 | V? | LOW | 54.00 V -- voltage-like, pairs with 66. |  | 5400 |
| 69 | +0x0e3 | `param69` |  | u16 |  | LOW | Changed 1c -> 04 by the GUI ESS install on one inverter. |  | 3, 4, 28 |
| 70 | +0x0e5 | `param70` |  | u16 |  | LOW | 0 -> 50 during the installer's configuration pass ('?flag_e5'). |  | 50, 0 |
| 71 | +0x0e7 | `param71` |  | u16 |  | UNKNOWN |  |  | 32768 |
| 72 | +0x0e9 | `charge_efficiency` | Battery charge efficiency | u16 |  | MEDIUM | Reference: 242 is about 95 % for LiFePO4. | Reference. | 250, 242, 255 |
| 73 | +0x0eb | `voltage_threshold_73_V` | Voltage threshold | u16 / 100 | V | MEDIUM | Reference calls it a voltage threshold that 'varies significantly'. Ours reads 63.00 V everywhere, the same value as the DC over-voltage protection trip we found in the alarm history. | Value coincidence with a known protection level; not toggled. | 6300 |
| 74 | +0x0ed | `param74` |  | u16 |  | UNKNOWN |  |  | 200 |
| 81 | +0x0fb | `grid_code_active` | Grid code active flag | u16 | flag | HIGH | 1 when a grid code (country standard) has been set with the dealer password in VEConfigure. | Reference; 0 on every bare block, 1 on every GUI-authored ESS block. Part of the 'grid-code fingerprint' our failed grafts tried to stamp. | 0, 1 |
| 85 | +0x103 | `param85` |  | u16 |  | UNKNOWN |  |  | 65535 |
| 87 | +0x107 | `param87` |  | u16 |  | UNKNOWN |  |  | 829 |
| 88 | +0x109 | `solar_wind_priority_V` | Solar & wind priority (sustain) voltage | u16 / 100 | V | MEDIUM | Reference: sustain voltage for solar & wind priority. | Reference; 52.00 V everywhere. NOTE: earlier notes decoded a 'VS SOC threshold = 20 %' at +0x10a. That byte is the high byte of this value (5200 = 0x1450). The Virtual Switch SoC threshold is NOT located; treat the old 'vs_soc_pct' field as a decode error. | 5200 |
| 128 | +0x159 | `lom_config_a` | LOM configuration A | u16 |  | LOW | Loss-of-mains configuration (grid code related). 0xffff on bare blocks; the GUI ESS install writes 1 / 0x0101. | Reference name; observed transition. | 65535, 1, 257, 65281, 0 |

IDs not listed read zero on every block (19–23, 31–36, 38–43, 61, 75–80, 82–84, 86, 89–127) or
0xffff (129–189 on bare blocks); they are omitted from the table but visible with `rvms decode --all`.

## How to add or promote a field

The differential method is what produced everything above; it needs no Windows and no source.

1. **Bracket one change.** Download the file, make exactly one change in VEConfigure (or have your
   installer make it), download again. `rvms diff before.rvms after.rvms` names the setting IDs that
   moved. One change at a time, or you cannot tell which is which.
2. **Look for lockstep.** A real setting changed by an installer's "configure properly" pass moves on
   both inverters of a pair at once and converges to the same standard value across systems. Timestamps,
   pointers and checksums move on every save and are never settings (`rvms.units.VOLATILE_DEVICE`).
3. **Anchor to a screen.** One screenshot of the VEConfigure tab showing the value turns a candidate into
   a CONFIRMED entry in seconds; it is how the Virtual Switch thresholds were pinned.
4. **Check the scale on the corpus.** A voltage should decode to a voltage on every block, not just yours.
   `tests/test_claims.py::test_confirmed_and_high_fields_decode_to_sensible_values` is where such a
   check belongs.
5. **Write it down with its evidence.** Add a `Field` to `rvms/fields.py` with `evidence` and `observed`
   filled in, regenerate this table, and say what you did not verify. A field promoted without evidence
   will be demoted in review.

Things that cannot be found this way: fields that never vary across the files you hold (grid code, phase
count, AC input current limit on a fleet where they are all the same). Those need either a screenshot or
a deliberate change.
