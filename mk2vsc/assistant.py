"""
Assistant operations by file: remove the assistant from a system, or reinstall it from an earlier download.

The device runs two different procedures depending on the container form of the uploaded file
(docs/FORMAT.md section 4):

* device form (what a download looks like) with an unchanged assistant area: a settings write, no VE.Bus
  reset.  This is what ``mk2vsc edit`` produces and the only form the writer accepts.  Device-form files
  with an altered assistant area have produced stubs, half installs and stored-but-never-started systems
  (docs/ASSISTANTS.md section 4), never a working change.
* upload form (what the VEConfigure GUI uploads): the install procedure.  "Resetting VE.Bus products",
  the inverters stop for its duration, and the device rebuilds its assistant state from the file.  On
  2026-09-04 a System D download turned into upload form with the assistant area emptied removed ESS
  from both inverters, and the same system's earlier ESS download turned into upload form put it back;
  the re-downloads matched the intended state byte for byte apart from bookkeeping (docs/ASSISTANTS.md).

Both functions here produce upload-form files and therefore reset the VE.Bus when uploaded.  The
inverters are off for the reset; the VRM tunnel is unresponsive for about five minutes afterwards, and
the upload dialog may end in "Error 1303" although the device completed.  Judge the result by a fresh
download and the GX's assistant list, never by the dialog.

What is proven: removing ESS, and reinstalling ESS from a download of the SAME system that had it.
What is not: installing an assistant on a system that never had one (the records would have to come
from another system, together with the settings a GUI install normalises; see ``mk2vsc.experimental``).
"""
from __future__ import annotations

import struct
from typing import Optional

from .sections import RvmsFile, SECTION_DATA
from .units import unit_blocks, OFF_ASSISTANT_FLAG, ASSISTANT_FLAGS
from .upload_form import to_upload_form, TransformRefused

GRID_CODE_WORDS = (81, 128, 190, 191)
BUDGET_UPLOAD = 2812 - 4          # the upload-form free-space budget after settings 190/191 left the area
BARE_AREA_UPLOAD = struct.pack("<H", 0) + b"\xff" + struct.pack("<H", BUDGET_UPLOAD - 2) + b"\x0a\x00"


class AssistantRefused(Exception):
    pass


def remove_assistant(device: bytes, timestamp: Optional[int] = None) -> bytes:
    """An upload-form file that, uploaded, removes the assistant from every inverter of the system.

    Input: a fresh device-form download whose blocks carry an assistant.  Output: the same settings in
    upload form with the assistant flag cleared (e4/e5 -> f4/f5), the grid code and its words
    (settings 81, 128, 190, 191) cleared to the never-coded values, and an empty assistant area.  The
    device stores the result as its canonical bare block (``00 00 ff 00 0b``); the re-download after the
    2026-09-04 removal differed from this file only in bookkeeping bytes.
    """
    f = RvmsFile.parse(device)
    if not f.all_checksums_ok:
        raise AssistantRefused("input checksums invalid")
    units = unit_blocks(f)
    if any(u.is_upload_form for u in units):
        raise AssistantRefused("input must be a device download, not an upload-form file")
    if not all(u.assistant_flag in ASSISTANT_FLAGS for u in units):
        raise AssistantRefused("no assistant on every inverter; nothing to remove")
    up = RvmsFile.parse(to_upload_form(device, timestamp=timestamp))
    hdr = len(SECTION_DATA) + 4
    payloads = []
    for s in up.sections:
        if not s.is_unit:
            payloads.append(s.payload)
            continue
        u = next(x for x in unit_blocks(up) if x.section is s)
        body = bytearray(u.raw[hdr: u.assistant_area_offset])
        body[OFF_ASSISTANT_FLAG - hdr] = {0xE4: 0xF4, 0xE5: 0xF5}[u.assistant_flag]
        for sid, val in zip(GRID_CODE_WORDS, (0, 0xFFFF, 0xFFFF, 0xFFFF)):
            o = u.setting_offset(sid) - hdr
            body[o: o + 2] = struct.pack("<H", val)
        body += BARE_AREA_UPLOAD
        payloads.append(bytes(body))
    out = up.rebuild(payloads).to_bytes()
    chk = RvmsFile.parse(out)
    if not chk.all_checksums_ok or any(u.assistant_flag in ASSISTANT_FLAGS or not u.is_upload_form for u in unit_blocks(chk)):
        raise AssistantRefused("internal error: output does not parse as an upload-form bare file")
    return out


def reinstall_assistant(device_with_assistant: bytes, timestamp: Optional[int] = None) -> bytes:
    """An upload-form file that, uploaded, installs the assistant(s) carried by an earlier device download
    of the same system.  Settings, grid code and records travel with the file.  Proven on System D
    (2026-09-04): ESS removed by ``remove_assistant`` and put back by this, both inverters advertising
    the assistant and the SOC limit enforced afterwards."""
    f = RvmsFile.parse(device_with_assistant)
    if not f.all_checksums_ok:
        raise AssistantRefused("input checksums invalid")
    units = unit_blocks(f)
    if not all(u.assistant_flag in ASSISTANT_FLAGS for u in units):
        raise AssistantRefused("the source download must carry the assistant on every inverter")
    try:
        return to_upload_form(device_with_assistant, timestamp=timestamp)
    except TransformRefused as e:
        raise AssistantRefused(str(e))
