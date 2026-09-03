# The `.rvms` file format, as far as we understand it

This is the specification a Victron Community thread asked Victron to publish and never received. It is
reverse-engineered from device downloads, not from any Victron source, so every statement here carries
one of three labels:

* **Observed**: true of every file in our corpus, checked by the test suite (`tests/`).
* **Inferred**: the narrowest reading of the observations that we have not verified independently.
* **Unknown**: bytes we can locate but cannot explain.

The corpus behind every claim: 84 unique files (`fixtures/`, see `docs/FIXTURES.md`), 8 inverters
(MultiPlus-II class, 48 V battery, 120 V output) in 4 two-inverter split-phase systems, a single firmware
version (2729560, shown as "v560" in VRM), a single format version ("1.33"). We have no `.rvsc`
(single-unit) file, no three-phase or 3+ unit file, and no file from any other firmware or tool version.
Anything outside that envelope is untested.

## 1. File grammar

**Observed.** A file is a magic header followed by a chain of sections. Every multi-byte integer is
little-endian.

```
file     := magic section*
magic    := u16 name_len(29) | "VEConfig setting section file"
section  := u16 name_len | name | u32 next | payload | u32 checksum
next     := absolute offset of the NEXT section's u16 prefix; equals file length for the last section
checksum := sum of 32-bit LE words over [section_start, checksum_start), mod 2**32
```

The sections always appear in this order:

| Section | Payload | Count |
|---|---|---|
| `Mk2vscInfo` | 10 bytes: `u32 1`, `u16 4`, `"1.33"` | 1 |
| `BareSettingInfo` | 4001 bytes, byte-identical across all 84 files | 1 |
| `BareSettingData` | one inverter's configuration | one per inverter (2 in every corpus file) |

A real header, from `fixtures/guava/guava_2026-07-20_download_bare_deviceform_1.rvms`:

```
00000000: 1d00 5645 436f 6e66 6967 2073 6574 7469  ..VEConfig setti
00000010: 6e67 2073 6563 7469 6f6e 2066 696c 650a  ng section file.
00000020: 004d 6b32 7673 6349 6e66 6f3d 0000 0001  .Mk2vscInfo=....
00000030: 0000 0004 0031 2e33 33fa 1758 6c0f 0042  .....1.33..Xl..B
00000040: 6172 6553 6574 7469 6e67 496e 666f f70f  areSettingInfo..
00000050: 0000 0400 0000 58a6 2900 0280 0701 0000  ......X.).......
```

Reading it with the grammar: `1d 00` + 29-byte magic; `0a 00` + `Mk2vscInfo`; `3d 00 00 00` = next section at
0x3d (the `=` that looks like part of the name is the low byte of that pointer); payload
`01 00 00 00 | 04 00 | "1.33"`; checksum `fa 17 58 6c`. Then `0f 00` + `BareSettingInfo`; next `f7 0f 00 00`
= 0xff7, which is where the first `BareSettingData` prefix sits.

The section table of that file as our parser reports it:

| name | start | next | payload bytes | checksum |
|---|---|---|---|---|
| Mk2vscInfo | 0x1f | 0x3d | 10 | 6c5817fa |
| BareSettingInfo | 0x3d | 0xff7 | 4001 | 1ecb0fba |
| BareSettingData | 0xff7 | 0x11db | 459 | 4b7bc06c |
| BareSettingData | 0x11db | 0x13bf (= file length) | 459 | a465c475 |

### 1.1 The checksum

**Observed.** The last four bytes of every section are the 32-bit little-endian word sum of the section
from its length prefix up to those four bytes, modulo 2**32, with a trailing partial word zero-padded on
the high side. This validates on all 107 files we have held (84 unique) and every section in them, with
the three deliberately broken files in `fixtures/` as negative controls. `mk2vsc.sections.sum32_le` is the
whole implementation.

History, because earlier write-ups describe the same thing differently. Our first solved formula was

```
field = ( sum32( block[0x02 : field] ) + 0x6142000F ) mod 2**32
```

