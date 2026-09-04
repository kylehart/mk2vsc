---
title: "What mk2vsc-36, mk2vsc-47, mk2vsc-49, Error 1303 and VE.Bus errors 6 and 10 mean"
description: "Decoder for the messages Remote VEConfigure and the device show, what was written, and what to do."
---

# Error and message decoder

What the messages mean, whether anything was written to the inverters, what to do, and how sure we are.
"Observed" means we saw it on our own systems and read the device state afterwards from a fresh
download. "Documented" means the meaning comes from Victron documentation or community posts and we
have not seen it ourselves.

The single most useful rule in this file: **if an upload is rejected and you are not sure why, download
a fresh copy from the device, then upload that (edited or not).** Most rejections we hit were mk2vsc-36 on
archived files; a fresh download of the same system was accepted every time (see mk2vsc-36).

## Remote VEConfigure upload errors (from the device's VE.Bus layer)

The `mk2vsc-NN` codes come from the MK2/MK3 protocol layer that parses the uploaded file on the GX or
inverter side, not from the VEConfigure program. They are verdicts on the bytes.

### mk2vsc-36  "Incorrect grid code password or old configuration file"

On a settings-only upload the file is refused and the settings are not applied. What the device objects to
is not fully established; the record below is what we hold.

**Observed rejections of archived files.** System A 2026-08-12: right after a hand-built file carrying
assistant records and grid-code words had been accepted into the install dialog and refused at commit, the
archived bare baseline (`system_a_2026-08-12_download_bare_deviceform_1`, settings 190/191 = 0xffff) was
refused repeatedly across two GX reboots; the fresh downloads taken then (`..._2`, `..._3`) carry settings
190/191 = 0xfff5/0xff00 on both inverters, so the device had written its grid-code words during the
attempt, and uploading that fresh download unmodified was accepted at once. System C 2026-07-20: after the
half-applied install (VE.Bus error 10), every pre-incident file was refused; the post-incident download
(`system_c_2026-07-20_download_half-ess_deviceform_5`) carries 190/191 = 0xfff5/0x0000 where the refused
files carry 0xffff/0xffff.

