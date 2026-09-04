---
title: "How mk2vsc came to be"
description: "The story of the format work, in order, including what went wrong."
---

# How this came to be

This toolkit exists because we operate four Victron MultiPlus systems (two inverters each, split
phase, 48 V lithium batteries) on an island where grid power is expensive and unreliable, and because
the only supported way to change their configuration was a Windows-only program driven through a virtual
machine. Every design choice in the code traces back to something that happened to a real system. This
file tells those stories in order, with dates, so the choices make sense.

Systems are referred to by public aliases, System A to System D, never by the property they serve.
Inverters are referred to by serial. "The installer" is the company that commissioned the systems and holds the grid-code password.

## June 2026: reading files, and a first patcher we later froze

We started by downloading each system's `.rvms` from VRM Remote VEConfigure and looking at the bytes. The
ASCII inverter serials were obvious. Scanning for adjacent u16 pairs in the 45 to 59 V range found the
absorption and float voltages at block offsets +0x5d and +0x5f, and they matched what VRM reported.

That alone paid for itself. Two of the four systems (System A and System C) had one inverter set to
48.0 / 48.0 V absorption / float while its partner ran 57.6 / 55.2 V. On a shared battery, a
48 V charge target means that inverter never really charges. The installer's technician had told us it
was harmless because "the slave's config is ignored". The files and the live per-leg currents said
otherwise: these are split-phase pairs, each inverter governs its own leg.

A second find came from a VEConfigure screenshot of the Virtual Switch tab, which let us anchor the
"ignore AC input when Udc lower than" and "accept battery again when Udc higher than" thresholds at
+0xc5 and +0xcd. System A and System C carried a return threshold of 64.00 V. A 48 V lithium battery cannot
reach 64 V, so once those systems dropped to grid pass-through they could never come back on voltage.
That was the mechanism behind a 5.6-day stuck-on-grid episode we had been unable to explain from
telemetry alone.

We wrote a byte patcher. Two files from System B produced by an older tool build (block length 0x1ea)
differed in three body bytes and two trailer bytes, and the trailer bytes moved by exactly the body
deltas. We concluded "two 8-bit sum checksums" and reproduced that file byte-for-byte. A code review a
few days later froze the patcher: it had been validated on one edit of one legacy file, the production
files had a different block length and a four-byte trailer that did not respond like two sum8 fields,
and the tool wrote charge voltages to a battery without a BMS. That freeze was correct, and the
"two sum8" reading turned out to be a special case of the real answer, right by luck.

## 2026-07-20: the checksum

The production trailer resisted a CRC search. We ran an exhaustive CRC-16 sweep: every odd polynomial,
both common inits, both reflections, both xor-outs, 25 candidate spans, required to match on four files.
13.1 million trials in five minutes, zero hits. Common CRC-32s, Fletcher and Adler also missed.

The breakthrough was noticing that we already held controlled pairs. VEConfigure rewrites a few bytes at
+0x4f on every save even when nothing changes, so two consecutive downloads of an unchanged system
differ only there. In such a pair the trailer bytes changed by exactly the same amounts as the input
bytes, in position. A CRC scrambles; this did not. The field is additive.

Fixing the span and width took one more observation: with a 32-bit little-endian word sum over the
block, the difference between the stored value and the computed sum was the same constant on every block,
0x6142000F. One formula, one constant, 28 of 28 blocks across four legacy and ESS block lengths.

This month (September 2026), while preparing this release, we looked at where that constant comes from.
Read from the section's own two-byte length prefix, the first word of `0f 00 "Ba"` is `0f 00 42 61`,
little-endian 0x6142000F. There is no constant. The checksum is a plain word sum over the whole section
starting at its length prefix, and the "`0f 00` framing" we had been describing at the end of each
block is the length prefix of the next section. The same sum validates the Mk2vscInfo and
BareSettingInfo sections too, which earlier tooling never checked. Every section of all 84 unique files
in the fixture corpus validates.

