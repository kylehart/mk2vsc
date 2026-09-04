from mk2vsc.sections import RvmsFile
from mk2vsc.units import unit_blocks
from mk2vsc.schema import schema_of
from mk2vsc.align import check, score, find_offset


def test_every_good_block_aligns_at_the_expected_offset(good_files):
    for name, data in good_files.items():
        f = RvmsFile.parse(data)
        sch = schema_of(f)
        for u in unit_blocks(f):
            if u.setting(2) == 0:
                continue   # stub-installed blocks carry zeroed settings
            al = check(u, sch)
            assert al.ok, (name, u.serial, al.summary)
            assert al.total >= 130


def test_a_shifted_offset_scores_much_lower(good_files):
    name, data = next(iter(good_files.items()))
    f = RvmsFile.parse(data)
    sch = schema_of(f)
    u = unit_blocks(f)[0]
    good, tot = score(u.raw, u.settings_offset, sch)
    for shift in (-10, -2, -1, 1, 2, 10):
        bad, _ = score(u.raw, u.settings_offset + shift, sch)
        assert bad < good - 25, (shift, bad, good)
    assert find_offset(u.raw, sch)[0] == u.settings_offset
