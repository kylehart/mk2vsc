# ESS injection by file: the experiment, in full

**Goal.** Install the ESS assistant on both inverters of a bare two-inverter system by editing the
`.rvms` file, so that the one job which still forces people onto a Windows machine (VictronConnect
cannot install assistants) can be done from any computer.

**Result, as of 2026-09-03.** Our best files are accepted by the device and stored byte-perfect, the
assistant is advertised on both inverters, and the system never leaves the "connecting" state: no
error, no inverting, stable across cold boots. Earlier variants were rejected before writing, replaced
by an empty stub, or half-applied with a VE.Bus error. No file we authored has produced a running ESS
system. The GUI-authored installs on the same hardware all run.

**What we ask.** If you try this, do it on a system nobody depends on, with a healthy CAN-bus BMS
connected, with a bypass path for the loads, and with a fresh bare download ready to upload back. Then
send us the bytes: the file you uploaded, the re-download, and what the GX showed. The code is in
`mk2vsc/experimental/`, gated behind `--i-accept-the-risk`; `tests/test_experimental.py` reproduces every
file we uploaded in August 2026 from its baseline so you can see exactly what was tried.

Vocabulary: systems are Guava, Mango, Papaya, Sugar Apple; inverters by serial; "the installer" is the
company that holds the grid-code password and performed the GUI installs. Block offsets are relative to
the `B` of `BareSettingData` (docs/FORMAT.md); settings are by VE.Bus ID (docs/FIELDS.md).

## 1. What a GUI install changes in the file

We hold a clean same-system pair: Papaya's bare download of 2026-06-23 and its device download of
2026-07-24 after the installer's GUI session (which also corrected the charge profile and Virtual Switch
thresholds, so not every line below is ESS). `mk2vsc diff` output, verbatim:

```
$ mk2vsc diff fixtures/papaya/papaya_2026-06-23_download_bare_deviceform_1.rvms \
              fixtures/papaya/papaya_2026-07-24_download_ess_deviceform_1.rvms
lengths 5055 -> 7049; prologue same; verdict: CONTENT CHANGED
  HQ24142MJUA: len 482->1703 form device->device bookkeeping=9B header=1B assistant=1229B  [block length differs (assistant area changed)]
      setting   0 flags0                       35316 -> 33268  [HIGH]
      setting   2 absorption_V                 48.0 -> 56.8  [CONFIRMED]
      setting   3 float_V                      48.0 -> 54.0  [CONFIRMED]
      setting  10 charge_characteristic        3 -> 1  [MEDIUM]
      setting  15 unknown_toggle_15            3 -> 0  [LOW]
      setting  58 vs_accept_battery_above_V    53.0 -> 52.5  [CONFIRMED]
      setting  60 solar_wind_priority_flags    0 -> 48  [MEDIUM]
      setting  62 param62                      41666 -> 41667  [UNKNOWN]
      setting  81 grid_code_active             0 -> 1  [HIGH]
      setting 128 lom_config_a                 65535 -> 1  [LOW]
      header +0x036: f4 -> e4
  HQ2414N7NAJ: len 482->1255 form device->device bookkeeping=9B header=1B assistant=781B  [block length differs (assistant area changed)]
      setting   0 flags0                       35252 -> 33268  [HIGH]
      setting   2 absorption_V                 57.6 -> 56.8  [CONFIRMED]
      setting   3 float_V                      55.2 -> 54.0  [CONFIRMED]
      setting   7 repeated_absorption_time     4 -> 2  [MEDIUM]
      setting   8 repeated_absorption_interval 28 -> 4  [MEDIUM]
      setting  10 charge_characteristic        3 -> 1  [MEDIUM]
      setting  11 dc_low_shutdown_V            37.2 -> 48.5  [HIGH]
      setting  12 dc_low_restart_offset_V      6.4 -> 2.0  [HIGH]
      setting  15 unknown_toggle_15            1 -> 0  [LOW]
      setting  52 vs_param52                   2125 -> 1250  [LOW]
      setting  53 vs_param53                   0 -> 6  [LOW]
      setting  54 vs_ignore_ac_below_V         47.0 -> 51.0  [CONFIRMED]
      setting  55 vs_param55                   0 -> 6  [LOW]
      setting  56 vs_param56                   531 -> 625  [LOW]
      setting  57 vs_param57                   0 -> 2  [LOW]
      setting  58 vs_accept_battery_above_V    64.0 -> 52.5  [CONFIRMED]
      setting  59 vs_param59                   0 -> 2  [LOW]
      setting  60 solar_wind_priority_flags    0 -> 48  [MEDIUM]
      setting  62 param62                      41666 -> 41667  [UNKNOWN]
      setting  63 param63                      32768 -> 32668  [UNKNOWN]
      setting  64 battery_capacity_Ah          0 -> 300  [HIGH]
      setting  65 soc_at_bulk_end_pct          85.0 -> 98.0  [HIGH]
      setting  70 param70                      0 -> 50  [LOW]
      setting  72 charge_efficiency            255 -> 250  [MEDIUM]
      setting  81 grid_code_active             0 -> 1  [HIGH]
      setting 128 lom_config_a                 65535 -> 257  [LOW]
      header +0x036: f5 -> e5
```

