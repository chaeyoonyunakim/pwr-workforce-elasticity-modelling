# Build plan — PWR workforce elasticity model

**Purpose:** brief for a coding agent (or analyst) to build the elasticity
model end-to-end, starting from the open-data substitute set documented in
[`../data/DATA_DICTIONARY.md`](../data/DATA_DICTIONARY.md) and the research
protocol in [`../README.md`](../README.md). This document is the single
source of truth for what to build, in what order, and to what quality bar.

## Status — shipped

All task IDs T1–T9 from §7 have been delivered and merged into `main`.

| Task | Status | Landing commit |
|---|---|---|
| T1 Project skeleton + pre-commit | ✅ | `b1764ea` |
| T2 Source readers (`io.py`) | ✅ | `bd45311` |
| T3 Panel assembly (`panel.py`) | ✅ | `e3a2f7a` |
| T4 Feature engineering (`features.py`) | ✅ | `55bcd88` |
| T5 Descriptive notebook | ✅ | `3d8d616` |
| T6 Models — TWFE / RF / heterogeneity / robustness | ✅ |  |
| T7 Diagnostics — pre-trend / placebo / VIF | ✅ |  |
| T8 Report + provider risk scores | ✅ | `0a96565` |
| T9 Pipeline + manifest | ✅ | `2bdd317` |
| Headline report snapshot | ✅ | `7668322` (PR #12) |
| Out-of-sample evaluation (eval branch) | ✅ | `2ce7e21` (PR #13) |

**Adaptation captured during T2.** TAC09 publishes staff cost as
Permanent vs Other (Bank + Agency + Contract for Services combined),
not Bank vs Agency separately. The plan §T4 features
`bank_agency_ratio` / `bank_share_of_pay` are therefore implemented as
`other_to_substantive_ratio` / `other_share_of_pay`. The economic
interpretation — elasticity of non-substantive workforce expenditure
with respect to agency-restriction policy — is preserved. The Bank-vs-
Agency split is available only through PWR (Foundry) or the REC FOI
case-study extracts. See `../data/DATA_DICTIONARY.md` §3.1.

**Adaptation captured during eval.** The 2019/20 TAC vintage uses
SubCode `STA0360` instead of `STA0366`; the reader now iterates a
candidate list (`STA0366` first, `STA0360` fallback). The fix is pinned
by `tests/test_io.py::test_read_tac_handles_legacy_vintage_subcode_and_columns`.

The plan below is preserved as the original specification. Where the
delivered implementation differs from the spec, the difference is
recorded in the relevant module docstring and in the data dictionary.

---

## 1. Objective

Quantify the elasticity of NHS provider Bank pay expenditure with respect to
the intensity of agency-restriction policy across financial years 2021/22
to 2025/26, identify any non-linearity (the tipping point at which the
Bank-to-agency cost ratio inverts), and surface the result for operational
decision support at provider and Integrated Care Board (ICB) level.

## 2. Scope

**In scope**
- Provider-level panel covering English NHS trusts and Foundation Trusts
- Audited annual Bank and agency pay expenditure from TAC
- Substantive workforce capacity (Staff in Post FTE) from HCHS
- Vacancy rate from NHS Vacancy Statistics
- Agency price-cap intensity and discrete policy events
- Operational pressure controls (A&E 4-hour standard; RTT 52+ week waits)
- Descriptive analysis, panel-data regression, non-linearity diagnostics
- One static dashboard or HTML report summarising the headline findings

**Out of scope (for this iteration)**
- Monthly cadence for the Bank / agency split (requires PWR / Foundry)
- `Override_Intensity` and Time-to-Hire features (PWR-only)
- Clinical safety incident analysis (NRLS / LFPSE)
- Causal claims that extend beyond the policy events occurring in-window
- Production engineering, scheduling, alerting

## 3. Analytical window

| Element | Window |
|---|---|
| Bank / agency expenditure (TAC) | 2021/22 to 2024/25 (4 audited financial years) |
| Workforce stock (HCHS) | Monthly observations covering the four TAC years; latest vintage Oct 2025 |
| Vacancy series | Restricted to observations from 2021/22 onwards |
| Earnings series | Restricted to observations from 2021/22 onwards |
| Policy treatment indicators | All in-window events listed in `DATA_DICTIONARY.md` §3.6 |
| Operational outcomes (A&E, RTT) | Restricted to observations from 2021/22 onwards |

The 2025/26 financial year is observed in real time through the operational
sources only; audited TAC for 2025/26 will not be available until spring
2027 and is therefore treated as a placeholder cohort.

## 4. Inputs

All inputs are documented authoritatively in
[`../data/DATA_DICTIONARY.md`](../data/DATA_DICTIONARY.md). The agent must
not duplicate that catalogue; it should reference it and read directly from
the files staged under `../data/`.

| Symbol | Source | Folder |
|---|---|---|
| `tac_y` | Trust Accounts Consolidation | `data/tac_provider_accounts/` |
| `hchs_m` | NHS Workforce Statistics, HCHS | `data/workforce_stats/hchs_oct_2025/` |
| `turnover_a` | NHS Workforce Statistics, Turnover | `data/workforce_stats/turnover_oct_2025/` |
| `vac_q` | NHS Vacancy Statistics | `data/vacancy_stats/` |
| `earn_m` | NHS Staff Earnings Estimates | `data/staff_earnings/` |
| `policy` | Agency rules, price card | `data/policy_timeline/` |
| `ae_m` | A&E Monthly Time Series | `data/ae_performance/` |
| `rtt_m` | Referral to Treatment | `data/rtt_performance/feb26/` |
| `rec_foi` | REC FOI extracts | `data/rec_foi/` (local only) |
| `ods` | Organisation reference (`etr`) | `data/reference/` |

## 5. Deliverables

| ID | Artefact | Format |
|---|---|---|
| D1 | Provider × financial-year analytical panel | Parquet under `outputs/panel/` |
| D2 | Feature-engineered analysis frame | Parquet under `outputs/features/` |
| D3 | Descriptive analysis notebook | `notebooks/01_descriptive.ipynb` |
| D4 | Model fitting notebook | `notebooks/02_model.ipynb` |
| D5 | Trained model object and prediction set | `outputs/models/`; pickled with metadata |
| D6 | Headline dashboard / report | `outputs/report.html` |
| D7 | Reproducibility manifest | `outputs/manifest.json` |

All deliverables sit under a new top-level `outputs/` directory which the
build pipeline will create. `outputs/` will be added to `.gitignore`.

## 6. Repository layout to create

```
.
├── .github/
│   └── workflows/
│       └── no-data-leak.yml       CI gate — blocks data and notebook outputs from main
├── .pre-commit-config.yaml        local enforcement of the same rules
├── scripts/
│   └── check_no_data_files.sh     shared rule set (also referenced by CI)
├── plan/
│   └── plan.md                    this document
├── src/
│   ├── pwr_elasticity/
│   │   ├── __init__.py
│   │   ├── io.py                  source readers (one function per data product)
│   │   ├── panel.py               panel assembly
│   │   ├── features.py            feature engineering
│   │   ├── models.py              estimators
│   │   ├── diagnostics.py         residuals, sensitivity, robustness
│   │   └── report.py              dashboard / HTML rendering
│   └── pipeline.py                end-to-end orchestration
├── notebooks/
│   ├── 01_descriptive.ipynb
│   └── 02_model.ipynb
├── tests/
│   ├── test_io.py
│   ├── test_panel.py
│   └── test_features.py
├── pyproject.toml                 dependencies, project metadata, ruff/black config
└── outputs/                       gitignored
```

## 7. Tasks

Tasks are ordered as a directed acyclic graph; tasks marked `(parallel)`
can be executed concurrently with the preceding task once their inputs are
satisfied.

### T1 — Environment and project skeleton
- Initialise `pyproject.toml` pinning Python ≥ 3.11. Dependencies: `pandas`,
  `pyarrow`, `numpy`, `openpyxl`, `pyjanitor`, `statsmodels`, `linearmodels`,
  `scikit-learn`, `matplotlib`, `seaborn`, `plotly`, `jupyterlab`,
  `pytest`, `pytest-cov`, `ruff`, `black`, `pre-commit`, `nbstripout`.
- Create the directory tree in §6.
- Extend the existing `.pre-commit-config.yaml` (which already enforces the
  data-leak controls in §8.1) to additionally run `ruff`, `black` and
  `pytest -q --no-header --quiet`. Run `pre-commit install` so commits
  are gated locally; CI runs the same checks via
  `.github/workflows/no-data-leak.yml`.
- Install the project-managed `nbstripout` git filter
  (`nbstripout --install`) so notebook outputs are scrubbed at staging
  time as well as at commit time.
- Append `/outputs/` to `.gitignore`.

**Acceptance:** `pip install -e .` succeeds; `pre-commit run --all-files`
is clean; `pytest` runs (zero tests OK at this stage); `ruff check .` is
clean; the `no-data-leak` CI workflow passes on the seed commit.

### T2 — Source readers (`src/pwr_elasticity/io.py`)
One pure function per data product, each returning a tidy `pandas.DataFrame`
with column names in snake_case and a documented schema:
- `read_tac(directory) -> DataFrame` — concatenate all four TAC vintages,
  emitting `[org_code, financial_year, bank_pay_gbp, agency_pay_gbp,
  substantive_pay_gbp, total_operating_expense_gbp]`.
- `read_hchs_staff_in_post(path) -> DataFrame` — long-format
  `[org_code, period_month, staff_group, fte, headcount]`.
- `read_hchs_turnover(path) -> DataFrame`
- `read_vacancies(path) -> DataFrame` — long-format
  `[period_quarter, staff_group, vacancy_rate]`.
- `read_earnings(path) -> DataFrame` — long-format
  `[org_code, period_month, afc_band, mean_basic_pay_gbp]`.
- `read_ae(path) -> DataFrame` — `[org_code, period_month,
  attendances_type1, met_4hr_type1, pct_met_4hr]`.
- `read_rtt(path) -> DataFrame` — incomplete pathways aggregated to
  `[org_code, treatment_function, n_waiting, n_waiting_52plus_weeks]`.
- `read_ods_trusts(path) -> DataFrame` — `[org_code, org_name, region_code,
  open_date, close_date]`.

Restrict every reader's output to observations dated 2021/22 onwards.

**Acceptance:** unit tests in `tests/test_io.py` verify the schema and row
counts for each reader against fixed expectations recorded in the test.

### T3 — Panel assembly (`src/pwr_elasticity/panel.py`) — (parallel to T2 once readers stabilise)
- Build a provider × financial-year panel: one row per `(org_code,
  financial_year)` from 2021/22 to 2024/25.
- Aggregate monthly HCHS to financial-year means (Apr–Mar) of FTE by staff
  group; join to TAC on `org_code` × `financial_year`.
- Attach vacancy rate by mapping each financial year to the four quarters
  in that year and taking the within-year mean.
- Attach annual turnover at the staff-group × region level (broadcast).
- Aggregate monthly A&E to financial-year means of `pct_met_4hr` and total
  attendances.
- Aggregate RTT to a financial-year snapshot using the latest in-year month
  (RTT is a stock variable).
- Attach the ICB / ICS code by joining HCHS `Core 1` ICS code to provider
  code.
- Handle 2022 ICS reorganisation: drop or relabel observations where the
  ICS code is missing or changed within the financial year.
- Handle provider mergers using the `etr` open/close dates; document
  exclusions in a side dataframe.

**Acceptance:** panel has the expected provider count (≈213) for each
financial year ± mergers; no duplicate `(org_code, financial_year)` keys;
all columns documented in a YAML schema file under
`src/pwr_elasticity/schema/panel.yaml`.

### T4 — Feature engineering (`src/pwr_elasticity/features.py`)
- `bank_agency_ratio = bank_pay_gbp / agency_pay_gbp` (handle agency == 0
  with a small-additive constant or a clipped lower bound; document the
  choice).
- `bank_share_of_pay = bank_pay_gbp / (bank_pay_gbp + agency_pay_gbp + substantive_pay_gbp)`.
- `agency_share_of_pay` (analogous).
- `pay_intensity = (bank_pay_gbp + agency_pay_gbp) / staff_in_post_fte`.
- `policy_intensity_t`: ordinal index 0..N encoding the cumulative count of
  in-window agency-rule events in force as of the financial-year midpoint.
- `policy_shock_t`: binary indicator for the year in which a new event came
  into force.
- `lagged_bank_pay`, `lagged_agency_pay`, `lagged_vacancy_rate`.
- `log_bank_pay`, `log_agency_pay` for elasticity (constant-elasticity)
  specifications.
- `provider_type`: one of {acute, mental_health, community, specialist,
  ambulance}, derived from `etr` or a manual lookup.

**Acceptance:** every feature has a unit test pinning its definition; null
rates per feature are below a documented threshold (e.g. 5%) and exclusions
are recorded.

### T5 — Descriptive analysis (`notebooks/01_descriptive.ipynb`)
- Distribution of `bank_agency_ratio` by year, by provider type.
- Bank vs agency expenditure trajectory at the four REC case-study trusts
  (Nottingham UH, Imperial College Healthcare, Manchester University,
  Newcastle upon Tyne), against the panel benchmark.
- Vacancy rate, A&E 4-hour performance, RTT 52+ week waits over the panel.
- Pairwise correlation matrix of candidate covariates.
- Document any provider-year cells flagged for exclusion (missing data,
  merger transition, outlier > 3·IQR on `bank_agency_ratio`).

**Acceptance:** notebook executes top-to-bottom in under 5 minutes; all
plots saved to `outputs/figures/descriptive/`.

### T6 — Model estimation (`src/pwr_elasticity/models.py`, `notebooks/02_model.ipynb`)

#### T6a — Primary specification: two-way fixed effects panel regression
Estimate, using `linearmodels.PanelOLS`:

```
log(bank_pay_it) = β·log(agency_pay_it) + γ·policy_intensity_t
                 + δ·controls_it + α_i + τ_t + ε_it
```

with `α_i` provider fixed effects, `τ_t` year fixed effects, and
heteroskedasticity-robust standard errors clustered at the ICB level.
`controls_it` = {`log(staff_in_post_fte)`, `vacancy_rate`,
`pct_met_4hr_ae`, `n_waiting_52plus_weeks` per 1k attendances,
`turnover_rate`}.

`β` is the contemporaneous elasticity of Bank pay with respect to agency
pay holding policy intensity constant. Report 95% confidence intervals.

#### T6b — Non-linearity diagnostic
Fit a Random Forest regressor on `log(bank_pay_it)` with all covariates;
extract partial-dependence plots for `log(agency_pay)` and
`policy_intensity` and inspect for inflection. Report SHAP values for
interpretability.

#### T6c — Heterogeneity
Re-estimate T6a stratified by `provider_type` and by ICB region. Report
β with confidence intervals as a coefficient plot.

#### T6d — Robustness
- Levels specification (not logs).
- Drop the COVID-affected 2021/22 observations.
- Drop the four REC case-study trusts.
- Cluster at provider level instead of ICB.

**Acceptance:** all four sub-specifications report results in a tidy long
DataFrame; estimated elasticities are stored to
`outputs/models/elasticity_estimates.parquet`; results survive a
deterministic seed re-run.

### T7 — Diagnostics (`src/pwr_elasticity/diagnostics.py`)
- Residual plots, leverage statistics, influence diagnostics.
- Pre-trend check for the Sep 2022 expenditure ceiling re-introduction
  using an event-study specification.
- Placebo test on a constructed null treatment (random reshuffle of
  policy years).
- Multicollinearity check (VIF) on the covariate set.

**Acceptance:** diagnostics notebook returns no red flags above
pre-specified thresholds, or red flags are documented and discussed.

### T8 — Reporting (`src/pwr_elasticity/report.py`)
- Static HTML report `outputs/report.html` covering: research question,
  data window, headline elasticity, tipping-point characterisation,
  heterogeneity by provider type and ICB, the four REC case studies,
  caveats.
- Provider-level risk score: weighted combination of bank-agency cost
  inversion, vacancy rate, operational pressure (A&E + RTT), and
  policy-intensity exposure. Output as `outputs/risk_scores.parquet`.

**Acceptance:** the report renders without manual intervention from
`python -m pwr_elasticity.report`; risk scores are reproducible across
two consecutive runs with the same seed.

### T9 — Reproducibility manifest
- `outputs/manifest.json` records: source-file SHA256 hashes, package
  versions, git commit, run timestamp, random seeds, and the resolved
  parameter set.

**Acceptance:** clearing `outputs/` and re-running `python src/pipeline.py`
produces byte-identical artefacts (modulo embedded timestamps).

## 8. Cross-cutting quality bar

### 8.1 Data-leak prevention (mandatory, defence-in-depth)

The repository ships with three coordinated controls, all of which must
remain in force throughout the project. The agent must not weaken any of
them without explicit reviewer sign-off.

| Layer | Artefact | What it blocks |
|---|---|---|
| Ignore policy | `.gitignore` (`/data/*` with the sole exception of `DATA_DICTIONARY.md`) | Accidental staging of any data file under `/data/`. |
| Pre-commit (local) | `.pre-commit-config.yaml` running `nbstripout`, `check-added-large-files` (≤ 512 KB), and the local `scripts/check_no_data_files.sh` hook | Notebook outputs, execution counts, cell attachments, widget state, large binaries, and any file with a data-bearing extension or under `/data/`. |
| Continuous integration | `.github/workflows/no-data-leak.yml` (runs on every PR and push to main) | The same conditions as the pre-commit hook, applied to every tracked file. Acts as the safety net when `git add -f` or a missing local hook bypasses the pre-commit. |

Blocked extensions (case-insensitive, list maintained in
`scripts/check_no_data_files.sh` and mirrored in the CI workflow): csv,
tsv, psv, xls, xlsx, xlsm, xlsb, ods, parquet, feather, arrow, orc, avro,
sav, dta, sas7bdat, rdata, rds, pkl, pickle, joblib, npz, npy, mat, h5,
hdf5, nc, db, sqlite, sqlite3, pdf, gz, bz2, xz, zst, zip, tar, 7z, rar.

Notebook authoring rules:

- All `.ipynb` files committed to the repository must be output-free.
  `nbstripout` (installed both as a pre-commit hook and as a git filter
  via `nbstripout --install`) handles this automatically; do not commit
  notebooks edited with `nbstripout` disabled.
- Cell metadata, kernel metadata and Jupyter widget state are also
  stripped. Do not embed plots inline as base64; persist figures to
  `outputs/figures/` and reference them from markdown.
- Do not include `print(df)` or `df.head()` calls that would render
  patient-identifiable or commercially sensitive content if the notebook
  ever picked up real PWR data. Replace exploratory prints with assertions
  on shape or hash.

If the CI check fails, the fix is always:

1. `git rm --cached <file>` to unstage,
2. move the file under `/data/` (or delete) so the ignore policy catches
   it next time,
3. for notebooks, `nbstripout <file>.ipynb` then re-stage.

### 8.2 Code quality

- All code passes `ruff check .` and `black --check .`.
- All public functions carry NumPy-style docstrings and type hints.
- Unit-test coverage on `io`, `panel` and `features` modules ≥ 80% lines.
- No use of `pd.read_csv` defaults; encoding, dtype and date parsing are
  always explicit.
- Currency is held in £ (GBP), unscaled. £m is a presentation choice only.
- Date columns are `pandas.Timestamp` with a documented timezone (UTC).
- Provider codes are uppercase strings (`pd.Series.astype("string")`).
- All notebooks are committed in cleared-output form (use the
  `nbstripout` pre-commit hook).

## 9. Decisions reserved for the analyst

The agent must surface these decisions for human review rather than
defaulting silently:

1. **Identification strategy.** Default to the two-way fixed effects panel
   regression in T6a unless the pre-trend diagnostic in T7 rejects parallel
   trends, in which case escalate.
2. **Treatment of provider mergers.** Default to dropping the merger year
   observation; escalate if it removes more than 5% of the panel.
3. **Handling of `agency_pay_gbp == 0`.** Default to adding £1 before
   logging; flag any provider with a structural zero across the window.
4. **REC case-study weighting in the dashboard.** Default to highlighting
   the four trusts named in the May 2026 letter; confirm before publishing
   any analysis that singles out a named provider.

## 10. Out-of-window items deliberately excluded

- Pre-2021/22 TAC vintages (archived; available from the UK Government
  Web Archive if needed for a longer panel).
- The Manchester University 2020/21 baseline cited in REC narrative
  (referenced in `data/rec_foi/SOURCE_NOTES.md` but not loaded).
- The 2015 and 2016 price-cap introductions (pre-window; recorded as
  historical context in `DATA_DICTIONARY.md` §3.6).

## 11. Definition of done

The agent's work is complete when:
1. The pipeline runs end-to-end from a clean checkout (`python src/pipeline.py`).
2. Headline elasticity estimate with confidence interval is recorded in
   `outputs/report.html` and `outputs/models/elasticity_estimates.parquet`.
3. All acceptance criteria in §7 are met.
4. The reproducibility manifest is produced (§T9).
5. A short summary of findings is appended to `README.md` under a new
   "Headline result" section with reference to the report.
