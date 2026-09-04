# Changelog

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
