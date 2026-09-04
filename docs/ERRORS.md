# Error and message decoder

What the messages mean, whether anything was written to the inverters, what to do, and how sure we are.
"Observed" means we saw it on our own systems and read the device state afterwards from a fresh
download. "Documented" means the meaning comes from Victron documentation or community posts and we
have not seen it ourselves.

The single most useful rule in this file: **if an upload is rejected and you are not sure why, download
a fresh copy from the device, then upload that (edited or not).** Most rejections we hit were the device
refusing a file whose save timestamp was older than the one it already had.

## Remote VEConfigure upload errors (from the device's VE.Bus layer)

The `mk2vsc-NN` codes come from the MK2/MK3 protocol layer that parses the uploaded file on the GX or
inverter side, not from the VEConfigure program. They are verdicts on the bytes.

### mk2vsc-36  "Incorrect grid code password or old configuration file"

Two meanings, and the text does not tell you which.

**Meaning 1 (common): the file is stale.** The device compares the save timestamp at block offset +0x4f
(or +0x59 in upload form) with what it holds and rejects anything older. Any archived file, including
a known-good baseline that loaded fine last week, triggers this after the device has been saved since.
*Observed* on Guava 2026-08-12: the archived bare baseline was rejected repeatedly across two GX reboots;
a fresh download compared byte-for-byte to that baseline showed the device had written nothing and
was not corrupt; uploading the fresh download unmodified was accepted immediately.

**Meaning 2 (rare): the grid-code step of a real assistant install failed.** *Observed* on Papaya
2026-07-20 and Guava 2026-08-12, both times after the "Resetting VE.Bus products" dialog, both times
with a file we had built by hand that carried assistant records. On Papaya the VE.Bus was left
half-configured (error 10); on Guava the fresh download proved nothing had been written.

How to tell them apart: if you never saw "Resetting VE.Bus products" and the file was not freshly
downloaded, it is meaning 1. If you are uploading a hand-built file with an assistant, assume meaning 2
and stop.

Device state: nothing written (meaning 1, and meaning 2 on Guava); possibly half-applied (meaning 2 on
Papaya). What to do: download fresh, rebuild your edit on that file, upload. If the system is in error
10, see below.

### mk2vsc-47  "More than one unknown unit detected"

A pre-write reject: the parser could not match the blocks in the file to the inverters it discovered on
the bus. *Observed* twice with different causes:

- A block copied from a GUI export (upload form) into a device-form file. The 16-byte blob at +0x45
  shifted every following field by 10 bytes, so the identity words sat at the wrong offsets (Mango
  2026-07-24, v2). Fixing the file did not clear the error, because of the second cause.
- The GX itself showed one inverter's serial as "Unknown" in VRM. A GX (Cerbo) reboot restored
  enumeration and the same construction was accepted (Mango 2026-07-24, v3 then v4).

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
(Papaya 2026-07-20, `NumberOfMultis` read as none on the GX). Wait for the device list to show all
inverters again, or reboot the GX. Device state: unchanged by the download attempt. Confidence: observed
once.

### Error 1303  "VRM connection stopped responding"

A VRM tunnel timeout, not a verdict on the file. *Observed* on both successful and failed uploads. The
device may still be working: on Guava 2026-08-12 the tunnel dropped at about two minutes while the
device continued an install and telemetry stayed silent for twenty minutes. On Mango 2026-07-24 it
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

The assistant program on an inverter is corrupt or inconsistent. *Observed* on Papaya 2026-07-20 after
we uploaded a block with its assistant records truncated. The system dropped from ESS to pass-through
and the inverter switched off; the stored file still showed the assistant present. Recovery: re-upload
a fresh known-good file with the assistant intact, then reboot the GX. Confidence: observed.

### VE.Bus error 10  "System time synchronisation problem"

We saw this in two situations: for about 17 minutes after an assistant install was interrupted at the
grid-code step (Papaya 2026-07-20), and briefly while the two rocker switches on a pair were in
different positions during a manual power cycle (Guava 2026-08-13). The first is the half-configured
state; the second is benign. Recovery from the first: GX reboots until all inverters re-enumerate, then
upload a fresh known-good file. Confidence: observed; the official meaning is documented by Victron.

### Off / Fault cycling every ~15 s after an upload

*Observed* on Guava after hand-built ESS files whose header words were internally inconsistent with the
assistant flag. Not an error code but a pattern. Recovery: upload a fresh bare download. Confidence:
observed twice, mechanism inferred.

### Stable Off, "Active input: Disconnected", no error, after an upload

*Observed* on Guava and Sugar Apple after hand-built ESS files that stored correctly. Every restart
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
