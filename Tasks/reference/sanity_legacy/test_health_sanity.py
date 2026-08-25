"""
@brief Sanity test for HealthExtension integration.

@details
Verifies that after booting the real application, HealthCheckQuery resolves
cleanly and returns expected component health statuses.
"""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.main import create_app
from sagittarius_engine.extensions.health.health_check_query import (
    HealthCheckQuery,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "src",
    "config",
)


def test_health_check_query_resolves_and_executes() -> None:
    """Assert HealthCheckQuery is registered and executes without error."""
    config_manager = ConfigManager()
    config_manager.load_json(os.path.join(_CONFIG_DIR, "app_config.json"))

    app = create_app(config_manager)
    app.boot()

    try:
        health_query = app.context.container.resolve(HealthCheckQuery)
        assert health_query is not None
        result = health_query.execute()
        assert isinstance(result, dict)
        assert "status" in result
        assert "components" in result
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "ok"
    finally:
        app.stop()
