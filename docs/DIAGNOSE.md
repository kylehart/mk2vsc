---
title: "mk2vsc diagnose: configuration problems read from the settings"
description: "The diagnose rules, their evidence, the report_version 1 JSON contract, fixes through the writer's guards, and the manual change sheet."
---

# `mk2vsc diagnose`

`diagnose` reads a Remote VEConfigure download and reports configuration problems from the settings
themselves, with the evidence for each, a proposed fix the user may take or leave, a corrected file built
through the writer's guards, and a manual change sheet for anyone who prefers to type the same change into
VEConfigure.

```
mk2vsc diagnose download.rvms
mk2vsc diagnose download.rvms --assume chemistry=lithium
mk2vsc diagnose download.rvms --fix --accept D1:HQ0000A0002
mk2vsc diagnose download.rvms --fix --accept D1:HQ0000C0001 --set absorption=56.8 float=54.0 low_shutdown=48.0
mk2vsc diagnose download.rvms --sheet --accept D2 --copy-from HQ0000A0001
mk2vsc diagnose download.rvms --json
```

Findings are observations with evidence, not verdicts: "absorption is 48.00 V, the schema minimum; default
57.60 V; a lithium bank above that voltage is never charged", never "misconfigured". Nothing is applied
silently: `--fix` writes `<FILE>.corrected.rvms` only for the finding ids named with `--accept`, the input is
never touched, and the corrected file goes through `set_settings` and `set_bits` with every guard they have
(docs/SAFETY.md). A fix that needs a value the file cannot supply asks for it (`--set FIELD=VALUE`); no
generic chemistry template is ever proposed. A copy fix with no automatic source asks for `--copy-from`.

## Two confidences per finding

- **Decode confidence** is the weakest field the finding read, from the settings table (CONFIRMED, HIGH,
  MEDIUM, LOW, UNKNOWN; docs/FIELDS.md). A fix is only offered for CONFIRMED and HIGH fields.
- **Evidence class** is how sure we are of the *behavioural* claim: `device-confirmed` (a before/after on
  hardware), `vendor-documented` (a Victron citation), or `inferred` (a corpus or forensic pattern). Decode
  certainty does not transfer to behaviour.

## Chemistry

Rules that depend on the battery chemistry read it from `--assume chemistry=lithium|lead-acid` when given,
else infer lithium when any inverter of the file carries the LithiumBattery flag (setting 60 bit 4; the two
inverters of a pair share one battery), else mark their findings `conditional` and list the question. The
report's `questions` array names every such question and the findings it affects.

## The rules (Phase 0)

Every rule names the corpus fixture that triggers it, and `tests/test_diagnose.py` counts its hits over the
whole device-form corpus (82 files, 164 blocks at 0.11.0); the counts below are those tests' numbers.

