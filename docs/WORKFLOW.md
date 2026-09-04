---
title: "Editing Victron inverter settings without VEConfigure: the VRM Remote VEConfigure workflow"
description: "Download, edit, upload, verify; assistant removal and reinstall; what still needs Windows and VEConfigure."
---

# Operational workflow with Victron's tools

This toolkit reads and writes files. Getting a file off a system and back onto it is done with
Victron's own, authenticated path: VRM Remote VEConfigure. This page records that path as we use it,
including the parts that still need Windows.

## File types

| extension | system | opened by |
|---|---|---|
| `.rvsc` | single inverter | VEConfigure 3 |
| `.rvms` | multiple inverters (parallel, split-phase, three-phase) | VE.Bus System Configurator |

Both are produced and consumed by Remote VEConfigure on VRM. Every file in our corpus is `.rvms`
(two-inverter split-phase systems). We hold no `.rvsc` files, so we cannot say whether the
single-unit layout matches. The file magic string is the same lineage for both
(`VEConfig setting section file`).

## Download

1. VRM portal, select the installation, Device list, the inverter/charger entry, then
   Remote VEConfigure.
2. Choose Download. Save the file to disk. Do not choose to open it in VEConfigure from the browser;
   you want the untouched bytes.
3. File it immediately into the change folder (`00_baseline/`, see docs/CHANGE_CONTROL.md) and run
   `mk2vsc show` to confirm the serials and the save timestamp.

A download does not change the device. It does require the GX device to have a working connection
to the inverters over VE.Bus; while the VE.Bus is re-enumerating after a reset, downloads fail with
`mk2vsc-62`.

## Monitoring during a remote operation

**Observed** (2026-09-04, System D and System A, on the operations where monitoring was read during
the window): while a Remote VEConfigure upload or the re-download that followed it was in progress,
monitoring that reads the GX (a gateway on VRM and MQTT) reported the site disconnected for under a
minute, and on System A the inverter state field read Passthru during that gap. Both cleared on their
own when the operation ended; health readings (state, grid presence, load) were unchanged before and after; no alarm
was raised and no "Resetting VE.Bus products" dialog appeared. **Inferred:** the GX stops receiving
inverter data while the MK2 tunnel holds the VE.Bus port, so values read in that window are a gap in
the GX's view, not fresh inverter readings. **Unknown:** the inverter's own behaviour during the
window was not measured independently of the GX; whether a download alone (no upload) produces the
same gap was not isolated. The gap is not a fault of the uploaded file. A health rule that judges a
site during or right after a remote operation must allow for that window before calling anything
wrong.

## Upload

1. Remote VEConfigure, Upload, pick the file from `01_prepared/`.
2. Dialogs you will see:
   - "Success. The system has been configured." The device accepted the bytes. It is not proof the
     settings are what you intended; re-download and check (Rule 4 in docs/CHANGE_CONTROL.md).
   - "Resetting VE.Bus products" with a long progress bar. A real assistant install or removal is
     happening on the device; it takes one to five minutes, the inverters are off for the reset, and
     the dialog often ends in "Error 1303" although the device completed. This is the device's normal
     behaviour for an assistant change from any source, VEConfigure's GUI included. Settings-only
     uploads do not show this. If you see it after uploading a settings-only edit, stop and investigate
     before doing anything else.
   - "Error 1303, VRM connection stopped responding." The tunnel between the portal and the GX
     timed out. The device may still be working. Wait, watch the VRM device page, then re-download.
   - "Error 1391, installation already executing another request." A write is still in progress on
     the device. Wait.
   - `mk2vsc-36`, `mk2vsc-47`, `mk2vsc-49`: the device refused the file and applied none of its settings.
     See docs/ERRORS.md. Every mk2vsc-36 on a settings-only upload in our record was an archived file,
     and a fresh download was accepted each time; download fresh and rebuild.
3. A settings-only upload (what `mk2vsc edit` produces) does not reset the VE.Bus and does not
   interrupt the inverters. We have applied such uploads to occupied buildings without any
   observable effect on loads. Assistant changes do reset the VE.Bus, and the inverters go off for
   the duration.

## What still needs Windows and VEConfigure

Be clear about this before choosing the toolkit for a job:

- Installing an assistant on a system that never had one, or reconfiguring an assistant's own settings.
  Removing an assistant and reinstalling it from an earlier download of the same system work by file
  (`mk2vsc assistant`, docs/ASSISTANTS.md section 8); both reset the VE.Bus.
- Setting or changing the grid code. This requires the dealer password, entered in VEConfigure. The
  toolkit reads the grid-code flag (setting 81) and does not write it.
