---
title: "Assistants (ESS) in VEConfigure .rvms files"
description: "What the assistant records look like, what a GUI install writes, and what this tool will not do."
---

# Assistants (ESS) in the file: what we know, what we do not, what we will not do

An "assistant" is a small program VEConfigure loads into a MultiPlus or Quattro. ESS is the one most
people want. Assistants cannot be installed with VictronConnect, so they are the main reason people
still need a Windows machine. This document records everything we learned about how assistants appear
in `.rvms` files, and the clear limit: **this toolkit reads assistant areas; it does not author,
transplant or remove them.** We tried, on live systems, and it did not work. Details below.

Vocabulary: CONFIRMED means observed on our systems and reproducible from the fixtures. HYPOTHESIS means
one explanation consistent with the evidence that we could not falsify. Systems are System A, System B, System C,
System D; inverters by serial.

## 1. Where the assistant lives (CONFIRMED)

Each inverter's block holds a 192-entry u16 settings array followed by an *assistant area* that runs to
the section checksum. The area is one record and a tail:

    area   := length(2) body[length] tail
    tail   := 0xff padding | ff | u16 free-space counter   (bare, container and stub blocks)

The four bytes just before the length are settings 190 and 191, the grid-code / loss-of-mains words
(`ff ff ff ff` when no grid code was ever applied, `f5 ff` + `01 00` or `01 01` with one; see
docs/FIELDS.md). They are part of the settings array, not of the assistant record.

| Block state | Area bytes (device form) | Meaning |
|---|---|---|
| bare | `00 00 ff 00 0b` (5 bytes) | length 0; free = 2816 |
| bare, older tool build | `06 00 a7 fe 00 00 57 01 ff fa 0a` | a 6-byte empty container carrying the signature `a7 fe 00 00 57 01`; free = 2810 |
| stub | `40 00 a7 fe 00 00 57 01` + 0xff filler + `ff c0 0a` | the 64-byte empty container VEConfigure writes when it discards a transplanted assistant; free = 2752 |
| ESS (GUI installed) | `c0 02` + 704 bytes, or `80 04` + 1152 bytes, then 72 bytes | one record per inverter of the pair; see below |

The free-space counter is 2816 (0x0b00) minus the body length on every bare, container and stub block
in the corpus. On ESS blocks the last three bytes read `ff 00 00` and the relation does not hold; the
72-byte ESS tail (mostly 0xff, then `0e 00 8e 01 15 00 76 c4 e8 db ff 00 00`) is **not understood**.

## 2. The ESS records (CONFIRMED)

Every GUI-installed ESS system we hold carries exactly two records, one on each inverter: 704 bytes and
1152 bytes. Which inverter gets which follows its role in the pair (the slot bytes at +0x35/+0x37 and
the low nibble of the flag at +0x36). Setting 191 next to the record reads 0x0001 (LOM type B) or
0x0101 (no loss-of-mains detection) and is a per-inverter grid-code setting, independent of the record.

Aligned by role, the 1152-byte body is byte-identical across System C, System B and System A. The 704-byte body
differs by one byte across systems (a primary/secondary flag near the record start). So the payload is a
fixed template chosen by role, not a program compiled per inverter. That observation was correct and
still did not make transplanting work; see section 4.

What the body is: entropy about 6.2 bits per byte, 8 % zero bytes, recurring two and three byte
sequences at regular strides, and embedded parameter values (the bytes for 48.00 V and 10 % appear
inside it). It looks like an assembled program with its settings woven in. VE.Bus error 6 is literally
"DDC program error", and truncating this region produced that error. We cannot read it.

## 3. Device form and upload form (CONFIRMED)

The GUI writes the assistant records compact (no 0xff padding runs, shorter block, a 16-byte export
blob at +0x45). The device stores them padded and returns zeros at +0x45. A transform between the two
forms exists and round-trips the installer's real export from the device's own download, byte-for-byte
per block. The device accepted such a file on System A on 2026-08-13. The system stored the configuration
and did not start (section 4, mode D). The transform ships as `mk2vsc.experimental.upload_form`, gated behind
`--i-accept-the-risk`; docs/ESS_INJECTION.md records every attempt made with it.

## 4. The four failure modes we observed

| Mode | What the device did | Written to device? | Examples |
|---|---|---|---|
| A. clean reject | mk2vsc-47 or mk2vsc-49 before any write | no | System C v1/v2 (07-20), System B v2/v3 (07-24), System A upload-form v1 (08-13) |
| B. accept, then stub | began an install, discarded our records, wrote a 64-byte empty container on each inverter, flipped the flags to e4/e5 | yes, a stub; rollback by re-uploading a fresh bare file works | System B v4 (07-24), System A v3 (08-12) |
| C. accept, half apply | "Resetting VE.Bus products", real install started, failed at the grid-code step with mk2vsc-36, VE.Bus error 10 for about 17 minutes | partially; GX reboots and a baseline re-upload recovered it | System C load-both v3 (07-20); System A v4 reached the same dialog and was rejected at commit with nothing written |
| D. accept, store, never start | configuration stored byte-perfect and stable across cold boot, assistant advertised on both inverters, system stays Off in the connecting state with no error | yes; a fresh bare file restores operation | System A v7 and upload-form v2 (08-13), System D one-shot graft (08-13) |

A fifth outcome belongs here for completeness: the removal attempt on System C (07-20) was accepted and
left the *running* assistant corrupt (VE.Bus error 6) while the stored file still showed it present.

## 5. Evidence table