| id | Finding | Signature | Severity | Evidence class | Corpus hits | Fix |
|---|---|---|---|---|---|---|
| D1 | Lead-acid factory profile on a lithium bank | Lithium chemistry (stated or inferred) and two or more of: LithiumBattery flag clear; absorption or float at the schema minimum or at the lead-acid schema default; flags0 bit 11 set; charge curve 3 (adaptive + BatterySafe); low-voltage shutdown at the schema default; capacity 0 Ah; VS return at the schema default | BLOCKS when absorption sits at the schema minimum (the bank is never charged), else DEGRADES | device-confirmed (talas9's 24 V case; three of eight fleet inverters) | 48 | copy the profile from the other inverter when exactly one passes D1 and carries the flag; else enter absorption, float and low-voltage shutdown; set the LithiumBattery flag; curve to 1. Storage mode (flags0 bit 11) is reported, not written: that bit is not yet qualified |
| D2 | Paired inverters disagree on a shared battery | Different values on any CONFIRMED charger field, or a different LithiumBattery flag | DEGRADES | device-confirmed | 44 | copy from the one block that passes D1; when both pass or both fail, the user names the source (`--copy-from`). Conditional on `shared_battery` |
| C1 | Setpoint at the edge of its allowed range | `mk2vsc.limits.at_limits()`: a CONFIRMED/HIGH physical setting at its schema minimum or maximum when that limit is not the default | DEGRADES | inferred (heuristic after talas9/rvsc-tools) | 14 | enter the intended value |
| V1 | Low-voltage shutdown at the lead-acid default | `dc_low_shutdown_V` equals the file's schema default (37.20 V on the 48 V model) with lithium chemistry | FRAGILE | inferred (fleet forensics: a blackout at 48.5 V while SOC read 39 %) | 18 | enter a floor for this battery |
| V2 | Virtual Switch return threshold unreachable | VS in use, no assistant, and `vs_accept_battery_above_V` at or above `absorption_V` or at its schema default (64.00 V on the 48 V model) | FRAGILE | inferred (a 5.6-day pass-through episode) | 11 | enter a return voltage below absorption |
| E1 | Failed by-file assistant install (empty stub) | the `40 00 a7 fe` container signature in the assistant area | BLOCKS | device-confirmed (four corpus downloads) | 6 | by file only through `mk2vsc assistant reinstall` from an earlier download carrying the assistant (resets the VE.Bus); else VEConfigure. The writer refuses the file until then |
| E2 | Assistant on one inverter of the pair | records on one block, none on the other | BLOCKS | device-confirmed (System C, 2026-07-17 to 07-20) | 10 | as E1; names the inverter that lacks it. Conditional on `ess_intended` |
| P3 | Upload-form file offered as device state | the 16-byte GUI export blob at +0x45 | INFO | device-confirmed | 7 files | none: diagnose a fresh device download |

Every voltage in this table is the 48 V model's number; a rule reads the file's own schema default and
range, so it holds on 12 V and 24 V units. No 12 V, 24 V, Quattro, three-phase or single-unit `.rvsc` file
is in the corpus: on such a file the rules run but nothing has been confirmed (issue #14).

## File status

`diagnose` reports one of: `ok`, `unparseable`, `checksum_invalid`, `duplicate_serial`, `upload_form`,
`no_schema`, `misaligned`. Rules run only on `ok`. A single-unit `.rvsc` saved by VEConfigure on a PC is not
supported: if it parses, every finding carries the note "unverified on single-unit .rvsc files"; if it does
not, the message says so and points at issue #14.

`editable` says whether the writer would accept the file (checksums, device form, no stub, schema, nominal
voltage, alignment), and `refusal_reason` carries the writer's own words when it would not. The change sheet
is produced either way.

## Report contract (`--json`, `report_version` 1)

```
report_version: 1
files[]:     name, status, message, serials[], editable, refusal_reason, nominal_voltage, chemistry,
             chemistry_source (stated | flag:<serials> | unknown), unverified_format
findings[]:  id (stable: RULE or RULE:SERIAL[:FIELD]), rule, title, severity (BLOCKS | DEGRADES | FRAGILE | INFO),
             decode_confidence, evidence_class, conditional[] (question ids), serials[],
             evidence[]: serial, field, label, unit, raw, value, schema_min, schema_max, schema_default, confidence, vote,
             message, file, note,
             fix: null
                | {kind: "copy",   source | null, candidates[], targets[], fields[], bit_edits[]}
                | {kind: "values", needs_value[]: {serial, field, unit, current, schema_min, schema_max, schema_default},
                                   edits[]: {serial, field, value}, bit_edits[]: {serial, field, bit, set}}
                | {kind: "gui",    text, lacks[]}
questions[]: id, text, affects[] (finding ids)
intent:      {edits[], bit_edits[]}   only after --fix or --sheet; the same record is written to <out>.intent.json
```

A page or script refuses a `report_version` it does not know.

## The manual change sheet

`--fix` and `--sheet` print, per inverter, where the setting lives in VEConfigure (tab › group › label, from
`Field.ui`, docs/FIELDS.md "In VEConfigure"), the value now and the value after. A field with no known
placement prints "(tab unknown)" rather than a guess. A flag bit prints as the box's ticked/unticked state,
honouring boxes that are ticked when the bit is clear.

## Nominal voltage

`mk2vsc.schema.nominal_voltage()` reads 12, 24 or 48 V from the absorption record's minimum in the file's
own schema and refuses anything else. The writer scales its voltage plausibility bounds by nominal/48, so a
24 V correction is accepted where it was refused before. Observed: 48 V on every corpus file. Inferred: 24
and 12 V from the schema convention (talas9's 24 V unit reads absorption 24.00 to 32.00 V).

## Bit-level writes

`set_bits` sets or clears one bit of a flag register. The target bit must be inside the register's settable
mask (the schema's `max` for a flag register); the whole-word range check is skipped because observed
flags0 words (0x81f4 on every device block) exceed the 0x6ffc mask. Without an override only qualified bits
are written: a bit qualifies when the corpus or a device holds a before/after flip of exactly that bit,
authored by VEConfigure or the device, on a system that subsequently ran, with no other bit of the register
changing. Today that is the LithiumBattery bit (setting 60 bit 4), on System A unit 1's commissioning
download. Flags0 bit 11 (three published meanings) and bit 8 (DisableAES) wait for such a flip.

## What Phase 0 has not done

- No file from outside the four fixture systems has produced a finding confirmed in VEConfigure. That is the
  exit criterion before the rules are treated as validated beyond this fleet.
- Storage mode on lithium (C4), absorption above the module limit (C3), and the remaining catalogue rules
  wait for a fixture that exhibits them or for a qualified bit.
