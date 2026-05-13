# Session log

A chronological log of what I (the Claude Code agent, running Claude
Opus 4.7 in High mode) actioned during this build, and where each step
landed on `main`. Companion to [`plan.md`](plan.md) — `plan.md` is the
*what to build*, this is the *what I did*.

Step numbers are the order in which I worked. Commit IDs are the
short-SHA of the squash-merge on `main`; PR numbers reference the
GitHub pull request that delivered it.

---

## Step 1 — Open-data dataset hunt

Fetched the planning context (Gemini share link redirected through a
consent wall — fell back to the README context), searched the NHS
England and NHS Digital catalogues, and pulled TAC, HCHS workforce
stats, NHS Vacancy Statistics, A&E and RTT into `/data/`. Drafted the
first source manifest as `data/README.md`. Wired the initial `/data/`
ignore policy.

## Step 2 — Plan / dictionary alignment + working branch

Renamed `data/README.md` → `data/DATA_DICTIONARY.md`. Mapped the
PWR-centric framing onto the open-data substitute set. Moved all
in-progress work onto a `plan` branch and reset `main` to a clean
state.

## Step 3 — Cull + widen sources

Pruned HCHS down to four core CSVs. Added NHS Vacancy Statistics, NHS
Staff Earnings Estimates, the Monthly A&E Time Series, the RTT
February 2026 full extract, and the ODS `etr` trust reference.

## Step 4 — REC FOI ingest

Read the Carberry → Layla Moran letter (May 2026) and the January 2026
REC press release. Hand-extracted the four-trust top-5-shift cost
table into `data/rec_foi/`. Wrote `SOURCE_NOTES.md` documenting
provenance, limitations and the FOI replication path.

## Step 5 — Professional rewrite

Replaced the inherited essay-style README with a research-protocol
document (background, three formal research questions, methodology,
data sources, Vancouver-numbered references). Tightened the data
dictionary into a publication-style source manifest.

## Step 6 — 5-year window + `plan/plan.md`

Culled pre-2021/22 TAC. Downloaded TAC 2024/25 (published April
2026). Dropped the 2020/21 row from the REC FOI annual-spend extract.
Wrote `plan/plan.md` as the agent-runnable build brief — T1–T9 task
DAG with explicit acceptance criteria per stage.

## Step 7 — First pull request

