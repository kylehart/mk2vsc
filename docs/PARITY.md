# Inverter parity

The two inverters of a parallel or split-phase pair are two halves of one machine: one DC bus, one
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

A disagreement changes what a calling program should do. `check_parity()` therefore **raises**
`ParityMismatch`; a caller either catches it (the exception carries the full `ParityReport` as
`.report`) or explicitly asks for `parity_report_bytes()`, which never raises.

```python
from mk2vsc import check_parity, ParityMismatch

try:
    check_parity("download.rvms")
except ParityMismatch as e:
    for d in e.report.errors:
        print(d.describe())
```

CLI: `mk2vsc parity FILE...` exits 2 on a mismatch; `mk2vsc show` prints the report when the pair
differs but keeps its exit code, being a display command.

## Two limits, stated plainly

- Parity is computed over the raw 16-bit words, so a register we have **not** named is still
  compared. Not having a label is not a reason to stay silent about a disagreement.
- "Expected" means *documented as per-unit*. It does not mean the value is correct.

## How this condition arises in practice

The configuration GUI edits one unit at a time. Saving after the first unit leaves exactly this
state. It was found live on a real system, and reproduced deliberately in a controlled test where a
float voltage was written to one inverter by serial: it stored on that unit alone, and the check
reported the disagreement from a fresh download rather than from the prepared file.
