"""The +0x4f stamp is a file-generation time and not an acceptance gate (System B, 2026-09-04)."""
from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks
from mk2vsc.diff import diff_bytes

D1 = "system_b/system_b_2026-09-04_download_ess_deviceform_1.rvms"   # 17:21, later accepted unmodified
D2 = "system_b/system_b_2026-09-04_download_ess_deviceform_2.rvms"   # 20:03
D3 = "system_b/system_b_2026-09-04_download_ess_deviceform_3.rvms"   # 20:06, after the older file was accepted
BACK = "system_b/system_b_2026-09-04_prepared_ess_deviceform_1.rvms"  # D2 content stamped 16:00, accepted


def _stamps(data):
    return {u.serial: u.save_timestamp for u in unit_blocks(RvmsFile.parse(data))}


def test_three_downloads_of_unchanged_content_carry_increasing_stamps(good_files):
    s1, s2, s3 = (_stamps(good_files[k]) for k in (D1, D2, D3))
    for serial in s1:
        assert s1[serial] < s2[serial] < s3[serial], serial
    assert diff_bytes(good_files[D1], good_files[D2]).only_bookkeeping
    assert diff_bytes(good_files[D2], good_files[D3]).only_bookkeeping


def test_the_accepted_back_stamped_file_differs_from_its_source_only_in_the_stamp(good_files):
    d = diff_bytes(good_files[D2], good_files[BACK])
    assert d.only_bookkeeping, d
    stamps = _stamps(good_files[BACK])
    assert set(stamps.values()) == {1788537600}          # 2026-09-04 16:00:00 UTC on both blocks
    assert all(v < min(_stamps(good_files[D1]).values()) for v in stamps.values())
