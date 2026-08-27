"""`EPIC-013F` — the Backtest View is a named choice, read once at bootstrap.

@details Before this, `main_window.py` registered `lambda: BackTestView()`:
the choice was a code edit rather than configuration, and the lambda had no
return type, so nothing said what the router was allowed to do with what it
got back. These tests pin both halves — the choice, and the contract.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.ports import (
    IBacktestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.view_factory import (
    DEFAULT_BACKTEST_VIEW_KEY,
    BacktestViewKey,
    build_backtest_view,
    resolve_backtest_view_key,
)


class _Config:
    """Just the one `get` the factory uses.

    @details Not a `MagicMock`: a mock returns a `Mock` for any key, so a
    factory that read the *wrong* config key would still look like it worked.
    """

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = values or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


def test_an_unconfigured_install_gets_the_default_view() -> None:
    assert resolve_backtest_view_key(_Config()) is DEFAULT_BACKTEST_VIEW_KEY


def test_the_configured_view_is_the_one_chosen() -> None:
    """Reads the real config key, so renaming it fails here rather than
    silently falling back forever."""
    config = _Config({ConfigKeys.BACKTEST_VIEW.value: BacktestViewKey.QT_WIDGETS.value})

    assert resolve_backtest_view_key(config) is BacktestViewKey.QT_WIDGETS


def test_an_unknown_view_falls_back_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A typo in `user_config.json` must not leave the user with no app — and
    must not be silent either (`logging-rule.md` §2)."""
    config = _Config({ConfigKeys.BACKTEST_VIEW.value: "qml"})

    with caplog.at_level(logging.WARNING, logger="App.BacktestViewFactory"):
        key = resolve_backtest_view_key(config)

    assert key is DEFAULT_BACKTEST_VIEW_KEY
    assert any("qml" in record.getMessage() for record in caplog.records)


def test_a_valid_choice_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """The counterpart, so the warning stays evidence of something wrong."""
    config = _Config({ConfigKeys.BACKTEST_VIEW.value: BacktestViewKey.QT_WIDGETS.value})

    with caplog.at_level(logging.WARNING, logger="App.BacktestViewFactory"):
        resolve_backtest_view_key(config)

    assert caplog.records == []


@pytest.mark.usefixtures("qapp")
def test_every_buildable_view_satisfies_the_declared_contract() -> None:
    """The factory's return type must be true of what it actually returns.

    @details Loops over the enum rather than naming one member: a View added
    to `BacktestViewKey` without satisfying `IBacktestView` fails here, which
    is the only mechanism that would catch it — `presentation/` is outside
    the `mypy` gate (`pyproject.toml`, `EPIC-002A`).
    """
    for key in BacktestViewKey:
        config = _Config({ConfigKeys.BACKTEST_VIEW.value: key.value})

        view = build_backtest_view(config)

        assert isinstance(view, IBacktestView), key
