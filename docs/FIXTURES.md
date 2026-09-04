---
title: "The fixture corpus"
description: "88 real .rvms files from four systems, what each is, and the negative controls."
---

# The fixture corpus

`fixtures/` holds every distinct `.rvms` file we collected while operating four inverter systems
between June and September 2026: 88 unique files (duplicates by SHA-256 were dropped). Every test in
`tests/` runs against these files, and `fixtures/manifest.json` records what each one is.

## Where the files come from

Four two-inverter, split-phase MultiPlus systems, each with its own battery. They are referred to
as System A to D throughout this repository; the letters are public aliases, not the systems' names.
Inverter serials in the files are pseudonyms of the same shape as real ones (`HQ0000A0001` = System A,
first inverter): the 11 serial bytes in each block were replaced and the section checksums recomputed;
every other byte is as downloaded. The two deliberately broken negatives keep their broken checksums.

| system | inverters |
|---|---|
| System A | HQ0000A0001, HQ0000A0002 |
| System B | HQ0000B0001, HQ0000B0002 |
| System C | HQ0000C0001, HQ0000C0002 |
| System D | HQ0000D0001, HQ0000D0002 |

All eight inverters run firmware 2729560 (shown as "v560" in VRM) and every file carries format
version 1.33 in its `Mk2vscInfo` section. That is the whole range of hardware and software the corpus
covers; see CONTRIBUTING.md for what we would like to add.

## Classification

Each file name encodes four facts, all derived from the bytes rather than from where the file was
found:

**origin**

* `download`: a device download through VRM Remote VEConfigure. This is what the device holds.
* `gui-export`: a file written by VEConfigure / VE.Bus System Configurator for upload. These are the
  installer's GUI exports and are the only files in the corpus authored by Victron's own tool.
* `prepared`: a file our tools produced. Some were uploaded (and the corresponding download follows
  them in the manifest), some were never uploaded, and a few are known-defective early attempts
  kept precisely because they were rejected.
* `experiment`: one file with deliberately stale checksums, kept as a negative control.

**state**

* `bare`: no assistant on either inverter (flag byte f4/f5, empty assistant area).
* `half-ess`: an assistant record on one inverter only. System C ran like this for weeks after a
  one-inverter install, which is how we learned it matters.
* `ess`: assistant records on both inverters.
* `stub`: both blocks carry the empty 64-byte container that VEConfigure writes after accepting a
  transplanted assistant and discarding it. A download in this state is the signature of a failed
  by-file install.

**form**

* `deviceform`: ten zero bytes at block offset +0x45. All device downloads are this form.
* `uploadform`: the 16-byte blob VEConfigure inserts at +0x45 followed by four zeros, which shifts
  every later offset by ten bytes. GUI exports are this form; so are two of our prepared files that
  imitated it.

**date** is the newest save timestamp found inside the file (block offset +0x4f, unix time, UTC),
so it is the day the device or the GUI last saved the configuration, not the day the file was
copied. The 2026-09-02 post-service download therefore appears as `2026-09-03` because the save
happened after midnight UTC.

The original file names were dropped. VRM names downloads after the installation's portal ID, which
identifies a specific VRM site and has no place in a public corpus. The manifest keeps the SHA-256 of
each file so a copy found elsewhere can still be matched.

## Negative controls

Three files are malformed on purpose and are listed in `KNOWN_BAD` in `tests/conftest.py`. The tests
assert that they fail, and how:

| file | defect | what it taught us |
|---|---|---|
| system_a/system_a_2026-06-18_experiment_bare_deviceform_1.rvms | both unit checksums left stale after editing two bytes | the device checks the trailer; an edited file needs the checksum recomputed |
| system_a/system_a_2026-07-21_prepared_ess_uploadform_1.rvms | an upload-form block from another system grafted into a device-form file; the pointer chain is broken | forms cannot be mixed; block offsets shift by ten after +0x45 |
| system_c/system_c_2026-07-20_prepared_ess_deviceform_1.rvms | the last section's pointer lands inside the file | rejected by the device as mk2vsc-49; the pointer must equal the file length |

Keep them. A parser that accepts these is wrong.

## Files worth reading

