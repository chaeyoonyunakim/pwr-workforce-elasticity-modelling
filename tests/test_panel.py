"""Panel assembly contract tests."""

from __future__ import annotations

import pandas as pd
import pytest

from pwr_elasticity import panel


def test_build_panel_is_currently_a_stub() -> None:
    empty = pd.DataFrame()
    with pytest.raises(NotImplementedError):
        panel.build_panel(empty, empty, empty, empty, empty, empty, empty)


def test_exclusions_log_is_currently_a_stub() -> None:
    with pytest.raises(NotImplementedError):
        panel.provider_exclusions({})
