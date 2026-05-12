# PWR workforce elasticity modelling

**Estimating the responsiveness of NHS provider bank pay expenditure to
agency-restriction policy, using the Provider Workforce Return (PWR) and
audited open-data substitutes.**

**Analytical window:** financial years 2021/22 to 2025/26 inclusive.
Audited TAC data is available for 2021/22–2024/25; the in-flight 2025/26
year is observed through monthly operational sources and through the
in-year policy treatment indicators.

---

## 1. Background

Since November 2015, NHS England has operated a regime of price caps and
framework rules intended to reduce expenditure on agency-procured temporary
staff[^1][^2]. Successive policy iterations have tightened the regime, most
recently a 2026 mandate requiring a 30% short-term reduction in agency spend
and zero off-framework procurement by 2029[^3]. The policy theory of change
assumes that restricted agency provision will be substituted by lower-cost
substantive or staff Bank shifts, generating net savings.

Emerging evidence challenges this assumption. Freedom of Information requests
to a number of English NHS trusts, conducted by the Recruitment & Employment
Confederation (REC) and disclosed in January and May 2026, indicate
shift-level cost inversion in several providers: at Imperial College
Healthcare NHS Trust in 2025/26 the mean cost of the five most expensive
Bank shifts was £5,509 against £2,116 for the five most expensive agency
shifts; at Manchester University NHS Foundation Trust, total Bank
expenditure rose from £60.2m in 2020/21 to £114.3m in 2024/25 while agency
expenditure fell by approximately £2.7m over the same period[^4][^5].

This pattern is consistent with a workforce-shortage explanation: under
binding agency caps, providers face inelastic demand for temporary cover and
pay a premium through the staff Bank instead. The empirical question is the
**magnitude and non-linearity of the substitution** — the elasticity of Bank
pay expenditure with respect to agency-rule intensity, and whether the
substitution curve exhibits a discontinuity above a defined intensity
threshold.

## 2. Research questions

- **Q1 (elasticity).** What is the contemporaneous and lagged elasticity of
  provider-level Bank pay expenditure with respect to a binding change in
  the agency price cap or framework rule set, conditional on substantive
  workforce capacity and operational demand pressure?
- **Q2 (tipping point).** At what level of agency-rule intensity, measured
  as override frequency per 100 substantive FTE, does the Bank-to-agency
  cost ratio cease to fall and begin to rise (the displacement
  inflection)?
- **Q3 (heterogeneity).** Does the elasticity differ systematically across
  ICBs, provider type (acute / mental health / community), and care
  setting?

## 3. Methodology

The project is scoped as a one-week analytical sprint:

| Day | Activity |
|---|---|
| 1–2 | Construct the provider-month panel by joining PWR, ESR turnover, NHS Vacancy Statistics, and policy-timeline variables. |
| 3 | Feature engineering: derive `Bank_Agency_Ratio`, `Override_Intensity` (overrides per 100 substantive FTE), and a `TTH_Efficiency` deviation from national mean Time-to-Hire. |
| 4 | Estimate the elasticity using a fixed-effects panel specification with provider and time fixed effects; complement with a Random Forest regressor on `Monthly_Override_Count` to characterise non-linearity and produce a weighted provider risk score. |
| 5 | Synthesise outputs into an Economic Value-for-Money dashboard, identifying ICBs at risk of failing the 30% agency reduction target. |

Statistical specification, identifying assumptions and standard-error
clustering will be specified in a separate analysis plan prior to model
fitting.

## 4. Data

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
| Provider bank and agency expenditure (annual, audited) | Trust Accounts Consolidation (TAC), NHS England[^6] |
| Substantive workforce (Staff in Post FTE) | NHS Workforce Statistics, NHS England[^7] |
| Vacancies (open proxy for budgeted–actual delta) | NHS Vacancy Statistics, NHS England[^8] |
| Pay calibration (£/FTE by AfC band) | NHS Staff Earnings Estimates, NHS England[^9] |
| Treatment-variable definition (price caps) | NHSE agency price card and agency rules long-read[^1][^2] |
| Operational pressure outcomes | Monthly A&E Attendances and Emergency Admissions[^10]; RTT Waiting Times[^11] |
| Shift-level cost inversion (case studies) | REC FOI disclosures, Jan and May 2026[^4][^5] |
| Organisational reference | NHS ODS NHS Trusts and Trust Sites[^12] |

No data files are version-controlled — only `data/DATA_DICTIONARY.md` is
tracked. Re-acquire all sources from the canonical URLs documented in the
dictionary; hand-extract the REC FOI tables from the public correspondence
cited there.

## 5. Repository structure

```
.
├── README.md                         this document
├── LICENSE                           MIT (project code)
├── .gitignore                        excludes /data/* except DATA_DICTIONARY.md
├── plan/
│   └── plan.md                       agent-runnable build plan (requirements, tasks, acceptance criteria)
└── data/
    ├── DATA_DICTIONARY.md            authoritative source manifest, variable mapping
    ├── tac_provider_accounts/        TAC 2021/22–2024/25 (NHSE OGL v3.0)
    ├── workforce_stats/              HCHS staff in post and turnover (NHSE OGL v3.0)
    ├── vacancy_stats/                NHS Vacancy Statistics Apr-2015 to Dec-2025
    ├── staff_earnings/               NHS Staff Earnings Estimates to Oct-2025
    ├── policy_timeline/              Agency price card and policy event dates
    ├── ae_performance/               Monthly A&E time series to Mar-2026
    ├── rtt_performance/              RTT full extract Feb-2026
    ├── rec_foi/                      Hand-extracted REC FOI shift-cost data (local only)
    ├── reference/                    NHS Trusts ODS reference (etr)
    └── Letter_to_Layla_Moran_MP...   Provenance for REC FOI extracts (Wave 2)
```

## 6. Reproducibility

The repository follows the NHS England Reproducible Analytical Pipelines
(RAP) principles[^13]:

1. Clone the repository and create a Python environment from the project's
   `pyproject.toml` (or `requirements.txt`) once added.
2. Run the data acquisition script to repopulate `/data/` from the URLs in
   `data/DATA_DICTIONARY.md`. All bulk artefacts are re-fetchable; the REC
   FOI tables must be hand-transcribed from the referenced public
   correspondence on first run.
3. Execute the analytical pipeline. Determinism is preserved by pinning the
   data vintage in each source filename (e.g. `Oct-25`, `Feb-26`).

## 7. Limitations and data caveats

- **PWR access is required for the headline analysis.** Open-data
  substitutes provide annual rather than monthly cadence for the bank /
  agency expenditure split and do not contain override counts or Time-to-Hire
  fields. Conclusions drawn from the open-data prototype must be replicated
  on PWR before publication.
- **The REC FOI sample is purposive, not representative.** REC selected
  trusts to illustrate cost inversion; the figures are useful as
  case-study calibration but not as a panel estimator.
- **HCHS substantive workforce statistics exclude bank staff.** The
  denominator for `Override_Intensity` therefore measures substantive
  capacity, not total filled capacity.
- **Model Health System retention compartments and ward-level safety
  incident data (NRLS / LFPSE) are not in scope** for the open-data
  prototype.

## 8. Licence and attribution

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
