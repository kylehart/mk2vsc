---
title: "Change control for Victron .rvms configuration files"
description: "The simple loop and the fleet discipline: fresh downloads, prepared files, verification, intent files."
---

# Change control for `.rvms` configuration changes

This is the part of the toolkit that a GUI cannot give you. VEConfigure lets you edit a file and
upload it. It does not tell you what changed, whether the device stored what you sent, or whether
the file you are about to upload still carries a correction you made last month. Every rule below
exists because we broke something without it.

## The simple loop (start here)

For one system and one change you do not need folders or an intent file:

```
mk2vsc show   download.rvms                          # read it; note the save timestamp is today's
mk2vsc edit   download.rvms absorption=56.8 float=54.0   # writes download.edited.rvms next to it
# VRM > Remote VEConfigure > Upload download.edited.rvms; then Download again
mk2vsc verify download.edited.rvms redownload.rvms   # "VERIFIED": the device took exactly your change
mk2vsc check  redownload.rvms --expect absorption=56.8 float=54.0
```

`edit` never overwrites the download, so the download is your rollback. `verify` fails loudly if the
device changed anything beyond pointers, timestamps and checksums. `check` fails if a value is not what
you expect or if the two inverters disagree. The rest of this page is the discipline we use when several
systems, several people and months of history are involved.

## The folder pattern

One folder per change:

```
changes/
  2026-07-20_system_a_charge-profile/
    00_baseline/     <- a FRESH download from VRM, taken minutes before you prepare the edit
    01_prepared/     <- the tool's output; the ONLY file you ever upload
    02_downloaded/   <- the re-download taken after the upload
    CHANGE.md        <- the record
```

Two folders are filled by a person at the VRM portal (baseline, downloaded). One is filled by the
tool (prepared). There is deliberately no `uploaded/` folder: the file that was uploaded is always
`01_prepared/`, and what the device actually stored is proven by `02_downloaded/`. We had an
`uploaded/` folder once. It was ambiguous, it got pre-filled with a copy, and it made it easy to
grab the wrong file.

Prepared files live only in `01_prepared/`. Upload from there. Never stage a copy in `~/Downloads`
or on the desktop.

## CHANGE.md template

```markdown
# <system> - <one-line description of the change>

Date: 2026-07-20    System: System A    Inverters: HQ0000A0001, HQ0000A0002
Tenant/occupancy impact: none (unit vacant)    Rollback: 00_baseline/<file>

## Why
One paragraph. What is wrong, what the target value is, where the target comes from
(battery spec sheet, installer guidance, a previous good file).

## Exact edits (per inverter)
| serial       | field         | old  | new  |
|--------------|---------------|------|------|
| HQ0000A0001  | absorption_V  | 56.0 | 56.8 |
| HQ0000A0002  | absorption_V  | 57.6 | 56.8 |
| HQ0000A0002  | float_V       | 55.2 | 54.0 |

Intent file: intent.json (copied into this folder)

## Checklist
- [ ] 00_baseline/ holds a download taken today (save timestamp checked with `mk2vsc show`)
- [ ] 01_prepared/ built from 00_baseline/ with `mk2vsc edit -o 01_prepared/<file>`; `mk2vsc diff` shows only the intended settings
- [ ] `mk2vsc check 01_prepared/<file> --intent intent.json` exits 0
- [ ] uploaded 01_prepared/<file> via VRM Remote VEConfigure; dialog result recorded here
- [ ] re-downloaded into 02_downloaded/
- [ ] `mk2vsc diff 01_prepared/<file> 02_downloaded/<file>` says ONLY BOOKKEEPING
- [ ] `mk2vsc check 02_downloaded/<file> --intent intent.json` exits 0
- [ ] live system checked (VRM device page shows the new value; no VE.Bus errors)
- [ ] recorded in the change log / monitoring

## Outcome
What happened, including anything unexpected.
```

## The four rules

### Rule 1: a full-config upload silently reverts every prior field edit

An `.rvms` upload replaces the entire configuration of every inverter in the system. There is no
merge and there is no warning, so a file built from an old baseline re-applies every value that baseline
carried, including ones you corrected since (it cost us a month of out-of-specification charging on one
inverter; docs/HISTORY.md). `mk2vsc check` exists for this: it compares a file with intended values kept
outside the file, and fails any file whose two inverters disagree on a confirmed setting.

### Rule 2: build only on a fresh download

An archived file carries the settings and grid-code words the device had when it was downloaded, not
the ones it has now: uploading it re-applies every value it holds (Rule 1) and, if its grid-code words
differ from the device's, it is refused with `mk2vsc-36` (docs/ERRORS.md). A fresh download has neither
problem. Download, edit that file, upload that file. The save timestamp at +0x4f is not what the device
checks (an older-stamped file with current content is accepted), so a fresh download is about currency of
content, not of clock.

### Rule 3: never leave prepared files loose

Every prepared file goes in `01_prepared/` of its own change folder and nowhere else. A stray copy in a
downloads folder is a stale file waiting to be uploaded by mistake; the change folder is the only place
an upload comes from.

