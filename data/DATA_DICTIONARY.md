# Data dictionary

**Project:** PWR workforce elasticity modelling
**Scope:** Source manifest, variable mapping, granularity, vintage, licence
**Analytical window:** Financial years 2021/22 to 2025/26 inclusive
**Status:** Open-data substitute set assembled in advance of Foundry PWR access

This document is the authoritative reference for the data assets supporting
the analytical work described in `README.md`. Every file under `/data/` is
version-controlled in this repository; all sources are public Crown
Copyright published under the [Open Government Licence v3.0][^14] (NHS
England / NHS England Digital), with the addition of the hand-extracted
REC FOI tables built from public correspondence (see §3.9). Cloning the
repository gives you everything the pipeline needs to run.

The dictionary remains the source of truth for *provenance*: publisher,
statistical type, vintage, granularity, licence, source URL, and
which file in `/data/` came from where.

---

## 1. Position relative to the canonical data product

The canonical source for both the outcome variable and the treatment
variable in this analysis is the **Provider Workforce Return (PWR)**, the
NHS England monthly temporary-staffing collection administered through the
NHSE Foundry platform. PWR is access-controlled and is not released as open
data[^1].

The assets in this repository constitute an **open-data substitute set**
intended to:

1. enable end-to-end pipeline development before Foundry access is granted;
2. provide independent, audited validation of Foundry-derived figures; and
3. supply the operational-outcome variables (A&E, RTT) required for the
   Economic Value-for-Money synthesis (Day 5 of the sprint).

## 2. Variable mapping: sprint specification → open-data source

| Sprint variable | Operational definition | Open-data source | File / folder |
|---|---|---|---|
| Combined Other-staff pay (£) | Bank + Agency + Contract for Services, annual, audited | TAC, annual, provider-level[^2] (see §3.1) | `tac_provider_accounts/` |
| Bank pay expenditure (£), isolated | Total spend on staff Bank shifts only | **Not in TAC** — PWR-only or individual provider notes | — |
| Agency pay expenditure (£), isolated | Total spend on agency-procured temporary staff only | **Not in TAC** — PWR-only or individual provider notes | — |
| `Bank_Agency_Ratio` (recast as `other_to_substantive_ratio`) | Other-staff £ ÷ Substantive £ | Derived from TAC | — |
| Override count | Number of shifts paid above the AfC + 55% cap | **No open substitute** — PWR-only | — |
| `Override_Intensity` | Overrides ÷ Staff-in-Post FTE × 100 | Denominator only from HCHS; numerator PWR-only | — |
| Staff in Post FTE (substantive) | Substantively employed HCHS workforce | NHS Workforce Statistics[^3] | `workforce_stats/hchs_oct_2025/` |
| Vacancy rate | (Budgeted FTE − Staff in Post FTE) ÷ Budgeted FTE | NHS Vacancy Statistics (best open proxy)[^4] | `vacancy_stats/` |
| Turnover | Annual leaver rate, substantive staff | NHS Workforce Statistics, Turnover release[^3] | `workforce_stats/turnover_oct_2025/` |
| Pay calibration (£ / FTE) | Substantive pay per FTE by AfC band | NHS Staff Earnings Estimates[^5] | `staff_earnings/` |
| Agency price cap (treatment intensity) | Hourly maximum permitted agency rate by grade | NHSE agency price card[^6] | `policy_timeline/` |
| Agency rule events | Discrete dates of policy change | NHSE agency rules long-read[^7] | `policy_timeline/` (see §6) |
| Operational pressure (acute) | Type-1 A&E 4-hour standard performance | Monthly A&E Time Series[^8] | `ae_performance/` |
| Operational pressure (elective) | RTT incomplete pathway waits, 52+ week waits | RTT Full CSV extract[^9] | `rtt_performance/` |
| Bank vs Agency cost inversion | Mean of top-5 most expensive shifts £ by category | REC FOI disclosures[^10][^11] | `rec_foi/` |
| Trust ↔ ICB ↔ region mapping | Canonical NHS organisational codes | NHS ODS Trusts (`etr`)[^12] | `reference/` |
| Time-to-Hire (TTH) | Working days from vacancy open to start | **No open substitute** — PWR-only (added Feb 2025) | — |
| Clinical safety incidents | Ward-level reported incident counts | Out of scope (NRLS / LFPSE) | — |
| Retention compartment | Forecast of staff retention | Model Health System (NHSE login) | — |

## 3. Data sources

### 3.1 `tac_provider_accounts/` — Trust Accounts Consolidation

