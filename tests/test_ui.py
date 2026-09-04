"""The VEConfigure placement layer (mk2vsc.ui) is consistent with the field table."""
import collections

from mk2vsc.fields import FIELDS, EPROM_NAMES, BY_ID, FLAGS0_BITS, FLAGS1_BITS, FLAGS2_BITS
from mk2vsc.ui import UI_BY_EPROM, UI_BITS, EBIT_NAMES, DERIVED, UNPLACED, ENUMS, TABS, by_tab


def test_every_placed_setting_is_a_known_identifier():
    for eprom, ui in UI_BY_EPROM.items():
        assert eprom in EPROM_NAMES, eprom
        assert ui.tab in dict(TABS) and ui.kind in ("number", "enum") and ui.certainty in ("confirmed", "probable")


def test_every_placed_bit_is_a_flag_register_bit():
    for (sid, bit), ui in UI_BITS.items():
        assert sid in (0, 1, 60, 82) and 0 <= bit <= 15, (sid, bit)
        assert BY_ID[sid].bits is not None or sid == 82, sid
        assert ui.kind == "bool"


def test_flag_names_agree_with_the_identifier_table():
    for (sid, bit), name in EBIT_NAMES.items():
        if sid == 60:
            assert FLAGS2_BITS[bit] == name, (bit, name)


def test_placement_counts():
    """57 numeric/enum settings and 32 bits placed, 7 derived, 6 unplaced (= the 102 GUI fields of VEConfigure 1.33);
    every field with a placement is at least LOW."""
    assert len(UI_BY_EPROM) == 57 and len(UI_BITS) == 32 and len(DERIVED) == 7 and len(UNPLACED) == 6
    for eprom in UI_BY_EPROM:
        f = next(x for x in FIELDS if x.eprom == eprom)
        assert f.confidence != "UNKNOWN", f.name


def test_units_agree_where_both_sides_state_one():
    """A placement unit of V, A, Ah or % must match the field's unit; W/A and Hr/min differences are documented."""
    for eprom, ui in UI_BY_EPROM.items():
        f = next(x for x in FIELDS if x.eprom == eprom)
        if ui.unit in ("V", "A", "Ah", "%") and f.unit:
            assert f.unit == ui.unit, (f.name, f.unit, ui.unit)


def test_enum_text_matches_field_descriptions():
    assert ENUMS["EPROM_ChargeCharacteristic"][1] == "Fixed"
    assert "Fixed" in BY_ID[10].description and "dedicated ignore AC input" in BY_ID[15].description


def test_by_tab_covers_every_placement_once():
    n = sum(len(items) for groups in by_tab().values() for items in groups.values())
    assert n == len(UI_BY_EPROM) + len(UI_BITS)


def test_field_ui_property():
    assert BY_ID[2].ui.path == "Charger › Charge curve › Absorption voltage"
    assert BY_ID[129].ui is None
