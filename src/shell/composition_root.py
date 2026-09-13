"""Building the object graph — Clean Architecture's *Main* component.

`create_app()` lived in `src/main.py`, which meant the headless entry point
owned the wiring and the GUI entry point imported it from there. Neither of them
is the composition root; **this** is (HLD §3.1, SDD boot step 3). Both entry
points now call it, and when Phase 1 starts moving contexts into `src/modules/`,
`MODULES` in `shell/modules.py` is the list that changes — not an entry point.

This file is the one place in `src/shell/` allowed to import the legacy tree,
because that is what a composition root does: it knows every component so that
no component has to know another. `test_module_boundaries.py` records it in
`COMPOSITION_ROOT_FILES`, beside `main.py` and `binance_bot_module.py`, and the
imports leave with the legacy tree in Phase 4.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.binance_bot_module import BinanceBotModule
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capability_validator_extension import (
    EngineCapabilityValidatorExtension,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    AssetValidatorExtension,
)
from Sagittarius_Elite_Warrior.src.shell.module_registration import register_modules
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES
from sagittarius_engine import App
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.extensions.logger.logger_module import LoggerExtension
from sagittarius_engine.extensions.thread_manager.thread_manager_module import (
    ThreadManagerExtension,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.logging.std_logger import StdLogger
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.middleware.pydantic_validation_middleware import (
    PydanticValidationMiddleware,
)


def create_app(config_manager: ConfigManager) -> App:
    container = StdLibContainer()

    # EPIC-008G §4 — bus nhận logger tường minh, không để `None`.
    #
    # `EPIC-008C` đã khiến bus không-logger vẫn báo được lỗi handler (nó tự lùi
    # về `FallbackLogger` dùng `logging` chuẩn), nên đây KHÔNG phải sửa lỗi mất
    # log. Cái nó mua: lỗi handler đi qua **đúng `ILogger` của app** — cùng
    # formatter, cùng file log mà `ci-local.ps1`'s "Run Log Scan" đọc — thay vì
    # rơi vào `logging` chuẩn ngoài file đó.
    #
    # Dựng `StdLogger` ở đây, trước `App`, là có chủ đích: bus tồn tại trước khi
    # `LoggerExtension` chạy `register()`. Lát nữa extension sẽ dựng một
    # `StdLogger` nữa cho DI — không nhân đôi log, vì **cả hai bọc cùng một**
    # `logging.getLogger("App")`; lần dựng sau chỉ dọn rồi gắn lại đúng bộ
    # handler theo cùng config.
    event_bus = MemoryEventBus(StdLogger(config_manager))

    # Register core ports
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    app = App(container, event_bus)

    # Load Framework Extensions
    app.use(DependencyValidatorExtension(["PySide6", "pyqtgraph", "sqlalchemy"]))
    # Presence first (above), then capability: the engine can be installed and
    # still predate an API this app's source calls, which is the failure
    # `pip show` cannot see and that has misled this project four times —
    # see `engine_capabilities.py` for the list and BOT-133.
    app.use(EngineCapabilityValidatorExtension())
    app.use(AssetValidatorExtension())

    app.use(LoggerExtension())
    app.use(ThreadManagerExtension())

    # Load Domain Module (Registers Repositories & UseCases)
    app.use(BinanceBotModule())

    # The bounded contexts, in the order `shell/modules.py` lists them — that
    # list is the mechanism, not the Engine's dependency sort (SDD boot step 3).
    # `register_modules` enforces both `register()` rules as each one goes in
    # (no resolve, no second claim of one abstract type). Empty until PR 0.4
    # brings `market_data`; `BinanceBotModule` above still carries every
    # context during the strangler period.
    register_modules(app, MODULES)

    # Load Health Check Diagnostic Extension after domain modules
    app.use(HealthExtension())

    # Register Global Validation Middleware
    app.use_middleware(PydanticValidationMiddleware(container))

    return app
