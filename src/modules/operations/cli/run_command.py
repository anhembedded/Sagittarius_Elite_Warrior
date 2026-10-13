"""`main.py run`, start to stop (`EPIC-038D`).

The entry point has already taken the lock (`3` otherwise) and built the app without
booting it; this is everything after, in the order that keeps money safe:

  1. refuse what can be refused without touching the exchange - a bad flag (`2`), an
     unavailable host signal (`2`), `--resume-recovering` with no alert channel and no
     acknowledgement (`5`), a mainnet `--start-planned` the operator did not confirm (`2`);
  2. the pre-flight (`PreflightGate`), **before the bots are restored**: restoring a
     bot reads the exchange and may cancel orders, which a machine whose clock or key
     is wrong must not do. A failure is its own exit code (`4`, `5`, `6`; decision D9);
  3. wire the host: start-up steps, stop policy, signal source, health cadence (the
     snapshot's interval and state, the probes before it, the health line after it);
  4. listen for signals, boot the app (modules restore, then the host serves), wait,
     drain, stop the app. Whatever happens, the signals are given back and the app stops.

An exception ends the process with status 1 (`run_command`): there is no retry here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IHealthProbeTable,
    IPreflightCheckTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.host_signals import (
    HostSignalUnavailableError,
    NullHostSignal,
    sd_notify_host_signal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.hosted_run_host import (
    HostedRunHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.leave_orders_resting import (
    LeaveOrdersResting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.stop_bots_first import (
    StopBotsFirst,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bots_status_read import (
    read_bot_status,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    CadenceHostHealth,
    HealthCadence,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line_logger import (
    HealthLineLogger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_probes import (
    HealthProbes,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    ReportRecoveringBots,
    ResumeRecoveringBots,
    StartPlannedBots,
    WarnWhenNoAlertChannel,
    mainnet_resume_refusal,
    mainnet_start_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_gate import (
    PreflightGate,
    PreflightPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host import (
    RunHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    RunHostParts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    HostSignalName,
    RunOptions,
    StopPolicyName,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_signal import (
    IHostSignal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_step import (
    IHostStep,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    IShutdownPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)

if TYPE_CHECKING:
    from sagittarius_engine import App

logger = logging.getLogger("App.Operations.Host")

#: Why a silent resume needs a typed acknowledgement (DESIGN §3, decision O2).
_NO_ALERT_FOR_RESUME = (
    "--resume-recovering resumes bots with nobody watching, and no alert channel carries "
    "bot events yet (EPIC-036B). Nothing was started. Use it once bot events reach you, "
    "or type --i-accept-silent-failures to say you accept that a halt will be silent."
)


class RunCommand:
    def __init__(
        self, app: App, options: RunOptions, signals: IShutdownSignalSource
    ) -> None:
        self._app = app
        self._options = options
        self._signals = signals
        self._container = app.container
        self._dispatcher = self._container.resolve(ICommandDispatcher)
        self._plan = self._container.resolve(IBotPlan)
        self._alerts = self._container.resolve(IAlertChannels)

    def execute(self) -> CliOutcome | None:
        refusal = self._refusal_before_preflight()
        if refusal is not None:
            return refusal
        host_signal = self._host_signal()
        if isinstance(host_signal, CliOutcome):
            return host_signal
        policy = (
            PreflightPolicy.SKIP
            if self._options.skip_preflight
            else PreflightPolicy.ENFORCE
        )
        refusal = self._preflight_gate().admit(PreflightScope(), policy)
        if refusal is not None:
            return refusal
        self._serve(self._build_host(host_signal))
        return None

    # --- what is refused before anything is touched ------------------------

    def _refusal_before_preflight(self) -> CliOutcome | None:
        options = self._options
        if (
            options.resume_recovering
            and not options.accept_silent_failures
            and not self._alerts.carries_bot_events()
        ):
            return CliOutcome(ExitCode.CONFIGURATION, _NO_ALERT_FOR_RESUME)
        message = self._unconfirmed_mainnet_refusal()
        return None if message is None else CliOutcome(ExitCode.USAGE, message)

    def _unconfirmed_mainnet_refusal(self) -> str | None:
        """Decision O8: real money is started or resumed only for the venue the operator typed."""
        options = self._options
        if not (options.start_planned or options.resume_recovering):
            return None
        bots = read_bot_status(self._dispatcher).bots
        if options.start_planned:
            message = mainnet_start_refusal(bots, self._plan, options.confirm_venue)
            if message is not None:
                return message
        if options.resume_recovering:
            return mainnet_resume_refusal(bots, options.confirm_venue)
        return None

    def _host_signal(self) -> IHostSignal | CliOutcome:
        if self._options.host_signal is HostSignalName.NONE:
            return NullHostSignal()
        try:
            return sd_notify_host_signal()
        except HostSignalUnavailableError as unavailable:
            return CliOutcome(ExitCode.USAGE, str(unavailable))

    def _preflight_gate(self) -> PreflightGate:
        runner = PreflightRunner(
            self._container.resolve(IPreflightCheckTable).descriptors(),
            self._container,
        )
        return PreflightGate(runner)

    # --- the host -----------------------------------------------------------

    def _build_host(self, host_signal: IHostSignal) -> RunHost:
        options = self._options
        cadence = self._container.resolve(HealthCadence)
        cadence.configure(options.health_interval_s, HostState.BOOTING)
        probes = HealthProbes(
            self._container.resolve(IHealthProbeTable), self._container
        )
        cadence.add_before(probes.run)
        cadence.add_after(HealthLineLogger(self._container.resolve(IProcessMemory)))
        policy = self._policy()
        logger.info(
            "[run] stop policy %s, stop timeout %.0f s, health every %d s, pre-flight %s, "
            "start-planned %s, resume-recovering %s, host signal %s",
            policy.name,
            options.stop_timeout_s,
            options.health_interval_s,
            "skipped" if options.skip_preflight else "enforced",
            options.start_planned,
            options.resume_recovering,
            options.host_signal.value,
        )
        return RunHost(
            RunHostParts(
                signals=self._signals,
                policy=policy,
                host_signal=host_signal,
                health=CadenceHostHealth(cadence),
                steps=self._steps(),
                stop_timeout_s=options.stop_timeout_s,
            )
        )

    def _policy(self) -> IShutdownPolicy:
        if self._options.on_stop is StopPolicyName.STOP_BOTS:
            return StopBotsFirst(self._dispatcher)
        return LeaveOrdersResting(self._dispatcher)

    def _steps(self) -> tuple[IHostStep, ...]:
        options = self._options
        steps: list[IHostStep] = [
            WarnWhenNoAlertChannel(self._alerts),
            ReportRecoveringBots(self._dispatcher),
        ]
        if options.resume_recovering:
            steps.append(ResumeRecoveringBots(self._dispatcher, options.confirm_venue))
        if options.start_planned:
            steps.append(
                StartPlannedBots(self._plan, self._dispatcher, options.confirm_venue)
            )
        return tuple(steps)

    def _serve(self, host: RunHost) -> None:
        """Listen, boot, wait, drain, stop. The app is stopped and the signals given back whatever happens.

        The signals are held until the app has stopped: a second Ctrl-C while the workers close
        is absorbed rather than left to kill the process half-way through."""
        self._app.context.hosted_services.register(HostedRunHost(host))
        host.listen()
        try:
            self._app.boot()
            host.wait_for_stop()
            host.drain()
        except BaseException as failure:
            host.fail(type(failure).__name__)
            raise
        finally:
            host.end()
            self._app.stop()
            host.release()
