---
title: "How to decide whether to trust mk2vsc"
description: "The test suite, the fixture corpus, and how to verify the claims on your own system."
---

# QA: how to decide whether to trust this

Trust in a tool that writes configuration to a battery inverter has to be earned by evidence you
can re-run yourself. This page lists what we test, what the evidence does and does not cover, and
a recipe for verifying the toolkit on your own system before you let it write anything.

## The test suite

Everything runs against the real device files in `fixtures/` (see docs/FIXTURES.md). The three files
under `fixtures/synthetic/` are built from those blocks to exercise the single-unit and three-phase shapes;
they are not evidence for any Observed claim and the corpus tests exclude them.

| file | what it proves |
|---|---|
| `tests/test_sections.py` | Every good fixture parses, every section checksum validates, the pointer chain is contiguous and ends at EOF, parse then serialize is byte-exact, rebuilding pointers and checksums from payloads reproduces the input byte-for-byte, the historical formula (`sum32(block[2:]) + 0x6142000F`) equals the plain word sum, the header sections are identical across the corpus, and the three deliberately broken files are detected. |
| `tests/test_claims.py` | Every checkable claim in docs/FIELDS.md and `mk2vsc/units.py`, checked on all 178 inverter blocks of the 89 well-formed fixtures: serial position, firmware word, slot bytes, assistant-flag encoding, the +10 upload-form shift (setting 5 reads 120 V on every block under the offset model), timestamps are plausible unix times, CONFIRMED/HIGH fields decode to physically sensible values, grid-code flag tracks GUI-authored installs, the retracted SOC field is the high byte of setting 88, region 128 to 189 is unprogrammed on bare blocks, and the field table itself is internally consistent (every CONFIRMED/HIGH entry states evidence). |
| `tests/test_writer.py` | Edit then revert reproduces the original file byte-for-byte; an edit to all inverters changes only the intended bytes plus checksums; edits on ESS blocks leave the assistant area untouched; unverified fields, flag registers, unknown serials, out-of-range values, upload-form input and corrupt input are refused; the archived prepared files from the 2026-07-20 charge-profile corrections are reproduced exactly from their baselines. |
| `tests/test_diff.py` | Two real consecutive downloads differ only in bookkeeping; the pair whose blocks swapped file position is invisible when compared by serial while a positional diff shows dozens of differences; a stub download is reported as a content change; a GUI export and the device's re-download of it agree on every setting. |
| `tests/test_qualify.py` | Inverter disagreement fails; intended values pass on the corrected file and fail on the mismatched one; wrong-system serials fail; the stub fails; the rollback file that caused the month-long regression is caught. |
| `tests/test_assistants.py` | Bare blocks have the empty header and the free-space counter relation holds; GUI-installed ESS has exactly one 704 and one 1152 byte record per system; the 1152 byte body is identical across systems; the stub is detected on all six stub blocks. |
| `tests/test_manifest.py` | Every fixture is in the manifest with a matching sha256 and size, and no two fixtures have the same content. |
| `tests/test_cli.py` | Exit codes and output of every subcommand. |
| `tests/test_topologies.py` | The synthetic single-unit and three-phase files (built by `tools/gen_synthetic_fixtures.py`, checked byte for byte against it): one, three and six inverters parse, validate, align and round-trip; the single-unit file is the byte prefix of its source; the phase and unit bytes decode per block and appear in `census`, `show` and the JSON; `diagnose` runs the per-block rules on one unit and reports D2 and E2 as not applicable; the writer edits absorption and float on the single-unit file with only those bytes and the checksum changing, and the revert is byte-exact; the firmware number is the low 24 bits of the word (a corpus block with the high byte set reads 2729560 and `census` says so); the assistant flag is read by its high nibble; `tools/validate_dir.py` prints aggregates and nothing identifying. |

Run it:

```sh
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

674 tests, under three seconds.

## The corpus and its limits

92 unique files (89 well-formed, 178 inverter blocks, plus 3 negative controls), 8 inverters in 4 two-inverter split-phase systems, one
firmware version (2729560), one format version (1.33), downloads spanning June to September 2026.
Three files are deliberately broken and listed in `tests/conftest.py` `KNOWN_BAD` with the reason:
a file with deliberately stale checksums (a negative control for the validator).

What the corpus does not cover, and therefore what the tests cannot promise:

- Other firmware versions. Every block we hold reads 2729560.
- Quattro (setting 49, AC input 2, is always 0 here).
- Other VEConfigure or System Configurator versions and other format versions than 1.33.
- Lead-acid or other charge characteristics; all our systems are lithium with a fixed curve.
- Assistants other than ESS.
- Single-unit `.rvsc` and three-phase files as device downloads: the repository holds synthetic ones built
  from our blocks (`fixtures/synthetic/`), which test the code paths, not the devices.

A claim test failing on a file from outside this envelope is the expected way to learn something.

### Files outside the repository: the aggregate evidence

Files from other people's systems are not committed (docs/donate.md says what we do with a donated file).
They are run through `tools/validate_dir.py`, which prints counts only: no file name, serial, timestamp or
full firmware number. The table below is that output for the set held on 2026-09-11: ten files posted
publicly by their owners on the Victron Community, used here for testing only. "phase_model" is the
per-slot byte pattern in docs/FORMAT.md 3.1.1 (not scored on two-unit files); "records_imply_assistant_flag"
is the one direction of the flag/area relation that holds on our corpus (a block carrying assistant records
always has flag high nibble `e`; the converse is false); the one alignment failure is a
GUI-saved three-unit file with setting 85 at 0xffff, above its schema maximum (docs/FORMAT.md 3.3), reported
by `census` as ALIGNMENT SUSPECT and by `diagnose` as `upload_form`.

Run on 2026-09-11 (`python tools/validate_dir.py <dir> --markdown`):

10 files, 20 inverter blocks (aggregate only; no names, serials or timestamps)

By unit count
| units | files |
|---|---|
| 1 | 6 |
| 2 | 1 |
| 3 | 2 |
| 6 | 1 |

By format version (Mk2vscInfo)
| format | files |
|---|---|
| 1.3 | 2 |
| 1.30 | 1 |
| 1.32 | 3 |
| 1.33 | 4 |

By firmware family (first two digits of the block firmware number)
| fw_family | files |
|---|---|
| 19 | 1 |
| 20 | 3 |
| 26 | 5 |
| 27 | 1 |

By form
| form | files |
|---|---|
| device | 8 |
| upload | 2 |

Facts
| fact | files |
|---|---|
| assistant records present | 6 |
| grid code set (setting 81 != 0) | 6 |
| firmware word high byte set | 1 |
| schema firmware differs from block firmware | 4 |
| diagnose status ok | 8 |
| diagnose status upload_form | 2 |
| diagnose status other | 0 |

Checks (pass / fail / not applicable)
| check | pass | fail | n/a |
|---|---|---|---|
| parse | 10 | 0 | 0 |
| checksums | 10 | 0 | 0 |
| round_trip | 10 | 0 | 0 |
| layout | 10 | 0 | 0 |
| schema_192 | 10 | 0 | 0 |
| alignment | 9 | 1 | 0 |
| census | 9 | 1 | 0 |
| diagnose_ok_or_upload_form | 10 | 0 | 0 |
| records_imply_assistant_flag | 10 | 0 | 0 |
| phase_model | 9 | 0 | 1 |

note: alignment failed on 1 file(s): a value outside its schema range; `mk2vsc census` on that file names the setting; --strict makes that set the exit status

## Two offline checks for hardware classes with no upload history

No file mk2vsc edited has been uploaded to a single-unit or three-phase system. Before the first such upload
of your own, two checks that need no target hardware and touch no VE.Bus:

1. **VEConfigure 3 in a Windows VM.** It opens any `.rvsc` or `.rvms` from disk and shows the values on its
   tabs; open the edited file, read the tabs, close without saving. Evidence that this works on files from
   systems the PC is not connected to: Victron's Remote VEConfigure manual describes editing the downloaded
   file offline, and Victron Community threads show Victron staff editing a stranger's downloaded `.rvsc` on
   their own PC for the owner to upload (observed 2026-09-11). What it proves: the file is well formed for
   Victron's own reader and the values decode as this tool says. What it does not prove: that the device
   accepts it.
2. **`mk2vsc -L -f <file>` on a GX you own.** The GX-side program that serves Remote VEConfigure and the
   Venus OS 3.60+ VE.Bus backup, `/opt/victronenergy/mk2vsc/mk2vsc`, has a list mode that parses a file and
   prints its firmware version, or reports the file as corrupt, without a VE.Bus operation. Evidence:
   venus-platform's `src/vebus_backup.cpp` (open source) calls `mk2vsc -L -f` on every backup in `/data/conf/`
   and parses the `Firmware version = N` line, logging "Discarding corrupt file" otherwise. Run it over SSH on
   any GX; the file need not be for that GX's system. What it proves: Victron's parser accepts the container.
   What it does not prove: the serial, unit-count and firmware gates of an upload (docs/ERRORS.md), which are
   checked against the connected system.

The same `/data/conf/` directory holds the VE.Bus backups Venus OS 3.60+ writes (`<firmware>-<name>-<tty>.rvsc`
or `.rvms`); they are the same file format as a Remote VEConfigure download, produced by the same program
(venus-platform source; Cerbo GX manual, VE.Bus Settings Backup & Restore), and are a second source of files
for the checks in this page.

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
| Section grammar and checksum | proven | every section of all 92 unique files (115 counting archive duplicates); four live uploads accepted; byte-exact round trip on every fixture |
| Settings array as VE.Bus setting IDs 0 to 191 | strong | absorption/float anchor IDs 2/3; IDs 5, 6, 65, 73, 81, 88 corroborate on every block; one firmware only |
| Individual fields | mixed | all 192 IDs carry VEConfigure's identifier; decode confidence 4 CONFIRMED (written and read back live), 68 HIGH, 9 MEDIUM, 12 LOW, 99 UNKNOWN (reserved and grid-code slots, mostly 0 or 0xffff); docs/FIELDS.md lists each with its evidence |
| Guarded writer | proven for its surface | edit-and-revert byte identity on every fixture; reproduces the archived prepared files; 4 live uploads |
| By-serial diff and bookkeeping model | proven | real consecutive downloads, including the swapped-order pair |
| Qualifier | proven against its motivating incident | catches the 2026-08-14 rollback file (fixture); the 2026-08-21 one-inverter GUI write is the case the agreement check was written for, but we hold no fixture from that day |
| Assistant records | read; remove and reinstall | record framing, sizes and the stub signature; `mk2vsc assistant` removed and reinstalled ESS on one live system (2026-09-04) with re-downloads verified; the record body and the 72-byte ESS tail are not understood |
| First-time assistant install (graft) | experimental, gated | `mk2vsc.experimental` behind `--i-accept-the-risk`; reproduces every August 2026 attempt file byte-for-byte; the device stored them and no system started (docs/ESS_INJECTION.md) |
| Grid code | not touched | flag read only; the dealer password is out of scope by policy |