**Publisher:** NHS England, Financial Accounting & Reporting
**Statistical type:** Audited annual financial returns
**Vintage held:** 2021/22 to 2024/25 (four audited financial years; 2025/26 publishes in spring 2027)
**Granularity:** NHS trust × financial year (the published "NHS trusts" file covers
non-Foundation Trusts; the Foundation Trust panel is published as a separate dataset
and is **not** loaded by the current readers)
**Licence:** Open Government Licence v3.0
**Index page:** https://www.england.nhs.uk/financial-accounting-and-reporting/nhs-providers-tac-data-publications/

**Pay schedule extraction (TAC09 Staff).** Implemented in
`pwr_elasticity.io.read_tac`, with constants centralised in
`pwr_elasticity._constants`. Each TAC09 row carries a `MainCode` of the form
`A09{CY|PY}{NN}{suffix}` where the suffix is empty (Total), `P`
(Permanently employed substantive staff), or `O` (Other staff — **Bank +
Agency + Contract for Services combined**). The reader emits three pay
columns for the current-year MainCode set:

| Column | Definition | TAC mapping |
|---|---|---|
| `substantive_pay_gbp` | Substantive staff cost (£) | `A09CY01P` × Net pay SubCode |
| `other_staff_pay_gbp` | Combined Bank + Agency + Contract (£) | `A09CY01O` × Net pay SubCode |
| `total_pay_gbp` | Total staff cost (£) | `A09CY01` × Net pay SubCode |

**Net-pay SubCode candidates** (`TAC_SUBCODE_NET_PAY_CANDIDATES` in
`pwr_elasticity._constants`). The 2022/23 and later vintages publish
`STA0366` (Net employee benefits expenditure, excluding capitalised
costs); earlier vintages (e.g. 2019/20 published April 2021) stop at
`STA0360` (Total employee benefits costs, excluding capitalised costs).
The gap between the two codes is capitalised employee benefits
expenditure (`STA0365`), which is sub-1% of total provider pay. The
reader tries the candidates in preference order (`STA0366` then
`STA0360`) and uses the first one populated for each vintage. This
makes the reader compatible with TAC files from at least 2019/20
onward — see the holdout evaluation at
`../reports/evaluation.md` for the validation result.

Values are stored in £ thousands in the source and scaled to £ at read time.

**Important limitation.** TAC does **not** separate Bank from Agency in the
published consolidated dataset; the split is reported only in each provider's
own published annual-report notes. For the bank-versus-agency elasticity
the project relies on either (a) Provider Workforce Return data from
Foundry, or (b) the case-study figures in `data/rec_foi/` (see §3.9).

| File | Year | URL |
|---|---|---|
| `TAC-data-published-in-NHS-trusts-accounts-for-2021-22.xlsx` | 2021/22 | https://www.england.nhs.uk/wp-content/uploads/2023/07/TAC-data-published-in-NHS-trusts-accounts-for-2021-22.xlsx |
| `TAC-data-published-in-NHS-trusts-accounts-for-2022-23.xlsx` | 2022/23 | https://www.england.nhs.uk/wp-content/uploads/2024/04/TAC-data-published-in-NHS-trusts-accounts-for-2022-23.xlsx |
| `TAC-data-published-in-NHS-trusts-accounts-for-2023-24.xlsx` | 2023/24 | https://www.england.nhs.uk/wp-content/uploads/2025/01/TAC-data-published-in-NHS-trusts-accounts-for-2023-24.xlsx |
| `TAC-data-published-in-NHS-trusts-accounts-for-2024-25.xlsx` | 2024/25 | https://www.england.nhs.uk/wp-content/uploads/2026/04/TAC-data-published-in-NHS-trusts-accounts-for-2024-25.xlsx |

TAC schedules disaggregate operating expenses into substantive pay, **Other
staff pay** (Bank + Agency + Contract for Services, combined), and non-pay
— see the *Important limitation* note above. The four held vintages give a
66–68-provider × 4-year panel; the published "NHS trusts" file does *not*
include the ~145 NHS Foundation Trusts (those are published as a separate
TAC dataset that is not currently loaded). The in-flight 2025/26 financial
year is observed in real time through monthly operational sources but does
not yet have an audited TAC submission.

### 3.2 `workforce_stats/hchs_oct_2025/` — NHS Workforce Statistics, HCHS