- Anything that is not one of the 192 u16 values in the settings array, or is in the array but is
  not yet identified (docs/FIELDS.md). You can edit an unidentified value with an explicit override,
  but you are then the first person to try that offset on hardware.

Everything else that we have needed day to day (charge voltages, Virtual Switch thresholds,
input current limit, DC low cutoff) is in the array and is a file edit.

## The GUI procedure for assistants, as recorded

Recorded because it is poorly documented and we lost two days to it. This is the split-phase,
two-inverter case.

1. Download the `.rvms` from VRM and save it to disk (above).
2. Double-click the `.rvms`. VE.Bus System Configurator opens (not VEConfigure). This is correct.
3. Left-click the phase button (for example "AC input 1 L1") to expand it.
4. Right-click the equipment icon (the "Dual AC input" icon, not the inverter picture) and choose
   "VEConfigure Multi". On a laptop trackpad, right-click is a two-finger tap or Shift+F10. Bare F10
   toggles the trackpad off on some machines.
5. Grid tab first. Choose the grid code standard (this is where the dealer password is asked for),
   then "send settings to all devices".
6. Assistants tab. Add ESS, complete the wizard, then "send settings to this device only".
7. Exit, and repeat from step 4 for the other inverter's icon. Loading the assistant on only one
   inverter of a pair is a real mistake we have seen; it produces cross-phase power flow.
8. Close and confirm. Do not use File, Save As: that writes a `.vsc`, which can only be applied
   locally over an MK3 cable and cannot be uploaded remotely. Closing with confirmation is what
   updates the uploadable `.rvms`.
9. Upload the `.rvms` via Remote VEConfigure. Expect "Resetting VE.Bus products".

Error decoder for this procedure:

- "This assistant requires that 'switch as group' is enabled for all AC inputs": step 6 was done
  before step 5. The checkbox is often not displayed anywhere in single-phase or split-phase
  configurations; it follows from the grid-code state. Fix the order, do not hunt for the checkbox.
- "Cannot determine assistant setup because not all assistants are configured yet": an assistant was
  added to the list but its wizard was never completed.

## Running VEConfigure on a Mac

VEConfigure is a 32-bit Windows application. What we tried:

- CrossOver (Wine): installed and launched, but menu commands did not dispatch, so files could not
  be loaded or saved. Community reports say raw Wine or WineskinServer works for some people on
  Apple Silicon. We did not get there.
- UTM with Windows 11 ARM: works. Windows' own x86 emulation runs VEConfigure with no problems.
  About an hour to set up, mostly unattended download and install. Install the SPICE tools for a
  shared folder, or simply download the `.rvms` from VRM inside the VM's browser.
- Parallels: reported to work; not tried.

If the job is a settings edit, none of this is needed; that is the point of the toolkit.

## After upload: checklist

- Re-download into `02_downloaded/`.
- `mk2vsc diff 01_prepared/<file> 02_downloaded/<file>` reports ONLY BOOKKEEPING.
- `mk2vsc check 02_downloaded/<file> --intent intent.json` exits 0.
- The VRM device page for the inverter/charger shows the new values (charge voltages appear under
  the device's settings; VS thresholds do not appear in VRM, the file is the only place to read them).
- No new VE.Bus errors on the device page or in alarms.
- Both inverters read the same values on any setting that must match on a shared battery.
- Record the outcome in CHANGE.md and in whatever change log or monitoring you keep.

## Verifying on the live system

- Charge voltages: after the next full charge, VRM's battery voltage should reach the new absorption
  value and settle at the new float. With a CAN-bus BMS and DVCC active, the BMS charge-voltage
  limit overrides the file's values; you may see the BMS limit instead, which is expected.
- Virtual Switch thresholds: the behaviour shows up as the inverter leaving or returning to
  passthrough at the configured DC voltages. Our monitoring detects this from the AC input state and
  battery voltage; VRM shows the input state.
- ESS state: on the GX device, Settings, ESS, and on VRM the "ESS" system type and the active SOC
  limit. A loaded but dormant assistant looks like success; check that the SOC limit is populated
  and that both inverters advertise the assistant.
- VE.Bus errors: error 6 (DDC program error) and error 10 (time sync) after an upload mean the
  assistant program or the install was left inconsistent. See docs/ERRORS.md and docs/SAFETY.md for
  the recovery steps.
- Timing: read health after the operation has finished and the GX has reconnected (see "Monitoring
  during a remote operation": GX-based monitoring can show a sub-minute disconnect, and a stale state
  field, while the tunnel holds the VE.Bus port). A settings-only upload that has been accepted leaves
  the inverter in the state it was in before.
