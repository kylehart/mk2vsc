"""Assistant removal and reinstall by file (mk2vsc.assistant), against the System D cycle of 2026-09-04."""
import pytest

from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks
from mk2vsc.assistant import remove_assistant, reinstall_assistant, AssistantRefused, BARE_AREA_UPLOAD
from mk2vsc.assistants import parse_assistant_area, grid_code_words
from mk2vsc.diff import diff_bytes

SRC = "system_d/system_d_2026-09-04_download_ess_deviceform_1.rvms"          # post-T5 download (ESS on both)
ACCEPTED_BARE = "system_d/system_d_2026-09-04_prepared_bare_uploadform_1.rvms"  # the file the device accepted
BARE_AFTER = "system_d/system_d_2026-09-04_download_bare_deviceform_1.rvms"     # re-download after removal
ESS_AFTER = "system_d/system_d_2026-09-04_download_ess_deviceform_2.rvms"       # re-download after reinstall


def test_remove_reproduces_the_accepted_file_byte_for_byte(good_files):
    """Same export timestamp as the file the device accepted -> identical bytes (serials are pseudonyms in both)."""
    import struct
    acc = good_files[ACCEPTED_BARE]
    first = unit_blocks(RvmsFile.parse(acc))[0]
    ts = struct.unpack_from("<I", first.raw, 0x45 + 12)[0]         # export timestamp in the upload-form blob
    out = remove_assistant(good_files[SRC], timestamp=ts)
    assert len(out) == len(acc) == 5079
    assert out == acc
    for u in unit_blocks(RvmsFile.parse(out)):
        assert u.is_upload_form and u.assistant_flag in (0xF4, 0xF5)
        assert u.assistant_area == BARE_AREA_UPLOAD
        w = grid_code_words(u)
        assert w["grid_code"] == 0 and (w["w128"], w["w190"], w["w191"]) == (0xFFFF, 0xFFFF, 0xFFFF)


def test_the_device_stored_the_removal_as_its_canonical_bare_block(good_files):
    """Uploading the removal file gave a device download whose settings match it and whose assistant area is the
    device's own bare shape."""
    d = diff_bytes(good_files[ACCEPTED_BARE], good_files[BARE_AFTER])
    assert d.only_bookkeeping, d
    for u in unit_blocks(RvmsFile.parse(good_files[BARE_AFTER])):
        assert u.assistant_area == bytes.fromhex("0000ff000b") and not u.is_upload_form
        assert parse_assistant_area(u)["kind"] == "none"


def test_reinstall_round_trips_to_the_original_ess_download(good_files):
    """reinstall(post-T5 download) uploaded, then re-downloaded, equals the post-T5 download apart from bookkeeping."""
    out = reinstall_assistant(good_files[SRC], timestamp=1_788_549_700)
    assert all(u.is_upload_form and u.assistant_flag in (0xE4, 0xE5) for u in unit_blocks(RvmsFile.parse(out)))
    assert diff_bytes(out, good_files[ESS_AFTER]).only_bookkeeping
    assert diff_bytes(good_files[SRC], good_files[ESS_AFTER]).only_bookkeeping


def test_remove_refuses_bare_and_upload_form_inputs(good_files):
    with pytest.raises(AssistantRefused):
        remove_assistant(good_files[BARE_AFTER])
    with pytest.raises(AssistantRefused):
        remove_assistant(good_files[ACCEPTED_BARE])
    with pytest.raises(AssistantRefused):
        reinstall_assistant(good_files[BARE_AFTER])


def test_remove_works_on_every_ess_download_in_the_corpus(good_files, manifest):
    by_file = {e["file"]: e for e in manifest["entries"]}
    n = 0
    for name, data in good_files.items():
        e = by_file[name]
        if e["origin"] != "download" or e["state"] != "ess":
            continue
        out = remove_assistant(data, timestamp=1_788_000_000)
        f = RvmsFile.parse(out)
        assert f.all_checksums_ok and len(unit_blocks(f)) == 2
        # every setting except the grid-code words (81, 128, 190, 191) is carried verbatim, per serial
        src = {u.serial: u for u in unit_blocks(RvmsFile.parse(data))}
        for v in unit_blocks(f):
            u = src[v.serial]
            assert [x for i, x in enumerate(u.settings()) if i not in (81, 128, 190, 191)] == \
                   [x for i, x in enumerate(v.settings()) if i not in (81, 128, 190, 191)], (name, v.serial)
        n += 1
    assert n >= 10