**Publisher:** NHS England Digital
**Statistical type:** National Statistics
**Vintage held:** October 2025
**Granularity:** NHS trust × staff group × grade × area of work × month
**Licence:** Open Government Licence v3.0
**Source ZIP:** https://files.digital.nhs.uk/F3/E08EF7/NHS%20HCHS%20Workforce%20Statistics%2C%20Trusts%20and%20core%20organisations%20-%20CSV%20data%20files%2C%20October%202025.zip

The HCHS publication reports headcount and full-time-equivalents for
substantively employed Hospital and Community Health Services (HCHS)
staff[^3]. Bank workers are **excluded**. The full release contains 17 CSV
extracts; the four retained here are those required by the model:

| File | Use |
|---|---|
| `Core 0. CSV data files description, notes and metadata.xlsx` | Column definitions, data quality notes |
| `Core 1. Staff group - England, NHSE region, ICS and org, Oct-25.csv` | Provider-level totals; primary join key |
| `Core 3. Medical staff by grade and specialty - org, Oct-25.csv` | Medical-and-dental grade mix for medical price-cap mapping |
| `Core 5. Staff groups (excl medical) care setting, level, grade - org, Oct-25.csv` | Nursing and AHP grade granularity |
| `Core 14. Mental health workforce - org, Oct-25.csv` | Mental health provider subgroup |

### 3.3 `workforce_stats/turnover_oct_2025/` — Workforce turnover

**Publisher:** NHS England Digital
**Vintage held:** Annual time series Sep-2009 to Oct-2025
**Granularity:** NHSE region × staff group × grade × age band
**Licence:** Open Government Licence v3.0
**Source ZIP:** https://files.digital.nhs.uk/EA/0D4078/NHS%20HCHS%20Workforce%20Statistics%2C%20Turnover%20-%20CSV%20data%20files%2C%20October%202025.zip

Used as a control variable when interpreting variation in
`Bank_Agency_Ratio` over time.

### 3.4 `vacancy_stats/` — NHS Vacancy Statistics

**Publisher:** NHS England Digital
**Statistical type:** Experimental Statistics (NHS Jobs + Trac + ESR linkage)
**Vintage held:** April 2015 to December 2025
**Granularity:** England aggregate; staff-group breakdown in tables
**Licence:** Open Government Licence v3.0
**Headline figure:** All-staff vacancy rate 6.7% at September 2025[^4]

| File | URL |
|---|---|
| `nhs-vac-stats-apr15-dec25-eng-tables.xlsx` | https://files.digital.nhs.uk/96/1FBDE9/nhs-vac-stats-apr15-dec25-eng-tables.xlsx |
| `nhs-vac-stats-apr15-dec25-eng-dq-annex.xlsx` | https://files.digital.nhs.uk/8F/6B34A0/nhs-vac-stats-apr15-dec25-eng-dq-annex.xlsx |

This series is the closest open-data substitute for the
"Position Budgeted FTE − Staff in Post FTE" derivation defined in the PWR
specification.

### 3.5 `staff_earnings/` — NHS Staff Earnings Estimates

**Publisher:** NHS England Digital
**Statistical type:** Official Statistics
**Vintage held:** Monthly estimates to October 2025
**Granularity:** NHS trust × staff group × AfC band × month
**Licence:** Open Government Licence v3.0

| File | URL |
|---|---|
| `Monthly-Earnings-to-Oct2025-NHS-Trusts.csv` | https://files.digital.nhs.uk/4D/76E51C/Monthly%20Earnings%20Estimates%20to%20October%202025%2C%20NHS%20Trusts%20and%20other%20core%20orgs%2C%20CSV.csv |
| `Monthly-Non-Basic-Pay-to-Oct2025-NHS-Trusts.csv` | https://files.digital.nhs.uk/70/475F61/Monthly%20Non%20Basic%20Pay%20to%20October%202025%2C%20NHS%20Trusts%20and%20other%20core%20orgs%2C%20CSV.csv |
| `Monthly-Earnings-by-AfC-band-to-Oct2025-NHS-Trusts.csv` | https://files.digital.nhs.uk/C4/E73645/Monthly%20Earnings%20by%20AfC%20band%20and%20grade%20step%20to%20October%202025%2C%20NHS%20Trusts%20and%20other%20core%20orgs%2C%20CSV.csv |

Used to (a) normalise TAC pay totals to a per-FTE basis and (b) translate
AfC bands into £ values for the agency price-cap comparison.

### 3.6 `policy_timeline/` — Agency rules and price caps

**Publisher:** NHS England, Workforce Training & Education

| File | Content | URL |
|---|---|---|
| `nhs-england-agency-price-card-26-27.xlsx` | Current AfC + 55% caps by grade and staff group | https://www.england.nhs.uk/publication/price-card/ |