where `block` began at the `B` of `BareSettingData` and `0x6142000F` was presented as a magic
initialisation constant. It is not a constant. It is the first word of the section read from its length
prefix: `0f 00 42 61` is `0x6142000F` little-endian. Likewise the "`0f 00` framing" that seemed to end
every block except the last is the *next* section's name-length prefix (15 = len("BareSettingData")).
The clean statement is the one in the grammar above, and it applies to `Mk2vscInfo` and
`BareSettingInfo` as well, which the earlier tooling never checked.

The checksum is linear. That is why a delta patch worked once by luck in June 2026, and why an exhaustive
13-million-trial CRC-16 search found nothing: it is not a CRC. The decisive evidence was two downloads of
an unchanged system: the only body bytes that moved were the save timestamp, and the checksum moved by
exactly those byte deltas, in position.

### 1.2 What the checksum is not

**Inferred.** It is an integrity check against corruption in transit, not authentication. Nothing in the
file is signed. The device's rejections that mention a "grid code password" (`mk2vsc-36`) are not about
this field; see `docs/ERRORS.md` and `docs/ASSISTANTS.md`.

## 2. `Mk2vscInfo` and `BareSettingInfo`

**Observed.** `Mk2vscInfo`'s payload is `u32 1`, `u16 4`, `"1.33"`. We read "1.33" as the format or tool
version; it is the same in every file, including those written by two different VEConfigure/System
Configurator builds.

**Observed.** `BareSettingInfo`'s 4001-byte payload is byte-identical in every file regardless of the
system, its settings, or the presence of an assistant. Its first bytes are
`04 00 00 00 58 a6 29 00 02 80 07 01 ...`; `58 a6 29 00` is 2729560, the firmware version that also appears in
every unit block.

**Inferred.** It is a template or schema describing the settings that follow, tied to the firmware
version. **Unknown.** Its internal structure. We tried and failed to read field names or scaling out of
it; it does not contain the per-unit values.

## 3. `BareSettingData`: one inverter's block

Offsets below are relative to the section's **name start** (the `B`), because that is how every note and
change record in this project addressed them. The section proper begins two bytes earlier at the length
prefix, so the section-relative offset is always +2.

The same Guava file, first unit block:

```
00000ff8: 0f 0042 6172 6553 6574 7469 6e67 4461 7461  ..BareSettingData
00001008: db11 0000 0300 0000 7b20 1b7a 58a6 2900      next=0x11db  3  unit-const  fw 2729560
00001018: ff01 0158 a629 0006 0008 1900 00fa 1b02      (unknown header bytes)
00001028: 0101 0300 0000 00f4 000b 0048 5132 3431      slot=00 flag=f4 slot=00 ... "HQ2414U6FVN"
00001038: 3455 3646 564e 0000 0000 0000 0000 0000
00001048: d86b 5e6a 0000 0000 8001 f481 fe4d e015      save ts 0x6a5e6bd8  0x0180  settings[0..]
```

### 3.1 Layout (device form)

| Offset | Size | Content | Status |
|---|---|---|---|
| +0x00 | 15 | `BareSettingData` | Observed |
| +0x0f | u32 | next-section pointer (see grammar) | Observed |
| +0x13 | u32 | value 3 in every block | Observed; meaning Unknown |
| +0x17 | u32 | per-unit constant; bytes +0x18..0x19 track the serial's date code (`HQ2240*` → `19`, `HQ2414*` → `1b`) | Observed; Inferred: hardware revision / production batch, not firmware |
| +0x1b | u32 | 2729560 = firmware "v560" | Observed |
| +0x1f | 22 | header bytes, e.g. `ff 01 01 58 a6 29 00 06 00 08 19 00 00 fa 1b 02 01 01 03 00 00 00` (contains the firmware word again at +0x22) | Unknown |
| +0x35 | u8 | slot byte A: `00` or `86` | Observed |
| +0x36 | u8 | assistant flag: `f4`/`f5` no assistant, `e4`/`e5` assistant present; low nibble follows the slot (4 with A=`00`, 5 with A=`86`) | Observed |
| +0x37 | u8 | slot byte B: `00` or `01` | Observed |
| +0x3a | 11 + pad | ASCII inverter serial `HQ...`, zero padded | Observed |
| +0x45 | 10 | zeros (device form); see §4 for the upload form | Observed |
| +0x4f | u32 | Unix timestamp of the last save; rewritten on every save. This is the "nonce" that makes an archived file "old" to the device | Observed |
| +0x53 | u32 | zero | Observed |
| +0x57 | u16 | `0x0180` in every block | Observed; Unknown |
| +0x59 | u16[190] | the settings array; entry *n* is VE.Bus setting ID *n* (see `docs/FIELDS.md`) | Observed |
| +0x1d5 | var | assistant area (§5) | Observed |
| last 4 | u32 | section checksum (§1.1) | Observed |

