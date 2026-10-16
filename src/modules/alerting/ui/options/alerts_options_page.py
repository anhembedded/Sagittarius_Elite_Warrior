"""The factory behind `alerting`'s page of Tools → Options (`EPIC-036D1`).

Named by a `Deferred` in `module.py`, so `contribute()` imports no widget.
The presenter is the page and holds its view; the shell holds the page.
"""

from __future__ import annotations

from sagittarius_engine.interfaces.i_container import IContainer

from .alerts_settings_presenter import AlertsSettingsPresenter
from .alerts_settings_view import AlertsSettingsView


def build_alerts_options_page(container: IContainer) -> AlertsSettingsPresenter:
    return AlertsSettingsPresenter(AlertsSettingsView(), container)
