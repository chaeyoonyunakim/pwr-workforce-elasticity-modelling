"""Model diagnostics — residual analysis, pre-trend tests, placebos, VIF.

See ``plan/plan.md`` §T7 for acceptance criteria and the pre-trend
threshold around the September 2022 expenditure-ceiling re-introduction.
"""

from __future__ import annotations

import pandas as pd


def residual_diagnostics(features: pd.DataFrame, fitted_values: pd.Series) -> pd.DataFrame:
    """Compute residual plots and leverage / influence statistics.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame used for fitting.
    fitted_values : pandas.Series
        Model predictions aligned to ``features.index``.

    Returns
    -------
    pandas.DataFrame
        One row per observation with ``residual``, ``standardised_residual``,
        ``leverage``, ``cook_distance``.
    """
    raise NotImplementedError


def pre_trend_check(features: pd.DataFrame, event_year: str = "2022/23") -> pd.DataFrame:
    """Test parallel pre-trends around a policy event.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame.
    event_year : str
        Financial year in which the policy event came into force.

    Returns
    -------
    pandas.DataFrame
        Event-study coefficients and confidence intervals by lead/lag.
    """
    raise NotImplementedError


def placebo_test(features: pd.DataFrame, n_iterations: int = 1_000, seed: int = 0) -> pd.DataFrame:
    """Construct a null treatment via random reshuffling of policy years.

    Parameters
    ----------
    features : pandas.DataFrame
        Feature frame.
    n_iterations : int, default ``1000``
        Number of placebo iterations.
    seed : int, default ``0``
        Deterministic seed for reproducibility.

    Returns
    -------
    pandas.DataFrame
        Distribution of placebo elasticities; the actual estimate should
        lie in the tails.
    """
    raise NotImplementedError


def variance_inflation(features: pd.DataFrame) -> pd.DataFrame:
    """Compute variance-inflation factors for the covariate set."""
    raise NotImplementedError
