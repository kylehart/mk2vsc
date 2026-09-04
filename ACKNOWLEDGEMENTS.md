# Acknowledgements

mk2vsc stands on work other people published first. This page says exactly what came from where, so
that credit lands in the right place and so that a reader can go to the source. Licence text for
imported material is in NOTICE.md.

## talas9/rvsc-tools
https://github.com/talas9/rvsc-tools (MIT, Mohammed Talas, July 2026)

- The VEConfigure identifier for every setting index (`EPROM_*`), extracted from the VEConfig.exe symbol
  table: `mk2vsc.fields.EPROM_NAMES`, the "VEConfigure identifier" column in docs/FIELDS.md. It renamed
  several of our settings correctly (73 is a current limit, 70 is the ignore-AC SoC threshold).
- The VEConfigure tab / group / field placement of every setting and flag bit the GUI shows, and the
  option text of the enum settings: `mk2vsc/ui.py`, `mk2vsc fields --by-tab`, the "In VEConfigure"
  column in docs/FIELDS.md.
- The idea of scoring the settings-array offset against the file's own schema ranges (their alignment
  search): `mk2vsc/align.py`, the alignment line in `show`, `census` and `check`.
- The "at the floor or ceiling of its range" warning on charger setpoints: `mk2vsc/limits.py`.
- The case-study format: a blind prediction from the file, confirmed by the vendor tool; the way
  docs/HISTORY.md reports the 2026-09-04 cycle follows it.

## xcellsior/ve-bus-programming
https://github.com/xcellsior/ve-bus-programming

- The public account of VE.Bus setting IDs and the MK2/MK3 wire protocol that let us read our settings
  array as VE.Bus setting IDs in the first place (docs/FIELDS.md, "How the mapping was found").
- The Setting 0 and Setting 1 flag-bit maps confirmed by toggle-and-diff; the UPS-function and
  Dynamic-current-limiter placements in `mk2vsc/ui.py` cite them.
- The bench table for settings 128, 190 and 191 that identified the bytes we had read as an
  assistant-record "marker" and "subtype" as grid-code words (mk2vsc 0.8.0).
- The sweep-and-diff method (change one thing in VEConfigure, diff) that is our standard for naming a
  flag bit.

## tomjnixon/mk2.py
https://github.com/tomjnixon/mk2.py

- Independent naming of setting 70 as the Virtual Switch SoC limit, corroborating our correction. No
  code was imported (their licence is GPL-3; nothing here derives from it).

## Victron Energy
- "Interfacing with VE.Bus products, MK2 Protocol 3.14": the names of settings 0 to 65 and of the flag
  bits, and the definition of `CommandGetSettingInfo` that our `BareSettingInfo` schema matches.
- The ESS design and installation manual, the parallel and three-phase manual, the DVCC chapter and the
  Virtual Switch lesson, cited throughout docs/. Trademarks and non-affiliation: NOTICE.md.

## Neighbouring projects we learned from
No code or data from these is in mk2vsc; they shaped how we think about writes, verification and
rollout, and readers of this project may want them: lubosstrejcek/victron-vrm-mcp (confirm-gated
writes, offline and live test tracks), martinthebrain/venus-ess-winter-soc-service (shadow mode,
decisions that list their inhibit causes), Zepheus/multiplus_ess_controller (per-event verification,
staged rollout with a watchdog), byPARSE/victron-tools-under-linux (VEConfigure under Wine).

If you recognise your work here and the credit is wrong or missing, open an issue and it will be fixed.