#### Discrete policy events (to be encoded as treatment indicators)

In-window events (within the 2021/22–2025/26 analytical horizon):

| Date | Event |
|---|---|
| Sep 2022 | Agency expenditure ceiling re-introduced into NHS System Oversight[^7] |
| 2023/24–2024/25 | Successive agency rule revisions and tightening of framework compliance[^7] |
| 1 Jul 2025 | Chief Executive sign-off required for all band 2/3 agency shifts[^7] |
| 2026 | 30% short-term agency reduction target; zero off-framework target by 2029[^13] |

Pre-window context (preceded the analytical horizon but established the
regulatory regime in force at baseline):

| Date | Event |
|---|---|
| 23 Nov 2015 | Agency price caps introduced (phased to AfC + 55% by April 2016)[^7] |
| 1 Apr 2016 | Mandatory procurement via approved framework agreements[^7] |
| 16 Sep 2019 | Admin and estates substitution rule (mandatory Bank or substantive)[^7] |

### 3.7 `ae_performance/` — A&E Attendances and Emergency Admissions

**Publisher:** NHS England, Performance Analysis Team
**Statistical type:** Official Statistics
**Vintage held:** Monthly time series to March 2026
**Granularity:** Provider × month, all A&E types
**Licence:** Open Government Licence v3.0

| File | URL |
|---|---|
| `Monthly-AE-Time-Series-March-2026.xls` | https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/04/Monthly-AE-Time-Series-March-2026-F5ldj2.xls |

Operational-pressure outcome variable for the Day 5 Economic
Value-for-Money synthesis.

### 3.8 `rtt_performance/feb26/` — Referral-to-Treatment waiting times

**Publisher:** NHS England, Operational Information for Commissioning
**Statistical type:** Official Statistics
**Vintage held:** February 2026 full extract (single month)
**Granularity:** Provider × treatment function × pathway state
**Licence:** Open Government Licence v3.0

| File | URL |
|---|---|
| `20260228-RTT-February-2026-full-extract.csv` | https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/04/Full-CSV-data-file-Feb26-ZIP-4M-9j03fJT.zip |

Elective-backlog outcome variable. A multi-month panel can be assembled by
fetching the same filename pattern for prior months from the [2025–26 RTT
data page](https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2025-26/).

### 3.9 `rec_foi/` — Recruitment & Employment Confederation FOI disclosures

**Publisher:** Recruitment & Employment Confederation
**Statistical type:** Case-study disclosure (purposive sample)
**Vintage held:** Wave 1 (January 2026) and Wave 2 (May 2026)
**Granularity:** Provider × financial year; top-5 most expensive shifts £
**Status:** Hand-transcribed from public correspondence — version-controlled in this repository
**Licence:** Public communication; quote with attribution to REC

| File | Content |
|---|---|
| `rec_foi_top5_shift_costs.csv` | Six provider-year observations: Nottingham UH, Imperial College Healthcare, Manchester University, Newcastle upon Tyne — mean cost of top-5 Bank vs Agency shifts |
| `rec_foi_annual_spend.csv` | Manchester University NHS Foundation Trust, total Bank and agency spend 2024/25 (in-window observation; the published 2020/21 baseline used in REC narrative falls outside the analytical window) |
| `SOURCE_NOTES.md` | Provenance, limitations and FOI replication path |

This is the only open source providing shift-level Bank vs Agency cost
comparison. The figures evidence cost inversion (Bank > Agency at the
distribution tail) in providers operating policy-compliantly without
off-framework procurement[^10][^11].

### 3.10 `reference/` — Organisation Data Service reference

**Publisher:** NHS England Digital, Organisation Data Service
**Vintage held:** As at retrieval (live endpoint)
**Granularity:** NHS trust / Foundation Trust
**Licence:** Open Government Licence v3.0

| File | URL |
|---|---|
| `etr-nhs-trusts.csv` | https://www.odsdatasearchandexport.nhs.uk/api/getReport?report=etr |

Canonical NHS trust list with codes, addresses and NHSE region. ICB
membership for each trust can be obtained either from the `Core 1` HCHS
extract (which carries the ICS code) or via the `epcmem` ICB membership
report from the same endpoint.

### 3.11 `Letter_to_Layla_Moran_MP_House_of_Commons_Health_and_Social_Care_Committee.pdf`

Provenance document for Wave 2 of the REC FOI extracts. Letter from Neil
Carberry (Chief Executive, REC) to Layla Moran MP, Chair of the House of
Commons Health and Social Care Select Committee, dated 7 May 2026[^11].

