# PWR workforce elasticity modelling

**Estimating the responsiveness of NHS provider non-substantive staff
expenditure to agency-restriction policy, using the Provider Workforce
Return (PWR) and audited open-data substitutes.**

[![CI](https://github.com/chaeyoonyunakim/pwr-workforce-elasticity-modelling/actions/workflows/ci.yml/badge.svg)](https://github.com/chaeyoonyunakim/pwr-workforce-elasticity-modelling/actions/workflows/ci.yml)

| | |
|---|---|
| **Analytical window** | Financial years 2021/22 to 2025/26 inclusive |
| **TAC vintages held** | 2021/22, 2022/23, 2023/24, 2024/25 (audited NHS trusts) |
| **Panel size** | 263 provider-year observations × 66–68 NHS trusts × 4 years |
| **Status** | Pipeline shipped end-to-end; out-of-sample evaluation merged; data + outputs version-controlled |
| **Tests** | 68 passing — see CI |
| **Headline elasticity** | β = **−0.287**, 95% CI **[−0.434, −0.140]**, cluster-robust SE on ICS, n = 262, 32 ICS clusters |

The rendered headline report lives at [`outputs/report.html`](outputs/report.html).
The pre-window holdout evaluation is documented at [`reports/evaluation.md`](reports/evaluation.md).
The descriptive notebook with all rendered figures is at [`notebooks/01_descriptive.ipynb`](notebooks/01_descriptive.ipynb).

---

## 1. Background

Since November 2015, NHS England has operated a regime of price caps and
framework rules intended to reduce expenditure on agency-procured temporary
staff[^1][^2]. Successive policy iterations have tightened the regime, most
recently a 2026 mandate requiring a 30% short-term reduction in agency spend
and zero off-framework procurement by 2029[^3]. The policy theory of change
assumes that restricted agency provision will be substituted by lower-cost
substantive or staff Bank shifts, generating net savings.

Emerging evidence challenges this assumption. Freedom of Information
requests to a number of English NHS trusts, conducted by the Recruitment &
Employment Confederation (REC) and disclosed in January and May 2026,
indicate shift-level cost inversion in several providers: at Imperial
College Healthcare NHS Trust in 2025/26 the mean cost of the five most
expensive Bank shifts was £5,509 against £2,116 for the five most expensive
agency shifts; at Manchester University NHS Foundation Trust, total Bank
expenditure rose from £60.2m in 2020/21 to £114.3m in 2024/25 while agency
expenditure fell by approximately £2.7m over the same period[^4][^5].

This pattern is consistent with a workforce-shortage explanation: under
binding agency caps, providers face inelastic demand for temporary cover and
pay a premium through the staff Bank instead.

## 2. Research questions

- **Q1 (elasticity).** What is the contemporaneous elasticity of
  provider-level non-substantive pay expenditure with respect to the
  cumulative intensity of in-window agency-rule policy, conditional on
  substantive workforce capacity and operational demand pressure?
- **Q2 (tipping point).** Does the relationship exhibit a non-linearity
  beyond a defined policy-intensity threshold?
- **Q3 (heterogeneity).** Does the elasticity differ systematically across
  ICBs and provider type (acute / mental health / community / ambulance /
  specialist)?

## 3. Data adaptation note

The plan was originally specified with `bank_pay_gbp` and `agency_pay_gbp`
as separate outcome variables. **TAC does not publish the Bank-versus-Agency
split as a separate line item**: TAC09 Staff reports staff cost as
*Permanent* (substantive) vs *Other* (Bank + Agency + Contract for Services
combined). The production pipeline therefore models the elasticity of
`other_staff_pay_gbp` with respect to policy intensity; the bank-vs-agency
cost-inversion finding is supported separately by the REC FOI extracts
([data/DATA_DICTIONARY.md §3.9](data/DATA_DICTIONARY.md)).

## 4. Data sources

The primary outcome and treatment data live in the **Provider Workforce
Return (PWR)**, NHS England's monthly temporary-staffing collection, hosted
on the NHSE Foundry platform and not released as open data. The repository
therefore assembles an **open-data substitute set** sufficient to (a)
prototype the modelling pipeline in advance of Foundry access and (b)
cross-validate Foundry-derived totals against audited published figures.

Key sources (see [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md) for
full provenance, vintage, granularity, and licensing):

| Domain | Source |
|---|---|
| Provider pay split (annual, audited) | Trust Accounts Consolidation (TAC), NHS England[^6] |
| Substantive workforce (Staff in Post FTE) | NHS Workforce Statistics, NHS England[^7] |
| Vacancies (open proxy for budgeted–actual delta) | NHS Vacancy Statistics, NHS England[^8] |
| Pay calibration (£/FTE by AfC band) | NHS Staff Earnings Estimates, NHS England[^9] |
| Treatment-variable definition (price caps) | NHSE agency price card and agency rules long-read[^1][^2] |
| Operational pressure outcomes | Monthly A&E Attendances and Emergency Admissions[^10]; RTT Waiting Times[^11] |
| Shift-level cost inversion (case studies) | REC FOI disclosures, Jan and May 2026[^4][^5] |
| Organisational reference | NHS ODS NHS Trusts and Trust Sites[^12] |

**Data are version-controlled.** Every file under `/data/` is a public
Crown-Copyright source published under the Open Government Licence v3.0
(NHS England / NHS England Digital), plus hand-extracted figures from
public REC correspondence. Cloning the repository gives you everything
the pipeline needs to run; no separate data download is required. The
two largest files (RTT February 2026 extract at ~80 MB; HCHS Core 1 at
~45 MB) exceed GitHub's 50 MB display warning but are well under the
100 MB hard limit. See [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md)
for full source URLs, vintages and licensing.

## 5. Repository structure

```
.
├── README.md                            this document
├── LICENSE
├── pyproject.toml                       Python package, deps, ruff/black/pytest config
├── .pre-commit-config.yaml              lint + format + pytest-on-push hooks
├── .gitignore                           excludes Python build artefacts; /data and /outputs are tracked
├── .github/workflows/
│   └── ci.yml                           lint + pytest CI
├── plan/
│   └── PLAN.md                          agent build plan, T1–T9 task DAG
├── src/pwr_elasticity/
│   ├── __init__.py
│   ├── _constants.py                    analytical window + TAC SubCode candidates
│   ├── io.py                            8 source readers (T2)
│   ├── panel.py                         build_panel, provider_exclusions (T3)
│   ├── features.py                      compute_features, encode_policy_intensity (T4)
│   ├── models.py                        TWFE, RF, heterogeneity, robustness (T6)
│   ├── diagnostics.py                   pre-trend, placebo, VIF (T7)
│   ├── report.py                        risk scores + HTML report renderer (T8)
│   ├── manifest.py                      reproducibility manifest (T9)
│   └── pipeline.py                      CLI entry point
├── tests/                               68 tests, fixture-based
├── notebooks/
│   └── 01_descriptive.ipynb             T5 descriptive analysis (rendered with outputs)
├── scripts/
│   └── evaluate_holdout.py              out-of-sample evaluation harness
├── reports/                             narrative write-ups
│   ├── README.md                        index + viewing instructions for outputs/report.html
│   └── evaluation.md                    pre-window holdout write-up
├── data/                                public sources under OGL v3.0
│   ├── DATA_DICTIONARY.md               authoritative source manifest
│   ├── tac_provider_accounts/           TAC 2021/22–2024/25
│   ├── eval_holdout/tac_provider_accounts/   TAC 2019/20–2020/21 (holdout)
│   ├── workforce_stats/                 HCHS Core 1, 3, 5, 14 + turnover
│   ├── vacancy_stats/                   NHS Vacancy Statistics tables
│   ├── staff_earnings/                  NHS Staff Earnings Estimates
│   ├── policy_timeline/                 NHSE agency price card
│   ├── ae_performance/                  Monthly A&E time series
│   ├── rtt_performance/feb26/           RTT February 2026 full extract
│   ├── rec_foi/                         REC FOI shift-cost extracts + notes
│   ├── reference/                       NHS Trusts ODS (etr)
│   └── Letter_to_Layla_Moran_MP_...pdf  Provenance for REC FOI Wave 2
└── outputs/                             regenerated pipeline artefacts (tracked snapshot)
    ├── report.html                      headline result HTML — canonical
    ├── manifest.json                    SHA-256 hashes + package versions + git commit
    ├── panel/                           provider × FY panel parquet
    ├── features/                        feature-engineered frame parquet
    ├── models/                          elasticity / heterogeneity / robustness parquet
    ├── diagnostics/                     pre-trend / placebo / VIF parquet
    ├── figures/descriptive/             notebook-rendered PNGs
    ├── risk_scores.parquet              provider EVfM risk scores
    └── eval_holdout/                    holdout-evaluation parallel tree
```

## 6. Running the pipeline

```bash
# 1. Install
pip install -e ".[dev]"
pre-commit install

# 2. Run end-to-end (data is already in the repo)
python -m pwr_elasticity.pipeline

# 3. Outputs are rewritten in outputs/
#    - panel/provider_year_panel.parquet
#    - features/features.parquet
#    - models/elasticity_estimates.parquet
#    - diagnostics/{pre_trend,placebo,vif}.parquet
#    - risk_scores.parquet
#    - report.html
#    - manifest.json  (SHA-256 hashes + git commit + package versions)

# 4. Out-of-sample holdout evaluation (optional)
python scripts/evaluate_holdout.py
#    writes outputs/eval_holdout/ — see reports/evaluation.md
```

The repository follows the NHS England Reproducible Analytical Pipelines
(RAP) principles[^13]. The manifest pins source-file hashes, package
versions, the git commit and the random seed; re-running against the same
inputs produces byte-identical artefacts modulo embedded timestamps.

## 7. Quality gates

Code-quality gates only — data and outputs are intentionally tracked
(all sources are public Crown-Copyright under OGL v3.0):

1. **Local pre-commit hooks** — ruff + ruff-format, black, the standard
   pre-commit-hooks set (trailing whitespace, end-of-file, yaml/toml/json
   validity, merge conflicts, case conflicts). Pytest runs on push.
2. **CI workflow** (`.github/workflows/ci.yml`) — `ruff check .`,
   `black --check .`, and `pytest -q` on every PR and every push to
   `main`.

An earlier project iteration ran a `no-data-leak` workflow that
actively refused to merge tracked data files. That workflow has been
removed alongside the decision to publish all open-data sources
in-repo; the commit history records the policy reversal.

## 8. Out-of-sample evaluation

The model was evaluated against pre-window TAC vintages (2019/20 and
2020/21) using `scripts/evaluate_holdout.py`. Headline finding: the
pipeline is structurally sound — every data-side stage works on unseen
vintages after a one-line reader fix (legacy SubCode `STA0360` added to
the candidate list alongside `STA0366`), and identification-requiring
stages (TWFE primary, placebo, VIF) degrade *gracefully* on the two-year
holdout rather than returning meaningless coefficients. Full write-up at
[reports/evaluation.md](reports/evaluation.md).

## 9. Limitations and data caveats

- **PWR access is required for the bank-vs-agency elasticity.** TAC
  publishes the Permanent vs Other split only; the Bank-vs-Agency split
  lives in PWR (Foundry-only) or in the REC FOI case-study extracts.
- **TAC NHS-trusts file only.** The Foundation Trust panel is published
  as a separate TAC dataset and is not yet loaded; coverage is therefore
  66–68 providers per year rather than the full ~213.
- **The REC FOI sample is purposive, not representative.** REC selected
  trusts to illustrate cost inversion; the figures are useful as
  case-study calibration but not as a panel estimator.
- **HCHS substantive workforce statistics exclude bank staff.** All
  workforce denominators measure substantive capacity, not total filled
  capacity.
- **Pre-trend rejects parallel trends and the placebo p-value is ~0.29.**
  The headline coefficient is reported as a *policy-period descriptive
  elasticity*, not a clean causal effect — see the editorial caveat box
  in the rendered report.
- **Model Health System retention compartments and ward-level safety
  incident data (NRLS / LFPSE) are out of scope** for the open-data
  prototype.

## 10. Licence and attribution

Project code is licensed under the terms of the `LICENSE` file. All NHS
England and NHS Digital data products incorporated in this analysis are
Crown Copyright, published under the [Open Government Licence
v3.0](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/);
attribution to "NHS England" or "NHS England Digital" is required in any
derivative publication. REC FOI figures cited in this analysis are
hand-transcribed from public correspondence and the REC press release;
quote with attribution to the Recruitment & Employment Confederation.

## References

[^1]: NHS England. *Agency rules*. Long-read guidance, last updated 2025. https://www.england.nhs.uk/long-read/agency-rules/
[^2]: NHS England. *Reducing expenditure on NHS agency staff: rules and price caps*. https://www.england.nhs.uk/reducing-expenditure-on-nhs-agency-staff-rules-and-price-caps/
[^3]: NHS England. *NHS finance business rules from 2026/27: guidance for integrated care boards and NHS trusts*. https://www.england.nhs.uk/long-read/nhs-finance-business-rules-from-2026-27-guidance-for-integrated-care-boards-and-nhs-trusts/
[^4]: Recruitment & Employment Confederation. *Patient safety taken for granted: Trusts admit failing to assess impact on patients and staff of Department of Health diktat to cut agency staff*. Press release, 20 January 2026. https://www.rec.uk.com/our-view/news/press-releases/patient-safety-taken-granted-trusts-admit-failing-assess-impact-patients-and-staff-department-health-diktat-cut-agency-staff
[^5]: Carberry N (Chief Executive, REC). Letter to Layla Moran MP, Chair, House of Commons Health and Social Care Select Committee, 7 May 2026. Reproduced at `data/Letter_to_Layla_Moran_MP_House_of_Commons_Health_and_Social_Care_Committee.pdf`.
[^6]: NHS England. *NHS providers: Trust Accounts Consolidation (TAC) data publications*. https://www.england.nhs.uk/financial-accounting-and-reporting/nhs-providers-tac-data-publications/
[^7]: NHS England Digital. *NHS Workforce Statistics*. Monthly publication. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-workforce-statistics
[^8]: NHS England Digital. *NHS Vacancy Statistics (and previous NHS Vacancies Survey)*. Experimental statistics, April 2015 – December 2025. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-vacancies-survey
[^9]: NHS England Digital. *NHS Staff Earnings Estimates*. Monthly publication. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-staff-earnings-estimates
[^10]: NHS England. *A&E Attendances and Emergency Admissions*. Statistical work area. https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/
[^11]: NHS England. *Consultant-led Referral to Treatment Waiting Times*. Statistical work area. https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/
[^12]: NHS England Digital. *Organisation Data Service: Other NHS organisations CSV downloads*. https://digital.nhs.uk/services/organisation-data-service/data-search-and-export/csv-downloads/other-nhs-organisations
[^13]: NHS England. *Reproducible Analytical Pipelines (RAP) Strategy*. https://transform.england.nhs.uk/key-tools-and-info/reproducible-analytical-pipelines/

---

## Build acknowledgement

This repository was built using **[Claude Code](https://claude.com/claude-code)**
with **Anthropic Claude Opus 4.7 (High mode)** as the implementing model,
under the repository owner's supervision and guardrails. The owner set
the research question, the analytical window, the open-data policy and
the data-leak controls; reviewed and approved every pull request before
merge; and made the final calls on identification strategy, scope
trade-offs and the decision to publish the source datasets in-repo.
Claude Code produced the implementation — readers, panel assembly,
features, estimators, diagnostics, report renderer, pipeline,
manifest, tests, CI configuration and prose — within those guardrails.
The build history is fully auditable in the merged PRs (#1 through #15).