| Date | System | File shape | Device response | Outcome |
|---|---|---|---|---|
| 2026-07-20 | System C | ESS block truncated to bare, v1/v2 | mk2vsc-49 | rejected; taught pointer and length rules |
| 2026-07-20 | System C | truncated, v3, correct shape | accepted | VE.Bus error 6, ESS dropped, inverter off; recovered by baseline + reboot |
| 2026-07-20 | System C | ESS block transplanted onto second inverter, v3 | accepted, "Resetting VE.Bus products", mk2vsc-36 | VE.Bus error 10, 17 min; recovered by reboots; pre-incident files then also rejected |
| 2026-07-24 | System B | both blocks with transplanted records, v2/v3 | mk2vsc-47 | GX showed a serial as Unknown; GX reboot fixed it |
| 2026-07-24 | System B | same, v4, after reboot | accepted | 64-byte stubs on both inverters; rolled back |
| 2026-08-12 | System A | records byte-identical to System C's, v3 | accepted, Error 1303 mid-write | stubs on both inverters, VE.Bus reset; rolled back |
| 2026-08-12 | System A | v4 with seven "grid code" header bytes stamped | "Resetting VE.Bus products", mk2vsc-36 at commit | nothing written; archived baseline also rejected until a fresh download was uploaded |
| 2026-08-13 | System A | v5/v6/v7 header normalisation | accepted | v7 stopped a 15 s off/fault cycle; system stable Off, connecting, no error; survived cold boot |
| 2026-08-13 | System A | device form converted to upload form, v1 | mk2vsc-49 | block order and framing; fixed |
| 2026-08-13 | System A | upload form v2, fresh timestamps | accepted | stored; did not start |
| 2026-08-13 | System D | one-shot graft with all known header values | accepted (Error 1303 at end) | stored; did not start; telemetry dark 6 h; building on bypass |
| 2026-09-02 | System A | installer's GUI session, healthy BMS, third module installed | accepted | ESS running on both inverters |

## 6. The grid code and the dealer password (stated carefully)

Victron gates grid-code selection in VEConfigure behind a password held by dealers. ESS will not use
the battery to support loads on grid unless a grid code is set. We do not have a way to bypass that
gate, we did not look for one, and this toolkit will not include one. What we observed is narrower:

- Setting 81 (`grid_code_active`) is 0 on every bare download and 1 on every GUI-authored ESS block.
  Setting 128 (`lom_config_a`) moves from 0xffff to 1 or 0x0101. A few other settings change too
  (60, 67, 69, and the adaptive-charge bit in flags register 0). Those are ordinary settings the GUI
  writes; they are not a credential.
- The password is not stored in the file. Two independent GUI exports from the same session carry
  identical bytes apart from timestamps.
- mk2vsc-36 reads "Incorrect grid code password or old configuration file". We hit it in two situations:
  once when a real install reached the grid-code step (mode C), and repeatedly when uploading archived
  files whose save timestamp was older than the device's. The second is the common case and the fix is
  a fresh download. See docs/ERRORS.md.

If you need a grid code set, that is a job for whoever holds the password, in VEConfigure. Everything
else in the file, including every charge and Virtual Switch setting, can be edited without it.

## 7. The BMS-gate hypothesis (HYPOTHESIS)

After the System A and System D installs stored correctly and did not start, we diffed the full live
runtime state of a running system against a non-starter. The one discriminator we could not remove was
battery data on the CAN bus: both runners had a live BMS; System A's CAN bus had been physically broken since
2026-07-20 (no RX packets, error-passive transmitter), and System D has no BMS connected. Both
non-starters sat with `SwitchoverInfo/Connecting = 1`, main state 2, zero errors. Things we falsified as
the blocker: the file bytes (stable across cold boot), GX grid-metering settings (fixed, no change),
DVCC on or off, every restart lever.

System A now runs ESS after the installer's GUI session on a repaired bus. That is consistent with the
hypothesis and does not test it, because the file was GUI-authored. The clean test would be uploading a
transformed file to a healthy-BMS system, and we have not done it.

## 8. What this toolkit will not do

- Author, remove or transplant an assistant as a supported operation. `set_settings` refuses any edit that
  changes block length. The graft and the upload-form transform exist only under `mk2vsc.experimental`,
  gated behind `--i-accept-the-risk`, because no file they produced has ever run; docs/ESS_INJECTION.md
  is the full record and the hand-off to whoever tries next.
- Treat upload-form files as an input for settings edits. The writer refuses them.
- Anything involving the grid-code password.

If you are tempted anyway: a file the device *accepts* is a higher-risk event than one it rejects. Modes
B, C and D above all started with "Success" or a progress bar. Do it on a system nobody depends on, with
someone at the switches, with the battery full, with a fresh bare download ready to upload.

## 9. What a contributor could safely investigate offline

- The record body: compare the 704 and 1152 byte bodies across the fixtures (they are in every
  `*_download_ess_*` file); locate the embedded parameters (48.00 V is `c0 12`, 10 % is `0a 00`) and see
  whether they track the ESS settings shown on the GX.
- The 72-byte ESS tail and the `0e 00 8e 01 15 00 76 c4 e8 db` sequence.
- Files from single-unit systems (`.rvsc`) and three-phase systems. We hold none; the section grammar
  and checksum probably carry over, the block layout may not.
- Files with other assistants (AC PV, generator start/stop, relay assistants) to see how the record
  length and body identify the assistant.
- A GUI export and its post-upload device download, from a session where exactly one thing was changed.
  Pairs like that are what moved this project forward; see docs/QA.md on contributing fixtures.