## 4. Join keys and ETL notes

| Join | Key | Notes |
|---|---|---|
| TAC ↔ HCHS | Provider code (3-character ODS code) | TAC reports the alpha code; HCHS reports the same in `Org code` column |
| HCHS ↔ vacancy stats | Staff group + reporting month | Vacancy stats are England aggregate; merge at England level for the rate, not at provider level |
| TAC / HCHS ↔ A&E / RTT | Provider code | Reconcile mergers using the `etr` reference and the [NHS England trust mergers register](https://digital.nhs.uk/services/organisation-data-service) |
| Provider ↔ ICB | ICS code via HCHS `Core 1` | The 2022 ICS reorganisation requires careful pre-/post-merger handling for any panel beginning before July 2022 |
| REC FOI ↔ TAC | Provider name (manual match) | Sample is too small to warrant automated fuzzy matching |

## 5. Gaps that cannot be closed from open data

1. **PWR Override Count** — definitionally a Foundry-only field. The
   `Override_Intensity` derived feature cannot be reconstructed from open
   sources; either obtain Foundry access or drop the feature.
2. **PWR Time-to-Hire** — introduced February 2025; no open equivalent.
3. **Monthly Bank / Agency expenditure split** — TAC publishes annual
   audited figures only. The Monthly Temporary Staffing Return remains
   internal.
4. **Full REC FOI panel** — REC publishes summary case studies only;
   contact `hamant.verma@rec.uk.com` to request the underlying tables, or
   reproduce the FOI requests directly (see `data/rec_foi/SOURCE_NOTES.md`).
5. **Model Health System retention compartment** — NHSE authenticated
   access only.

## 6. Licensing summary

All NHS England and NHS England Digital data products incorporated here are
Crown Copyright, licensed under the [Open Government Licence v3.0](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/),
which permits copying, adaptation and commercial use subject to
attribution. Attribute as "Source: NHS England" or "Source: NHS England
Digital, [year]". The REC FOI extracts retain REC attribution.

---

## References

[^1]: NHS England. *Provider Workforce Return (PWR)* — data collection notes referenced in NHS England temporary staffing guidance. PWR is administered via the NHSE Foundry platform; access is restricted to authorised analysts.
[^2]: NHS England. *NHS providers: Trust Accounts Consolidation (TAC) data publications*. https://www.england.nhs.uk/financial-accounting-and-reporting/nhs-providers-tac-data-publications/
[^3]: NHS England Digital. *NHS Workforce Statistics*. Monthly publication. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-workforce-statistics
[^4]: NHS England Digital. *NHS Vacancy Statistics, April 2015 to December 2025, Experimental Statistics*. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-vacancies-survey
[^5]: NHS England Digital. *NHS Staff Earnings Estimates*. Monthly publication. https://digital.nhs.uk/data-and-information/publications/statistical/nhs-staff-earnings-estimates
[^6]: NHS England. *Agency price card*. https://www.england.nhs.uk/publication/price-card/
[^7]: NHS England. *Agency rules*. Long-read guidance. https://www.england.nhs.uk/long-read/agency-rules/
[^8]: NHS England. *A&E Attendances and Emergency Admissions*. Statistical work area. https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/
[^9]: NHS England. *Consultant-led Referral to Treatment Waiting Times*. https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/
[^10]: Recruitment & Employment Confederation. *Patient safety taken for granted: Trusts admit failing to assess impact on patients and staff of Department of Health diktat to cut agency staff*. Press release, 20 January 2026. https://www.rec.uk.com/our-view/news/press-releases/patient-safety-taken-granted-trusts-admit-failing-assess-impact-patients-and-staff-department-health-diktat-cut-agency-staff
[^11]: Carberry N (Chief Executive, REC). Letter to Layla Moran MP, Chair, House of Commons Health and Social Care Select Committee, 7 May 2026. `../Letter_to_Layla_Moran_MP_House_of_Commons_Health_and_Social_Care_Committee.pdf`.
[^12]: NHS England Digital. *Organisation Data Service: Other NHS organisations CSV downloads*. https://digital.nhs.uk/services/organisation-data-service/data-search-and-export/csv-downloads/other-nhs-organisations
[^13]: NHS England. *NHS finance business rules from 2026/27: guidance for integrated care boards and NHS trusts*. https://www.england.nhs.uk/long-read/nhs-finance-business-rules-from-2026-27-guidance-for-integrated-care-boards-and-nhs-trusts/
[^14]: The National Archives. *Open Government Licence v3.0*. http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