* **The first live proof.** `system_d/system_d_2026-07-20_download_bare_deviceform_1.rvms` is
  the baseline, `system_d_2026-07-20_prepared_bare_deviceform_1.rvms` is the file we produced with
  float raised from 54.0 V to 54.1 V on both inverters, and the later `download_bare_deviceform_*`
  files of the same day are what the device sent back after the upload. `mk2vsc diff` between the
  prepared file and the re-download shows only bookkeeping bytes.
* **The swapped-order pair.** `system_b/system_b_2026-07-24_download_bare_deviceform_2.rvms` and
  `system_b_2026-07-24_download_bare_deviceform_3.rvms` are consecutive downloads of the same
  unchanged system in which the two inverter blocks exchanged positions. A positional byte diff shows
  dozens of differences; compared by serial there are six bookkeeping bytes per block. This is why
  every tool in the repository matches blocks by serial.
* **The stub downloads.** `system_b/system_b_2026-07-24_download_stub_deviceform_1.rvms` and
  `system_a/system_a_2026-08-12_download_stub_deviceform_{1,2}.rvms` show what the device holds after it
  accepted a transplanted assistant: flags flipped to e4/e5, a 64-byte empty container on each
  inverter, and our payload gone. docs/ASSISTANTS.md tells the story.
* **The installer's GUI exports.** `system_c/system_c_2026-07-13_gui-export_half-ess_uploadform_1.rvms`
  is a VEConfigure export with the ESS assistant on one inverter only (the first, defective attempt);
  `system_c_2026-07-21_gui-export_ess_uploadform_1.rvms` is the corrected export with the assistant on
  both. They are the only upload-form files not made by us, and `system_c_2026-07-24_download_ess_deviceform_1.rvms`
  is the device's own download after the second one was applied: the same settings, the same
  assistant records in padded form, zeros at +0x45.
* **The older-build layout.** `system_b/system_b_2026-06-08_download_bare_deviceform_{1,2}.rvms` were written
  by an older tool build. Their assistant area is 15 bytes instead of 9 (a six-byte empty container)
  and a few header settings differ. They are the only files of that shape we have.
* **The post-service download.** `system_a/system_a_2026-09-03_download_ess_deviceform_1.rvms` is System A
  after the installer's GUI session of 2026-09-02: ESS records on both inverters (704 and 1152
  bytes), absorption corrected to 56.8 V on both, and the first System A file to pass our qualifier.

## Regenerating the table

`examples/gen_fixture_table.py` prints the table below from the manifest. Re-run it after adding a
fixture and paste the output here.

