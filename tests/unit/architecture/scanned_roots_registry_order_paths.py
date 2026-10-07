"""The registry rows of the guards that keep every order on its one path.

Split from `scanned_roots_registry.py` when that file reached the 400-line
ceiling (`EPIC-034I`); the registry spreads `ORDER_PATH_GUARDS` into `GUARDS`,
so nothing that reads the registry changes. Same shape, same rules: register
the directories a guard *scans*.
"""

from __future__ import annotations

ORDER_PATH_GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "tests/unit/architecture/test_only_the_session_factory_constructs_binance_client.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    (
        "tests/unit/architecture/test_only_the_factory_constructs_futures_trading_client.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    (
        "tests/unit/architecture/test_only_the_factory_constructs_spot_trading_client.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    (
        "tests/unit/architecture/test_only_the_venue_assembly_constructs_venue_adapters.py",
        (("src", "*.py"),),
    ),
    (
        "tests/unit/architecture/test_venue_addressed_handlers_resolve_their_venue.py",
        (
            ("src/modules/trading/application", "handler.py"),
            ("src/modules/strategy/application/use_cases", "handler.py"),
        ),
    ),
    (
        "tests/unit/architecture/test_order_submission_mode_live_is_restricted.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    ("tests/unit/architecture/test_every_order_is_reconciled.py", (("src", "*.py"),)),
    # `BUG-172` — a chart is its venue's own market: who may read the setting,
    # and which trees must not take the default venue's ports.
    (
        "tests/unit/architecture/test_a_venue_screen_charts_its_own_venues_market.py",
        (
            ("src", "*.py"),
            ("src/modules/trading/ui/desk", "*.py"),
            ("src/modules/bots", "*.py"),
        ),
    ),
)