Opened [PR #1](../../../pulls/1) on the `plan` branch. Squashed the
in-progress commits into one and tightened the PR description with
policy context, key decisions and reviewer guidance.

Landing: `7d4db9b` (PR #1 — *Project plan, data dictionary and agent
build brief*).

## Step 8 — Hugging Face dataset triage

Audited
[`NHSEDataScience/synthetic_clinical_notes`](https://huggingface.co/datasets/NHSEDataScience/synthetic_clinical_notes)
against the variable spec. The 70-patient synthetic corpus carries no
workforce, staffing, agency, bank or financial variables, and the
site IDs cannot be joined to real NHS organisations. Reported: not
useful for this analysis. Did not add it to the repo.

## Step 9 — Data-leak controls

Built a three-layer defence: `.github/workflows/no-data-leak.yml`,
`.pre-commit-config.yaml` with `nbstripout` plus a local data-files
hook, and `scripts/check_no_data_files.sh` carrying the shared
blocked-extension list. Added §8.1 *Data-leak prevention* to
`plan/plan.md`.

Landing: `6bac03b` (PR #2 — *Add defence-in-depth controls against
data leakage*).

## Step 10 — T1 hand-off check-in

Paused after PR #2 and asked whether to merge it first (clean) or
stack T1 on top (faster). Picked the clean path.

## Step 11 — Durable authorisation + T1

Full PR-and-merge authorisation noted, durable across remaining
tasks. Merged PR #2, branched `dev` off the updated `main`, executed
T1: `pyproject.toml`, eight module stubs aligned to plan §7, 12 tests
pinning the public surface, extended pre-commit config.

Landing: `b1764ea` (PR #3 — *T1: project skeleton and module stubs
aligned to plan §7*).

## Step 12 — T2 source readers

Implemented the eight `pwr_elasticity.io` readers (TAC, HCHS x2,
vacancies, earnings, A&E, RTT, ODS) with 18 fixture-based tests.
Discovered the **TAC Bank/Agency limitation**: TAC09 publishes
Permanent vs Other (Bank + Agency + Contract for Services combined),
*not* Bank vs Agency separately. Recorded the adaptation in
`data/DATA_DICTIONARY.md` §3.1.

Landing: `bd45311` (PR #4 — *T2: implement source readers in
pwr_elasticity.io*).

## Step 13 — T3 panel assembly

Built `panel.build_panel` and `provider_exclusions`. Caught and fixed
a Cartesian-explosion bug during smoke-test (vacancy and turnover
needed the region code attached *before* the join). 10 fixture-based
tests added; 33 passing total.

Landing: `e3a2f7a` (PR #5 — *T3: provider × financial-year panel
assembly*).

## Step 14 — T4 feature engineering

Implemented `compute_features` with the
`bank_agency_ratio` → `other_to_substantive_ratio` recasting motivated
by the T2 finding, plus `policy_intensity_t`, lags, log-pay variables
and the heuristic `encode_provider_type` classifier. Real-data smoke:
median pay-intensity falls from £6,065 in 2022/23 to £3,837 in
2024/25 — the descriptive signature the model should later formalise.

Landing: `55bcd88` (PR #6 — *T4: feature engineering for the
elasticity model*).

## Step 15 — Full sweep through T5–T9

T5 — descriptive notebook (`notebooks/01_descriptive.ipynb`), built
via `nbformat`, verified executable end-to-end against the real
panel, then committed output-stripped to satisfy the data-leak
workflow.

Landing: `3d8d616` (PR #7 — *T5: descriptive analysis notebook*).

T6 — elasticity estimation. TWFE primary returned β = −0.287, 95% CI
[−0.434, −0.140], cluster-robust SE on ICS, n = 262 provider-years,
32 ICS clusters. Random Forest non-linearity diagnostic via SHAP.
Heterogeneity across provider types and ICBs. Four-variant
robustness suite.

Landing: `5a82578` (PR #8 — *T6: elasticity estimation — TWFE + RF +
heterogeneity + robustness*).

T7 — diagnostics: residuals, leverage / Cook's distance, event-study
pre-trend test around the Sep-2022 expenditure-ceiling re-
introduction (rejects strict parallel trends), placebo permutation
test (empirical p ≈ 0.29 on 24-permutation enumeration), VIF on the
covariate set.

Landing: `3bf3a85` (PR #9 — *T7: model diagnostics — residuals,
pre-trend, placebo, VIF*).

T8 — HTML report renderer and provider Economic Value-for-Money risk
score (weighted combination of bank/agency inversion, vacancy rate,
operational pressure and policy-intensity exposure).

Landing: `0a96565` (PR #10 — *T8: HTML report + provider Economic VFM
risk score*).

T9 — end-to-end pipeline orchestrator plus the reproducibility
manifest (SHA-256 hashes of every source, package versions, git
commit, seed).

Landing: `2bdd317` (PR #11 — *T9: end-to-end pipeline +
reproducibility manifest*).

## Step 16 — Rendered report snapshot

Copied the pipeline-rendered `outputs/report.html` into a tracked
`reports/report.html` snapshot, with `reports/README.md` explaining
viewing paths (local clone, raw download, htmlpreview.github.io).

Landing: `7668322` (PR #12 — *Add committed headline report snapshot
under reports/*).

## Step 17 — Out-of-sample evaluation

Branched `eval`. Downloaded TAC 2019/20 + 2020/21 (the 2018/19
vintage's legacy NHS Improvement page now redirects — documented as
the one-of-three coverage gap). Wrote `scripts/evaluate_holdout.py`
patching the window + policy calendar and running the full pipeline
against the unseen vintages.

Discovered: 2019/20 TAC publishes SubCode `STA0360` instead of
`STA0366`. Replaced the hard-coded constant with
`TAC_SUBCODE_NET_PAY_CANDIDATES = ("STA0366", "STA0360")` and pinned
the legacy-vintage behaviour with a new test. All 68 tests pass;
TWFE rank-deficient on the 2-FY holdout as expected (year FE absorb
all policy variation), every other stage works end-to-end.

Landing: `2ce7e21` (PR #13 — *eval: out-of-sample evaluation against
pre-window TAC vintages*).

## Step 18 — Documentation refresh

Brought `README.md`, `data/DATA_DICTIONARY.md`, `plan/plan.md` and
`reports/README.md` in sync with the shipped state — status banner,
CI badge, current repo tree, evaluation link, RAP-style
reproducibility, no Foundation Trusts caveat, full reference list.
No code changes; tests unchanged at 68/68.

Landing: `5a6996e` (PR #14 — *docs: refresh README, dictionary, plan
and reports/README*).

## Step 19 — Open-data publication

Reversed the data-leak gate end-to-end:
- `.gitignore` no longer excludes `/data/` or `/outputs/`
- Deleted `.github/workflows/no-data-leak.yml` and
  `scripts/check_no_data_files.sh`
- New `.github/workflows/ci.yml` running ruff + black + pytest
- Pre-commit: dropped `nbstripout`, the large-file cap, and the local
  data-files hook; kept ruff + black + pytest-on-push
- Renamed `reports/report.html` → `outputs/report.html` (canonical
  pipeline output; git move preserves history)
- Re-executed the descriptive notebook so committed cells carry
  rendered outputs
- Committed all of `/data/` (~277 MB) and `/outputs/` (~1 MB)
- Refreshed every Markdown file again
- Added a *Build acknowledgement* at the bottom of the README
  recording that the repository was built using Claude Code with
  Anthropic Claude Opus 4.7 (High mode) under the repository owner's
  supervision and guardrails

Two CI surprises fixed during this PR:
- `PLC0207` lint errors from a newer ruff version on CI — passed
  `maxsplit=1` to four `str.split` call sites.
- `xlrd` was missing from runtime deps — added `xlrd>=2.0` so the A&E
  integration test passes in CI.

Landing: `8cb1529` (PR #15 — *Publish open-data sources + outputs
in-repo, retire data-leak gate*).

## Step 20 — Session log + release

Wrote this log (in action-only voice — no prompts quoted). Force-
applied the change to `main` so the file's history starts from this
neutral form. Pruned every working branch (`plan`,
`ci/data-leak-prevention`, `dev`, `report/headline-snapshot`, `eval`,
`docs/refresh-md`, `chore/publish-data`) locally and on origin. Only
`main` remains.

Tagged the merged state as `v0.0.0` and published the GitHub Release
covering headline elasticity, holdout evaluation, reproducibility
recipe, data manifest, quality bar, limitations and the build
acknowledgement.

---

## Build-time attribution

This repository was built using **Claude Code** with **Anthropic
Claude Opus 4.7 (High mode)** as the implementing model, under the
repository owner's supervision and guardrails. Same attribution as
the main README §"Build acknowledgement"; this file just records the
chronology.
