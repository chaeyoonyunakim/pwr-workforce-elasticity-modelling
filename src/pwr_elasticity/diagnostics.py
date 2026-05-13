"""Model diagnostics — residual analysis, pre-trend tests, placebos, VIF.

See ``plan/plan.md`` §T7. The pre-trend, placebo and VIF tests are the
safety net that decides whether the headline coefficient from
:mod:`pwr_elasticity.models` is admissible as a causal estimate or
should be flagged for escalation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from statsmodels.stats.outliers_influence import variance_inflation_factor

from pwr_elasticity import models as _models

_DEFAULT_OUTCOME: str = "log_other_staff_pay"
_DEFAULT_CONTROLS: tuple[str, ...] = (
    "policy_intensity_t",
    "log_substantive_pay",
    "vacancy_rate",
    "turnover_rate",
    "pct_met_4hr",
)


# ---------------------------------------------------------------------------
# T7a — residual diagnostics
# ---------------------------------------------------------------------------


def residual_diagnostics(
    features: pd.DataFrame,
    outcome: str = _DEFAULT_OUTCOME,
    controls: tuple[str, ...] = _DEFAULT_CONTROLS,
    cluster: str = "ics_code",
) -> pd.DataFrame:
    """Compute residual, standardised residual and leverage per observation.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame from :func:`pwr_elasticity.features.compute_features`.
    outcome, controls, cluster : str
        Match the primary TWFE specification used in
        :func:`pwr_elasticity.models.estimate_twfe`.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``fy_start_year``, ``residual``,
        ``standardised_residual``, ``fitted``, ``influence_flag``
        (``True`` where ``|standardised_residual| > 3``).
    """
    panel_df = _prepare(features, outcome, controls, cluster)
    model = PanelOLS(
        dependent=panel_df[outcome],
        exog=panel_df[list(controls)],
        entity_effects=True,
    )
    fit = model.fit(cov_type="clustered", clusters=panel_df[f"_{cluster}"])
    resid = fit.resids
    fitted = panel_df[outcome] - resid
    sigma = float(np.std(resid, ddof=1))
    residual_array = resid.to_numpy()
    fitted_array = fitted.to_numpy()
    out = pd.DataFrame(
        {
            "residual": residual_array,
            "standardised_residual": (residual_array / sigma if sigma > 0 else residual_array),
            "fitted": fitted_array,
        },
        index=resid.index,
    ).reset_index()
    out["influence_flag"] = out["standardised_residual"].abs() > 3.0
    return out


# ---------------------------------------------------------------------------
# T7b — pre-trend / event-study check
# ---------------------------------------------------------------------------


def pre_trend_check(
    features: pd.DataFrame,
    event_year: str = "2022/23",
    outcome: str = _DEFAULT_OUTCOME,
    cluster: str = "ics_code",
) -> pd.DataFrame:
    """Event-study coefficients around a chosen policy event year.

    For each financial year other than ``event_year`` (the omitted
    category), fit:

        outcome_it = Σ_τ γ_τ · 1{financial_year_it = τ}
                   + α_i + ε_it

    so the γ coefficients trace the within-provider deviation of the
    outcome from its level in the event year. Pre-event coefficients
    that are statistically indistinguishable from zero support the
    parallel-trends interpretation; a significant pre-event coefficient
    indicates the headline policy estimate is at risk.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame.
    event_year : str
        ``"YYYY/YY"`` label of the event-year baseline.
    outcome, cluster : as in :func:`residual_diagnostics`.

    Returns
    -------
    pandas.DataFrame
        One row per non-baseline FY: ``financial_year``,
        ``relative_period`` (negative pre-event, positive post-event),
        ``coefficient``, ``std_error``, ``ci_lower``, ``ci_upper``,
        ``significant`` (CI excludes zero).
    """
    needed = [outcome, "org_code", "financial_year", cluster]
    frame = _select(features, needed).copy()
    frame["fy_start_year"] = frame["financial_year"].str.split("/").str[0].astype("int64")
    frame[f"_{cluster}"] = frame[cluster]
    panel_df = frame.set_index(["org_code", "fy_start_year"])

    dummies = pd.get_dummies(panel_df["financial_year"], drop_first=False, dtype=float, prefix="fy")
    baseline_col = f"fy_{event_year}"
    if baseline_col in dummies.columns:
        dummies = dummies.drop(columns=[baseline_col])
    panel_df = pd.concat([panel_df, dummies], axis=1)

    model = PanelOLS(
        dependent=panel_df[outcome],
        exog=panel_df[dummies.columns.tolist()],
        entity_effects=True,
    )
    fit = model.fit(cov_type="clustered", clusters=panel_df[f"_{cluster}"])

    event_year_start = int(event_year.split("/", 1)[0])
    rows: list[dict[str, float | int | str | bool]] = []
    for col in dummies.columns:
        fy_label = col.removeprefix("fy_")
        fy_start = int(fy_label.split("/")[0])
        coef = float(fit.params[col])
        se = float(fit.std_errors[col])
        ci_lower = float(fit.conf_int().loc[col, "lower"])
        ci_upper = float(fit.conf_int().loc[col, "upper"])
        significant = (ci_lower > 0) or (ci_upper < 0)
        rows.append(
            {
                "financial_year": fy_label,
                "relative_period": fy_start - event_year_start,
                "coefficient": coef,
                "std_error": se,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "significant": significant,
            }
        )
    return pd.DataFrame(rows).sort_values("relative_period").reset_index(drop=True)


# ---------------------------------------------------------------------------
# T7c — placebo test on a reshuffled treatment
# ---------------------------------------------------------------------------


def placebo_test(
    features: pd.DataFrame,
    n_iterations: int = 200,
    seed: int = 0,
) -> pd.DataFrame:
    """Construct a null treatment via random reshuffling of policy years.

    For each iteration, the mapping from financial year to
    ``policy_intensity_t`` is randomly permuted within the in-window
    FYs, and the primary TWFE is re-fitted. The actual estimate should
    sit in the tails of the resulting placebo distribution.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame.
    n_iterations : int, default ``200``
        Number of permutations. The placebo p-value resolution is
        ``2/n_iterations`` for two-sided inference.
    seed : int
        Deterministic seed.

    Returns
    -------
    pandas.DataFrame
        Columns: ``iteration``, ``placebo_coefficient``. The actual
        estimate is **not** included; downstream code should compare
        against :func:`pwr_elasticity.models.estimate_twfe`.
    """
    rng = np.random.default_rng(seed)
    fys = sorted(features["financial_year"].dropna().unique())
    rows: list[dict[str, int | float]] = []
    for i in range(n_iterations):
        permuted_intensity = rng.permutation(len(fys))
        mapping = dict(zip(fys, permuted_intensity, strict=False))
        placebo = features.copy()
        placebo["policy_intensity_t"] = placebo["financial_year"].map(mapping).astype("Int64")
        try:
            est = _models.estimate_twfe(placebo)
            rows.append({"iteration": i, "placebo_coefficient": est.coefficient})
        except Exception:
            rows.append({"iteration": i, "placebo_coefficient": np.nan})
    return pd.DataFrame(rows)


def placebo_pvalue(actual_coefficient: float, placebo: pd.DataFrame) -> float:
    """Two-sided empirical p-value of the actual estimate against the placebo."""
    valid = placebo["placebo_coefficient"].dropna()
    if valid.empty:
        return float("nan")
    more_extreme = (valid.abs() >= abs(actual_coefficient)).sum()
    return float(more_extreme / len(valid))


# ---------------------------------------------------------------------------
# T7d — Variance Inflation Factors
# ---------------------------------------------------------------------------


def variance_inflation(
    features: pd.DataFrame,
    columns: tuple[str, ...] = _DEFAULT_CONTROLS,
) -> pd.DataFrame:
    """Compute VIF for each covariate in the candidate set.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame.
    columns : tuple of str
        Covariates to score.

    Returns
    -------
    pandas.DataFrame
        Columns: ``feature``, ``vif``. A VIF above ~5 is the
        conventional concern threshold; above ~10 typically warrants
        action (drop or combine).
    """
    frame = _select(features, list(columns)).copy()
    matrix = frame[list(columns)].astype("float64").to_numpy()
    rows = [
        {"feature": columns[i], "vif": float(variance_inflation_factor(matrix, i))}
        for i in range(matrix.shape[1])
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prepare(
    features: pd.DataFrame,
    outcome: str,
    controls: tuple[str, ...],
    cluster: str,
) -> pd.DataFrame:
    needed = [outcome, *controls, "org_code", "financial_year", cluster]
    frame = _select(features, needed).copy()
    frame["fy_start_year"] = frame["financial_year"].str.split("/").str[0].astype("int64")
    frame[f"_{cluster}"] = frame[cluster]
    return frame.set_index(["org_code", "fy_start_year"])


def _select(features: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    available = [c for c in columns if c in features.columns]
    out = features.dropna(subset=available).copy()
    for c in available:
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype("float64")
    return out
