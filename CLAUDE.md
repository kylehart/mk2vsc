# Working rules for this repository

These rules apply to every session (human or AI-assisted) that changes this repository. They exist so
that the public record of the project is complete, honest, and useful to strangers. The public version
of these rules is docs/PRACTICES.md; this file is the operational checklist.

## 1. Everything goes through the public record

- Every change lands on `main` through a pull request, even from the maintainer. The PR description
  says what changed, why, what evidence supports it, and which issue it closes.
- Every open question, unknown byte, hypothesis, incident, and idea is a GitHub issue with a label.
  If we discuss something worth remembering, it becomes an issue or a doc change the same day.
- Decisions are recorded where they were made: an issue comment, a PR description, or a doc. Nothing
  that matters lives only in a chat transcript.
- AI assistance is disclosed. Commits produced with Claude carry `Co-Authored-By: Claude ...`; the
  README and CONTRIBUTING say the project is AI-assisted and that all claims are verified against the
  fixture corpus by tests, not by the model.

## 2. Claims need evidence, and the evidence is in the repo

- A statement about the file format is Observed, Inferred, or Unknown, and says which.
- Every Observed claim has a test in `tests/` that checks it against the fixtures. A claim without a
  test is Inferred at best.
- Every field in `mk2vsc/fields.py` carries confidence, evidence, and observed values. Promoting a
  field requires a new fixture pair or a screenshot, referenced in the commit.
- Counts in docs (files, blocks, tests) are regenerated, not hand-edited. If a number is typed by hand,
  it is wrong within a week.
- Reference docs describe the current state only. No "earlier tooling", "previously", "retracted",
  "used to", old names kept "so they raise an error". Narrative with dates and mistakes belongs in
  docs/HISTORY.md and docs/ESS_INJECTION.md, where the learning is the deliverable, and in CHANGELOG.md
  as terse entries. No backward-compatibility shims: remove, do not deprecate.

## 3. Safety of readers comes before completeness

- The writer edits only length-preserving settings on device-form downloads and self-verifies the
  diff. Anything else is experimental, gated behind an explicit flag, and documented as such.
- Never publish a command that uploads to a device. Uploads are a human action through VRM.
- Every incident on our own systems caused by this tooling is written up (docs/HISTORY.md,
  docs/ESS_INJECTION.md) with what was wrong, what it cost, and what changed as a result.
- Corrections are stated as corrections: "we previously said X; that was wrong because Y; now Z."

## 4. What never ships

- VRM portal IDs, VRM site IDs, tokens, passwords, the grid-code password, email addresses, names of
  companies or people other than the maintainer. Run `tools/leakscan.sh` before every push.
- Files from systems we are not entitled to publish. Contributor files need the contributor's explicit
  statement that they may be published (the issue template asks).
- Dependencies. The package stays zero-dependency; test tooling is the only dev dependency.

## 5. Releases

- Semantic versioning. `0.x` while the field table is mostly unnamed.
- A release is: CHANGELOG entry, version bump in `pyproject.toml` and `mk2vsc/__init__.py`, green CI on
  three OSes, a git tag `vX.Y.Z`, a GitHub Release with notes, and (once set up) a PyPI publish from
  the release workflow using trusted publishing.

## 6. Issue labels

`format-unknown` (a byte region we cannot explain) - `field-claim` (naming or promoting a setting) -
`hypothesis` (a testable idea about device behaviour) - `incident` (something that went wrong on
hardware) - `fixture-wanted` (a file we do not hold: other firmware, Quattro, three-phase, .rvsc) -
`experimental` (ESS injection and other unproven work) - `good first issue` - `help wanted` -
`documentation` - `bug` - `enhancement`.

## 7. Session checklist

Before ending a session that changed anything: tests green, `tools/leakscan.sh` clean, CHANGELOG
touched if user-visible, PR opened or merged, issues updated, memory/notes reflect the repo state.