**Observed rejections at the grid-code step.** System C 2026-07-20 and System A 2026-08-12, after the
"Resetting VE.Bus products" dialog of a hand-built assistant install (System A v4 carried grid-code words
that differed from the device's and was refused at commit, not up front).

**What it is not.** It is not a timestamp check. The u32 at block offset +0x4f (+0x59 in upload form) is
stamped when the file is generated (`system_b_2026-09-04_download_ess_deviceform_1/2/3`: unchanged content,
three increasing stamps), and on 2026-09-04 System B accepted the three-hour-old `_1` after `_2` had been
taken, and then `system_b_2026-09-04_prepared_ess_deviceform_1` (the `_2` content stamped 16:00, before a
file it had just accepted). Neither was refused.

**Cause: Unknown.** Two readings fit part of the record and neither fits all of it. (a) The first half of
the message is literal and a device-form file whose grid-code words (81, 128, 190, 191) disagree with the
device's is refused: every refused archived file above carried words that differed from the device's. But
on 2026-08-14 System A accepted a device-form bare file (`system_a_2026-08-14_prepared_bare_deviceform_1`,
128 = 0xffff, 191 = 0xff00) while it held an ESS install with 128 = 191 = 1: a device-form file with
differing words that was not refused. (b) A transient state of the device in the minutes after an
interrupted install: both refusals of archived files happened within the same session as an install
attempt that ended at commit or in error 10, and the 08-14 acceptance came a day later. Neither reading
has been tested as a controlled experiment (a current file with only those words changed; an archived file
uploaded long after any install attempt).

What to do: download fresh, rebuild your edit on that file, upload; a fresh download carries the device's
current grid-code words. Do not edit settings 81, 128, 190 or 191 in a device-form file. If the system is
in error 10, see below.

### mk2vsc-47  "More than one unknown unit detected"

A pre-write reject: the parser could not match the blocks in the file to the inverters it discovered on
the bus. *Observed* twice with different causes:

- A block copied from a GUI export (upload form) into a device-form file. The 16-byte blob at +0x45
  shifted every following field by 10 bytes, so the identity words sat at the wrong offsets (System B
  2026-07-24, v2). Fixing the file did not clear the error, because of the second cause.
- The GX itself showed one inverter's serial as "Unknown" in VRM. A GX (Cerbo) reboot restored
  enumeration and the same construction was accepted (System B 2026-07-24, v3 then v4).

Device state: nothing written. What to do: check the device list in VRM for an "Unknown" serial first;
reboot the GX if so. Then check the file with `mk2vsc validate` and `mk2vsc show` (form must be "device").
Confidence: observed.

### mk2vsc-49  "Number of units in file does not match number of units discovered"

A pre-write reject: the unit walk over the file found the wrong number of blocks. *Observed* four times,
always with a hand-built file: a wrong next-section pointer, a block shorter than the canonical length,
and blocks emitted in the wrong order so that the two-byte length prefix of the following section sat
after the wrong block. `mk2vsc validate` catches a broken pointer chain and bad checksums; it does not know the canonical block
length, so a structurally consistent but too-short block still passes it.

Device state: nothing written. What to do: run `mk2vsc validate`; if it passes and you still get this,
you have found a structural rule we do not know. Please open an issue with the file. Confidence: observed.

### mk2vsc-62  (download blocked)

Seen when trying to *download* while the VE.Bus was re-enumerating after an interrupted install
(System C 2026-07-20, `NumberOfMultis` read as none on the GX). Wait for the device list to show all
inverters again, or reboot the GX. Device state: unchanged by the download attempt. Confidence: observed
once.

### Error 745  "Cannot find VE.Bus system" (on download)

The GX cannot see the inverters over VE.Bus at this moment. Seen immediately after an upload that reset
the VE.Bus (an assistant change from any source): the bus is re-enumerating. Nothing is wrong with the
file. Wait a few minutes and download again; if it persists, check the VE.Bus cabling and the GX.

### Error 1303  "VRM connection stopped responding"

A VRM tunnel timeout, not a verdict on the file. *Observed* on both successful and failed uploads. The
device may still be working: on System A 2026-08-12 the tunnel dropped at about two minutes while the
device continued an install and telemetry stayed silent for twenty minutes. On System B 2026-07-24 it
appeared after the inverter had already returned to inverting.

Device state: unknown until you download. What to do: wait, then download fresh and diff against what
you uploaded (`mk2vsc diff uploaded.rvms fresh.rvms`). If the verdict is "only bookkeeping", the upload
took. Confidence: observed.

### Error 1391  "Installation already executing another request"

The VE.Bus write lock is held; a previous upload is still being processed. *Observed* once, about 13
minutes after an Error 1303 on an assistant install. Device state: mid-write. What to do: wait, do not
retry, watch VRM for the inverters to reappear. Confidence: observed once.

## VE.Bus errors reported by the GX after an upload

### VE.Bus error 6  "DDC program error"

The assistant program on an inverter is corrupt or inconsistent. *Observed* on System C 2026-07-20 after
we uploaded a block with its assistant records truncated. The system dropped from ESS to pass-through
and the inverter switched off; the stored file still showed the assistant present. Recovery: re-upload
a fresh known-good file with the assistant intact, then reboot the GX. Confidence: observed.

### VE.Bus error 10  "System time synchronisation problem"

We saw this in two situations: for about 17 minutes after an assistant install was interrupted at the
grid-code step (System C 2026-07-20), and briefly while the two rocker switches on a pair were in
different positions during a manual power cycle (System A 2026-08-13). The first is the half-configured
state; the second is benign. Recovery from the first: GX reboots until all inverters re-enumerate, then
upload a fresh known-good file. Confidence: observed; the official meaning is documented by Victron.

### Off / Fault cycling every ~15 s after an upload

*Observed* on System A after hand-built ESS files whose header words were internally inconsistent with the
assistant flag. Not an error code but a pattern. Recovery: upload a fresh bare download. Confidence:
observed twice, mechanism inferred.

### Stable Off, "Active input: Disconnected", no error, after an upload

*Observed* on System A and System D after hand-built ESS files that stored correctly. Every restart
lever failed (mode toggle, VE.Bus restart, GX reboot, rocker cold boot). Recovery: upload a fresh bare
download; the installer's GUI session later loaded a working assistant. See docs/ASSISTANTS.md
section 7. Confidence: observed; cause hypothesised.

## VEConfigure and VE.Bus System Configurator dialogs

### "Resetting VE.Bus products"

An assistant install (or removal) is in progress. The inverters will stop, the VE.Bus resets, and the
system may take 15 to 20 minutes to re-enumerate. This is what distinguishes a settings-only upload
(no dialog, no interruption, inverters keep running) from a structure-changing one. Do not interrupt it.
Confidence: observed on every assistant install we witnessed.

### "This assistant requires that 'switch as group' is enabled for all AC inputs"

You added the ESS assistant before setting a grid code. The order in VE.Bus System Configurator is:
open the inverter, Grid tab, choose a grid code standard (needs the dealer password), send to all
devices; then Assistants tab. "Switch as group" is often not displayed as a checkbox; it follows from the
grid code state, so searching for it is futile. Confidence: observed on our Windows session and confirmed
by community posts.

### "Cannot determine assistant setup because not all assistants are configured yet"

An assistant was added to the list but its wizard was not completed. Open it and finish every page.
Confidence: observed.

### Saving produces a `.vsc` that cannot be uploaded

File, Save As in VEConfigure writes a `.vsc` that only applies locally over an MK3 cable. Close the
inverter window and confirm instead; that updates the `.rvms` that Remote VEConfigure uploads.
Confidence: observed.

### "Success. The system has been configured."

The upload was accepted. It is not proof the settings are right: download fresh and run `mk2vsc diff`
against what you uploaded, and `mk2vsc check` against your intent file. On 2026-08-14 a file with this
dialog reintroduced an out-of-spec charge voltage (docs/HISTORY.md).

## Quick table

| Message | Written? | First action | Confidence |
|---|---|---|---|
| mk2vsc-36 (no reset dialog seen) | no | download fresh, rebuild edit on it | observed |
| mk2vsc-36 (after "Resetting VE.Bus products") | possibly partial | stop, GX reboot, fresh known-good upload | observed |
| mk2vsc-47 | no | check VRM device list for "Unknown"; GX reboot; check file form | observed |
| mk2vsc-49 | no | `mk2vsc validate`; fix pointers/order | observed |
| mk2vsc-62 | n/a | wait for re-enumeration | observed once |
| Error 1303 | unknown | wait, download, diff | observed |
| Error 1391 | in progress | wait | observed once |
| VE.Bus error 6 | yes, corrupt program | fresh good file + GX reboot | observed |
| VE.Bus error 10 | half-configured or benign | reboot until enumerated, then fresh upload | observed |
| "Resetting VE.Bus products" | in progress | do not interrupt | observed |
| "switch as group" | n/a | set grid code first | observed + documented |
| "not all assistants configured" | n/a | finish the wizard | observed |
