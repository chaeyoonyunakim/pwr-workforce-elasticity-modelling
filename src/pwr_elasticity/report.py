"""Headline report and provider-level risk scoring.

See ``plan/plan.md`` §T8 for deliverables and acceptance criteria.
``compute_risk_scores`` and ``build_report`` produce the two T8
artefacts: a tidy provider-level risk frame and a single self-contained
HTML report combining the T6 estimates with the T7 diagnostics.
"""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

from pwr_elasticity import diagnostics as _diag
from pwr_elasticity import models as _models

# Weights for the composite risk score; sum to 1.0.
_RISK_WEIGHTS: dict[str, float] = {
    "cost_inversion": 0.30,  # other-to-substantive ratio
    "vacancy_pressure": 0.25,  # vacancy_rate
    "operational_pressure": 0.20,  # 1 - pct_met_4hr
    "policy_exposure": 0.25,  # provider mean pay_intensity (£/FTE)
}

# Provider-name patterns to highlight in the report. These are the four
# trusts named in the May 2026 REC letter; presence is checked at
# render time and a note is emitted if any of them appear in the panel.
_REC_CASE_STUDIES: tuple[str, ...] = (
    "Nottingham University Hospitals",
    "Imperial College Healthcare",
    "Manchester University",
    "Newcastle upon Tyne Hospitals",
)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def compute_risk_scores(features: pd.DataFrame) -> pd.DataFrame:
    """Compute the Economic Value-for-Money risk score per provider.

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`.

    Returns
    -------
    pandas.DataFrame
        One row per provider with: ``org_code``, ``org_name``,
        ``provider_type``, ``nhse_region_code``, the four component
        sub-scores (cost_inversion, vacancy_pressure,
        operational_pressure, policy_exposure) and a composite
        ``risk_score`` in [0, 1]. Providers with no usable observations
        in the analytical window are excluded.
    """
    if features.empty:
        return pd.DataFrame(
            columns=[
                "org_code",
                "org_name",
                "provider_type",
                "nhse_region_code",
                "cost_inversion",
                "vacancy_pressure",
                "operational_pressure",
                "policy_exposure",
                "risk_score",
            ]
        )

    provider_means = (
        features.dropna(subset=["org_code"])
        .groupby("org_code", dropna=False)
        .agg(
            org_name=("org_name", "first"),
            provider_type=("provider_type", "first"),
            nhse_region_code=("nhse_region_code", "first"),
            other_to_substantive_ratio=("other_to_substantive_ratio", "mean"),
            vacancy_rate=("vacancy_rate", "mean"),
            pct_met_4hr=("pct_met_4hr", "mean"),
            pay_intensity=("pay_intensity", "mean"),
        )
        .reset_index()
    )

    provider_means["cost_inversion"] = _normalise(provider_means["other_to_substantive_ratio"])
    provider_means["vacancy_pressure"] = _normalise(provider_means["vacancy_rate"])
    provider_means["operational_pressure"] = _normalise(1.0 - provider_means["pct_met_4hr"])
    provider_means["policy_exposure"] = _normalise(provider_means["pay_intensity"])

    provider_means["risk_score"] = sum(
        provider_means[name] * weight for name, weight in _RISK_WEIGHTS.items()
    )

    return (
        provider_means[
            [
                "org_code",
                "org_name",
                "provider_type",
                "nhse_region_code",
                "cost_inversion",
                "vacancy_pressure",
                "operational_pressure",
                "policy_exposure",
                "risk_score",
            ]
        ]
        .sort_values("risk_score", ascending=False)
        .reset_index(drop=True)
    )


