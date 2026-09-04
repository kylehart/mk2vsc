# Changelog

## 0.5.0 (2026-09-04)

* Every setting index 0 to 191 now carries VEConfigure's own identifier (`Field.eprom`, `EPROM_NAMES`), from the identifier table published by talas9/rvsc-tools (MIT). Settings above 65 renamed from those identifiers: `fs_ubat_start_V` .. `fs_ubat_stop_delay_s`, `vs_dont_ignore_soc_below_pct` (= vs2StartOnSOC), `inverter_current_limit_during_assist_A` (73 was mislabelled a voltage), `abs_to_float_soc_reset_pct`, `ubat_dont_charge_V`, `grid_settings_valid_checker_a`, reserved and grid-code slots.
* `vs_usage` and `charge_characteristic` enum option text from VEConfigure.
* README: related projects; the "no prior art" statement corrected.

## 0.4.1 (2026-09-04)

* `mk2vsc census` is now the self-check report contributors are asked for: structure, checksum status, schema parse, settings-in-range count, key values per inverter, and the reporting hint. Contribution docs and issue forms lead with it; the fixture form is replaced by a census-report form.
* Frequency decode fixed (Hz = 2500000 / raw).

## 0.4.0 (2026-09-04)

* Settings 0 to 65 and all flag bits now carry Victron's own names from the public MK2 Protocol 3.14 document; 63 of 80 named fields are HIGH confidence. New: Virtual Switch relay-mode settings 15 to 43, mains voltage window 44 to 47, assist boost factor 48, AES current limit 50/51, low-battery pre-alarm offset 63, three-phase mode 14, slave count 13.
* Renamed: `grid_code_active` -> `grid_code`, `solar_wind_priority_flags` -> `flags2`, absorption timers gain `_min`.
* Values with a schema offset (durations, pre-alarm offset, highest mains voltage) decode and encode correctly.

## 0.3.0 (2026-09-04)

* `BareSettingInfo` decoded as the device settings schema: one 10-byte record per setting with scale, offset, default, min and max (`mk2vsc.schema`). The writer now refuses raw values outside the device's own range; the fields table shows each setting's default and range.
* From the schema: Virtual Switch durations are `raw - 1` seconds/minutes (MEDIUM, editable with `--allow-unverified`), setting 62 is the output frequency (60.00 Hz, stored as a period), charge efficiency is `(raw + 1) / 256`, settings 63/71 are signed offsets, 70/74 percentages, 81 a 0..32 grid-code index.
* Field values now honour the schema offset (e.g. `vs_udc_below_for_s=20`).

## 0.2.1 (2026-09-04)

* Virtual Switch block decoded from the VEConfigure tab and the same-period download (issue #8): load thresholds are current in 0.01 A (`vs_load_high`, `vs_load_low`, HIGH, editable), SoC-lower is setting 51 at x0.5 % (MEDIUM), SoC-higher 50 (LOW), durations 53/55/57/59 located but encoding unknown. Settings 16 to 18 and 28 to 30 identified as a second copy of the same conditions.

## Unreleased

* Installations are referred to by public aliases System A to D. Fixture directories and files are
  `system_a` ... `system_d`; the manifest key `site` is now `system` with values `A` ... `D`.
  `tools/leakscan.sh` refuses the former names.

## 0.2.0 (2026-09-04)

Redesigned for first use. No backward compatibility with 0.1.x command names.

* CLI is now `show`, `edit`, `verify`, `check` (the loop), plus `diff`, `history`, `validate`, `fields`,
  `census`, `experimental`. `edit` writes `<file>.edited.rvms` next to the input and never overwrites it;
  `check --expect field=value` needs no intent file; `verify` is the one-command post-upload proof.
* Field aliases: `absorption`, `float`, `charge_current`, `ac_limit`, `low_shutdown`, `restart_offset`,
  `vs_entry`, `vs_return`, `capacity`, `soc_bulk_end`, `grid_code`; numeric setting IDs accepted.
* Python facade: `mk2vsc.load()`, `Config.set/set_many/save/check/diff/summary`, `Unit[...]`, `mk2vsc.verify()`.
* `show` groups settings by function, hides low-confidence entries unless `--all`, flags inverter disagreement.
* Removed: `info`, `decode`, `set`, `qualify`, `fix` (use the library for checksum repair).

## 0.1.1 (2026-09-04)

* Packaging only: release workflow renamed to `release.yml` to match the PyPI trusted publisher; first PyPI publish. No code changes.

## 0.1.0 (2026-09-03)

Initial extraction into a standalone repository from the tooling we built while operating four
MultiPlus systems between June and September 2026.

* Section parser and serializer with byte-exact round trip (`mk2vsc/sections.py`).
* Integrity checksum: a plain 32-bit little-endian word sum over every section from its length prefix.
  This replaces the earlier description "sum from block offset 2 plus the constant 0x6142000F"; the
  constant was the section's own first word.
* Per-inverter block model with device-form and upload-form detection (`mk2vsc/units.py`).
* Settings table keyed by VE.Bus setting ID (array of 190 u16 at block offset +0x59) with a
  confidence level per field (`mk2vsc/fields.py`). The earlier field `vs_soc_pct` at +0x10a is retracted;
  that byte is the high byte of setting 88.
* Decoder, by-serial diff with bookkeeping classification, guarded length-preserving writer,
  intent-based qualifier, read-only assistant-area parser, and the `mk2vsc` CLI.
* Experimental package `mk2vsc.experimental` (ESS graft, device-to-upload-form transform), gated behind
  `--i-accept-the-risk`, with regression tests against the August 2026 attempt files; docs/ESS_INJECTION.md
* Corpus of 84 unique fixture files with manifest, and 468 tests that check every documented claim
  against it.
* Documentation: FORMAT, FIELDS, CHANGE_CONTROL, WORKFLOW, SAFETY, QA, ASSISTANTS, ERRORS, HISTORY,
  FIXTURES.
