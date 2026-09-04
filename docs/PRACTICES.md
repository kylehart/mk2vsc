# How this project is run

This page says how the repository is maintained, so you can judge whether to trust it and know how to
take part. The maintainer's operational checklist is the `CLAUDE.md` file in the repository root; this
is the readable version.

## The public record is the project

Everything that matters is on GitHub, in the open:

- **Pull requests** for every change to `main`, including the maintainer's own. The PR says what
  changed, why, what evidence supports it, and which issue it closes.
- **Issues** for every open question. Each unknown byte region, each unnamed setting, each hypothesis
  about device behaviour, each incident on our own hardware, and each file we wish we had is an issue
  with a label. The issue list is the honest map of what is and is not known.
- **Discussions** for questions and for reports from other systems that are not yet a bug or a claim.
- **Releases** with notes, tags, and a changelog.

## Evidence rules

- Statements about the file format are labelled Observed (checked by a test on every fixture),
  Inferred (the narrowest reading of the observations), or Unknown.
- Every named setting in `mk2vsc/fields.py` carries a confidence level, the evidence for it, and the
  values observed in the corpus. Promotion requires new evidence that is committed with the change.
- Every documented claim that can be checked is checked by `tests/test_claims.py` on every fixture. If
  your file makes one of those tests fail, that is a finding, not a nuisance; please open an issue.
- Numbers in the docs (file, block and test counts) are generated from the repository, not typed.

## Safety rules

- The library produces files. It never uploads. The decision to upload, and its consequences on a live
  battery system, are the operator's.
- The guarded writer only makes length-preserving changes to settings with CONFIRMED or HIGH confidence
  on device-form downloads, and proves that nothing else in the file moved. Everything beyond that is in
  `mk2vsc/experimental/`, behind an explicit flag, with its full history in docs/ESS_INJECTION.md.
- Incidents caused by this tooling on our own systems are written up with what went wrong, what it
  cost, and what changed as a result (docs/HISTORY.md). Corrections are stated as corrections.

## Privacy and what never ships

The fixture corpus consists of real device files and therefore carries inverter serial numbers and save
timestamps. It carries nothing else that identifies anyone: no VRM identifiers, no credentials, no
names. `tools/leakscan.sh` runs before every push. Contributor files are published only with the
contributor's explicit permission, which the fixture issue template asks for.

## AI assistance, disclosed

This project is developed with AI assistance (Claude, by Anthropic). Commits produced that way carry a
`Co-Authored-By` trailer. The model wrote much of the code and prose; it did not decide what is true.
Every format claim is checked by tests against real files, every live result was observed on real
hardware by the maintainer, and every doc was reviewed before merge. If you find a statement that is
not backed by a fixture, a test, or a described observation, open an issue: that is a defect.

## Releases

Semantic versioning; `0.x` while most of the settings array is unnamed. A release means a CHANGELOG
entry, a version bump, green CI on Linux, macOS and Windows, a tag, GitHub Release notes, and a PyPI
publish through the release workflow.

## How to take part

See CONTRIBUTING.md. The most valuable contributions are files and controlled pairs from systems we do
not have, and independent verification of our claims on your own hardware.
