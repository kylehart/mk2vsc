---
title: "mk2vsc: Victron VEConfigure .rvms and .rvsc files without VEConfigure"
description: "Read, validate, decode, diff and edit Victron VEConfigure .rvms configuration files on macOS, Linux or Windows, without VEConfigure. File format, checksum, settings table, error codes."
---

# mk2vsc

Read, validate, decode, diff and edit the `.rvms` configuration files that Victron's VRM Remote
VEConfigure downloads from a MultiPlus or Quattro system, on macOS, Linux or Windows, without
VEConfigure. Zero-dependency Python library and command line.

```
pip install mk2vsc
mk2vsc show download.rvms
mk2vsc edit download.rvms absorption=56.8 float=54.0
mk2vsc verify download.edited.rvms redownload.rvms
```

Source and issues: [github.com/kylehart/mk2vsc](https://github.com/kylehart/mk2vsc).

## The file format

- [The .rvms file format](FORMAT.md): section grammar, the per-section checksum, the per-inverter
  block, device form versus upload form, the assistant area.
- [The settings table](FIELDS.md): every VE.Bus setting ID with Victron's name, VEConfigure's
  identifier, scale, unit, default and range, and how sure we are.
- [Assistants (ESS) in the file](ASSISTANTS.md) and [ESS injection by file: the experiment in full](ESS_INJECTION.md).

## Working with the device

- [Error codes: mk2vsc-36, mk2vsc-47, mk2vsc-49, Error 1303, VE.Bus errors](ERRORS.md).
- [Workflow with VRM Remote VEConfigure](WORKFLOW.md), including assistant removal and reinstall and what still needs Windows.
- [Change control](CHANGE_CONTROL.md): the loop that keeps a fleet's configuration auditable.
- [Safety](SAFETY.md) and [how to decide whether to trust this](QA.md).

## Background

- [How this came to be](HISTORY.md), [the fixture corpus](FIXTURES.md), [how the project is run](PRACTICES.md).
