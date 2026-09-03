# Contributing

This project advances one controlled experiment at a time. The most valuable contributions are
files and observations, not code. Everything below is about making those contributions safe for
you, for the systems involved, and for the people who rely on the field table.

## A note on what the fixtures disclose

The fixtures carry the eight inverter serial numbers of our systems and their save timestamps. Victron
and its dealers can resolve a serial to an installation; we chose to publish them because the files are
useless as evidence without them. Nothing else identifying is in the files: no VRM identifiers, no
credentials, no names.

## The three contributions we need most

### 1. A controlled pair

Download your system's file from VRM (Remote VEConfigure, "Download", save to disk), change exactly
one setting in VEConfigure, upload, download again. Send both files and a screenshot of the
VEConfigure tab that shows the setting and its value. One such pair pins a field for everyone: the
only bytes that differ between the two downloads, other than the bookkeeping bytes, are the field.
This is how the Virtual Switch thresholds in docs/FIELDS.md were confirmed. Pairs that change one of
the fields currently marked MEDIUM, LOW or UNKNOWN are the most useful; pairs that touch the flag
registers (settings 0 and 1) or the load-watt and time parameters of the Virtual Switch would close
gaps we know about.

### 2. Files from hardware we do not have

Every file in the corpus is from a 48 V, 120 V MultiPlus-class inverter, firmware 2729560, format
version 1.33, in a two-inverter split-phase pair. We would like to see:

* a single-unit `.rvsc` file,
* a three-phase or three-plus-unit `.rvms`,
* a Quattro (which has a second AC input and populates setting 49),
* any other firmware version or VEConfigure version,
* a 230 V system.

Run `mk2vsc validate` and `mk2vsc census` on the file first. If validation fails, that is already a
finding: it means the checksum model does not hold for your file, and we want to know.

### 3. Reproducing our claims on your own system

docs/QA.md has a verify-it-yourself recipe: two downloads a minute apart should differ only in
bookkeeping, every checksum should validate, and decoded absorption/float/AC input limit should match
what VRM and VEConfigure show. Reporting "it held" on a different installation is as valuable as a
bug report, and a lot more valuable than a star.

## Adding a fixture

Fixtures live under `fixtures/<system>/` and are named

```
<system>_<YYYY-MM-DD>_<origin>_<state>_<form>_<n>.rvms
```

* `system`: a short name for the installation, not a VRM portal identifier.
* `date`: the newest save timestamp inside the file (block offset +0x4f, unix time), not the day
  you copied it.
* `origin`: `download` (a VRM Remote VEConfigure download), `gui-export` (a file VEConfigure or
  System Configurator wrote for upload), `prepared` (a file produced by tooling), or `experiment`
  (deliberately malformed).
* `state`: `bare` (no assistant on any inverter), `half-ess` (assistant on some), `ess` (assistant
  records on every inverter), `stub` (the empty 64-byte container VEConfigure writes after a failed
  by-file install).
* `form`: `deviceform` (zeros at block +0x45) or `uploadform` (the 16-byte GUI blob at +0x45).
* `n`: a counter to keep names unique.

Then add an entry to `fixtures/manifest.json`:

| key | meaning |
|---|---|
| `file` | path relative to `fixtures/` |
| `sha256`, `size` | of the file as committed |
| `site`, `date`, `origin`, `state`, `form` | as in the name |
| `blocks` | one entry per inverter: `serial`, `length` (block length in the name-start-to-next-name convention), `flag` (the byte at +0x36) |
| `notes` | free text: what the file is and why it matters |

`mk2vsc census <file>` prints the block lengths, flags, form and assistant kind you need for the entry.
`examples/gen_fixture_table.py` renders the manifest as the table in docs/FIXTURES.md.

Run `pytest`. The tests in `tests/test_claims.py` check every documented claim against every fixture.
If one of them fails on your file, do not weaken the test: open an issue with the `mk2vsc census` output
and, if you can share it, the file. A failing claim is the result we are looking for; it means the
field table or the format description needs a revision, and the revision needs your file as evidence.

If a file is malformed on purpose, add it to `KNOWN_BAD` in `tests/conftest.py` with the reason.

## Privacy and permission

An `.rvms` file contains the serial number of every inverter in the system, the firmware version,
save timestamps, and the configuration. It does not contain VRM credentials, the grid-code password,
Wi-Fi settings or personal data. Even so:

* Only commit files from systems you own or are explicitly permitted to share.
* Strip identifying material from the file name (we dropped the VRM portal ID from ours).
* Do not include VRM portal IDs, site IDs, addresses or people's names in manifest notes or docs.
* Never commit anything containing a password. The grid-code password is a dealer credential and
  has no place in this repository in any form.

## Code rules

* No runtime dependencies. The library must stay importable on a bare Python 3.9.
* Every offset or meaning asserted in `mk2vsc/fields.py` or `mk2vsc/units.py` needs a test in
  `tests/test_claims.py` that checks it against the corpus.
* Every new `Field` needs `evidence` text if it is CONFIRMED or HIGH, and `observed` values if it is
  UNKNOWN. Do not promote a field's confidence without a controlled pair or a screenshot match.
* The writer stays length-preserving. Anything that changes the length of a section, adds or removes
  records, or edits the assistant area is out of scope for `set_settings`; see docs/ASSISTANTS.md for
  why.
* Nothing in this repository uploads to a device or talks to VRM. Keep it that way.
* Parsing must remain byte-exact: `RvmsFile.parse(data).to_bytes() == data` for every good fixture.

## Review

Changes to the parser, the writer or the field table get an independent review before merge: someone
other than the author reads the diff, runs the tests, and checks the claim against at least one
fixture by hand. A change that only adds fixtures and notes can be merged after the tests pass.

## Commits

One change per commit, in the imperative, with the evidence in the body: which fixture, which pair,
which screenshot. When a commit revises a claim, say what the old claim was and why it was wrong;
docs/HISTORY.md is built from exactly that kind of record.
