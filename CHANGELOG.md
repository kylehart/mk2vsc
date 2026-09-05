# Changelog

## Unreleased

* `mk2vsc.census.census_text(data, name)`, `mk2vsc.api.verify_bytes(prepared, redownload)` and `mk2vsc.history.snapshots_from_bytes([(name, data)])`: the `census`, `verify` and `history` verbs on bytes already in hand, for callers that hold files in memory; the CLI runs through them, so the two cannot disagree.
* `mk2vsc diagnose`: configuration problems read from the settings themselves, with evidence, a fix to take or leave, a corrected file through the writer's guards (`--fix --accept ID`, `--set FIELD=VALUE`, `--copy-from SERIAL`) and a manual change sheet (`--sheet`); `--json` is the `report_version` 1 contract. Eight rules: D1 lead-acid profile on a lithium bank, D2 pair disagreement, C1 range edge (over `limits`), V1 low-voltage shutdown at the lead-acid default, V2 unreachable Virtual Switch return, E1 stub, E2 half-loaded assistant, P3 upload form. Every finding carries decode confidence and an evidence class (device-confirmed / vendor-documented / inferred). A conditional finding's fix is refused until its question is answered (`--assume chemistry=`, `shared_battery=`, `ess_intended=`); a copy source is proposed only from a clean lithium block; conflicting values for one setting are refused; `--sheet` runs the writer's guards; an output that is the input or a link to it is refused; `--json` stays one document under `--fix`; the intent sidecar is readable by `check --intent`. Corpus hit counts are asserted by the tests (82 device-form files, 164 blocks). docs/DIAGNOSE.md.
* `mk2vsc.schema.nominal_voltage()`: 12, 24 or 48 V from the absorption record's minimum; the writer's DC voltage plausibility bounds (`fields.DC_VOLT_IDS`) scale with it instead of assuming a 48 V system (synthetic 24 V and 12 V twins accept absorption 28.4 V and the AC output voltage unchanged).
* `set_bits`: set or clear one bit of a flag register, target bit checked against the schema's settable mask; only qualified bits without an override (today the LithiumBattery bit, setting 60 bit 4).
* The writer refuses the grid-code block and its validity words, settings 81, 128, 129-189, 190 and 191 (`fields.GRID_CODE_LOCKED`), with no override flag; `EDITABLE` excludes them. Observed 2026-09-04: a live System A took a device-form file that changed only setting 191 (0x0101 -> 0xff00); it was not refused before the reset began, the dialog ran "Resetting VE.Bus products", and the GX went offline within ten seconds (docs/HISTORY.md, docs/SAFETY.md); cause Unknown pending the re-download. 128/191 descriptions carry VEConfigure's GridSettingsValidCheckerA/B name. mk2vsc-36 reading (a) recorded as tested: a 191-only mismatch is not a pre-write gate. The CLI flag is `--allow-unverified` in every doc.
* The +0x4f timestamp is a file-generation stamp, not an acceptance gate: four System B fixtures from 2026-09-04 (three downloads of unchanged content with increasing stamps, and a back-stamped file the device accepted) and a test. mk2vsc-36 rewritten around the observed rejections; the fixtures show the device had written its grid-code words (190/191) during the August attempts and the archived files it refused carried the earlier words, but a device-form file with differing words was accepted on 2026-08-14, so the cause is recorded as unknown with both readings. Rule 2 kept as practice. 92 fixtures.

## 0.10.0 (2026-09-04)

* `mk2vsc assistant remove` and `mk2vsc assistant reinstall`: remove an assistant from a system, or reinstall the one an earlier download of the same system carried, as upload-form files. Proven on one live system on 2026-09-04 (ESS removed and put back; re-downloads verified). Uploading them resets the VE.Bus, as any assistant change does, GUI included; `--resets-the-vebus` acknowledges that.
* The upload-form transform moved from `mk2vsc.experimental` to `mk2vsc.upload_form`; `experimental to-upload-form` is gone, `experimental graft` (first-time install from another system's records) stays gated and unproven.
* Four System D fixtures from the cycle (post-T5 ESS download, the accepted removal file, the bare re-download, the ESS re-download); 88 files.
* Settings 128/191 also take 0x0201 and 0x0301 (System D); descriptions updated.
* docs: during a Remote VEConfigure operation, GX-based monitoring can report the site disconnected for under a minute and carry a stale inverter state while the MK2 tunnel holds the VE.Bus port (observed on two systems; inverter behaviour not measured independently); not a file fault; health checks must allow for the window (WORKFLOW "Monitoring during a remote operation", CHANGE_CONTROL Rule 4).

## 0.9.0 (2026-09-04)

* VEConfigure placement for every setting and flag bit the GUI shows (`mk2vsc/ui.py`): tab, group and field label, from the layout talas9/rvsc-tools observed on VEConfigure 1.33 (MIT, credited), keyed by identifier. `Field.ui`, `mk2vsc fields --by-tab`, and an "In VEConfigure" column in docs/FIELDS.md. 62 settings and 32 bits placed; 7 GUI fields are computed by the GUI from other settings; 6 have no known setting. The Ignore AC input tab (settings 52 to 59, 70) is placed from our own screenshot; UPS function (setting 0 bit 3, inverted) and Dynamic current limiter (setting 1 bit 12) from Victron's MK2 document and xcellsior's toggle-and-diff. NOTICE.md gains a third-party section with the MIT notice.
* Flag bits 3 to 9 of setting 60 named from VEConfigure's identifiers; VEConfigure option text for the grid-code list (0 to 22) recorded in `mk2vsc.ui.ENUMS`.

## 0.8.0 (2026-09-04)

* The settings array is 192 entries. Settings 190 and 191 are grid-code words (0xffff until a grid code is set; then 190 = 0xfff5 and 128 = 191 = 1 or 0x0101, set per inverter; partly retained after a grid code is removed). They were previously read as the assistant record's "marker" and "subtype"; the assistant area now starts at +0x1d9 as `u16 length | body | tail`. `grid_code_words()` reports never / set / residual; `census` prints it; `show` lists 190/191. Settings 128/190/191 descriptions updated. Issue #24 re-stated: the differing word is setting 191, set per inverter by the grid-code step; System C's two inverters carry different values.

## 0.7.0 (2026-09-04)

* `show` prints the alignment self-check under each inverter and marks any physical setting sitting at the minimum or maximum of its own schema range when that limit is not the default (`mk2vsc.limits`). On the fixture corpus this marks exactly the blocks commissioned with absorption = float = 48.00 V.
* `check` fails a block whose settings array does not align with the device schema and warns on at-limit settings.

## 0.6.0 (2026-09-04)

* Fixture serials are pseudonyms (`HQ0000A0001` style); every other byte unchanged, checksums recomputed. The leak scan refuses real-format serials.
* Alignment self-check (`mk2vsc.align`): the settings-array offset is scored against the file's own schema ranges; `census` reports it and the writer refuses files whose array is not where the layout model expects.
* CI checks that the generated settings table in docs/FIELDS.md matches `fields.py` (`tools/check_generated.py`).

## 0.5.1 (2026-09-04)

* Documentation site at https://kylehart.github.io/mk2vsc/ (GitHub Pages from `docs/`), CITATION.cff, NOTICE.md (interoperability and trademark notice, editing guards stated), PyPI project links, README opening rewritten around the terms people search for. No code changes.

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
