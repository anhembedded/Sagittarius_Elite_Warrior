"""`BOT-195`: the booted application registers the terminal-aware text renderer.

The renderer's own tests build their subject; this one asks the graph `create_app()`
really builds, so a composition root that went back to the plain registry fails here
(`CS-003`). No network: bindings resolve lazily."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.terminal_report_text import (
    TerminalAwareTextRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def test_the_text_format_of_the_booted_app_is_terminal_aware_and_json_is_not():
    formats = create_app(ConfigManager()).container.resolve(IReportFormats)  # type: ignore[type-abstract]

    assert isinstance(formats.get("text"), TerminalAwareTextRenderer)
    assert isinstance(formats.get("json"), JsonReportRenderer)
