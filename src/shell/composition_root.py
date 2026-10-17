"""Building the object graph — Clean Architecture's *Main* component.

`create_app()` lived in `src/main.py`, which meant the headless entry point
owned the wiring and the GUI entry point imported it from there. Neither of them
is the composition root; **this** is (HLD §3.1, SDD boot step 3). Both entry
points now call it, and when Phase 1 starts moving contexts into `src/modules/`,
`MODULES` in `shell/modules.py` is the list that changes — not an entry point.

This file is the one place in `src/shell/` allowed to import the legacy tree,
because that is what a composition root does: it knows every component so that
no component has to know another. `test_module_boundaries.py` records it in
`COMPOSITION_ROOT_FILES`, beside `main.py`, and (until `EPIC-025E` PR 4.4f-5
deleted it) `binance_bot_module.py`.

`EPIC-025E` PR 4.4f-5 inlined `binance_bot_module.py`'s last two
responsibilities directly here, since neither is owned by any one bounded
context: the shared core engine-adapter ports (`IEventPublisher`/
`IConfigReader`/`ICommandDispatcher` — `EPIC-008F`) and the indicator-script
registry. `_register_indicator_scripts()` below is that module's own
`_register_indicator_scripts()` verbatim, and the three engine-adapter
bindings sit inline in `create_app()` — they need no `register()`/`boot()`
split of their own, since `event_bus`, `config_manager` and `app` are already
resolved local variables here, not values a module would need to fetch from
a `RegisteringContainer` (`Docs/SDD/04_boot_and_configuration.md` §4).

Capability: Take the data root's single-instance lock before building the app (one writable copy per data root)
    Also: instance lock, single instance, second copy, read-only copy, instance.lock, data root access
    Use: acquire_instance_access
    User: src/main.py
    Status: stable
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    IHealthContributorTable,
    IHealthProbeTable,
    IPreflightCheckTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.command_dispatcher_adapter import (
    EngineCommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.config_reader_adapter import (
    EngineConfigReader,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_health_contributor import (
    EngineHealthContributor,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.ordered_health_extension import (
    OrderedHealthExtension,
)
from Sagittarius_Elite_Warrior.src.infrastructure.notifications.telegram_notification_channel import (
    TelegramNotificationChannel,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_probe import (
    FileLockInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.shell.cli_log_routing import CliLogRouting
from Sagittarius_Elite_Warrior.src.shell.cli_registry import CliRegistry
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.src.shell.config_writer import ConfigManagerWriter
from Sagittarius_Elite_Warrior.src.shell.dispatch_log_filter import (
    quiet_query_dispatch_outside_developer_mode,
)
from Sagittarius_Elite_Warrior.src.shell.logging_notifier import LoggingNotifier
from Sagittarius_Elite_Warrior.src.shell.module_registration import register_modules
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES, RegisteredModules
from Sagittarius_Elite_Warrior.src.shell.notification_event_handler import (
    NotificationEventHandler,
)
from Sagittarius_Elite_Warrior.src.shell.operations_registry import OperationsRegistry
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.dev_indicator_script import (
    DevIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_50_script import (
    Ema50Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_100_script import (
    Ema100Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_200_script import (
    Ema200Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_cross_script import (
    EmaCrossScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_ribbon_script import (
    EmaRibbonScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.macd_full_script import (
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)
from sagittarius_engine import App
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
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
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.middleware.pydantic_validation_middleware import (
    PydanticValidationMiddleware,
)


def _register_indicator_scripts(container: IContainer) -> None:
    """Registers all domain indicator scripts into IndicatorScriptRegistry."""
    script_registry = IndicatorScriptRegistry()
    script_registry.register("rsi_14", Rsi14Script)
    script_registry.register("ema_20", Ema20Script)
    script_registry.register("ema_50", Ema50Script)
    script_registry.register("ema_100", Ema100Script)
    script_registry.register("ema_200", Ema200Script)
    script_registry.register("macd_full", MacdFullScript)
    script_registry.register("ema_ribbon", EmaRibbonScript)
    script_registry.register("ema_cross", EmaCrossScript)
    script_registry.register("dev_showcase", DevIndicatorScript)
    container.singleton(IndicatorScriptRegistry, script_registry)


_logger = logging.getLogger("App.Instance")


def instance_lock_file() -> Path:
    """The lock file of the current data root (`EPIC-035H`)."""
    return data_root() / "state" / "instance.lock"


def acquire_instance_access() -> InstanceAccess:
    """Writable if this is the first copy of the app on the data root, else
    read-only (`EPIC-035H`). The two entry points call it once, before the
    object graph is built, and release the result at a clean exit; `create_app`
    and the UI's `build` take the answer as a parameter, so a test that builds
    the app in-process never contends for the lock, and the file lives under
    `data_root()` so two different roots (every test run has its own,
    `EPIC-030M`) never meet."""
    return InstanceAccess.acquire(instance_lock_file())


def read_only_instance_access() -> InstanceAccess:
    """Read-only by the caller's request, with no lock taken (`EPIC-038C`).

    For a command that only reads (`support/cli_host/command_access.py`): it
    must not be the writable copy, whose boot applies the restart rule to the
    bots, and it must not hold the lock `status` asks a host about."""
    return InstanceAccess.declined(
        "This command only reads: it shows what is there, and places, cancels "
        "and saves nothing."
    )


def _log_instance(instance: IInstanceAccess | None) -> None:
    if instance is not None and instance.read_only:
        _logger.info("[instance] read-only: %s", instance.reason)
    else:
        _logger.info("[instance] writable: no other copy holds the data root")


def create_app(
    config_manager: ConfigManager,
    instance: IInstanceAccess | None = None,
    cli_log: CliLogRouting | None = None,
) -> App:
    """Builds the object graph. `instance` says whether this copy of the app
    may trade (`EPIC-035H`): the entry points pass what `single_instance`
    decided; a run that is not the app's own (a test, a script) passes nothing
    and is writable, since it holds no data root against anyone. `cli_log`
    (`BOT-185`): a quiet read-only command's log goes to its file, warnings stay."""
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
    app_logger = StdLogger(config_manager)
    if cli_log is not None:
        cli_log.apply()
        cli_log.log_decision()
    # `BOT-178` — the Engine's per-query INFO line is developer detail.
    quiet_query_dispatch_outside_developer_mode(config_manager)
    # `EPIC-035H` — said here because the run log exists only from this point,
    # and a read-only copy is the one fact a reader of the log needs first.
    _log_instance(instance)
    event_bus = MemoryEventBus(app_logger)

    # Register core ports
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)
    container.singleton(
        IInstanceAccess,
        instance if instance is not None else InstanceAccess.unguarded(),
    )
    # `EPIC-025` PR 1.5b — the ability to *write* configuration, as a port.
    # `IConfig` has `set()` but not `save()`, which is why
    # `settings_presenter.py` downcasts to `ConfigManager` today; the Welcome
    # screen's developer-mode switch is the first caller to go through the
    # port instead, and the downcast retires with that screen (SDD §4).
    container.singleton(IConfigWriter, ConfigManagerWriter(config_manager))

    # `BUG-126` — the two failure paths `EPIC-008` §1 found unsubscribed get a
    # subscriber, at the one place the entry points pass through, rather than in
    # a screen. `EPIC-008G`'s answer was a Qt feed constructed *by a screen*, and
    # no screen ever constructed it: a UI slot that raised and a background task
    # that died still reached nobody. This one hears the background task; the UI
    # slot's event has a Qt type, so `add_gui_wiring` (`shell/gui_wiring.py`)
    # subscribes to it for the GUI entry point only (`EPIC-038A`). Registered as
    # a singleton so the graph owns it — `bus.on()` alone would keep it alive
    # through the bound handler, which is a lifetime nobody reading this file
    # could see.
    #
    # Before `boot()` on purpose: an extension that fails during `boot()` is
    # exactly the failure worth seeing, and a subscriber registered afterwards
    # would miss it.
    container.singleton(SystemFailureLog, SystemFailureLog(event_bus, app_logger))

    app = App(container, event_bus)

    # `EPIC-008F` — the Application layer talks to the engine only through
    # these three ports; the adapters are the only place naming `IEventBus`,
    # `IConfig` or `IDispatcher`. Bound inline here (not in a module's
    # `register()`) since no bounded context owns them, and `app.context`'s
    # `tasks`/`dispatcher` are already available at this point — populated by
    # `EngineContext.__init__` before any `register()`/`boot()` runs.
    container.singleton(ITaskManager, app.context.tasks)
    container.singleton(IEventPublisher, EngineEventPublisher(event_bus))
    # `EPIC-029F` (ADR O4) — modules register in `boot()`, the window asks.
    container.singleton(ICloseObjections, CloseObjections())
    # `BOT-169` — what a module tells the user goes through one port. A run
    # with no window logs it; the GUI entry point replaces this with the Qt
    # presenter before any screen is built.
    container.singleton(INotifier, LoggingNotifier())
    container.singleton(IConfigReader, EngineConfigReader(config_manager))
    container.singleton(
        ICommandDispatcher, EngineCommandDispatcher(app.context.dispatcher)
    )

    # `BOT-018` — the same "one place both entry points pass through" reasoning
    # as `SystemFailureLog` above, but after `boot()` would still be started:
    # unlike that subscriber, nothing here needs to see a boot-time failure,
    # and constructing it needs `IConfigReader` bound just above. The GUI
    # channel is added later, once a `MainWindow` exists to own it
    # (`app_bootstrapper.py`); the headless entry point never adds one, so it
    # gets Telegram delivery only, exactly as the task's own risk note expects
    # ("hỗ trợ gửi qua kênh ngoài khi app chạy headless/CLI").
    notification_handler = NotificationEventHandler(
        event_bus, app_logger, app.context.tasks
    )
    notification_handler.add_channel(
        TelegramNotificationChannel(container.resolve(IConfigReader), app_logger)
    )
    container.singleton(NotificationEventHandler, notification_handler)

    _register_indicator_scripts(container)

    # Load Framework Extensions. Only what every entry point needs is checked
    # here: a process with no window boots where Qt is not installed
    # (`EPIC-038A`); the GUI adds its Qt package check, its icon-asset
    # validator and the engine-build check (every API that one declares is the
    # Engine's Qt workbench) in `add_gui_wiring`.
    app.use(DependencyValidatorExtension(["sqlalchemy"]))

    app.use(LoggerExtension())
    if cli_log is not None:
        # The extension built a second `StdLogger`, which cleared the handlers.
        cli_log.apply()
    app.use(ThreadManagerExtension())

    # The bounded contexts, in the order `shell/modules.py` lists them — that
    # list is the mechanism, not the Engine's dependency sort (SDD boot step 3).
    # `register_modules` enforces both `register()` rules as each one goes in
    # (no resolve, no second claim of one abstract type).
    modules, _ = register_modules(app, MODULES)
    # The instances, for the entry point that will call `contribute()` after
    # `boot()` — see `RegisteredModules`' own docstring for why a second
    # instantiation there would contribute against nothing.
    container.singleton(RegisteredModules, RegisteredModules(tuple(modules)))

    # `EPIC-025` PR 1.3c-5 — every module declares the prompt commands it owns,
    # and the shell collects them. Registered under the *reading* port only:
    # `InteractiveShell` resolves `ICliCommandTable` and cannot declare, which
    # is the half of the inversion that keeps the collection single-sourced.
    cli_registry = CliRegistry()
    for module in modules:
        module.declare_cli(cli_registry)
    container.singleton(ICliCommandTable, cli_registry)

    # `EPIC-038F` — what every module contributes to running unattended (its
    # pre-flight checks). Registered under the *reading* port only, as the
    # command table is: `operations` reads the finished table and cannot add.
    operations_registry = OperationsRegistry()
    for module in modules:
        module.declare_operations(operations_registry)
    container.singleton(IPreflightCheckTable, operations_registry)
    # `EPIC-038C` — the health sections modules contribute to the snapshot, and
    # the Engine's own check, which the shell (not a module) declares because it
    # is the shell that composes the Engine's extensions.
    operations_registry.declare_health(
        HealthContributorDescriptor(
            "engine",
            lambda _resolver: EngineHealthContributor(container, app.context.event_bus),
            "shell",
        )
    )
    container.singleton(IHealthContributorTable, operations_registry)
    # `EPIC-038D` - the measurements the `run` host takes before each snapshot.
    container.singleton(IHealthProbeTable, operations_registry)

    # `EPIC-038B` — the output formats a report command offers (`--json`,
    # `--format`). A new format is one `register` call on this object; no
    # command and no parser changes.
    report_formats = ReportFormats.default()
    container.singleton(IReportFormats, report_formats)
    container.singleton(IReportPrinter, ReportPrinter(report_formats))

    # `EPIC-038C` — `status` asks whether some copy holds the data root, on the
    # lock file this module names and `InstanceAccess` takes.
    container.singleton(IInstanceProbe, FileLockInstanceProbe(instance_lock_file()))

    # `HealthCheckQuery`'s container sweep (engine `health_check_query.py`)
    # only finds what each bounded context's own `register()` already bound —
    # a real ordering constraint, not just a comment (BOT-119). This is what
    # keeps the health check correct regardless of where `app.use(health)`
    # ends up relative to the modules above; see `OrderedHealthExtension` for
    # why it is a typed subclass rather than a bare instance attribute.
    app.use(OrderedHealthExtension([module.module_id for module in modules]))

    # Register Global Validation Middleware
    app.use_middleware(PydanticValidationMiddleware(container))

    return app
