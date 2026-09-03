# Change control for `.rvms` configuration changes

This is the part of the toolkit that a GUI cannot give you. VEConfigure lets you edit a file and
upload it. It does not tell you what changed, whether the device stored what you sent, or whether
the file you are about to upload still carries a correction you made last month. Every rule below
exists because we broke something without it.

## The folder pattern

One folder per change:

```
changes/
  2026-07-20_guava_charge-profile/
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

Date: 2026-07-20    System: Guava    Inverters: HQ2414U6FVN, HQ2414AXENJ
Tenant/occupancy impact: none (unit vacant)    Rollback: 00_baseline/<file>

## Why
One paragraph. What is wrong, what the target value is, where the target comes from
(battery spec sheet, installer guidance, a previous good file).

## Exact edits (per inverter)
| serial       | field         | old  | new  |
|--------------|---------------|------|------|
| HQ2414U6FVN  | absorption_V  | 56.0 | 56.8 |
| HQ2414AXENJ  | absorption_V  | 57.6 | 56.8 |
| HQ2414AXENJ  | float_V       | 55.2 | 54.0 |

Intent file: intent.json (copied into this folder)

## Checklist
- [ ] 00_baseline/ holds a download taken today (save timestamp checked with `rvms info`)
- [ ] 01_prepared/ built from 00_baseline/ with `rvms set`; `rvms diff` shows only the intended settings
- [ ] `rvms qualify 01_prepared/<file> --intent intent.json` exits 0
- [ ] uploaded 01_prepared/<file> via VRM Remote VEConfigure; dialog result recorded here
- [ ] re-downloaded into 02_downloaded/
- [ ] `rvms diff 01_prepared/<file> 02_downloaded/<file>` says ONLY BOOKKEEPING
- [ ] `rvms qualify 02_downloaded/<file> --intent intent.json` exits 0
- [ ] live system checked (VRM device page shows the new value; no VE.Bus errors)
- [ ] recorded in the change log / monitoring

## Outcome
What happened, including anything unexpected.
```

## The four rules

### Rule 1: a full-config upload silently reverts every prior field edit

An `.rvms` upload replaces the entire configuration of every inverter in the system. There is no
merge and there is no warning. On 2026-07-20 we corrected Guava's mismatched charge profile by file
(one inverter had been charging at 57.6 V absorption / 55.2 V float, above the battery
specification) and verified the correction on the re-download. In August we uploaded several
full configurations to the same system for other reasons, each built from an older archived
baseline that still carried the pre-correction values. On 2026-08-19 a routine decode showed the
old values back in place. The battery had been charging above specification on one inverter for
roughly a month. Our monitoring had logged the reversion the day it happened. Nobody looked.
Detection without a review step is not protection. The qualifier (`rvms qualify`) exists because
of this: it checks a file against intended values that are kept outside the file, and it fails any
file whose two inverters disagree on a confirmed setting.

### Rule 2: build only on a fresh download

The device rejects a file whose save timestamp is older than the one it holds. The error is
`mk2vsc-36 "Incorrect grid code password or old configuration file"`, and the second half of that
message is the common meaning. On 2026-08-12 an archived, known-good bare configuration for Guava
was rejected with mk2vsc-36 on every attempt, across two reboots, while we chased grid-code
theories. A fresh download, uploaded unmodified, was accepted on the first try. Download, edit
that file, upload that file. If any new download happens after you prepared a file, prepare it
again from the newest download.

### Rule 3: never leave prepared files loose

Every prepared file goes in `01_prepared/` of its own change folder and nowhere else. During the
August work a copy of a prepared file left in `~/Downloads` was nearly uploaded twice after a newer
version had been built. Loose copies at the root of the changes directory and in download folders
are stale duplicates waiting to be uploaded by mistake. The naming convention in `fixtures/`
(system, date, origin, state, form) is the same idea applied to the archive.

### Rule 4: verify the re-download, not the upload dialog

"Success. The system has been configured" means the device accepted the bytes. It does not mean
the settings are right, and it does not mean the settings landed on every inverter. On 2026-08-21
a GUI session on Sugar Apple wrote seven settings to one inverter and none to the other, leaving
the two legs of a shared battery 0.3 V apart. The only proof of a change is the re-download:
`rvms diff` against the prepared file must report only bookkeeping bytes (pointer, save timestamp,
checksum), and `rvms qualify` must pass on the re-download with the same intent file that passed
on the prepared file.

## The CLI sequence for one change

```sh
# 0. fresh download from VRM -> changes/<change>/00_baseline/system.rvms
rvms validate 00_baseline/system.rvms                 # checksums OK on your firmware
rvms info     00_baseline/system.rvms                 # confirm serials and today's save timestamp

# 1. prepare (edits every inverter unless --serial is given)
rvms set 00_baseline/system.rvms 01_prepared/system_charge-profile.rvms absorption_V=56.8 float_V=54.0
rvms diff 00_baseline/system.rvms 01_prepared/system_charge-profile.rvms   # only the intended settings
rvms qualify 01_prepared/system_charge-profile.rvms --intent intent.json    # exit 0

# 2. upload 01_prepared/system_charge-profile.rvms via VRM -> Remote VEConfigure -> Upload

# 3. re-download from VRM -> 02_downloaded/system.rvms
rvms diff 01_prepared/system_charge-profile.rvms 02_downloaded/system.rvms  # expect: ONLY BOOKKEEPING
rvms qualify 02_downloaded/system.rvms --intent intent.json                 # exit 0
```

`rvms diff` exits 0 when the two files are identical or differ only in bookkeeping, and 2 when
content differs. `rvms qualify` exits 0 for QUALIFIED and 1 for NOT QUALIFIED. Both are usable in
scripts.

## Intent files

An intent file holds what the settings are supposed to be. It is deliberately not derived from the
file under test. `examples/intent.example.json`:

```json
{
  "system": "guava",
  "serials": ["HQ2414U6FVN", "HQ2414AXENJ"],
  "settings": {"absorption_V": 56.8, "float_V": 54.0, "vs_accept_battery_above_V": 52.5},
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
  assistant flag, and a notes field. `rvms census FILE...` prints the one-line summary used to build it.
- Compare by serial, never by filename or file position. The two blocks of a pair swap position
  between downloads of the same system. `rvms diff` does this for you.
- Mine the history. Decoding every archived download in date order dates when each setting
  changed, which is information the portal does not keep. The caveat: the save timestamp in a file
  is when the device last stored a configuration, and a download taken later brackets the change.
  Report changes as intervals between two downloads, not as points.
- Keep the deliberately broken files too, labelled. They are the negative controls that prove a
  validator actually validates.
