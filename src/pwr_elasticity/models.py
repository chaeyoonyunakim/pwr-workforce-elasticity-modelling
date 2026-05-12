"""Elasticity estimators.

See ``plan/plan.md`` §T6 for the four sub-specifications (TWFE primary,
Random Forest non-linearity diagnostic, heterogeneity by provider type
and ICB, robustness).

Adaptation note. The plan §T6 primary specification was originally
``log(bank_pay) = β·log(agency_pay) + γ·policy_intensity + δ·controls``,
but Trust Accounts Consolidation does not publish the Bank-versus-Agency
split (see ``data/DATA_DICTIONARY.md`` §3.1). The model here therefore
estimates the elasticity of non-substantive (Other staff) pay with
respect to policy intensity, with substantive pay carried as a control
to net out the within-provider scale effect:

    log(other_staff_pay_it) = β·policy_intensity_t
                            + δ_1·log(substantive_pay_it)
                            + δ_2·vacancy_rate_it
                            + δ_3·turnover_rate_it
                            + δ_4·pct_met_4hr_it
                            + α_i + τ_t + ε_it

``β`` is the headline coefficient: the elasticity of provider Other-staff
pay with respect to a one-unit step in cumulative agency-rule intensity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import partial_dependence

# Default columns
_OUTCOME: str = "log_other_staff_pay"
_CONTROLS: tuple[str, ...] = (
    "policy_intensity_t",
    "log_substantive_pay",
    "vacancy_rate",
    "turnover_rate",
    "pct_met_4hr",
)
_RF_FEATURES: tuple[str, ...] = (
    "log_substantive_pay",
    "policy_intensity_t",
    "vacancy_rate",
    "turnover_rate",
    "pct_met_4hr",
    "staff_in_post_fte",
)
_RANDOM_SEED: int = 0


@dataclass(frozen=True)
class ElasticityEstimate:
    """Container for a single elasticity estimate with its confidence interval."""

    specification: str
    coefficient_name: str
    coefficient: float
    std_error: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    n_clusters: int


# ---------------------------------------------------------------------------
# T6a — primary TWFE specification
# ---------------------------------------------------------------------------


def estimate_twfe(
    features: pd.DataFrame,
    cluster: str = "ics_code",
    outcome: str = _OUTCOME,
    controls: tuple[str, ...] = _CONTROLS,
    time_effects: bool = False,
    drop_absorbed: bool = False,
) -> ElasticityEstimate:
    """Fit the primary panel specification — provider fixed effects by default.

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`. Must
        carry the columns referenced by ``outcome``, ``controls``,
        ``org_code``, ``financial_year`` and ``cluster``.
    cluster : str, default ``"ics_code"``
        Column used for cluster-robust standard errors.
    outcome, controls : optional overrides for sensitivity analysis.
    time_effects : bool, default ``False``
        With only four financial years in the panel, two-way fixed
        effects fully absorb the policy-intensity treatment variable
        (it varies only by year, by construction). The default
        therefore uses entity-effects only — the trade-off is that
        common time shocks are not removed; the robustness suite in
        :func:`run_robustness` re-fits with ``time_effects=True``
        and ``drop_absorbed=True`` as a sensitivity check.
    drop_absorbed : bool, default ``False``
        Pass-through to ``PanelOLS.fit``.

    Returns
    -------
    ElasticityEstimate
        Coefficient on ``policy_intensity_t`` (or its first non-absorbed
        substitute) with 95 % CI clustered on ``cluster``.
    """
    panel_df = _prepare_panel(features, outcome, controls, cluster)
    model = PanelOLS(
        dependent=panel_df[outcome],
        exog=panel_df[list(controls)],
        entity_effects=True,
        time_effects=time_effects,
        drop_absorbed=drop_absorbed,
    )
    res = model.fit(cov_type="clustered", clusters=panel_df[f"_{cluster}"])
    coefficient_name = (
        "policy_intensity_t" if "policy_intensity_t" in res.params.index else res.params.index[0]
    )
    return _to_estimate(res, "twfe_primary", coefficient_name, panel_df, cluster)


# ---------------------------------------------------------------------------
# T6b — Random Forest non-linearity diagnostic
# ---------------------------------------------------------------------------


def estimate_rf_nonlinearity(
    features: pd.DataFrame,
    outcome: str = _OUTCOME,
    rf_features: tuple[str, ...] = _RF_FEATURES,
    n_estimators: int = 400,
    seed: int = _RANDOM_SEED,
) -> pd.DataFrame:
    """Random Forest diagnostic for non-linearity in the policy-intensity response.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame from :func:`pwr_elasticity.features.compute_features`.
    outcome : str
        Outcome column (default ``log_other_staff_pay``).
    rf_features : tuple of str
        Features to feed the regressor.
    n_estimators : int
        Number of trees.
    seed : int
        Deterministic seed.

    Returns
    -------
    pandas.DataFrame
        Partial-dependence values across the grid of two key features
        (``policy_intensity_t`` and ``log_substantive_pay``), one row per
        ``(feature, grid_value)`` with the predicted ``log_other_staff_pay``.
    """
    frame = _select_complete_rows(features, [outcome, *rf_features])
    rf = RandomForestRegressor(
        n_estimators=n_estimators, random_state=seed, n_jobs=-1, min_samples_leaf=3
    )
    rf.fit(frame[list(rf_features)], frame[outcome])
    rows: list[dict[str, float | str]] = []
    for feat in ("policy_intensity_t", "log_substantive_pay"):
        if feat not in rf_features:
            continue
        pdp = partial_dependence(rf, frame[list(rf_features)], [feat], kind="average")
        values = pdp["grid_values"][0]
        predictions = pdp["average"][0]
        rows.extend(
            {"feature": feat, "grid_value": float(v), "predicted_outcome": float(p)}
            for v, p in zip(values, predictions, strict=False)
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# T6c — heterogeneity by provider_type and ICB
# ---------------------------------------------------------------------------


def estimate_heterogeneity(
    features: pd.DataFrame,
    by: str = "provider_type",
    cluster: str = "ics_code",
    outcome: str = _OUTCOME,
    controls: tuple[str, ...] = _CONTROLS,
    min_observations: int = 12,
) -> pd.DataFrame:
    """Re-estimate the TWFE primary spec stratified by ``by``.

    Parameters
    ----------
    by : str, default ``"provider_type"``
        Column to stratify on.
    min_observations : int
        Strata with fewer observations than this are skipped (the TWFE
        cannot identify the elasticity from a single year or single
        provider).

    Returns
    -------
    pandas.DataFrame
        One row per stratum: ``stratum``, ``coefficient``, ``std_error``,
        ``ci_lower``, ``ci_upper``, ``n_observations``, ``n_clusters``.
    """
    rows: list[dict[str, float | int | str]] = []
    for stratum, sub in features.groupby(by, dropna=False):
        if len(sub) < min_observations:
            continue
        try:
            est = estimate_twfe(sub, cluster=cluster, outcome=outcome, controls=controls)
        except Exception as exc:
            rows.append({"stratum": stratum, "error": str(exc)})
            continue
        rows.append(
            {
                "stratum": stratum,
                "coefficient_name": est.coefficient_name,
                "coefficient": est.coefficient,
                "std_error": est.std_error,
                "ci_lower": est.ci_lower,
                "ci_upper": est.ci_upper,
                "n_observations": est.n_observations,
                "n_clusters": est.n_clusters,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# T6d — robustness suite
# ---------------------------------------------------------------------------


def run_robustness(features: pd.DataFrame) -> pd.DataFrame:
    """Run the robustness suite specified in plan §T6d.

    Variants:

    1. ``levels`` — outcome in levels (``other_staff_pay_gbp``), not logs.
    2. ``drop_2021_22`` — drop the COVID-affected first FY of the window.
    3. ``drop_rec_trusts`` — drop the four REC case-study trusts (if
       present in the panel).
    4. ``cluster_at_provider`` — cluster standard errors at provider
       rather than ICB.

    Returns
    -------
    pandas.DataFrame
        One row per variant with the same schema as
        :class:`ElasticityEstimate`.
    """
    rows: list[dict[str, float | int | str]] = []

    # 1. levels
    rows.append(
        _estimate_as_row(
            features,
            specification="levels",
            outcome="other_staff_pay_gbp",
            controls=(
                "policy_intensity_t",
                "substantive_pay_gbp",
                "vacancy_rate",
                "turnover_rate",
                "pct_met_4hr",
            ),
        )
    )

    # 2. drop 2021/22
    rows.append(
        _estimate_as_row(
            features[features["financial_year"] != "2021/22"],
            specification="drop_2021_22",
        )
    )

    # 3. drop REC case-study trusts
    rec_trust_prefixes = (
        "nottingham university hospitals",
        "imperial college healthcare",
        "manchester university",
        "newcastle upon tyne hospitals",
    )
    is_case_study = (
        features["org_name"]
        .astype("string")
        .str.lower()
        .str.startswith(rec_trust_prefixes)
        .fillna(False)
    )
    rows.append(_estimate_as_row(features[~is_case_study], specification="drop_rec_trusts"))

    # 4. cluster at provider
    rows.append(_estimate_as_row(features, specification="cluster_at_provider", cluster="org_code"))

    # 5. two-way fixed effects (sensitivity) — policy_intensity is
    #    absorbed by time effects, so the reported coefficient is on
    #    the first non-absorbed control.
    rows.append(
        _estimate_as_row(
            features,
            specification="twfe_drop_absorbed",
            time_effects=True,
            drop_absorbed=True,
        )
    )

    return pd.DataFrame(rows)


def _estimate_as_row(
    features: pd.DataFrame,
    specification: str,
    cluster: str = "ics_code",
    outcome: str = _OUTCOME,
    controls: tuple[str, ...] = _CONTROLS,
    time_effects: bool = False,
    drop_absorbed: bool = False,
) -> dict[str, float | int | str]:
    try:
        est = estimate_twfe(
            features,
            cluster=cluster,
            outcome=outcome,
            controls=controls,
            time_effects=time_effects,
            drop_absorbed=drop_absorbed,
        )
    except Exception as exc:
        return {"specification": specification, "error": str(exc)}
    return {
        "specification": specification,
        "coefficient_name": est.coefficient_name,
        "coefficient": est.coefficient,
        "std_error": est.std_error,
        "ci_lower": est.ci_lower,
        "ci_upper": est.ci_upper,
        "n_observations": est.n_observations,
        "n_clusters": est.n_clusters,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prepare_panel(
    features: pd.DataFrame,
    outcome: str,
    controls: tuple[str, ...],
    cluster: str,
) -> pd.DataFrame:
    """Return a complete-cases panel indexed by (org_code, fy_start_year)."""
    needed = [outcome, *controls, "org_code", "financial_year", cluster]
    frame = _select_complete_rows(features, needed)
    frame = frame.copy()
    # PanelOLS demands a numeric or date-like time index. Convert
    # "YYYY/YY" to the FY-start integer (2021, 2022, ...).
    frame["fy_start_year"] = frame["financial_year"].str.split("/").str[0].astype("int64")
    frame[f"_{cluster}"] = frame[cluster]
    frame = frame.set_index(["org_code", "fy_start_year"])
    return frame


def _select_complete_rows(features: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Drop rows with NA in any of ``columns`` and cast to plain float dtypes."""
    available = [c for c in columns if c in features.columns]
    out = features.dropna(subset=available).copy()
    for c in available:
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype("float64")
    return out


def _to_estimate(
    fit_result,
    specification: str,
    coefficient_name: str,
    panel_df: pd.DataFrame,
    cluster: str,
) -> ElasticityEstimate:
    coef = float(fit_result.params[coefficient_name])
    se = float(fit_result.std_errors[coefficient_name])
    ci_lower = float(fit_result.conf_int().loc[coefficient_name, "lower"])
    ci_upper = float(fit_result.conf_int().loc[coefficient_name, "upper"])
    n_obs = int(fit_result.nobs)
    n_clusters = int(panel_df[f"_{cluster}"].nunique())
    return ElasticityEstimate(
        specification=specification,
        coefficient_name=coefficient_name,
        coefficient=coef,
        std_error=se,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        n_observations=n_obs,
        n_clusters=n_clusters,
    )


# Suppress NumPy long_long sign overflow warning specific to PanelOLS internals.
np.seterr(all="ignore")