## 2026-07-20: the first live proof

The same afternoon we changed float from 54.0 to 54.1 V on both System D inverters with the new
writer, uploaded the file through VRM Remote VEConfigure, and got "Success, the system has been
configured". The re-download read 54.1 V on both inverters and passed our validator, which meant
VEConfigure and the device compute the field the same way we do. The diff between what we uploaded and
what came back was the save timestamp and the checksum, nothing else.

By evening the charge profiles on all four systems had been corrected by file: 56.8 / 54.0 V on both
inverters where they had been mismatched. Each change was staged in a folder with the fresh download,
the prepared file and the post-upload download, and a written record. That folder pattern became
docs/CHANGE_CONTROL.md.

## July to August 2026: the assistant campaign

We tell this part in detail because the failures shaped the safety rules, and because someone will be
tempted to repeat it.

System C had the ESS assistant loaded on one inverter only, a half-installation that caused power to
flow across the two phases. We wanted ESS on both inverters of every system, and we wanted to do it by
file rather than wait for another Windows session.

**Removal test, 2026-07-20 afternoon.** We truncated System C's ESS block back to a bare block, recomputed
the pointer and checksum, and uploaded. Two earlier versions were cleanly rejected (mk2vsc-49) and taught
us the pointer and framing rules. The third was accepted, and the running assistant became corrupt:
VE.Bus error 6 (DDC program error), the system dropped from ESS to pass-through, the inverter went off.
The stored file still showed the assistant present. Recovery was a baseline re-upload and a GX reboot;
the battery was full and the building never lost power. Lesson: file validity is necessary, not
sufficient. An assistant is a program with internal consistency, and truncation breaks it.

**Load-both v3, 2026-07-20 evening.** A transplanted assistant block for the second inverter was
accepted. VEConfigure showed "Resetting VE.Bus products", began a real install, and failed at the grid
code step with mk2vsc-36. The VE.Bus sat in error 10 for about 17 minutes, then re-enumerated after
reboots. Afterwards even the clean pre-incident files were rejected with mk2vsc-36. At the time we
read that as the device now demanding a password; see the recovery lesson below for what it really was.

**System B, 2026-07-24.** Two versions were rejected with mk2vsc-47 ("more than one unknown unit"). One had
a real defect (a block copied from a GUI export in upload form, so every field after +0x45 was shifted
10 bytes). Fixing it changed nothing, because the actual cause was the GX showing one serial as
"Unknown"; a GX reboot cleared it and the same construction was accepted. Then VEConfigure wrote a
64-byte empty container on each inverter and discarded our 7049-byte payload. We rolled back. The
re-download taught us that the two blocks swap file position between downloads, so every comparison must
be by serial (see mk2vsc/diff.py).

**System A, August.** On 2026-08-12 a graft with assistant records byte-identical to the working System C
install was accepted and stubbed again, with a tunnel timeout mid-write and a VE.Bus reset. A second
version that also stamped the seven header bytes that differ between bare and grid-coded blocks got
further, into "Resetting VE.Bus products", and was rejected at commit with mk2vsc-36. The archived bare
baseline was then rejected with the same error after a clean reboot. We wrote it up as "the device now
requires the password to commit anything". A fresh download, byte-compared to the baseline, showed the
device had written nothing at all: every rejection was a clean pre-write reject. Uploading that fresh
download, unmodified, was accepted first try. The "old configuration file" half of the mk2vsc-36
message was literal: the archived file carried a stale save timestamp. This is now Rule 2 of change
control and the most useful thing in docs/ERRORS.md.

Versions 5 through 7 hunted for "install state" bytes by diffing working installs against bare blocks.
v7 stopped a 15-second off/fault cycle by normalising five header bytes, which showed internal
consistency matters, but the system then sat stably Off, connecting, with no error. A cold boot from the
rocker switches preserved every byte and changed nothing.

