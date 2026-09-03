# rvms

Read, validate, decode, diff, edit and qualify Victron VEConfigure `.rvms` configuration files
without VEConfigure, on any operating system, from Python or the command line.

## The problem

Victron MultiPlus and Quattro inverter/chargers are configured with VEConfigure and VE.Bus System
Configurator. Those tools run only on Windows. VictronConnect is replacing them but does not support
assistants (ESS, AC PV and the rest), so anyone maintaining a real installation still needs a Windows
machine or a virtual machine. The configuration itself travels as a small binary file: `.rvsc` for a
single unit, `.rvms` for parallel and multi-phase systems, downloaded and uploaded through VRM's Remote
VEConfigure. A Victron Community thread titled "RVSC File Format Specification" asked Victron to publish
the format so people could write their own editors; it received no answer. As of September 2026 we
found no open-source parser, specification or editor for these files anywhere.

We operate four two-inverter systems and needed to change charge voltages and Virtual Switch
thresholds on them remotely, repeatably, and with a record of what changed. This repository is what we
built to do that, together with everything we learned about the file along the way.

## What this is

* A zero-dependency Python 3.9+ library and a CLI (`rvms`) that:
  * parses the file's section structure and verifies every integrity checksum,
  * decodes the per-inverter settings array into labelled values with a confidence level per field,
  * compares two files by inverter serial and tells you whether they differ only in bookkeeping,
  * edits settings in place, self-verifies that nothing else changed, and never changes file length,
  * qualifies a file against the values you intended before you upload and after you re-download,
  * mines a library of archived downloads into a dated, per-inverter change log (`rvms history`).
* A corpus of 84 real device files with a manifest, and a test suite that checks every documented
  claim against that corpus (453 tests).
* A written account of the format as we understand it, and of what we do not understand.

## What this is not

* It does not upload anything. You upload through VRM, exactly as before.
* It does not add, remove or modify assistants (ESS and others). We tried; see docs/ASSISTANTS.md.
* It does not touch grid codes or the dealer password that protects them.
* It is not affiliated with or endorsed by Victron Energy.

## Status and confidence

| Capability | Status | Evidence |
|---|---|---|
| Section grammar and integrity checksum | Proven | Validates on 107/107 files, every section; edited files accepted by the device on 4 systems |
| Settings array = VE.Bus setting IDs at +0x59 + 2n | High | Reference IDs reproduce 120 V output, 50.0 A limit, 95 %/98 % SoC, grid-code flag on 214 blocks |
| Field table (190 entries) | Partial | 4 CONFIRMED, 10 HIGH, 9 MEDIUM, 19 LOW, 20 UNKNOWN named; the rest unnamed |
| Guarded writer (`rvms set`) | Proven live | Absorption, float and Virtual Switch thresholds written and read back on 4 systems, July to August 2026 |
| By-serial diff (`rvms diff`) | Proven | Consecutive downloads, including a pair whose blocks swapped position, classify as bookkeeping only |
| Qualifier (`rvms qualify`) | Proven | Reproduces the incident that motivated it (a rollback that reverted a charge-voltage fix) |
| Assistant area | Read only | Record structure and stub signature recognised; record bodies not understood |
| Upload-form (GUI export) files | Read only, experimental | Detected and decoded; the writer refuses them |

The confidence vocabulary (CONFIRMED, HIGH, MEDIUM, LOW, UNKNOWN) is defined in `rvms/fields.py` and
docs/FIELDS.md. The writer edits CONFIRMED and HIGH fields; anything lower needs an explicit override.

## Install

```
git clone <this repository>
cd rvms-toolkit
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest          # 453 tests against the fixture corpus
```

Or run without installing: `PYTHONPATH=. python3 -m rvms.cli ...`.

## Quickstart

```
rvms info fixtures/mango/mango_2026-07-24_download_bare_deviceform_1.rvms
```
```
format 1.33  length 5055  checksums OK
  HQ24149MY9U  fw 2729560  form=device  flag=f5  saved 2026-07-24T22:49:20+00:00  assistant: no assistant
      absorption_V                     56.8 V    [CONFIRMED] (+0x05d)
      float_V                          54.0 V    [CONFIRMED] (+0x05f)
      charge_current_A                   35 A    [HIGH] (+0x061)
      ...
```

Two downloads of the same system a few minutes apart differ only in bookkeeping (pointer, save
timestamp, checksum), even though the two inverter blocks may have swapped position in the file:

```
rvms diff fixtures/mango/mango_2026-07-24_download_bare_deviceform_1.rvms \
          fixtures/mango/mango_2026-07-24_download_bare_deviceform_2.rvms
```
```
lengths 5055 -> 5055; prologue same; verdict: ONLY BOOKKEEPING (settings verbatim)
  HQ2240FKJDE: len 482->482 form device->device bookkeeping=6B header=0B assistant=0B
  HQ24149MY9U: len 482->482 form device->device bookkeeping=6B header=0B assistant=0B
```

Edit a setting on every inverter, then check the result against what you intended:

```
rvms set fixtures/guava/guava_2026-07-20_download_bare_deviceform_1.rvms /tmp/prepared.rvms \
         absorption_V=56.8 float_V=54.0
rvms qualify /tmp/prepared.rvms --intent examples/intent.example.json
```
```
HQ2414U6FVN  absorption_V  56.0 -> 56.8 V  (+0x05d / file 0x1056)
HQ2414AXENJ  absorption_V  57.6 -> 56.8 V  (+0x05d / file 0x123a)
...
wrote /tmp/prepared.rvms; verified: only the listed bytes and their section checksums changed
/tmp/prepared.rvms: QUALIFIED
  ok   all section checksums valid
  ok   serials match the intended system
  ok   absorption_V = 56.8 on all inverters
  ok   float_V = 54.0 on all inverters
```

Every command: `info`, `validate`, `decode`, `diff`, `set`, `qualify`, `fix`, `fields`, `census`,
`history`. `rvms --help` and `rvms <command> --help` describe the options.

From Python:

```python
from rvms import RvmsFile, units_by_serial, set_settings, diff_bytes

data = open("download.rvms", "rb").read()
print(units_by_serial(RvmsFile.parse(data))["HQ2414U6FVN"].setting(2) / 100)   # absorption, volts
out, edits = set_settings(data, [(None, "absorption_V", 56.8)])                # None = every inverter
assert not diff_bytes(data, out).only_bookkeeping                               # the setting changed
open("prepared.rvms", "wb").write(out)
```

See examples/edit_and_verify.py for the full loop.

## The change-control loop

Uploading a file replaces the whole configuration of every inverter in the system. These five steps
are how we make that safe; docs/CHANGE_CONTROL.md explains each one and the incident behind it.

1. Download a fresh file from VRM (Remote VEConfigure) into `00_baseline/`. Never start from an
   archived copy: the device rejects stale save timestamps, and old files carry old values.
2. `rvms set` the baseline into `01_prepared/`, then `rvms qualify` it against an intent file that
   lives outside the file under test.
3. Upload `01_prepared/` through VRM.
4. Download again into `02_downloaded/`.
5. `rvms diff` prepared against downloaded (expect "ONLY BOOKKEEPING") and `rvms qualify` the
   download. "Success" in the upload dialog is not the same as "the settings are right".

## Corpus and tests

The `fixtures/` directory holds 84 unique files from 4 split-phase MultiPlus systems (8 inverters,
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
| docs/FIXTURES.md | What every file in the corpus is |

## Limits and unknowns

* We hold files from one firmware (2729560), one format version (1.33), one product family, one
  topology (two inverters, split phase). Other hardware may differ; the tests will tell you.
* We have no `.rvsc` single-unit files and no three-phase or three-plus-unit files.
* About two thirds of the settings array is unnamed or named with low confidence. docs/FIELDS.md
  lists what each value looks like even where we cannot say what it does.
* The assistant record bodies, the 4001-byte BareSettingInfo section and parts of the block header
  are not understood. docs/FORMAT.md keeps an explicit Observed / Inferred / Unknown list.
* Installing an assistant by file has never produced a running system for us. docs/ASSISTANTS.md
  records each attempt and its outcome so nobody has to repeat them on live hardware.

## How to help

The most useful contributions are files and controlled pairs, not code:

* A download, one setting changed in VEConfigure, and a second download, plus a screenshot of the
  VEConfigure tab showing the value. One such pair names a field for everyone.
* Files from other hardware: Quattro, other firmware, three-phase, single-unit `.rvsc`.
* Running the verify-it-yourself recipe in docs/QA.md on your system and reporting what happened.

See CONTRIBUTING.md for how to add a fixture and what the privacy expectations are.

## License and responsible use

MIT, see LICENSE. This tool is for people who are already responsible for, and authorized to
configure, the systems they apply it to. It produces files; the decision to upload one, and the
consequences on a live battery system, remain yours. Read docs/SAFETY.md first.

## Acknowledgements

* github.com/xcellsior/ve-bus-programming documented the VE.Bus setting IDs and scales over the MK2/MK3
  protocol; that table is what let us name most of the settings array.
* The Victron Community threads on `.rvsc`/`.rvms` files, Remote VEConfigure and the "switch as group"
  error saved us time and confirmed the demand for this work.