| file | bytes | state | form | origin | inverters (block length, flag) |
|---|---:|---|---|---|---|
| system_a/system_a_2026-06-18_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000A0002 (484, f5), HQ0000A0001 (482, f4) |
| system_a/system_a_2026-06-18_experiment_bare_deviceform_1.rvms | 5055 | bare | deviceform | experiment | HQ0000A0002 (484, f5), HQ0000A0001 (482, f4) |
| system_a/system_a_2026-06-19_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-07-13_prepared_half-ess_uploadform_1.rvms | 6182 | half-ess | uploadform | prepared | HQ0000A0001 (484, f4), HQ0000A0002 (1609, e4) |
| system_a/system_a_2026-07-13_prepared_half-ess_uploadform_2.rvms | 6182 | half-ess | uploadform | prepared | HQ0000B0001 (484, f5), HQ0000B0002 (1609, e4) |
| system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-07-20_download_bare_deviceform_2.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-07-20_download_bare_deviceform_3.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-07-20_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-07-21_prepared_ess_uploadform_1.rvms | 6877 | ess | uploadform | prepared | HQ0000A0002 (1177, e5), HQ0000A0001 (1611, e4) |
| system_a/system_a_2026-08-12_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000A0002 (484, f5), HQ0000A0001 (482, f4) |
| system_a/system_a_2026-08-12_download_bare_deviceform_2.rvms | 5055 | bare | deviceform | download | HQ0000A0002 (484, f5), HQ0000A0001 (482, f4) |
| system_a/system_a_2026-08-12_download_bare_deviceform_3.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-08-12_download_bare_deviceform_4.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-08-12_download_stub_deviceform_1.rvms | 5183 | stub | deviceform | download | HQ0000A0002 (548, e5), HQ0000A0001 (546, e4) |
| system_a/system_a_2026-08-12_download_stub_deviceform_2.rvms | 5183 | stub | deviceform | download | HQ0000A0001 (548, e4), HQ0000A0002 (546, e5) |
| system_a/system_a_2026-08-12_prepared_ess_deviceform_1.rvms | 7049 | ess | deviceform | prepared | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_a/system_a_2026-08-12_prepared_ess_deviceform_2.rvms | 7049 | ess | deviceform | prepared | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-12_prepared_ess_deviceform_3.rvms | 7049 | ess | deviceform | prepared | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_a/system_a_2026-08-13_download_ess_deviceform_2.rvms | 7049 | ess | deviceform | download | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_a/system_a_2026-08-13_download_ess_deviceform_3.rvms | 7049 | ess | deviceform | download | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_download_ess_deviceform_4.rvms | 7049 | ess | deviceform | download | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_a/system_a_2026-08-13_download_ess_deviceform_5.rvms | 7049 | ess | deviceform | download | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_download_ess_deviceform_6.rvms | 7049 | ess | deviceform | download | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_download_ess_deviceform_7.rvms | 7049 | ess | deviceform | download | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_a/system_a_2026-08-13_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-08-13_prepared_ess_deviceform_1.rvms | 7049 | ess | deviceform | prepared | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_prepared_ess_deviceform_2.rvms | 7049 | ess | deviceform | prepared | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-13_prepared_ess_uploadform_1.rvms | 6877 | ess | uploadform | prepared | HQ0000A0001 (1611, e4), HQ0000A0002 (1177, e5) |
| system_a/system_a_2026-08-14_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000A0001 (1705, e4), HQ0000A0002 (1255, e5) |
| system_a/system_a_2026-08-14_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-08-14_prepared_bare_deviceform_2.rvms | 5055 | bare | deviceform | prepared | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-08-19_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000A0001 (484, f4), HQ0000A0002 (482, f5) |
| system_a/system_a_2026-09-03_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000A0002 (1257, e5), HQ0000A0001 (1703, e4) |
| system_b/system_b_2026-06-08_download_bare_deviceform_1.rvms | 5067 | bare | deviceform | download | HQ0000B0002 (490, f4), HQ0000B0001 (488, f5) |
| system_b/system_b_2026-06-08_download_bare_deviceform_2.rvms | 5067 | bare | deviceform | download | HQ0000B0002 (490, f4), HQ0000B0001 (488, f5) |
| system_b/system_b_2026-06-18_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-20_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-20_download_bare_deviceform_2.rvms | 5055 | bare | deviceform | download | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-20_download_bare_deviceform_3.rvms | 5055 | bare | deviceform | download | HQ0000B0002 (484, f4), HQ0000B0001 (482, f5) |
| system_b/system_b_2026-07-20_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-20_prepared_half-ess_deviceform_1.rvms | 7497 | half-ess | deviceform | prepared | HQ0000B0002 (1705, e4), HQ0000B0001 (1703, e4) |
| system_b/system_b_2026-07-21_prepared_ess_uploadform_1.rvms | 6877 | ess | uploadform | prepared | HQ0000B0001 (1179, e5), HQ0000B0002 (1609, e4) |
| system_b/system_b_2026-07-24_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-24_download_bare_deviceform_2.rvms | 5055 | bare | deviceform | download | HQ0000B0001 (484, f5), HQ0000B0002 (482, f4) |
| system_b/system_b_2026-07-24_download_bare_deviceform_3.rvms | 5055 | bare | deviceform | download | HQ0000B0002 (484, f4), HQ0000B0001 (482, f5) |
| system_b/system_b_2026-07-24_download_stub_deviceform_1.rvms | 5183 | stub | deviceform | download | HQ0000B0001 (548, e5), HQ0000B0002 (546, e4) |
| system_b/system_b_2026-07-24_prepared_ess_deviceform_1.rvms | 7049 | ess | deviceform | prepared | HQ0000B0001 (1257, e5), HQ0000B0002 (1703, e4) |
| system_b/system_b_2026-07-24_prepared_ess_deviceform_2.rvms | 7049 | ess | deviceform | prepared | HQ0000B0001 (1257, e5), HQ0000B0002 (1703, e4) |
| system_b/system_b_2026-08-12_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000B0002 (1705, e4), HQ0000B0001 (1255, e5) |
| system_c/system_c_2026-06-18_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000C0001 (484, f4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-06-23_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000C0002 (484, f5), HQ0000C0001 (482, f4) |
| system_c/system_c_2026-07-13_gui-export_half-ess_uploadform_1.rvms | 6182 | half-ess | uploadform | gui-export | HQ0000C0002 (484, f5), HQ0000C0001 (1609, e4) |
| system_c/system_c_2026-07-17_download_half-ess_deviceform_1.rvms | 6276 | half-ess | deviceform | download | HQ0000C0002 (484, f5), HQ0000C0001 (1703, e4) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_1.rvms | 6276 | half-ess | deviceform | download | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_2.rvms | 6276 | half-ess | deviceform | download | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_3.rvms | 6276 | half-ess | deviceform | download | HQ0000C0002 (484, f5), HQ0000C0001 (1703, e4) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_4.rvms | 6276 | half-ess | deviceform | download | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_5.rvms | 6276 | half-ess | deviceform | download | HQ0000C0002 (484, f5), HQ0000C0001 (1703, e4) |
| system_c/system_c_2026-07-20_download_half-ess_deviceform_6.rvms | 6276 | half-ess | deviceform | download | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_prepared_ess_deviceform_1.rvms | 7495 | ess | deviceform | prepared | HQ0000C0002 (1703, e4), HQ0000C0001 (1703, e4) |
| system_c/system_c_2026-07-20_prepared_half-ess_deviceform_1.rvms | 6276 | half-ess | deviceform | prepared | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_prepared_half-ess_deviceform_2.rvms | 6276 | half-ess | deviceform | prepared | HQ0000C0001 (1705, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-20_prepared_half-ess_deviceform_3.rvms | 7497 | half-ess | deviceform | prepared | HQ0000C0002 (1705, e4), HQ0000C0001 (1703, e4) |
| system_c/system_c_2026-07-20_prepared_half-ess_deviceform_4.rvms | 5055 | half-ess | deviceform | prepared | HQ0000C0001 (484, e4), HQ0000C0002 (482, f5) |
| system_c/system_c_2026-07-21_gui-export_ess_uploadform_1.rvms | 6877 | ess | uploadform | gui-export | HQ0000C0001 (1611, e4), HQ0000C0002 (1177, e5) |
| system_c/system_c_2026-07-24_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000C0002 (1257, e5), HQ0000C0001 (1703, e4) |
| system_d/system_d_2026-06-18_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000D0002 (484, f4), HQ0000D0001 (482, f5) |
| system_d/system_d_2026-07-20_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-07-20_download_bare_deviceform_2.rvms | 5055 | bare | deviceform | download | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-07-20_download_bare_deviceform_3.rvms | 5055 | bare | deviceform | download | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-07-20_download_bare_deviceform_4.rvms | 5055 | bare | deviceform | download | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-07-20_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-07-23_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000D0002 (484, f4), HQ0000D0001 (482, f5) |
| system_d/system_d_2026-07-23_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000D0002 (484, f4), HQ0000D0001 (482, f5) |
| system_d/system_d_2026-08-12_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
| system_d/system_d_2026-08-12_prepared_ess_deviceform_1.rvms | 7049 | ess | deviceform | prepared | HQ0000D0001 (1257, e5), HQ0000D0002 (1703, e4) |
| system_d/system_d_2026-08-13_download_bare_deviceform_1.rvms | 5055 | bare | deviceform | download | HQ0000D0002 (484, f4), HQ0000D0001 (482, f5) |
| system_d/system_d_2026-08-13_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000D0001 (1257, e5), HQ0000D0002 (1703, e4) |
| system_d/system_d_2026-08-13_prepared_ess_deviceform_1.rvms | 7049 | ess | deviceform | prepared | HQ0000D0002 (1705, e4), HQ0000D0001 (1255, e5) |
| system_d/system_d_2026-08-14_download_ess_deviceform_1.rvms | 7049 | ess | deviceform | download | HQ0000D0001 (1257, e5), HQ0000D0002 (1703, e4) |
| system_d/system_d_2026-08-14_prepared_bare_deviceform_1.rvms | 5055 | bare | deviceform | prepared | HQ0000D0002 (484, f4), HQ0000D0001 (482, f5) |
| system_d/system_d_2026-08-14_prepared_bare_deviceform_2.rvms | 5055 | bare | deviceform | prepared | HQ0000D0001 (484, f5), HQ0000D0002 (482, f4) |
