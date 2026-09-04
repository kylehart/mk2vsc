---
title: "Safety and responsible use"
description: "What is proven, what is not, the guards in the writer, and how to recover."
---

# Safety and responsible use

## Who this is for

People who are already responsible for configuring the Victron systems they work on: owners,
installers, technicians, and integrators who today do this job in VEConfigure. The toolkit gives
that person a scriptable, diffable, reviewable way to make the same settings edits. It does not
give anyone access they did not have. Every file still travels through Victron's authenticated
Remote VEConfigure path on VRM, with the same account and permissions as before.

The library never uploads. It has no network code. It reads a file, writes a file, and tells you
what it changed.

## The proven-safe surface

What we have done repeatedly on live systems without incident:

- Length-preserving edits to u16 values in the settings array, on a device-form download taken
  minutes earlier, with every section checksum recomputed. This is exactly and only what `mk2vsc edit`
  does.
- Fields at CONFIRMED or HIGH confidence (docs/FIELDS.md). CONFIRMED fields (absorption, float, the
  two Virtual Switch DC thresholds) have been written by this toolchain, uploaded, and read back.
  HIGH fields are read correctly on every block we hold but have not been written by us.
- Both inverters of a pair edited together for anything that must match on a shared battery. The
  writer edits every inverter by default; use `--serial` only when you mean a per-inverter value.
- `mk2vsc diagnose --fix` builds its corrected file through exactly these guards, plus one more: it writes
  only the findings named with `--accept`, never a default. A value the file cannot supply is yours to
  enter; the tool proposes no chemistry numbers of its own. The change sheet it prints is the same change
  for VEConfigure, so declining the file costs nothing but typing. Bit-level writes touch one qualified
  flag bit (the LithiumBattery bit); docs/DIAGNOSE.md says what qualifies a bit.

Settings-only uploads did not reset the VE.Bus or interrupt loads on any of our uploads.

## Assistant changes: what works, what is unproven, what has broken live systems

Removing an assistant, and reinstalling one from an earlier download of the same system, work by file
(`mk2vsc assistant`). Both produce upload-form files, and uploading one resets the VE.Bus: the inverters
stop for the duration, the tunnel is unresponsive for about five minutes afterwards, GX-based monitoring
shows the site disconnected and stale inverter states, and the dialog can end in an error although the
device completed. None of that is specific to this toolkit: an assistant change saved from VEConfigure's
GUI and uploaded through VRM behaves the same way. Do it only with someone able to power-cycle the
inverters, the battery well charged and the reinstall file ready before the removal.

Installing an assistant on a system that never had one (a graft of another system's records) is
unproven, and the attempts produced: clean rejection before write (harmless); accepted then a 64-byte
stub written and the payload discarded; accepted, install started, failed at the grid-code step with
VE.Bus error 10 for about 17 minutes; accepted and stored byte-perfectly with the inverters never
starting. A device-form removal attempt left a corrupt assistant program (VE.Bus error 6): device form
is a settings write and cannot remove an assistant. docs/ASSISTANTS.md has the evidence table. The
settings writer refuses to change block length, and the qualifier fails any file that carries the stub.

Fields below HIGH confidence. `mk2vsc edit` refuses them unless you pass
`--i-know-this-is-unverified`. If you do, you are the first person to test that offset on hardware:
do it on a system you can watch, one field at a time, with the baseline ready.

Upload-form files. The GUI's export form has a different layout after +0x45. The writer refuses
upload-form input; edit a device download instead.

## Charge-voltage edits touch a real battery

Absorption and float are the first thing most people want to change and the one edit that can
damage hardware. Before writing them:

- Take the values from the battery manufacturer's specification for your chemistry and module
  count, not from another site's file.
- Know whether a CAN-bus BMS with DVCC is active. If it is, the BMS charge-voltage limit overrides
  the file's values while the link is up, and the file's values are the fallback when it is not.
  That fallback is exactly when a wrong value bites.
- Keep the baseline. Rollback is uploading `00_baseline/`.
- Check the re-download on both inverters. A mismatch between the two inverters on a shared battery
  is a defect in itself; our qualifier fails on it.

## The grid code: what the writer never touches

Victron gates the grid code (country standard, loss-of-mains behaviour, feed-in) behind a password held
by the dealer or distributor. That is their credential and their responsibility. This project does not
attempt to reproduce, derive, or bypass it, and will not accept contributions that do.

The grid code lives in the file as setting 81, a settings block 129 to 189, and three words the
firmware keeps with it: 128 and 191 (`GridSettingsValidCheckerA/B`, equal on each inverter of every
GUI-authored download) and 190. Those words are the firmware's own validity check on the block. The
writer refuses all of them (`fields.GRID_CODE_LOCKED`) and there is no override flag, because a file
that carries them inconsistently is not a settings change but a fault the device meets at its next boot:

- On 2026-09-04 a live System A, ESS running, grid code set, took a device-form file that changed only
  setting 191 from 0x0101 to 0xff00 on both inverters. The device accepted it, ran "Resetting VE.Bus
  products", and within ten seconds every data source on the GX (VE.Bus, BMS, both solar chargers, the
  GX itself) went silent and stayed silent. The system was offline on VRM for the rest of the evening.
  Three other systems on the same network path were unaffected. The file had been built to test whether
  the device would refuse mismatched words before writing; it did not refuse.