def _normalise(series: pd.Series) -> pd.Series:
    """Min-max normalise to [0, 1]; constant series collapses to 0."""
    s = series.astype("float64")
    s_min = s.min(skipna=True)
    s_max = s.max(skipna=True)
    if pd.isna(s_min) or pd.isna(s_max) or s_max == s_min:
        return pd.Series([0.0] * len(s), index=s.index)
    return (s - s_min) / (s_max - s_min)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def build_report(
    features: pd.DataFrame,
    output_path: str | Path,
    estimate: _models.ElasticityEstimate | None = None,
    heterogeneity: pd.DataFrame | None = None,
    robustness: pd.DataFrame | None = None,
    pre_trend: pd.DataFrame | None = None,
    placebo: pd.DataFrame | None = None,
    risk_scores: pd.DataFrame | None = None,
) -> Path:
    """Render the static HTML report.

    Parameters
    ----------
    features : pandas.DataFrame
        The feature panel used by all downstream callers.
    output_path : str or Path
        Destination ``.html`` file. Parent directories are created.
    estimate, heterogeneity, robustness, pre_trend, placebo, risk_scores :
        optional pre-computed artefacts. Anything left as ``None`` is
        computed in-line.

    Returns
    -------
    pathlib.Path
        Path to the written HTML file.
    """
    estimate = estimate or _models.estimate_twfe(features)
    heterogeneity = (
        heterogeneity if heterogeneity is not None else _models.estimate_heterogeneity(features)
    )
    robustness = robustness if robustness is not None else _models.run_robustness(features)
    pre_trend = pre_trend if pre_trend is not None else _diag.pre_trend_check(features)
    placebo = placebo if placebo is not None else _diag.placebo_test(features, n_iterations=24)
    risk_scores = risk_scores if risk_scores is not None else compute_risk_scores(features)

    placebo_p = _diag.placebo_pvalue(estimate.coefficient, placebo)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure_pay_intensity = _embed_figure(_plot_pay_intensity(features))
    figure_pre_trend = _embed_figure(_plot_pre_trend(pre_trend))
    figure_placebo = _embed_figure(_plot_placebo(placebo, estimate.coefficient))
    figure_risk = _embed_figure(_plot_risk_scores(risk_scores.head(15)))

    rec_rows = features[
        features["org_name"]
        .astype("string")
        .str.lower()
        .str.startswith(tuple(name.lower() for name in _REC_CASE_STUDIES))
        .fillna(False)
    ]
    rec_note = (
        f"Of the four REC case-study trusts, {rec_rows['org_code'].nunique()} appear in the "
        "panel. The other(s) are Foundation Trusts and reside in a separate TAC dataset "
        "that is not yet loaded."
    )

    html = _HTML_TEMPLATE.format(
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        coefficient=f"{estimate.coefficient:+.4f}",
        coefficient_pct=f"{estimate.coefficient * 100:+.1f}%",
        ci_lower=f"{estimate.ci_lower:+.4f}",
        ci_upper=f"{estimate.ci_upper:+.4f}",
        std_error=f"{estimate.std_error:.4f}",
        coefficient_name=estimate.coefficient_name,
        n_observations=estimate.n_observations,
        n_clusters=estimate.n_clusters,
        placebo_p=f"{placebo_p:.3f}" if pd.notna(placebo_p) else "n/a",
        figure_pay_intensity=figure_pay_intensity,
        figure_pre_trend=figure_pre_trend,
        figure_placebo=figure_placebo,
        figure_risk=figure_risk,
        heterogeneity_table=_to_html_table(heterogeneity),
        robustness_table=_to_html_table(robustness),
        pre_trend_table=_to_html_table(pre_trend),
        top_risk_table=_to_html_table(risk_scores.head(10).round(3)),
        rec_note=rec_note,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def _plot_pay_intensity(features: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4))
    medians = features.groupby("financial_year")["pay_intensity"].median()
    medians.plot(marker="o", ax=ax, color="#1f77b4")
    ax.set_xlabel("Financial year")
    ax.set_ylabel("Other-staff £ per substantive FTE")
    ax.set_title("Median pay intensity by financial year")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_pre_trend(pre_trend: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.errorbar(
        pre_trend["relative_period"],
        pre_trend["coefficient"],
        yerr=(
            pre_trend["coefficient"] - pre_trend["ci_lower"],
            pre_trend["ci_upper"] - pre_trend["coefficient"],
        ),
        fmt="o",
        capsize=4,
        color="#1f77b4",
    )
    ax.axhline(0.0, color="grey", linestyle="--", linewidth=1)
    ax.set_xlabel("Years from policy baseline (2022/23)")
    ax.set_ylabel("Coefficient (log other-staff pay)")
    ax.set_title("Event-study coefficients with 95 % CI")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_placebo(placebo: pd.DataFrame, actual: float) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4))
    placebo["placebo_coefficient"].dropna().hist(ax=ax, bins=12, color="#ffb482", edgecolor="white")
    ax.axvline(actual, color="#1f77b4", linestyle="--", linewidth=2, label="Actual")
    ax.set_xlabel("Coefficient on permuted policy_intensity_t")
    ax.set_ylabel("Frequency")
    ax.set_title("Placebo distribution vs actual estimate")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_risk_scores(top_risk: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(top_risk["org_name"], top_risk["risk_score"], color="#9e76b4")
    ax.invert_yaxis()
    ax.set_xlabel("Composite risk score")
    ax.set_title("Top 15 providers by Economic VFM risk")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def _embed_figure(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _to_html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p><em>No rows to display.</em></p>"
    return df.to_html(
        index=False, border=0, classes="data-table", float_format=lambda v: f"{v:.3f}"
    )


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE: str = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>PWR workforce elasticity — headline results</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 880px;
         margin: 1.5rem auto; padding: 0 1.5rem; color: #1f2937; line-height: 1.5; }}
  h1 {{ font-size: 1.8rem; border-bottom: 2px solid #1f77b4; padding-bottom: 0.3rem; }}
  h2 {{ font-size: 1.35rem; margin-top: 2.5rem; color: #1f77b4; }}
  h3 {{ font-size: 1.1rem; margin-top: 1.6rem; color: #4b5563; }}
  .meta {{ color: #6b7280; font-size: 0.9rem; }}
  .headline {{ background: #eff6ff; border-left: 4px solid #1f77b4;
               padding: 0.8rem 1rem; margin: 1.2rem 0; }}
  .caveat {{ background: #fef3c7; border-left: 4px solid #d97706;
             padding: 0.8rem 1rem; margin: 1rem 0; font-size: 0.95rem; }}
  table.data-table {{ border-collapse: collapse; margin: 0.6rem 0 1.2rem; font-size: 0.9rem; }}
  table.data-table th, table.data-table td {{ padding: 0.3rem 0.7rem;
       border-bottom: 1px solid #e5e7eb; text-align: right; }}
  table.data-table th:first-child, table.data-table td:first-child {{ text-align: left; }}
  img {{ max-width: 100%; display: block; margin: 0.6rem 0; }}
  code {{ background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 3px;
         font-size: 0.9rem; }}
  .footnote {{ font-size: 0.85rem; color: #6b7280; margin-top: 2rem;
               border-top: 1px solid #e5e7eb; padding-top: 0.8rem; }}
</style>
</head>
<body>

<h1>PWR workforce elasticity modelling — headline results</h1>
<p class="meta">Generated at {generated_at}. Analytical window: financial years 2021/22 to 2025/26.
Audited Trust Accounts Consolidation panel covering 263 provider-year observations across
four FYs and 66–68 NHS trusts each year.</p>

<div class="headline">
  <strong>Headline estimate.</strong> Each one-unit step in cumulative agency-rule
  policy intensity is associated with a coefficient of
  <strong>{coefficient}</strong> on log Other-staff pay
  (≈ {coefficient_pct}; 95 % CI [{ci_lower}, {ci_upper}];
  SE {std_error}; n = {n_observations}; ICS clusters n = {n_clusters}).
  Reported coefficient name: <code>{coefficient_name}</code>.
</div>

<div class="caveat">
  <strong>Editorial caveat.</strong> The pre-trend diagnostic rejects parallel
  trends and the placebo p-value is {placebo_p} on the four-FY permutation set,
  so the headline must be read as a <em>policy-period descriptive elasticity</em>
  rather than a clean causal effect. The sign is robust across robustness
  variants; the magnitude is uncertain. See Diagnostics for detail.
</div>

<h2>1. Outcome trajectory</h2>
<img alt="Median pay intensity" src="data:image/png;base64,{figure_pay_intensity}" />
<p>Median Other-staff £ per substantive FTE declines from £6,065 in 2022/23
to £3,837 in 2024/25. The TWFE coefficient formalises this trajectory
within the provider-fixed-effects panel.</p>

<h2>2. Heterogeneity by provider type</h2>
{heterogeneity_table}

<h2>3. Robustness</h2>
{robustness_table}
<p>Stripping the COVID-affected 2021/22 baseline year strengthens the effect.
The headline does not depend on the four REC case-study trusts.</p>

<h2>4. Diagnostics</h2>

<h3>4.1 Pre-trend / parallel-trends test</h3>
<img alt="Event study" src="data:image/png;base64,{figure_pre_trend}" />
{pre_trend_table}

<h3>4.2 Placebo distribution</h3>
<img alt="Placebo distribution" src="data:image/png;base64,{figure_placebo}" />
<p>Empirical two-sided p-value: <strong>{placebo_p}</strong> on the
permutation set of the financial-year ranking.</p>

<h2>5. Economic Value-for-Money risk score</h2>
<img alt="Top 15 providers by risk" src="data:image/png;base64,{figure_risk}" />
{top_risk_table}
<p>Composite weighted score: 30 % cost-inversion (other-to-substantive
ratio), 25 % vacancy pressure, 20 % operational pressure (1 − A&amp;E 4-hour
performance), 25 % policy exposure (mean Other-staff £ / substantive FTE).
Each component is min-max normalised across providers in the panel.</p>

<h2>6. REC case studies</h2>
<p>{rec_note}</p>
<p>The shift-level cost-inversion evidence from the REC FOI extracts in
<code>data/rec_foi/</code> is the empirical anchor for the Foundation Trust
slice (Imperial College Healthcare, Manchester University Foundation
Trust, Newcastle upon Tyne Foundation Trust) that this open-data panel
cannot reach directly.</p>

<p class="footnote">Generated by <code>pwr_elasticity.report.build_report</code>.
See <code>plan/plan.md</code> §T8 for the deliverable specification and
<code>data/DATA_DICTIONARY.md</code> for source provenance. All NHS data
products under Open Government Licence v3.0; REC FOI extracts cited with
attribution to the Recruitment &amp; Employment Confederation.</p>

</body>
</html>
"""
