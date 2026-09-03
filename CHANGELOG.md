# Changelog

## 0.1.0 (2026-09-03)

Initial extraction into a standalone repository from the tooling we built while operating four
MultiPlus systems between June and September 2026.

* Section parser and serializer with byte-exact round trip (`rvms/sections.py`).
* Integrity checksum: a plain 32-bit little-endian word sum over every section from its length prefix.
  This replaces the earlier description "sum from block offset 2 plus the constant 0x6142000F"; the
  constant was the section's own first word.
* Per-inverter block model with device-form and upload-form detection (`rvms/units.py`).
* Settings table keyed by VE.Bus setting ID (array of 190 u16 at block offset +0x59) with a
  confidence level per field (`rvms/fields.py`). The earlier field `vs_soc_pct` at +0x10a is retracted;
  that byte is the high byte of setting 88.
* Decoder, by-serial diff with bookkeeping classification, guarded length-preserving writer,
  intent-based qualifier, read-only assistant-area parser, and the `rvms` CLI.
* Corpus of 84 unique fixture files with manifest, and 451 tests that check every documented claim
  against it.
* Documentation: FORMAT, FIELDS, CHANGE_CONTROL, WORKFLOW, SAFETY, QA, ASSISTANTS, ERRORS, HISTORY,
  FIXTURES.