A grid code reaches a device through VEConfigure with the password, or by file only as a complete
device-authored block: a fresh download of the same system, or `mk2vsc assistant reinstall` built from
one, which carries 81/128/190/191 exactly as the device last wrote them. That path has never needed
the password (docs/ASSISTANTS.md §8).

## Recovery playbook

In the order we have found to work:

1. Download a fresh file from the device and upload that file back, unmodified or with the minimal
   edit. An archived baseline is rejected as "old configuration file" (mk2vsc-36) once the device
   has saved anything newer. This alone recovered a system we had spent an afternoon believing was
   grid-code-locked.
2. If the portal shows an inverter as "Unknown" or the download is blocked (mk2vsc-62), reboot the
   GX device (Cerbo) and wait for the VE.Bus to re-enumerate. This fixed a run of mk2vsc-47 rejects.
3. Physical power cycle of the inverters, last. Confirm from telemetry that the VE.Bus service
   actually went silent; the display board can go dark while the control board stays up.
4. If the installation has a manual bypass or transfer switch, it keeps loads powered while the
   inverters are down. Remember that a system in bypass is blind in telemetry; do not evaluate a
   change while it is bypassed.

## First-use protocol

1. Run `mk2vsc validate` and `mk2vsc show` on your own downloads for a while, read-only. Compare
   absorption, float and the AC input limit with what VEConfigure or VRM shows.
2. Download twice a minute apart and run `mk2vsc diff`. Expect "ONLY BOOKKEEPING". If you see
   anything else, stop and open an issue with both files.
3. First live edit: one innocuous step, for example float 54.0 to 54.1 V, on a system someone is
   watching, with the battery in a state where a wrong value cannot hurt (our first test was on a
   full battery in daylight).
4. Keep the baseline and the prepared file in the change folder. Diff the re-download against the
   prepared file. Only then trust the tool with the change you actually wanted.

## Things we got wrong, so you do not have to

- We said "uploads do not interrupt the inverters", which was true for settings edits, and then
  applied it to an assistant install, which resets the VE.Bus. Distinguish the two upload classes
  before every upload.
- We treated a structurally valid file as a safe file. Two incidents proved that valid and
  checksummed is necessary and not sufficient. A file the device accepts is a higher-risk event
  than one it rejects.
- We read mk2vsc-36 as "the device now demands a grid-code password" and spent hours on it. It was
  an archived file; a fresh download was accepted at once. Download fresh first, theorize second.
- We then explained that rejection as a save-timestamp check. Tested on 2026-09-04, it is not: older
  stamps with current content are accepted. Test the mechanism before writing it into a rule.
- We built a rollback from a month-old baseline and reverted a correction without noticing. Keep
  intended values outside the file and check every upload against them.
- We compared downloads by file position and saw dozens of spurious differences. Block order is not
  stable. Compare by serial.
- We treated a field named "valid checker" as a bookkeeping word and wrote one of its two halves on a
  live system to see whether the device would object. It did not object; it accepted the file, reset the
  bus, and the GX went dark. A validity check is not a setting. Read the name before the test.
