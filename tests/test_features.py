"""Feature engineering contract tests."""

from __future__ import annotations

import pandas as pd
import pytest

from pwr_elasticity import features


def test_compute_features_is_currently_a_stub() -> None:
    with pytest.raises(NotImplementedError):
        features.compute_features(pd.DataFrame())


def test_encode_policy_intensity_is_currently_a_stub() -> None:
    with pytest.raises(NotImplementedError):
        features.encode_policy_intensity(pd.Series([], dtype="string"))
