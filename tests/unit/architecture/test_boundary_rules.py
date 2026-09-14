"""The boundary policy, pinned row by row (HLD §6.1 table, first row).

Pure: no file system. Each row is one sentence of the rule turned into an
example; a change to `rules.py` that is not reflected here is a policy
change nobody wrote down.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.rules import (
    import_is_allowed,
)


@pytest.mark.parametrize(
    ("importing", "imported", "allowed"),
    [
        # --- legacy layers (architecture-rule §3) ---------------------------
        ("domain.trading.order", "application.ports.i_cqrs", False),
        ("application.use_cases.x.handler", "infrastructure.binance.client", False),
        ("application.use_cases.x.handler", "domain.trading.order", True),
        ("presentation.ui.screens.x.presenter", "infrastructure.binance.client", False),
        (
            "presentation.ui.screens.x.presenter",
            "application.use_cases.x.handler",
            True,
        ),
        ("infrastructure.binance.client", "presentation.ui.x", False),
        ("infrastructure.binance.client", "application.ports.i_x", True),
        # --- strangler period: legacy → new tree only through contracts/core/support
        (
            "presentation.ui.screens.x.presenter",
            "modules.market_data.contracts.i_sync",
            True,
        ),
        (
            "presentation.ui.screens.x.presenter",
            "modules.market_data.application.sync",
            False,
        ),
        ("application.use_cases.x.handler", "core.vo.symbol", True),
        # --- the new tree never imports the legacy tree ---------------------
        ("modules.market_data.application.sync", "domain.market_data.kline", False),
        ("core.contracts.i_place_host", "presentation.ui.x", False),
        # --- module ↔ module only through contracts; core imports only core --
        (
            "modules.trading.application.x",
            "modules.market_data.contracts.i_klines",
            True,
        ),
        (
            "modules.trading.application.x",
            "modules.market_data.application.sync",
            False,
        ),
        ("modules.trading.ui.panel", "support.ui_kit.page_shell", True),
        ("modules.trading.application.x", "support.ui_kit.page_shell", False),
        (
            "modules.trading.application.x",
            "support.binance_gateway.contracts.i_gateway",
            True,
        ),
        ("core.contracts.i_place_host", "support.ui_kit.page_shell", False),
        ("support.ui_kit.page_shell", "core.contracts.i_place_host", True),
        ("support.ui_kit.page_shell", "modules.trading.contracts.i_session", False),
        ("shell.modules", "modules.trading.module", True),
        ("shell.modules", "modules.trading.application.x", False),
        # --- config/ is vocabulary: everyone reads it, it reads nobody -------
        ("domain.trading.order", "config.config_keys", True),
        ("shell.dev_mode", "config.config_keys", True),
        ("modules.trading.application.x", "config.config_keys", True),
        ("config.config_keys", "domain.trading.order", False),
        # --- only an entry point may call into the shell ---------------------
        ("presentation.ui.app_bootstrapper", "shell.app_config", True),
        (
            "presentation.ui.screens.trading.trading_presenter",
            "shell.app_config",
            False,
        ),
        ("application.use_cases.x.handler", "shell.modules", False),
        # --- the shell is Main: during the strangler period it wires the old
        #     tree too, and the baseline file keeps that finite ---------------
        ("shell.legacy_screens", "presentation.ui.registry", True),
        ("shell.screen_wiring", "presentation.ui.registry", True),
        # --- outside the tree: never a violation ----------------------------
        ("domain.trading.order", "sagittarius_engine.domain.base_event", True),
        ("domain.trading.order", "PySide6.QtCore", True),
    ],
)
def test_rule_table(importing: str, imported: str, allowed: bool) -> None:
    assert import_is_allowed(importing, imported) is allowed
