from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import BaseIndicatorScript


class IndicatorScriptRegistry:
    """
    @brief Maps a stable key to an indicator script class, so the UI can list
    what's available and build one on demand.

    @details
    Registration is explicit — scripts are registered from
    `BinanceBotModule.register()`, the same place command/query handlers are
    bound, rather than by scanning the filesystem for classes. A directory
    scan would make "what's installed" depend on import side effects and
    silently pick up half-finished files; an explicit list is greppable and
    reviewable. The trade-off (writing a script but forgetting to register it)
    is covered by a guard test instead.

    Deliberately has no interface/Protocol: it has exactly one implementation
    and nothing swaps it out. The DI-bound interfaces in this codebase
    (IMarketDataRepository, IExchangeClient) exist because they genuinely have
    alternative implementations — adding one here would be ceremony.
    """

    def __init__(self) -> None:
        self._scripts: dict[str, type[BaseIndicatorScript]] = {}

    def register(self, key: str, script_cls: type[BaseIndicatorScript]) -> None:
        """
        @param key Stable identifier used by the UI and in chart curve names.
        @raises ValueError if the key is already taken — silently overwriting
        would make two scripts fight over one key depending on import order.
        """
        if key in self._scripts:
            raise ValueError(
                f"Indicator script key {key!r} is already registered to "
                f"{self._scripts[key].__name__}"
            )
        self._scripts[key] = script_cls

    def create(
        self, key: str, params: Mapping[str, Any] | None = None
    ) -> BaseIndicatorScript:
        """
        @brief Builds a fresh script instance.
        @param params Values for the parameters the script declares via
        `input_*()` in setup() (BOT-044). None uses every declared default.
        A key the script never declares raises, rather than being ignored —
        see BaseIndicatorScript.__init__.
        @details Always a new instance — indicators carry warm-up state and
        have no reset(), so a fresh run needs a fresh object (the same reason
        BOT-020 rejected IIndicator.reset()).
        """
        script_cls = self._scripts.get(key)
        if script_cls is None:
            raise KeyError(f"No indicator script registered under key {key!r}")
        return script_cls(params)

    def available(self) -> Mapping[str, type[BaseIndicatorScript]]:
        """Returns a copy, so a caller iterating this can't mutate the registry."""
        return dict(self._scripts)
