# QA: how to decide whether to trust this

Trust in a tool that writes configuration to a battery inverter has to be earned by evidence you
can re-run yourself. This page lists what we test, what the evidence does and does not cover, and
a recipe for verifying the toolkit on your own system before you let it write anything.

## The test suite

Everything runs against the real device files in `fixtures/` (see docs/FIXTURES.md). There are no
synthetic fixtures for the format itself.

| file | what it proves |
|---|---|
| `tests/test_sections.py` | Every good fixture parses, every section checksum validates, the pointer chain is contiguous and ends at EOF, parse then serialize is byte-exact, rebuilding pointers and checksums from payloads reproduces the input byte-for-byte, the historical formula (`sum32(block[2:]) + 0x6142000F`) equals the plain word sum, the header sections are identical across the corpus, and the three deliberately broken files are detected. |
| `tests/test_claims.py` | Every checkable claim in docs/FIELDS.md and `rvms/units.py`, checked on all 162 inverter blocks of the 81 well-formed fixtures: serial position, firmware word, slot bytes, assistant-flag encoding, the +10 upload-form shift (setting 5 reads 120 V on every block under the offset model), timestamps are plausible unix times, CONFIRMED/HIGH fields decode to physically sensible values, grid-code flag tracks GUI-authored installs, the retracted SOC field is the high byte of setting 88, region 128 to 189 is unprogrammed on bare blocks, and the field table itself is internally consistent (every CONFIRMED/HIGH entry states evidence). |
| `tests/test_writer.py` | Edit then revert reproduces the original file byte-for-byte; an edit to all inverters changes only the intended bytes plus checksums; edits on ESS blocks leave the assistant area untouched; unverified fields, flag registers, unknown serials, out-of-range values, upload-form input and corrupt input are refused; the archived prepared files from the 2026-07-20 charge-profile corrections are reproduced exactly from their baselines. |
| `tests/test_diff.py` | Two real consecutive downloads differ only in bookkeeping; the pair whose blocks swapped file position is invisible when compared by serial while a positional diff shows dozens of differences; a stub download is reported as a content change; a GUI export and the device's re-download of it agree on every setting. |
| `tests/test_qualify.py` | Inverter disagreement fails; intended values pass on the corrected file and fail on the mismatched one; wrong-system serials fail; the stub fails; the rollback file that caused the month-long regression is caught. |
| `tests/test_assistants.py` | Bare blocks have the empty header and the free-space counter relation holds; GUI-installed ESS has exactly one 704 and one 1152 byte record per system; the 1152 byte body is identical across systems; the stub is detected on all six stub blocks. |
| `tests/test_manifest.py` | Every fixture is in the manifest with a matching sha256 and size, and no two fixtures have the same content. |
| `tests/test_cli.py` | Exit codes and output of every subcommand. |

Run it:

```sh
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

459 tests, under a second.

## The corpus and its limits

84 unique files (81 well-formed, 162 inverter blocks, plus 3 negative controls), 8 inverters in 4 two-inverter split-phase systems, one
firmware version (2729560), one format version (1.33), downloads spanning June to September 2026.
Three files are deliberately broken and listed in `tests/conftest.py` `KNOWN_BAD` with the reason:
a file with stale checksums that we built in June to learn whether the device validates the
trailer, and two hand-built assistant grafts with broken pointer chains.

What the corpus does not cover, and therefore what the tests cannot promise:

- Other firmware versions. Every block we hold reads 2729560.
- Quattro (setting 49, AC input 2, is always 0 here), three-phase or three-plus-unit systems,
  single-unit `.rvsc` files. We have none.
- Other VEConfigure or System Configurator versions and other format versions than 1.33.
- Lead-acid or other charge characteristics; all our systems are lithium with a fixed curve.
- Assistants other than ESS.

A claim test failing on a file from outside this envelope is the expected way to learn something.

## Verify it yourself before writing anything

1. Download your system's file twice, a minute apart. `rvms diff a.rvms b.rvms` should say
   ONLY BOOKKEEPING and exit 0. This checks that the parser, the by-serial comparison, and the
   bookkeeping model (pointer, save timestamp, checksum) hold on your firmware.
2. `rvms validate a.rvms`. All checksums OK means the checksum model is exactly what your device
   and your VEConfigure version compute. If any section reads BAD on a genuine download, stop: the
   integrity model does not hold for your files, and nothing else here should be trusted until it
   is understood.
3. `rvms decode a.rvms`. Compare absorption, float, charge current and the AC input current limit
   with VEConfigure's Charger and General tabs or the VRM device page. If they match, the
   settings-array mapping holds for your block layout.
4. Run the test suite with your file added to `fixtures/` (and to the manifest, see
   docs/FIXTURES.md). Claim tests that fail are findings, not bugs in your file.
5. Only then the first live edit: one innocuous 0.1 V step on a watched system, following
   docs/SAFETY.md and docs/CHANGE_CONTROL.md.

When a claim test fails on your file, open an issue with the file (device downloads contain
inverter serials and nothing else identifying) and the output of `rvms census` and
`rvms decode --all --json`.

## The live-verification protocol we used

For each of the four live uploads that established the writer:

1. Fresh download into the change folder.
2. Prepared file built with the writer; self-verification proved only the intended bytes and the
   section checksums changed.
3. Upload through VRM Remote VEConfigure; "Success. The system has been configured."
4. Re-download; `diff` against the prepared file reports only the save timestamp, pointers and
   checksums; every setting verbatim.
5. VRM device page shows the new value; no VE.Bus errors; the battery charges to the new voltage
   on the next cycle.

The first was float 54.0 to 54.1 V on both inverters of one system (2026-07-20), chosen because a
0.1 V change cannot hurt anything and is unambiguous to read back. The same day the charge
profiles of four systems were corrected the same way.

## Review discipline

Code changes to the parser, writer or field table are reviewed independently before merge, with
the test suite green and, for anything touching the writer, an edit-and-revert byte-identity
check on every fixture. We treat a new field-table entry at CONFIRMED as requiring a live
read-back, and at HIGH as requiring a corpus-wide consistency check plus a public reference or a
matching GUI screenshot.

## Confidence summary

| area | status | evidence |
|---|---|---|
| Section grammar and checksum | proven | every section of all 84 unique files (107 counting archive duplicates); four live uploads accepted; byte-exact round trip on every fixture |
| Settings array as VE.Bus setting IDs 0 to 189 | strong | absorption/float anchor IDs 2/3; IDs 5, 6, 65, 73, 81, 88 corroborate on every block; one firmware only |
| Individual fields | mixed | of 190 IDs, 62 are named: 4 CONFIRMED (written and read back live), 10 HIGH, 9 MEDIUM, 19 LOW, 20 UNKNOWN; the other 128 are unnamed (mostly 0 or 0xffff); docs/FIELDS.md lists each with its evidence |
| Guarded writer | proven for its surface | edit-and-revert byte identity on every fixture; reproduces the archived prepared files; 4 live uploads |
| By-serial diff and bookkeeping model | proven | real consecutive downloads, including the swapped-order pair |
| Qualifier | proven against its motivating incident | catches the 2026-08-14 rollback file (fixture); the 2026-08-21 one-inverter GUI write is the case the agreement check was written for, but we hold no fixture from that day |
| Assistant records | read-only, structure only | record framing, sizes and the stub signature; the record body and the 72-byte ESS tail are not understood |
| Upload-form transform | partial | reproduced a GUI export byte-for-byte once; the device accepted one such file; the resulting install never started; not shipped as a command |
| Grid code | not touched | flag read only; the dealer password is out of scope by policy |
