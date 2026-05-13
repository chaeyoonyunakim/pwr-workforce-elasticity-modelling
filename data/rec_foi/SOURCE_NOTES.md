# REC FOI data — bank vs agency shift costs

This folder is the **only open source** in the project giving shift-level
Bank vs Agency cost comparison at trust level. It is hand-extracted from
two Recruitment & Employment Confederation (REC) publications.

## Sources

**Wave 1 — Jan 2026:** REC press release "Patient safety taken for granted:
Trusts admit failing to assess impact on patients and staff of Department of
Health diktat to cut agency staff" (20 January 2026).
https://www.rec.uk.com/our-view/news/press-releases/patient-safety-taken-granted-trusts-admit-failing-assess-impact-patients-and-staff-department-health-diktat-cut-agency-staff

Scope: 13 London NHS trusts, FY 2019/20–2024/25. Variables: total bank spend
£, total agency spend £. Specific trusts cited: Imperial College Healthcare,
Royal Free London, West London NHS Trust, Whittington Health. Raw FOI tables
are **not** published on the REC site — only summary narrative.

**Wave 2 — May 2026:** Neil Carberry (REC CEO) follow-up letter to Layla
Moran MP, Chair of the Health and Social Care Select Committee, 7 May 2026
(`../Letter_to_Layla_Moran_MP_House_of_Commons_Health_and_Social_Care_Committee.pdf`).

Scope: top-5 most expensive Bank vs Agency shifts at four named trusts
(Nottingham UH, Imperial College Healthcare, Manchester University,
Newcastle upon Tyne), plus Manchester annual totals 2020/21 and 2024/25.
Off-framework status declared "No" for every trust × year cited.

## Files

| File | Granularity |
|---|---|
| `rec_foi_top5_shift_costs.csv` | Trust × FY mean of the top-5 most expensive shifts (£ per shift), Bank vs Agency |
| `rec_foi_annual_spend.csv` | Trust × FY total bank & agency spend (£m). Manchester only — REC let the others stay narrative. |

## Limitations

- Hand-extracted from press release summaries / letter text — figures are
  whatever REC chose to publish. The underlying FOI responses are **not**
  released publicly.
- Sample is small and non-random: REC picks illustrative trusts to make
  policy points. Don't use as a representative panel — use as case-study
  benchmarks against TAC-derived figures.
- "Top-5 most expensive shifts" is a tail statistic, not a mean rate. Useful
  for *cost inversion* visualisation on the Day 5 dashboard, not for
  estimating average bank/agency unit costs.

## How to extend

Two replication paths:

1. **Email REC** — `hamant.verma@rec.uk.com` (press contact on the Jan 2026
   release). They may share the underlying tables on request.
2. **Reproduce the FOI ourselves** — file FOI requests with the same trusts
   under the Freedom of Information Act 2000, asking for "average cost of
   the top five most expensive Bank and Agency shifts in each financial
   year from 2019/20 to current". Each trust has a statutory 20-working-day
   response window. Use the official FOI inbox listed on each trust's
   "Publications" or "Open Data" page (e.g. foi@nuh.nhs.uk).

A full FOI panel covering all 213 English acute / MH / community trusts
would be the strongest replacement for the missing PWR Override Count
signal, but at 213 separate requests is out of scope for the 1-week sprint.
A representative sample of ~20–30 trusts stratified by size and ICB is the
practical compromise.

## Licensing

The REC press release and the letter to Parliament are public communications
(no explicit licence stated). Quote with attribution to REC.