**Observed.** Slot bytes: in every file the two blocks differ, one being (`00`,`00`) and the other
(`86`,`01`). **Inferred.** They identify the inverter's position in the VE.Bus system (which one is the
first device). We have no three-unit file to see a third value.

**Observed.** Block order is **not** stable. The two blocks of the same system swap file position between
downloads taken minutes apart, and the length in the "B to next B" convention follows the position (484
then 482 bytes) rather than the inverter. A positional byte diff of two consecutive downloads therefore
shows dozens of differences; compared by serial there are exactly six bookkeeping bytes per block
(pointer, timestamp) plus the checksum. `mk2vsc diff` always compares by serial.

### 3.2 The timestamp

**Observed.** The u32 at +0x4f decodes to a plausible UTC time on every device-form block (2026-06 to
2026-09 in our corpus) and the two blocks of one download differ by a few seconds. Two same-hour re-saves
of an unchanged system differ only here (and in the checksum). **Inferred.** The device compares this
against its own record and rejects an upload whose stamp is older than its current state with
`mk2vsc-36` ("Incorrect grid code password or old configuration file"). Uploading a freshly downloaded
file back unchanged is always accepted; uploading a weeks-old archived file of the same system is
rejected. Build every edit on a fresh download.

## 4. Device form and upload form

**Observed.** Files come in two forms.

* **Device form**: what VRM's Remote VEConfigure *download* produces. Bytes +0x45..+0x4e are ten zeros.
* **Upload form**: what VEConfigure / VE.Bus System Configurator *writes* for upload. The ten zeros are
  replaced by a 16-byte blob followed by four zeros, so everything after +0x45 shifts by +10: the save
  timestamp sits at +0x59 and the settings array starts at +0x63.

```
device : ... serial ... | 00×10                                   | ts(4) | 00×4 | 80 01 | settings
upload : ... serial ... | 01 00 08 00 4a 39 81 80 4e 93 d7 0c ts'(4) | 00×4 | ts(4) | 00×4 | 80 01 | settings
```

The 12 leading blob bytes are identical in every GUI export we hold (two exports a week apart from the
same tool, plus files we transformed to match). The trailing u32 `ts'` is another Unix timestamp; in the
two GUI exports it is a few seconds before the per-block save stamps, so we read it as the export time.

**Observed.** The GUI also writes assistant records in a compact form (the 1152-byte device record is a
1102-byte record in the export; 704 becomes 670) and a shorter trailer; the device stores the padded form.
When VRM adopts an upload-form file and the device is next downloaded, the result is device form again,
so the blob never survives a round trip.

**Observed.** The two forms otherwise agree on every setting: `mk2vsc diff` of a GUI export against the
subsequent device download reports no setting differences.

Detection: `UnitBlock.is_upload_form` is true when any of the ten bytes at +0x45 is non-zero. The writer
refuses upload-form input because the only files we have ever uploaded after editing were device
downloads, and because a file that carries the blob is a GUI artifact, not a statement of device state.

**Unknown.** What the 12 constant bytes mean, and whether the blob is required for the device to run an
assistant *install* procedure (see `docs/ASSISTANTS.md`).

## 5. The assistant area

**Observed.** After the 190 settings the block continues with a sequence of records and a tail:

```
area   := record* tail
record := marker(2) | subtype(2) | len(2) | body[len]
marker := ff ff   empty slot / container
        | f5 ff   assistant record
```

Every block in the corpus fits one of these shapes:

