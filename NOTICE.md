# Notice

## Not affiliated with Victron Energy

mk2vsc is an independent project. It is not affiliated with, endorsed by, sponsored by, or connected
to Victron Energy B.V. "Victron", "Victron Energy", "VEConfigure", "VE.Bus", "MultiPlus", "Quattro",
"Cerbo GX" and "VRM" are trademarks of Victron Energy B.V., used here only to identify the products
and file formats this software works with.

## Purpose: interoperability

This software lets owners and installers of Victron equipment read, check and change their own
configuration files on their own computers, on platforms the vendor's tooling does not support. The
file-format analysis was carried out solely to achieve interoperability with an independently created
program, as permitted by Article 6 of EU Directive 2009/24/EC, the corresponding provisions of
national law, and 17 U.S.C. 1201(f). The format contains no encryption, no signature and no access
control; the integrity trailer on each section is a plain checksum against corruption. No technological
protection measure was circumvented, and the dealer grid-code password is neither stored in the file
nor handled by this project.

## What this repository does not contain

No Victron source code, binaries, installers, documentation or artwork. Setting names come from
Victron's publicly published MK2 Protocol document and from functional identifiers derived from
publicly distributed software (see docs/FIELDS.md for attribution); such identifiers are, in our
understanding, not protectable expression and are included so that decoded values can be labelled.

## Editing, and what protects you

This project writes configuration files. Every edit is length-preserving, restricted to settings with
CONFIRMED or HIGH confidence unless overridden, checked against the device's own minimum and maximum
for that setting, checked for physical plausibility, and verified byte for byte before the file is
written; the input file is never overwritten. None of that replaces verification on the device: the
documented loop is edit, upload through Victron's own VRM Remote VEConfigure, download again, and
verify. Read docs/SAFETY.md before uploading anything.

## Third-party material

Two tables in this project are taken from [talas9/rvsc-tools](https://github.com/talas9/rvsc-tools),
Copyright (c) 2026 Mohammed Talas, MIT License: VEConfigure's internal setting identifiers
(`mk2vsc.fields.EPROM_NAMES`) and the VEConfigure tab/group/label placement and option text
(`mk2vsc.ui`). The MIT permission notice applies to that material:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
> associated documentation files (the "Software"), to deal in the Software without restriction,
> including without limitation the rights to use, copy, modify, merge, publish, distribute,
> sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions: The above copyright notice and this
> permission notice shall be included in all copies or substantial portions of the Software. THE
> SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
> LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
> IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
> WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Setting IDs, scales and flag-bit names are cited from Victron's public MK2 Protocol document and from
[xcellsior/ve-bus-programming](https://github.com/xcellsior/ve-bus-programming) (FINDINGS.md) as
references; no text from either is reproduced beyond identifiers.

## No warranty, and a safety warning

This software is provided "as is", without warranty of any kind; see LICENSE (MIT). Battery inverter
systems can damage batteries and equipment or cause fire when misconfigured. Decoded values can be
wrong. Verify against the vendor's tools and the battery manufacturer's documentation before changing
anything on a system people depend on. The authors accept no liability for loss or damage arising from
use of this software.

## Takedown

If Victron Energy B.V. believes this project infringes its rights, open an issue or contact the
repository owner; we will engage in good faith.
