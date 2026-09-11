# Inverter parity

The inverters of a parallel, split-phase or three-phase system are parts of one machine: one DC bus, one
battery, one synchronised AC reference. Victron's parallel/split-phase manual requires them to be the
same type, size, system voltage, feature set and firmware, and warns that when settings disagree the
values shown on the GX and VRM "will or can be wrong" and control "will not always work properly".

It is **not** a rule that the two blocks are byte-identical. The same manual names settings that are
configured **per unit** and may legitimately differ:

| documented per unit | setting ids |
|---|---|
| Country / grid code and related values | 81, 128-191 |
| Virtual Switch configuration | 15-43, 52-59, 70 |
| DC input low shut-down values | 11, 12 |
| Assistants (genset start/stop, relay locker, ...) | assistant area, not a numbered setting |

So the rule mk2vsc applies is: **parity everywhere outside that list.**

## Severity

| class | example | meaning |
|---|---|---|
| `expected` | grid-code word 128 differs | documented per-unit; a note, never a finding |
| `error` | absorption 57.6 V vs 48.0 V | acts on the **shared battery**; probable commissioning error |
| `warning` | flags0 differs | not documented per-unit; check it is intended |

The "shared battery" set is 2, 3, 4, 5, 6, 7, 8, 9, 64, 65, 72, 74: charge voltages, charge current,
absorption timing, capacity and SoC bookkeeping. Both units charge one pack, so two targets is not a
tuning.

## Why an exception rather than a warning string

A disagreement changes what a calling program should do. `check_parity()` therefore **raises**:

| exception | when |
|---|---|
| `ParityMismatch` | the units disagree on a setting outside the documented per-unit list |
| `ParityNotComparable` | the file could not be judged: fewer than two inverter blocks, a block too short to hold its 192-word settings array, or duplicate serials |

Both carry the full `ParityReport` as `.report`. The second exists so that *not checked* can never be
mistaken for *OK*: a report that compared nothing has `ok == False`. A caller that wants the report
regardless asks for `parity_report_bytes()`, which never raises.

```python
from mk2vsc import check_parity, ParityMismatch

try:
    check_parity("download.rvms")
except ParityMismatch as e:
    for d in e.report.errors:
        print(d.describe())
```

CLI: `mk2vsc parity FILE...` exits 2 on a mismatch, 1 when a file could not be read or compared, 0 only
when every file was compared and agrees; a mismatch anywhere in a batch wins over a read error whatever
the argument order. `mk2vsc show` prints the report when the units differ (or when the file could not
be compared) but keeps its exit code, being a display command.

## Three-phase systems: written for N units, exercised only for pairs

The comparison is written for **N >= 2 inverter blocks**, so a three-phase file is checked rather than
refused: every setting is compared across all units and a difference lists every unit's value.

**What is and is not established:**

| | status |
|---|---|
| Two-inverter pairs (parallel / split-phase) | **Observed** on real hardware: the whole fixture corpus, and controlled one-sided writes |
| Three or more units | **Not established.** No three-phase system has been read, written or verified with this tool. Every fixture holds exactly two blocks. The tests cover N > 2 only with a synthetic file built by duplicating a real block under a placeholder serial |
| The exception list for N > 2 | **Assumed** unchanged: it is a property of the setting, not of the unit count. That is an assumption, not an observation |

Treat N > 2 as **unsupported**. The code path exists so that a three-phase file fails loudly on a real
disagreement rather than silently passing as "not a pair"; it is not a claim that the tool understands
three-phase configuration. If you hold a three-phase download, a comparison result is worth reading,
and worth doubting.


## Limits, stated plainly

- Parity is computed over the raw 16-bit words, so a register we have **not** named is still
  compared. Not having a label is not a reason to stay silent about a disagreement.
- "Expected" means *documented as per-unit*. It does not mean the value is correct.
- **Virtual Switch bits also live in flag words 1, 60 and 62**, alongside unrelated bits. Those words
  are not on the exception list, so a legitimately per-unit VS configuration that differs only there
  is reported as a `warning`. The list is by whole register on purpose: excusing a flag word would
  also excuse its non-VS bits.
- A truncated-but-parseable file is reported as not comparable, not as a partial result. The length
  check reserves the four-byte section checksum: without it a block short by a few bytes would read
  checksum bytes as settings 190 and 191, which are on the exception list, so two equally damaged
  blocks could report OK.
- **Firmware is compared too.** Victron requires every unit on the same version, and settings can
  agree word for word while the versions differ, so a settings-only check would wrongly pass. It is a
  block-header property, reported separately from the 192-register comparison, and it fails the
  eager check.

## How this condition arises in practice

The configuration GUI edits one unit at a time. Saving after the first unit leaves exactly this
state. It was found live on a real system, and reproduced deliberately in a controlled test where a
float voltage was written to one inverter by serial: it stored on that unit alone, and the check
reported the disagreement from a fresh download rather than from the prepared file.
