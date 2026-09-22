"""`EngineCapabilityValidatorExtension` — boot-time gate on the engine build.

@details The third pre-flight validator, beside the engine's own
`DependencyValidatorExtension` (is the package installed?) and this app's
`AssetValidatorExtension` (are the icons on disk?). Same shape as both, one
step further: the package can be installed and still be **too old**, which is
the case neither of the others can see and the one that has actually bitten
this project four times (`engine_capabilities.py` names them).

Ordering matters: presence must be checked before capability, so a completely
missing engine reports "not installed" rather than a confusing list of missing
attributes. `BOT-119` found this encoded only as `app.use()` call order plus an
English comment in `composition_root.py` — swapping the two calls broke nothing
that told you. `dependencies` below is what the engine's own topological sort
(`ExtensionManager._build_and_sort`) now enforces instead, by name, against the
engine's own `DependencyValidatorExtension`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, ClassVar

from sagittarius_engine.interfaces.i_extension import IExtension

from .engine_capabilities import (
    REQUIRED_ENGINE_CAPABILITIES,
    RequiredEngineCapability,
    find_missing_capabilities,
    format_missing_capabilities,
)

logger = logging.getLogger("App.EngineCapabilityValidator")

_PASSED_MESSAGE = (
    "Pre-flight engine check passed. Installed sagittarius_engine provides "
    "every API this app depends on."
)


class EngineCapabilityValidatorExtension(IExtension[Any]):
    """
    @brief Fails the boot with an actionable message when the installed
    engine build predates an API this app's source already calls.

    @param capabilities Override for tests; production uses the declared
        `REQUIRED_ENGINE_CAPABILITIES`.

    @details Exits rather than raising, matching `DependencyValidatorExtension`:
    the alternative is a `TypeError` surfacing later inside a widget
    constructor, which is precisely the misleading signature this exists to
    replace. Nothing downstream can recover from a stale engine anyway.
    """

    #: By name, since `DependencyValidatorExtension` lives in
    #: `sagittarius_engine`, not this app — `descriptor.name` for an
    #: undeclared-name extension defaults to its class name.
    dependencies: ClassVar[list[str]] = ["DependencyValidatorExtension"]

    def __init__(
        self,
        capabilities: tuple[
            RequiredEngineCapability, ...
        ] = REQUIRED_ENGINE_CAPABILITIES,
    ) -> None:
        self._capabilities = capabilities

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        missing = find_missing_capabilities(self._capabilities)
        if not missing:
            logger.info(_PASSED_MESSAGE)
            if getattr(context, "logger", None):
                context.logger.info(_PASSED_MESSAGE)
            return

        report = format_missing_capabilities(missing)
        logger.error(report)
        if getattr(context, "logger", None):
            context.logger.error(report)
        else:  # pragma: no cover - only when booted without a logger
            print(report)
        sys.exit(1)

    def shutdown(self, context: Any) -> None:
        pass
