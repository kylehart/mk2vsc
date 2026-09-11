---
title: "Donate a configuration file"
description: "How to send a VRM Remote VEConfigure download so it can be run through the validation tools; what happens to it; the consent sentence."
---

# Donate a configuration file

## Why

Every claim in this project is tested on files. The corpus holds one firmware, one format version and one
topology (two-inverter split-phase pairs). Every firmware and topology we have not seen is a test we cannot
run: a single unit on a 24 V MultiPlus, a Quattro, a three-phase system with a generator assistant, an
old-microcontroller unit, a 230 V system. One file from such a system either confirms that the format model
holds there or shows where it does not, and both are useful.

## What to send

- A fresh VRM Remote VEConfigure download (VRM, Device list, the inverter/charger, Remote VEConfigure,
  Download), `.rvsc` or `.rvms`, of a system you are responsible for. Save it to disk; do not open it in
  VEConfigure first.
- Optionally, a screenshot of one VEConfigure tab (Charger or General) so one value in the file can be
  matched to what the GUI shows.
- The consent sentence below, and whether the file may become a fixture.

A Venus OS 3.60+ VE.Bus backup from `/data/conf/` on the GX is the same file and is equally welcome.

## How

Email the file to `DONATE_EMAIL_PLACEHOLDER`. Nothing else is needed; if you prefer, say what the system is
(model, battery voltage, number of units), but that is also read from the file.

## What we do with it

- Run it locally through `mk2vsc validate`, `census`, `diagnose` and `tools/validate_dir.py`.
- Report aggregate results only (counts by unit count, firmware family, format version, form, pass/fail per
  check), as in docs/QA.md. The file, its serials, its timestamps and any site name are never published.
- Create a pseudonymised fixture (serials replaced, every other byte as downloaded, checksums recomputed) for
  the public corpus only if you gave written consent for that.
- Delete the file on request.

## What you get back

- The tool's read of your file: the `census` output, the decoded settings, and any finding `diagnose` raises,
  with the evidence.
- If your file breaks a claim, the finding and what changed in the format description as a result.

## Consent sentence

Include one of these in the email:

> I am responsible for this system and you may use this file for testing; publish aggregate results only.

> I am responsible for this system and you may use this file for testing and publish a pseudonymised copy of
> it as a fixture in the mk2vsc repository.