**The upload-form transform, 2026-08-13.** GUI exports carry a 16-byte blob at +0x45 and compact
assistant records; device downloads carry zeros and padded records. We built a transform from device
form to upload form and proved it reproduces the installer's actual export from the device's own
download, byte-for-byte per block. The first upload was rejected mk2vsc-49 because we emitted blocks in
the download's order and the two-byte prefix that follows the first block belongs to the next section,
so the parser miscounted units. Fixing order and stamping current unix timestamps (that is what the
"nonce" fields are) produced a file the device accepted. System A then stored a perfect ESS configuration
and still did not start.

**System D, 2026-08-13.** A one-shot graft from a clean bare state, carrying every header value the
working installs had, was accepted and stored, and the system did not start either. Telemetry was dark
for six hours and the building was found without power; it was put on manual bypass.

**Pattern and hypothesis.** GUI-authored files (System C, System B) load and run. Our byte-authored files
(System A, System D) load, store byte-perfect, advertise the assistant, and never leave the connecting
state. The only discriminator we could not falsify was live BMS data: the two runners had it, the two
non-starters did not (System A's CAN bus had been physically dead since 2026-07-20, System D has no BMS
connected). A loaded ESS assistant may gate system start on valid battery data. This is a hypothesis,
not a finding.

**End state, 2026-09-02.** The installer performed GUI sessions on the remaining systems. System A, with
its CAN bus repaired and a third battery module installed, now runs ESS on both inverters with the
charge profile corrected in the same session. That is consistent with the BMS hypothesis but does not
test it: the assistant was GUI-authored. Whether a file built by our transform would have started on a
healthy-BMS system remains untested. The transform and the graft ship under `mk2vsc.experimental`, gated
and documented in docs/ESS_INJECTION.md, so that someone can run that test.

## 2026-08-19: the month-long regression

A routine decode showed System A back at the mismatched 56.0 / 57.6 V and 54.0 / 55.2 V charge profile
we had corrected on 2026-07-20. Every August full-configuration upload (grafts, the upload-form test,
the rollback) had been built from a baseline that predated the fix. A `.rvms` upload replaces the whole
configuration; there is no merge and no warning. Our configuration-change monitor logged the reversion
the day it happened. Nobody looked. Detection without a review step is not protection.

The rollback file that reintroduced the error passed every structural check we had: valid checksums,
diff limited to intended bytes, all 15 graft assertions. What it lacked was a comparison against what
the settings were *supposed* to be. mk2vsc/qualify.py keeps intended values outside the file under test
and refuses any file that disagrees with them, and any file whose two inverters disagree with each
other. Run before upload and again on the re-download.

## 2026-08-21: seven settings on one inverter

During a GUI session on System D, seven settings were written to one inverter and none to the other,
leaving the two legs 0.3 V apart on a shared battery. VEConfigure sends settings one inverter at a time
and it is easy to forget the second. The qualifier's agreement check exists for exactly this case.

## September 2026: the settings array

