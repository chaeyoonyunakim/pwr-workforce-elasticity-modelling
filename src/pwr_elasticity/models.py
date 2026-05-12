"""Elasticity estimators.

See ``plan/plan.md`` §T6 for the four sub-specifications (TWFE primary,
Random Forest non-linearity diagnostic, heterogeneity by provider type
and ICB, robustness).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ElasticityEstimate:
    """Container for a single elasticity estimate with its confidence interval.

    Attributes
    ----------
    specification : str
        Identifier for the model specification (e.g. ``"twfe_primary"``).
    coefficient : float
        Estimated elasticity (``β``).
    std_error : float
        Standard error of the coefficient.
    ci_lower : float
        Lower bound of the 95 % confidence interval.
    ci_upper : float
        Upper bound of the 95 % confidence interval.
    n_observations : int
        Number of provider-year observations entering the regression.
    n_clusters : int
        Number of clusters for the cluster-robust SE.
    """

    specification: str
    coefficient: float
    std_error: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    n_clusters: int


def estimate_twfe(features: pd.DataFrame, cluster: str = "icb_code") -> ElasticityEstimate:
    """Fit the two-way fixed-effects primary specification.

    Model:
        ``log(bank_pay_it) = β·log(agency_pay_it) + γ·policy_intensity_t
                            + δ·controls_it + α_i + τ_t + ε_it``

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`.
    cluster : str, default ``"icb_code"``
        Column used for cluster-robust standard errors.

    Returns
    -------
    ElasticityEstimate
        Headline elasticity ``β`` with 95 % CI.
    """
    raise NotImplementedError


def estimate_rf_nonlinearity(features: pd.DataFrame) -> pd.DataFrame:
    """Random Forest diagnostic for non-linearity in the bank-agency relationship.

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`.

    Returns
    -------
    pandas.DataFrame
        Partial-dependence values for ``log(agency_pay)`` and
        ``policy_intensity_t``, plus SHAP values per observation
        for interpretability.
    """
    raise NotImplementedError


def estimate_heterogeneity(features: pd.DataFrame) -> pd.DataFrame:
    """Re-estimate the TWFE model stratified by provider type and ICB.

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`.

    Returns
    -------
    pandas.DataFrame
        One :class:`ElasticityEstimate` per stratum, in long format.
    """
    raise NotImplementedError


def run_robustness(features: pd.DataFrame) -> pd.DataFrame:
    """Run the robustness suite specified in plan §T6d.

    Variants: levels (not logs); drop COVID-affected 2021/22; drop the
    four REC case-study trusts; cluster at provider level instead of ICB.
    """
    raise NotImplementedError
