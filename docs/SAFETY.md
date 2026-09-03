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
  minutes earlier, with every section checksum recomputed. This is exactly and only what `rvms set`
  does.
- Fields at CONFIRMED or HIGH confidence (docs/FIELDS.md). CONFIRMED fields (absorption, float, the
  two Virtual Switch DC thresholds) have been written by this toolchain, uploaded, and read back.
  HIGH fields are read correctly on every block we hold but have not been written by us.
- Both inverters of a pair edited together for anything that must match on a shared battery. The
  writer edits every inverter by default; use `--serial` only when you mean a per-inverter value.

Settings-only uploads did not reset the VE.Bus or interrupt loads on any of our uploads.

## What is unproven and what has broken live systems

Assistant changes by file. Adding, removing, or transplanting an assistant record has produced four
outcomes for us, none of them a working install:

1. Clean rejection before write (mk2vsc-47, mk2vsc-49). Harmless.
2. Accepted, then the device wrote a 64-byte empty stub and discarded our payload.
3. Accepted, began installing, failed at the grid-code step; the VE.Bus was left half-configured
   (VE.Bus error 10) for about 17 minutes, and an earlier removal attempt left a corrupt assistant
   program (VE.Bus error 6). Both were recovered by re-uploading the baseline and rebooting the GX.
4. Accepted and stored byte-perfectly, and the inverters never started.

docs/ASSISTANTS.md has the evidence table. The writer refuses to change block length, and the
qualifier fails any file that carries the stub. Do not work around either on a system that matters.

Fields below HIGH confidence. `rvms set` refuses them unless you pass
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

## The grid-code password

Victron gates the grid code (country standard, loss-of-mains behaviour, feed-in) behind a password
held by the dealer or distributor. That is their credential and their responsibility. This project
does not attempt to reproduce, derive, or bypass it, and will not accept contributions that do.
Setting 81 (grid-code active flag) and the LOM entries are documented so that files can be read and
compared; the writer does not touch them. If your job needs a grid code, it needs the dealer and
VEConfigure.

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

1. Run `rvms validate` and `rvms decode` on your own downloads for a while, read-only. Compare
   absorption, float and the AC input limit with what VEConfigure or VRM shows.
2. Download twice a minute apart and run `rvms diff`. Expect "ONLY BOOKKEEPING". If you see
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
  a stale save timestamp. Download fresh first, theorize second.
- We built a rollback from a month-old baseline and reverted a correction without noticing. Keep
  intended values outside the file and check every upload against them.
- We compared downloads by file position and saw dozens of spurious differences. Block order is not
  stable. Compare by serial.
