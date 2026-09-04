# mk2vsc

[![tests](https://github.com/kylehart/mk2vsc/actions/workflows/test.yml/badge.svg)](https://github.com/kylehart/mk2vsc/actions/workflows/test.yml) [![PyPI](https://img.shields.io/pypi/v/mk2vsc.svg)](https://pypi.org/project/mk2vsc/) [![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Read, validate, decode, diff, edit and verify Victron VEConfigure `.rvms` configuration files (the
files VRM Remote VEConfigure downloads and uploads for MultiPlus and Quattro systems) on macOS, Linux
or Windows, without VEConfigure. Zero dependencies, Python 3.9+. Includes the file format as we
understand it, the per-section checksum, the settings table with Victron's names, and what the
`mk2vsc-36`, `mk2vsc-47` and `mk2vsc-49` upload errors mean. Documentation: https://kylehart.github.io/mk2vsc/

## The problem

Victron MultiPlus and Quattro inverter/chargers are configured with VEConfigure and VE.Bus System
Configurator. Those tools run only on Windows. VictronConnect is replacing them but does not support
assistants (ESS, AC PV and the rest), so anyone maintaining a real installation still needs a Windows
machine or a virtual machine. The configuration itself travels as a small binary file: `.rvsc` for a
single unit, `.rvms` for parallel and multi-phase systems, downloaded and uploaded through VRM's Remote
VEConfigure. A Victron Community thread titled "RVSC File Format Specification" asked Victron to publish
the format so people could write their own editors; it received no answer. When we started (June 2026) we
found no open-source parser, specification or editor for these files; one has since appeared for the
single-unit `.rvsc` format (see Related projects below), and the two agree where they overlap.

We operate four two-inverter systems and needed to change charge voltages and Virtual Switch
thresholds on them remotely, repeatably, and with a record of what changed. This repository is what we
built to do that, together with everything we learned about the file along the way.

## What this is

* A zero-dependency Python 3.9+ library and a CLI (`mk2vsc`) that:
  * parses the file's section structure and verifies every integrity checksum,
  * decodes the per-inverter settings array into labelled values with a confidence level per field,
  * compares two files by inverter serial and tells you whether they differ only in bookkeeping,
  * edits settings in place, self-verifies that nothing else changed, and never changes file length,
  * qualifies a file against the values you intended before you upload and after you re-download,
  * mines a library of archived downloads into a dated, per-inverter change log (`mk2vsc history`).
* A corpus of 88 real device files with a manifest, and a test suite that checks every documented
  claim against that corpus (528 tests).
* A written account of the format as we understand it, and of what we do not understand.

## What this is not

* It does not upload anything. You upload through VRM, exactly as before.
* It does not install an assistant on a system that never had one. It can remove an assistant and
  reinstall one from an earlier download of the same system (`mk2vsc assistant`, docs/ASSISTANTS.md);
  the graft for a first-time install stays under `mk2vsc.experimental`, gated and unproven.
* It does not touch grid codes or the dealer password that protects them.
* It is not affiliated with or endorsed by Victron Energy.

## Status and confidence

| Capability | Status | Evidence |
|---|---|---|
| Section grammar and integrity checksum | Proven | Validates on every section of all 88 fixture files (111 counting archive duplicates); edited files accepted by the device on 4 systems |
| Settings array = VE.Bus setting IDs at +0x59 + 2n | High | Reference IDs reproduce 120 V output, 50.0 A limit, 95 %/98 % SoC, grid-code flag on all 170 blocks of the 85 well-formed fixtures |
| Field table (192 entries) | Partial | every ID carries VEConfigure's identifier; 94 settings and bits placed on VEConfigure's tabs (`mk2vsc fields --by-tab`); decode confidence 4 CONFIRMED, 68 HIGH, 9 MEDIUM, 12 LOW, 99 UNKNOWN (reserved and grid-code slots) |
| Guarded writer (`mk2vsc edit`) | Proven live | Absorption, float and Virtual Switch thresholds written and read back on 4 systems, July to August 2026 |
| By-serial diff (`mk2vsc diff`) | Proven | Consecutive downloads, including a pair whose blocks swapped position, classify as bookkeeping only |
| Checker (`mk2vsc check`) | Proven | Reproduces the incident that motivated it (a rollback that reverted a charge-voltage fix) |
| Assistant area | Read; remove and reinstall | Record structure and stub signature recognised; record bodies not understood. `mk2vsc assistant remove` and `reinstall` removed and re-installed ESS on one live system (2026-09-04), re-downloads matching byte for byte apart from bookkeeping |
| Upload-form (GUI export) files | Read only | Detected and decoded; the writer refuses them |
| First-time ESS install (`mk2vsc experimental graft`) | Experimental, never ran | Grafts of another system's records stored but never started; the upload-form transform they rely on is now proven by `mk2vsc assistant` |

The confidence vocabulary (CONFIRMED, HIGH, MEDIUM, LOW, UNKNOWN) is defined in `mk2vsc/fields.py` and
docs/FIELDS.md. The writer edits CONFIRMED and HIGH fields; anything lower needs an explicit override.

## Install

```
pip install mk2vsc
```

Or from source, with the fixture corpus and tests:

```
git clone https://github.com/kylehart/mk2vsc.git && cd mk2vsc
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest          # 528 tests against the fixture corpus
```

## Quickstart: one download, one change

Download the file from VRM (Device list, Remote VEConfigure, Download). Then:

```
mk2vsc show download.rvms
```
```
download.rvms: 5055 bytes, 2 inverter(s), form=device, checksums OK
  HQ0000A0002: firmware 2729560, saved 2026-07-20T18:41:22+00:00, assistant: no assistant
    alignment OK (+0x059, 138/138 in range)
  HQ0000A0001: firmware 2729560, saved 2026-07-20T18:41:28+00:00, assistant: no assistant
    alignment OK (+0x059, 138/138 in range)
  Charger
    absorption_V        Absorption voltage       57.6 V    56 V   <- inverters differ
    float_V             Float voltage            55.2 V    54 V   <- inverters differ
    charge_current_A    Charge current             35 A    35 A
    ...
```

Change what needs changing. The output is written next to the input; the input is never touched:

```
mk2vsc edit download.rvms absorption=56.8 float=54.0
```
```
  HQ0000A0002  absorption_V   57.6 -> 56.8 V
  HQ0000A0001  absorption_V   56.0 -> 56.8 V
  HQ0000A0002  float_V        55.2 -> 54.0 V
  HQ0000A0001  float_V        54.0 -> 54.0 V (unchanged)

wrote download.edited.rvms
verified: only those bytes and their section checksums changed; the input file is untouched.

Next:
  1. VRM > Device list > Remote VEConfigure > Upload: download.edited.rvms
  2. Download again from the same page.
  3. mk2vsc verify download.edited.rvms <the new download>
```

After the upload, prove the device took exactly your change and nothing else, and that the values are
what you intended on both inverters:

```
mk2vsc verify download.edited.rvms redownload.rvms
mk2vsc check  redownload.rvms --expect absorption=56.8 float=54.0
```

That is the whole loop. `show`, `edit`, `verify`, `check`; plus `diff` for any two files, `history` for
a folder of old downloads, `validate`, `fields`, and `experimental` (read docs/ESS_INJECTION.md first).
Field names take aliases (`absorption`, `float`, `charge_current`, `ac_limit`, `low_shutdown`,
`vs_entry`, `vs_return`, `capacity`), full names from `mk2vsc fields`, or VE.Bus setting IDs.

From Python, the same loop:

```python
import mk2vsc

cfg = mk2vsc.load("download.rvms")
print(cfg["HQ0000A0001"]["absorption"])        # 56.0
cfg.set("absorption", 56.8)                      # every inverter
cfg.set("float", 54.0)
path = cfg.save()                                # download.edited.rvms
# upload through VRM, download again, then:
ok, report = mk2vsc.verify(path, "redownload.rvms")
ok, results = mk2vsc.load("redownload.rvms").check(absorption=56.8, float=54.0)
```

## When you run a fleet: the change-control loop

Uploading a file replaces the whole configuration of every inverter in the system. These five steps
are how we make that safe; docs/CHANGE_CONTROL.md explains each one and the incident behind it.

1. Download a fresh file from VRM (Remote VEConfigure) into `00_baseline/`. Never start from an
   archived copy: the device rejects stale save timestamps, and old files carry old values.
2. `mk2vsc edit` the baseline into `01_prepared/`, then `mk2vsc check` it against the values you intend
   (on the command line, or an intent file that lives outside the file under test).
3. Upload `01_prepared/` through VRM.
4. Download again into `02_downloaded/`.
5. `mk2vsc verify` prepared against downloaded and `mk2vsc check` the download. "Success" in the upload dialog is not the same as "the settings are right".

## Corpus and tests

The `fixtures/` directory holds 88 unique files from 4 split-phase MultiPlus systems (8 inverters,
firmware 2729560, format version 1.33) collected between June and September 2026, including device
downloads, GUI exports, files our tools produced, and three deliberately broken files kept as negative
controls. `fixtures/manifest.json` records each file's hash, origin, state and inverters. The tests in
`tests/` check structure, checksums, byte-exact round trips, every documented field claim, the writer,
the diff, the qualifier and the CLI against that corpus. docs/QA.md describes how to verify the same
things on your own system before trusting the tool with it.

## Documentation

| File | Contents |
|---|---|
| docs/FORMAT.md | The file format as we understand it: sections, checksum, unit block layout, device vs upload form, assistant area |
| docs/FIELDS.md | The settings table: every field's offset, label, scale, confidence, presumed purpose and evidence |
| docs/CHANGE_CONTROL.md | The baseline / prepared / downloaded pattern, the rules, and the incidents that produced them |
| docs/WORKFLOW.md | Working with VRM Remote VEConfigure, and what still needs the Windows GUI |
| docs/SAFETY.md | Responsible use, the proven-safe surface, recovery, first-use protocol |
| docs/QA.md | How to decide whether to trust this: the test suite, the corpus, and a verify-it-yourself recipe |
| docs/ASSISTANTS.md | What we know and do not know about ESS and other assistants in the file |
| docs/ERRORS.md | What mk2vsc-36, mk2vsc-47, mk2vsc-49, Error 1303 and the VE.Bus errors mean |
| docs/HISTORY.md | How this came to be, in order, including the things we got wrong |
| docs/ESS_INJECTION.md | The ESS-by-file experiment in full: what a GUI install writes, every attempt, hypotheses, the next test |
| docs/FIXTURES.md | What every file in the corpus is |
| docs/PRACTICES.md | How the project is run: public record, evidence rules, safety rules, AI-assistance disclosure |

## Limits and unknowns

* We hold files from one firmware (2729560), one format version (1.33), one product family, one
  topology (two inverters, split phase). Other hardware may differ; the tests will tell you.
* We have no `.rvsc` single-unit files and no three-phase or three-plus-unit files.
* About two thirds of the settings array is unnamed or named with low confidence. docs/FIELDS.md
  lists what each value looks like even where we cannot say what it does.
* The assistant record bodies, the 4001-byte BareSettingInfo section and parts of the block header
  are not understood. docs/FORMAT.md keeps an explicit Observed / Inferred / Unknown list.
* Installing an assistant on a system that never had one has not been done by file. Removal and
  reinstall from the system's own earlier download have (docs/ASSISTANTS.md section 8).

## How to help

Run it on your own system and report what it says:

```
pip install mk2vsc
mk2vsc census <your download>.rvms
```

Open a "Census report" issue with the output and what the values should be according to VEConfigure or
VRM. That is the contribution: it tests every claim here on hardware we do not have, and a disagreement
is a finding. A pair of downloads with one setting changed between them (and which) names a field. See
CONTRIBUTING.md.

## License and responsible use

MIT, see LICENSE. This tool is for people who are already responsible for, and authorized to
configure, the systems they apply it to. It produces files; the decision to upload one, and the
consequences on a live battery system, remain yours. Read docs/SAFETY.md first.

## How this project is run

Every change goes through a public pull request, every open question is a labelled issue, and every
format claim is tied to a test on real files. The project is developed with AI assistance, disclosed
in commits and in docs/PRACTICES.md.

## Related projects

What this project took from each of them, and where it landed, is in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

* [talas9/rvsc-tools](https://github.com/talas9/rvsc-tools) (July 2026): a read-only viewer and format
  specification for single-unit `.rvsc` files, with VEConfigure's internal setting identifiers extracted
  from the application binary. It decoded the same settings schema independently; we adopted its
  identifier table (MIT) for the `VEConfigure identifier` column in docs/FIELDS.md. It does not cover
  multi-unit `.rvms`, assistants, or editing, and reports no checksum on `.rvsc`, which our `.rvms` files
  contradict; reconciling the two is open.
* [xcellsior/ve-bus-programming](https://github.com/xcellsior/ve-bus-programming): the same settings
  over an MK3 cable, live, on Linux.

## Acknowledgements

* Victron's public document "Interfacing with VE.Bus products, MK2 Protocol 3.14" names settings 0 to 65,
  every flag bit, and the setting-info record that turned out to be the `BareSettingInfo` section.
* github.com/xcellsior/ve-bus-programming documented the VE.Bus setting IDs and scales over the MK2/MK3
  protocol before we found the Victron document; it is what led us to the setting-ID mapping.
* The Victron Community threads on `.rvsc`/`.rvms` files, Remote VEConfigure and the "switch as group"
  error saved us time and confirmed the demand for this work.
