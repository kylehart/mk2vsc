from rvms.qualify import Intent, qualify_bytes
from rvms.writer import set_settings

MISMATCHED = "guava/guava_2026-07-20_download_bare_deviceform_1.rvms"   # 56.0/54.0 vs 57.6/55.2 on the pair
FIXED = "guava/guava_2026-07-20_prepared_bare_deviceform_1.rvms"
STUB = "guava/guava_2026-08-12_download_stub_deviceform_1.rvms"


def test_inverter_disagreement_fails_even_without_intended_values(good_files):
    ok, res = qualify_bytes(good_files[MISMATCHED], Intent(settings={}))
    assert not ok
    assert any("DISAGREE" in m for _, m in res)


def test_intended_values_pass_on_the_corrected_file(good_files):
    intent = Intent(settings={"absorption_V": 56.8, "float_V": 54.0})
    ok, res = qualify_bytes(good_files[FIXED], intent)
    assert ok, res
    ok, res = qualify_bytes(good_files[MISMATCHED], intent)
    assert not ok


def test_wrong_system_serials_fail(good_files):
    intent = Intent(settings={}, serials=["HQ0000000001", "HQ0000000002"])
    ok, res = qualify_bytes(good_files[FIXED], intent)
    assert not ok and any("wrong system" in m for _, m in res)


def test_stub_signature_fails(good_files):
    ok, res = qualify_bytes(good_files[STUB], Intent(settings={}))
    assert not ok and any("STUB" in m for _, m in res)


def test_the_rollback_that_bit_us(good_files):
    """A file can pass every structural check and still be wrong.  Reproduce the 2026-08-14 case: a
    rollback built from an old baseline carrying the pre-correction charge profile."""
    old = good_files[MISMATCHED]
    from rvms.sections import RvmsFile
    assert RvmsFile.parse(old).all_checksums_ok                # structurally fine
    ok, res = qualify_bytes(old, Intent(settings={"absorption_V": 56.8, "float_V": 54.0}))
    fails = [m for l, m in res if l == "FAIL"]
    assert len(fails) >= 3, fails


def test_agreement_fields_extend_the_default_set(good_files):
    """agreement_fields must ADD to the CONFIRMED set, never replace it (review finding, 2026-09-03)."""
    intent = Intent(settings={}, agreement_fields=["float_V"])
    ok, res = qualify_bytes(good_files[MISMATCHED], intent)
    fails = [m for l, m in res if l == "FAIL"]
    assert any("absorption_V" in m for m in fails), fails
    assert any("float_V" in m for m in fails), fails
    # a HIGH field promoted to must-agree turns its WARN into a FAIL
    intent = Intent(settings={}, agreement_fields=["soc_at_bulk_end_pct"])
    ok, res = qualify_bytes(good_files[FIXED], intent)
    assert any(l == "FAIL" and "soc_at_bulk_end_pct" in m for l, m in res)
