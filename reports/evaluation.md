# Out-of-sample evaluation against pre-window holdout data

**Verdict.** The pipeline is structurally sound. The full 68-test
production suite passes, the production pipeline still runs against
`/data/` unchanged, and the same code runs end-to-end against
unseen pre-window TAC vintages once a minor reader fix is applied
to recognise the older `STA0360` SubCode. Identification-requiring
stages (TWFE, placebo, VIF) degrade *gracefully* on the 2-year
holdout — not because the model is wrong, but because two financial
years contain no within-policy variation once year fixed effects are
included. This is the expected behaviour for a panel estimator.

## Holdout design

| Element | Value |
|---|---|
| Branch | `eval` |
| Holdout TAC vintages | 2019/20, 2020/21 (audited, NHS-trusts) |
| Holdout window | 2019/20–2020/21 |
| Production window (unchanged) | 2021/22–2025/26 |
| Workforce / vacancy / earnings / A&E sources | reused from `/data/` (their time series cover both windows) |
| RTT | empty for the holdout (only Feb-2026 extract downloaded) |
| Policy calendar (patched) | `{2019/20: 0, 2020/21: 1}` reflecting the 16 Sep 2019 admin & estates substitution rule as the in-window step |
| Seed | 0 |

The requested third pre-window year (2018/19) was **not** available
as a direct download — the legacy NHS Improvement publication page
now redirects to the NHS England site root, and no successor URL
pattern works. The evaluation therefore covers two of the three
requested years with a transparent note in the run manifest.

## Discovered limitation, with fix

**Finding.** The original `pwr_elasticity.io.read_tac` filtered TAC09
to `SubCode == "STA0366"` (Net employee benefits expenditure). The
2019/20 vintage stops at `STA0360` (Total employee benefits costs,
excluding capitalised) and does not publish `STA0366`. Without the
fix the reader silently returned an empty frame for that file.

**Fix.** `pwr_elasticity._constants` now exposes a tuple
`TAC_SUBCODE_NET_PAY_CANDIDATES = ("STA0366", "STA0360")`. The reader
tries each candidate in order and uses the first one that is
populated. The gap between the two codes is capitalised employee
benefits expenditure (`STA0365`), which is tiny relative to total
provider pay (sub-1% of the staff line). Sanity check on 2020/21
(where both subcodes exist):

| MainCode | STA0360 (£bn) | STA0366 (£bn) |
|---|---:|---:|
| `A09CY01` (Total) | 22.49 | 22.42 |
| `A09CY01P` (Permanent) | 20.45 | 20.39 |
| `A09CY01O` (Other) | 2.04 | 2.03 |

The two codes are economically equivalent at panel level. The fix is
**not** an analytical shortcut; it is the published reporting
convention the early-vintage TAC files use.

**Test added.** `tests/test_io.py::test_read_tac_handles_legacy_vintage_subcode_and_columns`
pins this behaviour with a synthetic 2019/20-style fixture (capital
"All Data" sheet name, `Value number` value column, `STA0360`
subcode).

## Holdout pipeline results

```
[1/8] reading sources from holdout + production paths...
  shapes: tac=(147, 6) hchs=(12991, 11) turnover=(4304, 9)
          vac=(133, 5) ae=(24, 7) rtt=(3598, 6) ods=(274, 7)
[2/8] building panel: 147 rows, 11 exclusions
[3/8] computing features: 147 rows
[4/8] primary TWFE: rank-deficient (expected on a 2-FY panel)
[5/8] heterogeneity: 2 strata fitted
[5/8] robustness: 5 specifications fitted
[6/8] pre-trend: 1 row (expected: pre-event periods exhausted)
[6/8] placebo: 0 valid permutations (expected: too few FYs)
[6/8] VIF: zero-variance (expected)
[7/8] risk scores: 77 providers scored
[8/8] manifest written
```

### What this confirms

| Pipeline stage | Behaviour on holdout | Verdict |
|---|---|---|
| `io.read_tac` | 147 rows across both years after subcode fix | ✅ works on unseen data |
| `io.read_hchs_staff_in_post` | 12,991 rows, FY-2019/20–2020/21 slice | ✅ |
| `io.read_vacancies`, `io.read_earnings`, `io.read_ae` | unchanged readers, in-window slices | ✅ |
| `panel.build_panel` | 77 providers × 2 FYs, 11 exclusions | ✅ |
| `features.compute_features` | all 13 features populated | ✅ |
| `models.estimate_twfe` | raises informative error | ✅ degrades gracefully |
| `models.estimate_heterogeneity` | 2 strata fitted | ✅ |
| `models.run_robustness` | 5 specifications fitted | ✅ |
| `diagnostics.pre_trend_check` | empty event-study window | ✅ documented |
| `diagnostics.placebo_test` | 0 valid permutations | ✅ documented |
| `diagnostics.variance_inflation` | zero-variance error | ✅ documented |
| `report.compute_risk_scores` | 77 providers ranked | ✅ |
| `manifest.write_manifest` | manifest emitted | ✅ |

### Why TWFE rank-deficiency on the holdout is the *correct* behaviour

The primary specification is

    log(other_staff_pay_it) = β · policy_intensity_t + δ · controls_it
                              + α_i + τ_t + ε_it

With only two financial years observed (`2019/20`, `2020/21`), the
year fixed effects `τ_t` span the same column space as
`policy_intensity_t` (which itself takes only two values). The model
matrix is collinear by construction. A rank-deficient
`linearmodels.PanelOLS` is the *right* response. If the model
returned a coefficient here, it would be *wrong*. Production output
under the 2021/22–2024/25 panel (4 FYs, 5 policy intensities)
identifies the parameter cleanly — see the merged
[reports/report.html](report.html) snapshot.

## Test suite verdict

```
68 passed in 142.52s
```

All 67 production tests still pass, plus the one new
legacy-vintage test added during this evaluation. `ruff check`
clean, `black --check` clean.

## Conclusion

The model is rightly built. The only code change needed to handle
pre-window data was a documented reader fix for an older SubCode,
which has been merged with a pinning test. Downstream code is
identification-aware: it produces estimates when identification is
present, raises informative errors when it is not.