(The HQ24142MJUA block shows fewer changes because that inverter had already received a half-install
of ESS on 2026-07-13, so its bare file already carried most of the install state. That is the "half
loaded" defect described in docs/HISTORY.md.)

Separating the ESS install from the installer's other edits, a GUI install writes:

**The assistant flag.** +0x36 changes `f4 -> e4` on the slot-(00,00) block and `f5 -> e5` on the
slot-(86,01) block. The low nibble is the slot; the high nibble drops from f to e.

**Two records in the assistant area** (docs/FORMAT.md section 5), one per inverter:

| Slot | Flag | Record | Subtype | Device-form length | Upload-form length |
|---|---|---|---|---|---|
| (00,00) | e4 | first record | 0001 | 1152 | 1102 |
| (86,01) | e5 | second record | 0101 (0001 on Mango) | 704 | 670 |

The 1152-byte body is byte-identical on Papaya, Mango, Guava and Sugar Apple. The 704-byte body is
byte-identical too; the one byte that differs between systems is the subtype word in the record
header (0101 on three systems, 0001 on Mango). So the assistant payload is a template chosen by role,
not compiled per inverter. We cannot read the body: entropy about 6.2 bits per byte, recurring two and
three byte sequences, and recognisable parameter values inside it (48.00 V as `c0 12`, 10 % as
`0a 00`). VE.Bus error 6 is "DDC program error", and truncating this region produced exactly that error,
so we treat it as a program.

**The "install state": ordinary settings the wizard writes.** We found these by byte offset in August
and only understood them as settings in September, when the settings array was mapped to VE.Bus IDs.
Every GUI-installed ESS block we hold has:

| Setting | Value after install | Meaning | Note |
|---|---|---|---|
| 0 (flags0) bit 11 | cleared | adaptive (lead-acid) charge curve off | the "+0x5a 0x89 -> 0x81" byte we chased for a week |
| 7 | 2 | repeated absorption time | |
| 8 | 4 | repeated absorption interval | |
| 10 | 1 | charge characteristic: fixed | lithium |
| 15 | 0 | unknown toggle | |
| 60 | 48 | solar & wind priority flags | bare blocks read 16 or 0 |
| 62 (low byte) | 0xc3 | unknown (41667) | bare reads 41666 |
| 64 | as typed in the wizard | battery capacity, Ah | 300 on the template system. We stamped 300 onto Guava (200 Ah) on v7 and onto Sugar Apple; an error we did not understand at the time |
| 81 | 1 | grid code active | 0 on every bare block |
| 128 | 1 (0x0101 on one Papaya block) | LOM configuration A | 0xffff on bare blocks |

`mk2vsc.experimental.ess_graft.INSTALL_STATE` is that list. It is applied only with `install_state=True`,
and `capacity_ah` lets you supply the right capacity.

**The device-form tail.** After the record the device stores 0xff padding and a 13-byte trailer, 72
bytes in all. The trailer is `0e 00 8e 01 15 00 <4 bytes> ff 00 00`. The four bytes are
`20 51 b8 4d` on every slot-(00,00) block and `76 c4 e8 db` on every slot-(86,01) block, across all four
systems and the installer's GUI export. They follow the role, not the inverter. What they mean is
unknown.

**The upload form.** The installer's GUI export of the same configuration differs from the device
download in four ways: a 16-byte blob at +0x45 (12 constant bytes `01 00 08 00 4a 39 81 80 4e 93 d7 0c`
plus a u32 export timestamp), the save timestamp moved to +0x59 with four zeros either side, the
records stored compact (1102 and 670 bytes, no 0xff runs) with correspondingly smaller length words,
and a shorter tail: the u16 right after the record reads `0a 00` in the export where the device holds
`40 00`, and the trailer ends `00 00 00` instead of `ff 00 00`. See section 3, upload-form v2, for why
those last two details matter.

## 2. Attempt log

All dates 2026. "Written" says what the device held afterwards, proven by a fresh download.

| Date | System | Recipe | File shape | Device response | Written | Recovery | Taught |
|---|---|---|---|---|---|---|---|
| 07-20 | Papaya | remove: truncate the ESS block to bare, v1, v2 | wrong next-pointer; then a block two bytes short | mk2vsc-49 | nothing | none needed | pointer = absolute offset of next section; the first block's canonical length |
| 07-20 | Papaya | remove, v3 | correct shape, 5055 B | accepted | assistant still present in the file; running assistant corrupt: VE.Bus error 6, ESS dropped, inverter off | baseline re-upload + GX reboot | file validity is necessary, not sufficient; the assistant is a program |
| 07-20 | Papaya | load-both v1, v2 | transplanted record, bad framing | mk2vsc-49 | nothing | | |
| 07-20 | Papaya | load-both v3 | second inverter given a transplanted record | accepted, "Resetting VE.Bus products", then mk2vsc-36 | half-applied: VE.Bus error 10 for about 17 min | two GX reboots; pre-incident files also rejected until re-enumeration | an accepted structure-changing file is riskier than a rejected one |
| 07-24 | Mango | v2: blocks copied from the GUI export | upload-form block in a device-form file (+10 shift) | mk2vsc-47 | nothing | | the two forms; do not mix them |
| 07-24 | Mango | v3: slot-matched tail from Papaya's device download | 7049 B, 14 self-checks | mk2vsc-47 again | nothing | GX reboot | the GX showed one serial as "Unknown"; mk2vsc-47 was enumeration, not the file |
| 07-24 | Mango | v4: same, rebuilt on the post-reboot download | 7049 B | accepted | a 64-byte empty stub on each inverter, flags e4/e5, records gone | baseline re-upload; blocks swapped order in the re-download | accept-then-stub; compare by serial |
| 08-12 | Guava | v3: same recipe, template = Papaya device download | 7049 B, records byte-identical to template | accepted; Error 1303 mid-write | stub on both inverters, VE.Bus reset (battery full) | baseline re-upload, verified bare | third independent stub |
| 08-12 | Guava | v4: v3 + seven "grid-code fingerprint" bytes | fingerprint from a cross-unit diff | "Resetting VE.Bus products", then mk2vsc-36 at commit | nothing (fresh download byte-identical to baseline) | see next row | the fingerprint was wrong in 4 of 7 bytes: it included two capacity bytes (setting 64) and missed setting 10 and the flags0 bit |
| 08-12 | Guava | re-upload of the archived bare baseline, after two clean GX reboots | archived file | mk2vsc-36 | nothing | upload the fresh download instead: accepted first try | mk2vsc-36 "old configuration file" is literal: stale save timestamp |
| 08-13 | Guava | v5: v3 + corrected six-byte grid-code set (10, 15, 60, 62, 81, 128), on a fresh baseline | 7049 B | accepted | stored byte-perfect, records present, no stub | | first by-file ESS that the device kept |
| 08-13 | Guava | (observation) | | inverter cycles Off -> Fault every ~15 s | | | config internally inconsistent |
| 08-13 | Guava | v6: v5 + flags0 bit 11 cleared on one block | two bytes changed | superseded before upload | | | |
| 08-13 | Guava | v7: v5 + full install state (flags0 bit 11, 7, 8, 64 on the second block; 128 high byte) | 7049 B, matches every working install at 12 offsets | accepted | stored; cycling stopped; system stable Off, "connecting", zero errors | | internal consistency matters; consistency is not start |
| 08-13 | Guava | OUTPUT rotary 2 -> 1 for two minutes; MQTT mode toggle; "Restart VE.Bus system" x3; GX reboot x3; fresh re-upload | | no change | | | the OUTPUT switch does not gate the inverter |
| 08-13 | Guava | full rocker cold boot, both inverters | | same state after boot; download identical except timestamp and checksums | | | refusal lives in stored config or a device-side check, not runtime |
| 08-13 | Guava | upload-form v1: device -> GUI form transform, download order | compact records, blob, July timestamps | mk2vsc-49 | nothing | | block order: e4-slot first; the two-byte prefix after the first block belongs to the next section |
| 08-13 | Guava | upload-form v2: e4 first, fresh unix timestamps | reproduces the installer's export format | accepted | stored; still Off | | timestamps are unix time; the upload form is not by itself the trigger |
| 08-13 | Sugar Apple | one-shot: v3 + full install state from a clean bare download | 7049 B | accepted; Error 1303 at the end | stored; Off; telemetry dark 6 h; building found without power, put on bypass | GUI session by the installer later | same outcome on a second system with all "good" bytes |
| 08-13 | both | GX ESS setting RunWithoutGridMeter 0 -> 1 (both non-starters read "external meter required"; runners read "inverter/charger") | | still Off after a fresh re-upload | | | a real commissioning defect, not the blocker |
| 08-14 | Guava | CAN bus diagnosis: 0 RX packets, transmitter error-passive | | | | | the BMS bus had been physically dead since 07-20 |
| 09-02 | Guava | the installer's GUI session, after the CAN bus was repaired and a third battery module installed | GUI export | accepted | ESS running on both inverters, charge profile corrected in the same session | | consistent with H3 below; does not test it |

Two things in that table deserve a closer look.

**The three-unit truth table (v7).** Diffing Guava's v5 result against both working installs, and then
checking the bare blocks of all three systems, showed why the earlier "fingerprint" diffs kept missing
bytes: an intersection over two diffs drops any byte that only one system needed to change, and a diff
against one system misses bytes that system already had right. Every working ESS block ends up at the
same values (the install-state table above) but each system starts from a different bare shape, so the
set of bytes the wizard actually writes differs per system. v7 applied the five that Guava still lacked
and the 15-second Off/Fault loop stopped at the moment of the write. That is strong evidence the
device validates the settings against the assistant at startup, and that our v5 file was internally
inconsistent. It is not evidence about why a consistent file still does not start.

**The mk2vsc-36 misreading.** Twice we read "Incorrect grid code password or old configuration file" as
the device demanding a password. On 08-12 a fresh download proved the device had written nothing and
was not corrupt; the archived baseline was being refused for its old save timestamp, and the freshly
downloaded file uploaded first time. Every later attempt was built on a same-day download for that
reason. The one time the message followed the "Resetting VE.Bus products" dialog (v4, and Papaya
07-20) it came at the commit of a real install and may well be the grid-code meaning; we cannot tell
the two apart from the message alone. docs/ERRORS.md has the decision rule.

## 3. The outcomes, by file shape

| Outcome | File shape that produced it | Written to the device |
|---|---|---|
| A. Clean reject (mk2vsc-47, mk2vsc-49) | wrong pointer, wrong block length, wrong block order, mixed forms, or a healthy file while the GX had a serial as "Unknown" | nothing |
| B. Accept, then stub | device-form graft with correct records but bare install state (Mango v4, Guava v3) | 64-byte empty container per inverter, flags flipped, our records discarded |
| C. Accept, half apply | a transplanted record with the grid-code state partly set (Papaya v3, Guava v4) | "Resetting VE.Bus products", then mk2vsc-36; VE.Bus error 10 on Papaya, nothing on Guava |
| D. Accept, store, never start | records + full install state, device form (Guava v7, Sugar Apple) or upload form (Guava upload-form v2) | everything, byte-perfect and stable across cold boot; system Off, connecting, no error |
| E. Removal accepted, running program corrupt | the ESS block truncated back to bare with correct framing (Papaya 07-20) | file unchanged; VE.Bus error 6 until baseline re-upload and reboot |

The progression B -> C -> D tracks how much of the install state the file carried. A file with the
records but none of the settings the wizard writes is stubbed; a file with some of them reaches the
install dialog and fails at commit; a file with all of them is stored and does not start.

## 4. Hypotheses

**H1. The install needs an out-of-file trigger.** The GUI's upload path may issue MK2 commands (a
"reset products, load program, commit" sequence) that plain file storage does not. Evidence for: the
Mango stub shows the device actively processes the assistant section on upload and authors its own
container. Evidence against: upload-form v2 (the GUI's exact file format) was accepted and did not
start either, and VRM's Remote VEConfigure upload is a file transfer with no interactive session.
Status: weakened, open. Test: capture the MK2 traffic of a real GUI install over an MK3 cable and
compare with a Remote VEConfigure upload of the same file.

**H2. The upload form itself is the trigger.** The 16-byte blob and compact records might be what tells
the device to run the install procedure. Tested once (Guava, 08-13): accepted, stored, no start. But
that system had a dead BMS bus at the time (H3), so the test does not separate H2 from H3. Our v2 was
compacted against the installer's Papaya export, so it carried the GUI's tail words (`0a 00`, and
`00 00 00`); the shipped no-reference transform writes the same GUI words, and the test suite checks
that it reproduces v2 byte-for-byte. Whether the device would also accept the device-form tail words in
an upload is untested. Status: inconclusive. Test: upload-form transform on a healthy-BMS system, both tail
variants if the first does not start.

**H3. A loaded ESS assistant gates system start on valid CAN battery data.** After a full live
runtime-state diff between a running system and a non-starter, the only discriminator we could not
falsify was battery data on the CAN bus. Both runners (Papaya, Mango) had a live BMS. Guava's CAN bus
had been physically broken since 07-20 (0 RX packets, error-passive transmitter, no 120 ohm
termination fixed until later) and Sugar Apple has no BMS connected. Both non-starters sat at
`SwitchoverInfo/Connecting = 1`, `VebusMainState = 2`, zero errors, on grid, with the assistant
advertised. Falsified as the cause: the file bytes (stable across cold boot), RunWithoutGridMeter
(fixed, no change), DVCC on or off (Sugar Apple runs DVCC off and still would not start), every restart
lever. Guava now runs ESS after the installer's GUI session on a repaired bus and with a third module;
that is consistent with H3 and does not test it, because the file was GUI-authored. Status: the last
discriminator standing, untested. Test: section 5.

**H4. The tail words are a per-unit or per-session signature we copied wrong.** The four bytes after
`0e 00 8e 01 15 00` turned out to follow the slot (`20 51 b8 4d` with the 1152 record, `76 c4 e8 db`
with the 704 record) on every system including the GUI export, so they are not per-inverter identity.
What remains unexplained is the u16 immediately after the record (`40 00` device, `0a 00` GUI export)
and the final byte (`ff` device, `00` GUI export), which our upload-form v2 carried in the GUI form and
our device-form grafts carried in the device form. Neither started. (`mk2vsc experimental to-upload-form`
writes the GUI form.) Status: open, low prior. Test: a
second GUI export from a different system to see whether `0a 00` is constant.

**H5. Something in BareSettingInfo or the record body encodes identity.** BareSettingInfo is
byte-identical in every file, including files from different systems, so it cannot carry identity. The
record bodies are byte-identical across systems. Status: no evidence either way; nothing left in the
file to carry it. If the device binds the assistant to something, it is outside the file.

**H6. The GX-side ESS commissioning must be done first.** The two non-starters had the GX at "grid
metering: external meter", which a GUI-guided install would have led the operator to change. We changed
it and re-kicked both systems; no start. Status: falsified for the start problem, but a real
requirement for correct regulation once running, and a step by-file installs skip.

## 5. The one experiment we would run next

Preconditions, all required:

1. A two-inverter system nobody depends on, with the CAN-bus BMS connected and reporting on the GX
   (`com.victronenergy.battery` service present with live voltage and SoC, CAN RX counters increasing).
2. A bypass path for the loads and a person at the switches.
3. Battery above 80 %, grid present.
4. A fresh bare download taken minutes before the upload; `mk2vsc validate` OK; `mk2vsc check` with the
   system's intent file OK; keep it as the rollback file.
5. A template: a device download of a GUI-installed ESS system with the same inverter model and firmware
   (ours: `fixtures/papaya/papaya_2026-07-24_download_ess_deviceform_1.rvms`, firmware 2729560).

Steps:

```
mk2vsc experimental graft fresh.rvms template.rvms prepared.rvms --install-state --capacity-ah <Ah> --i-accept-the-risk
mk2vsc validate prepared.rvms
mk2vsc diff fresh.rvms prepared.rvms          # expect: flag byte, the install-state settings, assistant area only
mk2vsc check prepared.rvms --intent intent.json
```

Upload `prepared.rvms` through VRM Remote VEConfigure. Re-download immediately, then:

```
mk2vsc diff prepared.rvms redownload.rvms     # expect ONLY BOOKKEEPING; a stub or bare file means outcome B or A
```

Watch on the GX (or over MQTT) for ten minutes: `Devices/0/Assistants` and `Devices/1/Assistants` should
list the ESS assistant on both; `SwitchoverInfo/Connecting`, `VebusMainState`; `Hub4/AssistantId`;
`ActiveSocLimit`; VE.Bus state. Then:

| Observation | Meaning |
|---|---|
| State goes to Inverting or Bulk, Active input = AC In 1, ActiveSocLimit populated | by-file ESS install works on a healthy-BMS system; H3 confirmed; report everything |
| Stable Off, Connecting = 1, no error, assistants listed | H3 falsified; the blocker is in the file or the transport; try the upload-form variant next, then H1 |
| Off/Fault cycling every ~15 s | the install state is incomplete for this firmware or battery; diff your file against a GUI install of the same model |
| Stub in the re-download | the device discarded the records; report the file, this is outcome B on a configuration we have not seen |
| mk2vsc-36 without the "Resetting" dialog | stale timestamp; download fresh and rebuild |

Whatever happens, upload the fresh bare download back afterwards and confirm with `mk2vsc diff` that the
system is byte-for-byte its pre-experiment self except bookkeeping.

## 6. Safe offline research

None of this touches hardware.

- **The record body.** Both bodies are in every `*_download_ess_*` fixture. Locate the embedded
  parameters (48.00 V is `c0 12`, 10 % is `0a 00`, 25 % would be `19 00`) and check whether they track
  the ESS settings shown on the GX of the same system at the time of the download. If they do, the body
  carries the wizard's answers and a by-file install must set them per system.
- **The record header.** Why Mango's 704 record is subtype 0001 and the others 0101. Mango is the only
  mixed-hardware-generation pair in our corpus (one 2022 and one 2024 inverter).
- **The tail.** `0e 00 8e 01 15 00` and the two per-slot words; the `40 00` / `0a 00` and `ff` / `00`
  differences between device and GUI form.
- **Other assistants.** A file with a different assistant (AC PV, generator start/stop, relay
  assistants) would show whether the subtype identifies the assistant and whether every assistant
  writes the same install state.
- **Other topologies.** A single-unit `.rvsc`, a three-phase `.rvms`, a Quattro. We hold none.
- **Another GUI export.** A second export from another system would settle whether BLOB12 and the tail
  words are constants.

To contribute: add the file under `fixtures/` following CONTRIBUTING.md, run `pytest` (a failing claim
test on your file is itself the finding), and open an issue with `mk2vsc census` and `mk2vsc show --json`
output.

## 7. Do not, and how to recover

Do not:

- upload any file from `mk2vsc experimental` to a system that people depend on, or without someone at
  the switches;
- upload an archived file; the device rejects stale timestamps and old files carry old settings;
- treat "Success" or "Resetting VE.Bus products" as a good sign: outcomes B, C and D all began that way;
- try to remove an assistant by truncating the block (outcome E);
- stamp `INSTALL_STATE` without `--capacity-ah`; it writes the template system's battery capacity;
- attempt to bypass the grid-code password. It is the dealer's credential, it is not in the file, and this
  project does not look for a way around it. Setting 81 and the LOM entries are what a GUI install
  writes; reading them is documented, forging them is what outcome C looks like.

Recovery, in order:

1. Download a fresh copy from the device and upload that file back, unmodified. Never an archived copy.
   This restored Guava from every stored-but-Off state (outcome D) and from the stub (outcome B).
2. If the upload is refused or the device list shows an inverter as "Unknown": reboot the GX (Cerbo),
   wait for the VE.Bus to re-enumerate, retry step 1.
3. If the VE.Bus is in error 10 after an interrupted install: reboot the GX, wait, download fresh, upload.
4. Rocker power cycle of both inverters (0, wait a minute with the LEDs dark, back to I) as the last
   lever. Confirm from the GX that the VE.Bus service actually went silent; LEDs off is not proof.
5. If the system has a bypass switch, put the loads on it for the whole window and take them off only
   when the inverter is inverting with AC In 1 active.
