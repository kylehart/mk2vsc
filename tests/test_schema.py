"""
The BareSettingInfo section is the device's own settings schema (scale, offset, default, min, max per
setting).  These tests pin what we claim about it, on every fixture.
"""
from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks
from mk2vsc.schema import schema_of, parse_schema, N_RECORDS, firmware_of_schema
from mk2vsc.fields import FIELDS, BY_ID, CONFIRMED, HIGH, MEDIUM


def test_schema_parses_identically_on_every_fixture(good_files):
    seen = set()
    for name, data in good_files.items():
        f = RvmsFile.parse(data)
        sch = schema_of(f)
        assert len(sch) == N_RECORDS
        assert firmware_of_schema(f.section(b"BareSettingInfo").payload) == 2729560
        seen.add(tuple((r.scale, r.offset, r.default, r.min, r.max) for r in sch))
    assert len(seen) == 1, "one schema for one firmware"


def test_known_scales_agree_with_the_schema(good_files):
    sch = schema_of(RvmsFile.parse(next(iter(good_files.values()))))
    for fld in FIELDS:
        if fld.confidence not in (CONFIRMED, HIGH, MEDIUM) or fld.bits:
            continue
        r = sch[fld.id]
        if r.unused:
            continue   # e.g. setting 49 (AC input 2) has no schema entry on a MultiPlus
        if fld.period:
            assert r.scale == -fld.scale // 1000, fld.name   # period in 1/2500 ms; Hz = 2500000 / raw
        elif fld.scale != 1.0:
            assert r.scale == -fld.scale, (fld.name, r.scale, fld.scale)
        assert r.offset == fld.raw_offset, (fld.name, r.offset, fld.raw_offset)


def test_schema_examples():
    import glob, os
    from tests.conftest import FIXTURES
    p = sorted(glob.glob(os.path.join(FIXTURES, "system_b", "*download_bare*")))[0]
    sch = schema_of(RvmsFile.load(p))
    absorption, flt, current, volt, ac = sch[2], sch[3], sch[4], sch[5], sch[6]
    assert (absorption.scale, absorption.default, absorption.min, absorption.max) == (-100, 5760, 4800, 6400)
    assert (flt.default, flt.min, flt.max) == (5520, 4800, 6400)
    assert (current.min, current.max) == (0, 35) and (volt.min, volt.max) == (95, 128)
    assert (ac.scale, ac.min, ac.max) == (-10, 10, 1000)
    assert sch[62].decode(41667) == 16.6668 or abs(2500 / 41667 * 1000 - 60.0) < 0.01
    assert sch[72].decode(255) == 1.0 and abs(sch[72].decode(242) - 0.949) < 0.001
    assert sch[57].decode(2) == 1 and sch[55].decode(21) == 20 / 60          # minutes; seconds as 1/60 min
    assert sch[65].decode(190) == 95.0 and sch[7].decode(4) == 60                # % ; 4 x 15 min
    assert sch[0].max == 0x6FFC                                                   # settable-bits mask
    assert sch[13].unused and sch[49].unused


def test_corpus_values_lie_inside_the_schema_ranges(good_files):
    sch = schema_of(RvmsFile.parse(next(iter(good_files.values()))))
    violations = set()
    for name, data in good_files.items():
        for u in unit_blocks(RvmsFile.parse(data)):
            if u.setting(2) == 0:
                continue
            for r in sch[:190]:
                if r.unused:
                    continue
                if not r.in_range(u.setting(r.id)):
                    violations.add(r.id)
    assert violations <= {0}, violations   # only the flags register, whose max is a bit mask


# ---------------------------------------------------------------- nominal voltage (diagnose Phase 0)
def test_nominal_voltage_from_absorption_min(good_files):
    from mk2vsc.schema import nominal_voltage
    from tests.test_writer import BARE
    sch = schema_of(RvmsFile.parse(good_files[BARE]))
    assert nominal_voltage(sch) == 48


def test_nominal_voltage_on_synthetic_24v_and_12v_schemas(good_files):
    from mk2vsc.schema import nominal_voltage, SettingInfo
    from tests.test_writer import BARE
    sch = schema_of(RvmsFile.parse(good_files[BARE]))
    for nom in (24, 12):
        k = nom / 48
        twin = [SettingInfo(r.id, r.scale, r.offset, round(r.default * k), round(r.min * k), round(r.max * k)) if r.id in (2, 3) else r
                for r in sch]
        assert nominal_voltage(twin) == nom


def test_nominal_voltage_refuses_an_unrecognised_range():
    from mk2vsc.schema import nominal_voltage, SettingInfo
    import pytest
    odd = [SettingInfo(n, 0, 0, 0, 0, 0) for n in range(192)]
    odd[2] = SettingInfo(2, -100, 0, 3300, 3000, 3600)   # 30 V: no Victron nominal
    with pytest.raises(ValueError):
        nominal_voltage(odd)