Preparing this release, we asked where the two confirmed charge voltages sit relative to each other
and to the block. Absorption is at +0x5d and float at +0x5f, and in the public MK2 protocol reference
they are VE.Bus settings 2 and 3. If the block holds the settings as a flat u16 array starting at
+0x59, setting n is at +0x59 + 2n. We checked the rest of the array against that reference across all
every block in the corpus: setting 5 reads 120 (these are 120 V inverters) on every device-form block, 6 reads 500
(50.0 A input limit), 65 reads 190 or 196 (95 % or 98 %, exactly the reference's LiFePO4 example),
81 reads 0 on bare blocks and 1 on grid-coded ones, 73 reads 63.00 V (a protection threshold we had
seen in the alarm history). Several bytes we had chased for weeks as "install state" turned out to be
ordinary settings: the byte at +0x5a that changed from 0x89 to 0x81 during GUI installs is the
adaptive-charge bit of flags register 0; "+0xdb be vs c4" is SoC at bulk end, 95 % versus 98 %.

The same pass retracted one of our five "confirmed" fields. The "Virtual Switch SoC threshold = 20 %"
at +0x10a is the high byte of setting 88 (5200 = 0x1450, high byte 0x14 = 20) which reads 52.00 V on
every block. All four systems really are set to 20 %, which is why the coincidence survived so long.
The SoC threshold's true location is not known.

## What we would do differently

- Treat every consecutive download as a controlled experiment from day one. The checksum was solvable
  from files we already had a month before we solved it.
- Look up the public VE.Bus setting IDs before naming a single offset. The array mapping would have
  replaced weeks of differential decoding.
- Never test a structure-changing upload on the only production ESS system. A file that is accepted is
  a higher-risk event than one that is rejected, and we crossed that line without pausing.
- Compare by serial from the first diff. Block order is not stable.
- Read the monitor. A configuration-change detector that nobody reviews is not a control.
- Write the intended values down before uploading anything, and check the file against them.

## September 2026: neighbours

After release we found talas9/rvsc-tools, a read-only `.rvsc` viewer published in July 2026 whose author
had decoded the same per-setting schema independently and extracted VEConfigure's internal setting
identifiers from the application binary. Our "no prior art" statement was wrong by two months. We
adopted the identifier table with attribution; it named the settings above 65 that Victron's document
does not, and corrected two of ours (73 is a current limit, not a voltage; 70 is `vs2StartOnSOC`).

## September 2026: the two bytes before the record

For two months the assistant area was described as `marker(2) subtype(2) len(2) body`, with `ff ff` an
empty slot and `f5 ff` an assistant record, and issue #24 asked why System B's 704-byte record carried
subtype `0001` where the other systems carried `0101`. Reading the wire-protocol work in
xcellsior/ve-bus-programming showed settings 128, 190 and 191 as grid-code / loss-of-mains words that
read 0xffff until a grid code is set. Our array was read as 190 entries; the file's own schema has 192
records. Reading two more words put `f5 ff` at setting 190 and `01 00` / `01 01` at setting 191 on every
grid-coded block, `ff ff ff ff` on every never-coded block, and partial residues on bare blocks taken after
a rollback. The "marker" and "subtype" were settings; the record is `len | body`. The independent review
of that change then corrected the first reading of the words: on the GUI-authored installs 128 equals 191 on
each inverter and a pair can carry different values (System C: 1 on one inverter, 0x0101 on the other) or
the same (System B both 1, System A both 0x0101), while, among blocks with a grid code set, our own
never-started grafts are the only files with 128 and 191 disagreeing. So the value is set per inverter by the grid-code step; whether it encodes the
loss-of-mains mode as it does on xcellsior's single bench unit is not established from our files, and
issue #24 was mis-stated rather than answered. The lesson repeats the one from the settings array
itself: name a byte by its VE.Bus setting ID before giving it a meaning, and a value that fits two
stories fits neither until a second observation separates them.

## 2026-09-04: assistants by file

Six uploads on System D, each on a fresh download and each verified by re-download, took the toolkit from
"settings only" to removing and reinstalling the ESS assistant by file. The decisive step was uploading the
system's own download rewritten in the GUI's upload form with nothing changed: the device reset the VE.Bus,
which no device-form upload had ever caused, and ESS came back. The container form, not the content, was
what every earlier attempt had wrong. A removal file and a reinstall file built the same way then did
exactly what they said, and the dialog's closing "Error 1303" turned out to mean only that the tunnel had
timed out while the device finished. The lesson for the record: when the device stores your bytes and does
nothing with them, ask which procedure it ran, not which bytes it disliked.

## What remains open

The open questions are tracked as GitHub issues, in priority order, at
https://github.com/kylehart/mk2vsc/issues (pinned roadmap issue at the top). Everything unresolved in this
document has an issue there; nothing is tracked only here.
