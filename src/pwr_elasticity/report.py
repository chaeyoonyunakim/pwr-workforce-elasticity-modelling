"""Headline report and provider-level risk scoring.

See ``plan/plan.md`` §T8 for deliverables and acceptance criteria.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def compute_risk_scores(features: pd.DataFrame, estimates: pd.DataFrame) -> pd.DataFrame:
    """Compute the provider-level Economic Value-for-Money risk score.

    Parameters
    ----------
    features : pandas.DataFrame
        Output of :func:`pwr_elasticity.features.compute_features`.
    estimates : pandas.DataFrame
        Heterogeneity estimates from
        :func:`pwr_elasticity.models.estimate_heterogeneity`.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``risk_score`` (float, 0–1),
        ``risk_components`` (struct: bank-agency inversion, vacancy rate,
        operational pressure, policy intensity).
    """
    raise NotImplementedError


def build_report(
    features: pd.DataFrame,
    estimates: pd.DataFrame,
    risk_scores: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Render the static HTML report to ``output_path``.

    Parameters
    ----------
    features, estimates, risk_scores : pandas.DataFrame
        Inputs from the upstream pipeline stages.
    output_path : str or Path
        Destination for the HTML report.

    Returns
    -------
    pathlib.Path
        Path to the written report.
    """
    raise NotImplementedError