| Shape | Bytes | Where seen |
|---|---|---|
| bare | `ff ff ff ff 00 00` + `ff 00 0b` | every well-formed block without an assistant (89 blocks; a few show the residue or legacy shapes below) |
| residue | `f5 ff 00 ff 00 00` + `ff 00 0b` (also `ff ff 00 00 00 00`, `f5 ff 00 00 00 00`) | downloads taken after a rejected or rolled-back assistant upload; functionally bare |
| legacy container | `ff ff ff ff 06 00` + `a7 fe 00 00 57 01` + `ff fa 0a` | the two June 2026 files written by an older tool build |
| stub | `ff ff ff ff 40 00` + `a7 fe 00 00 57 01` + 56 × `ff` + `c0 0a`, then `ff 40 0a` | what VEConfigure wrote on both inverters after accepting a transplanted assistant and discarding it |
| GUI-installed ESS | `f5 ff 01 01 c0 02` + 704-byte body, or `f5 ff 01 00 80 04` + 1152-byte body, then a 72-byte tail | every working ESS install (one record per inverter; the pair holds one of each) |

**Observed.** On bare, residue, legacy and stub blocks the tail is `ff` + u16, and that u16 plus the bytes
used by the records is always 2822 (= 2816 + the 6-byte empty header). **Inferred.** The u16 is a
remaining-space counter over a 2816-byte assistant budget.

**Observed.** On device-form ESS blocks the 72-byte tail is `ff` padding followed by
`0e 00 8e 01 15 00 <4 bytes> ff 00 00`, where the 4 bytes are constant per inverter (`20 51 b8 4d` on one
Papaya unit, `76 c4 e8 db` on one Guava unit). The upload form carries the same 13-byte trailer without
the padding and ending `00 00 00`. **Unknown.** What any of it means.

**Observed.** The 1152-byte body is byte-identical across every system; the 704-byte body differs between
systems in at most one byte (a primary/secondary flag). **Inferred.** The assistant payload is a fixed
program template chosen by VEConfigure for the installation type, not something compiled per unit.
**Unknown.** The body's encoding. It has the statistics of code (entropy about 6.2 bits/byte, recurring
2-3 byte patterns) and contains recognisable parameter values (48.00 V, 10 %). `mk2vsc` reports the records;
it does not author them, and `docs/ASSISTANTS.md` explains why we stopped trying.

## 6. Observed / Inferred / Unknown, collected

**Observed** (asserted by tests on every good fixture)

* section grammar, pointer chain contiguous and ending at EOF, every checksum a plain word sum
* `Mk2vscInfo` and `BareSettingInfo` constant across the corpus
* serial at +0x3a, firmware 2729560 at +0x1b, `3` at +0x13, `0x0180` at +0x57
* assistant flag ∈ {f4, f5, e4, e5} with the low nibble tied to the slot bytes
* upload-form shift of exactly 10 bytes; setting 5 reads 120 (V) on every block under the shifted or
  unshifted offset, which is how the shift was pinned
* save timestamp plausible on every device-form block
* assistant area shapes as tabulated; free + used = 2822 on non-ESS blocks; ESS records 704/1152 only
* block order not stable; content identical by serial

**Inferred**

* +0x17 word encodes hardware revision / batch (tracks the serial date code; firmware is elsewhere)
* the timestamp is the freshness token behind `mk2vsc-36`
* the trailer u16 is a free-space counter over 2816 bytes
* the assistant body is a fixed template per installation type

**Unknown**

* `BareSettingInfo` semantics (4001 bytes)
* header bytes +0x1f..+0x34 and the `0x0180` word at +0x57
* the 12 constant blob bytes of the upload form and whether they gate an install
* the ESS record body encoding and the 13-byte ESS trailer
* settings 128..189 (0xffff on bare blocks; the GUI ESS install writes 1 or 0x0101 into 128 and 129)
* whether `.rvsc` single-unit files share this layout: we have none
* three-phase or 3+ unit files: we have none
* any other firmware version or format version: we have none

If you hold a file outside our envelope, `mk2vsc validate` and `mk2vsc info` on it are the most useful
contributions you can make; see `CONTRIBUTING.md`.