### Rule 4: verify the re-download, not the upload dialog

"Success. The system has been configured" means the device accepted the bytes. It does not mean
the settings are right, and it does not mean the settings landed on every inverter. On 2026-08-21
a GUI session on System D wrote seven settings to one inverter and none to the other, leaving
the two legs of a shared battery 0.3 V apart. The only proof of a change is the re-download:
`mk2vsc diff` against the prepared file must report only bookkeeping bytes (pointer, save timestamp,
checksum), and `mk2vsc check` must pass on the re-download with the same intent file that passed
on the prepared file. Give the GX a minute before reading telemetry: during a remote operation
GX-based monitoring can report the site disconnected and carry a stale inverter state while the MK2
tunnel holds the VE.Bus port (docs/WORKFLOW.md, "Monitoring during a remote operation").

## The CLI sequence for one change

```sh
# 0. fresh download from VRM -> changes/<change>/00_baseline/system.rvms
mk2vsc validate 00_baseline/system.rvms                 # checksums OK on your firmware
mk2vsc show     00_baseline/system.rvms                 # confirm serials and today's save timestamp

# 1. prepare (edits every inverter unless --serial is given)
mk2vsc edit 00_baseline/system.rvms absorption=56.8 float=54.0 -o 01_prepared/system_charge-profile.rvms
mk2vsc diff 00_baseline/system.rvms 01_prepared/system_charge-profile.rvms   # only the intended settings
mk2vsc check 01_prepared/system_charge-profile.rvms --intent intent.json    # exit 0

# 2. upload 01_prepared/system_charge-profile.rvms via VRM -> Remote VEConfigure -> Upload

# 3. re-download from VRM -> 02_downloaded/system.rvms
mk2vsc diff 01_prepared/system_charge-profile.rvms 02_downloaded/system.rvms  # expect: ONLY BOOKKEEPING
mk2vsc check 02_downloaded/system.rvms --intent intent.json                 # exit 0
```

`mk2vsc diff` exits 0 when the two files are identical or differ only in bookkeeping, and 2 when
content differs. `mk2vsc check` exits 0 for QUALIFIED and 1 for NOT QUALIFIED. Both are usable in
scripts.

## Intent files

An intent file holds what the settings are supposed to be. It is deliberately not derived from the
file under test. `examples/intent.example.json`:

```json
{
  "system": "house-1",
  "serials": ["HQ0000A0001", "HQ0000A0002"],
  "settings": {
    "absorption_V": 56.8,
    "float_V": 54.0,
    "vs_ignore_ac_below_V": 51.0,
    "vs_accept_battery_above_V": 52.5
  },
  "require_agreement": true,
  "agreement_fields": ["absorption_V", "float_V"]
}
```

| key | meaning |
|---|---|
| `system` | label for the record; not checked against the file |
| `serials` | optional; the file must contain exactly these inverters, otherwise FAIL ("wrong system?") |
| `settings` | field name (see docs/FIELDS.md) to intended value in engineering units; every inverter must match |
| `require_agreement` | when true, the inverters must agree on every CONFIRMED field (FAIL) and are compared on HIGH fields (WARN) |
| `agreement_fields` | optional list of fields that must agree regardless of confidence |

Keep one intent file per system, under version control, and update it the moment you decide a
value. A future baseline is then checked rather than trusted. The qualifier also fails on any
invalid checksum and on the 64-byte empty stub that VEConfigure writes after a failed by-file
assistant install (see docs/ASSISTANTS.md).

## Keeping a library of past files

Technicians already keep folders of `.rvms` files, and the failure modes are the same everywhere:
uploading the wrong file to the wrong system, and forgetting a standard change. Some habits that
made ours useful:

- Name files by system, date, origin and state, not by the portal's download name. The portal
  numbers files `Tunnel-2`, `Tunnel-3` and so on, which says nothing about content. The `fixtures/`
  directory uses `<system>_<date>_<origin>_<state>_<form>_<n>.rvms`, where the date is the save
  timestamp inside the file, origin is `download`, `prepared`, `gui-export` or `experiment`, and
  state is `bare`, `ess`, `half-ess` or `stub`.
- Keep a manifest (`fixtures/manifest.json` is an example): sha256, size, serials, block lengths,
  assistant flag, and a notes field. `mk2vsc census FILE...` prints the one-line summary used to build it.
- Compare by serial, never by filename or file position. The two blocks of a pair swap position
  between downloads of the same system. `mk2vsc diff` does this for you.
- Mine the history. Decoding every archived download in date order dates when each setting
  changed, which is information the portal does not keep. The caveat: the save timestamp in a file
  is when the device last stored a configuration, and a download taken later brackets the change.
  Report changes as intervals between two downloads, not as points.
  `mk2vsc history FILE...` does this over a library of downloads, grouped by system and serial.
- Keep the deliberately broken files too, labelled. They are the negative controls that prove a
  validator actually validates.
