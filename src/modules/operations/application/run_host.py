"""The `run` host: serve until told to stop, then stop cleanly (`EPIC-038D`).

The host only sequences. It knows no bot, no exchange and no signal: it runs the
start-up steps it was given, installs the shutdown signal source, says
`SERVING`, waits, and when the first request to stop arrives it drains - runs
the stop policy under `--stop-timeout`, then lets the app close (`app.stop()`
closes the bots' workers, the module shutdown writes the last snapshot, the
entry point releases the lock) and the process exits 0.

@par The two signals
The first request to stop starts the drain. A second, while the drain is
waiting, skips the wait: the operator who presses the key twice has decided not
to wait, and the host says which bots it left. Neither is acted on in the signal
handler, which only counts: the work runs on the main thread when its wait
returns.

@par What the host does not do
It does not restart anything, retry anything or catch a crash. An unhandled
exception ends the process with status 1 and the service manager restarts it;
boot recovery then does what it does after any crash (`DESIGN` §6). A restart
loop in two layers hides failures.

@par Threads
`begin`, `wait_for_stop`, `drain`, `fail` and `end` are called from the main
thread, one after another. Only `_on_signal` can run at any moment, and it only
sets two events. The policy runs on a daemon worker so a stop that never
finishes cannot keep the process alive past the timeout.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_state_machine import (
    HostStateMachine,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_health import (
    IHostHealth,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_signal import (
    IHostSignal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_step import (
    IHostStep,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    BotLeftBehind,
    IShutdownPolicy,
    StopLedger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)

logger = logging.getLogger("App.Operations.Host")

#: How often a wait with no deadline looks up from `Event.wait`: a console's
#: Ctrl-C does not interrupt a bare wait on Windows, and the watchdog needs a beat.
WAIT_STEP_SECONDS = 0.25
#: How often the drain looks at the policy, the timeout and the second signal.
_DRAIN_STEP_SECONDS = 0.05


class RunHost:
    """`BOOTING -> SERVING -> DRAINING -> STOPPED`, or `FAILED` (`host_state_machine.py`).

    Not itself an Engine `IHostedService`: application code imports no Engine type.
    `HostedRunHost` (`adapters/`) is the `IHostedService` that calls `begin` and `end`.
    """

    def __init__(
        self,
        *,
        signals: IShutdownSignalSource,
        policy: IShutdownPolicy,
        host_signal: IHostSignal,
        health: IHostHealth,
        steps: Sequence[IHostStep],
        stop_timeout_s: float,
    ) -> None:
        self._signals = signals
        self._policy = policy
        self._host_signal = host_signal
        self._health = health
        self._steps = tuple(steps)
        self._stop_timeout_s = stop_timeout_s
        self._machine = HostStateMachine()
        self._stop_requested = threading.Event()
        self._hurry = threading.Event()
        self._signals_heard = 0
        self._listening = False
        self._ended = False

    @property
    def state(self) -> HostState:
        return self._machine.state

    def listen(self) -> None:
        """Start hearing requests to stop. Idempotent.

        The entry point calls this before the app boots: a SIGTERM that arrives while
        the bots are being restored is a request to stop, not a reason to be killed
        with the workers half-started. It is remembered and honoured the moment the
        host serves.
        """
        if self._listening:
            return
        self._listening = True
        self._signals.install(self._on_signal)

    def begin(self) -> None:
        """Run the steps, then serve. A step that raises fails the host and the error goes on."""
        self._health.set_state(HostState.BOOTING)
        self.listen()
        try:
            for step in self._steps:
                logger.info("[host] step %s", step.name)
                step.run()
        except BaseException as failure:
            self.fail(f"step failed: {type(failure).__name__}")
            # The Engine stops only the services that started, and this one did not.
            self.end()
            self.release()
            raise
        self._machine.move_to(HostState.SERVING)
        self._health.set_state(HostState.SERVING)
        self._health.publish_now()
        self._host_signal.ready()

    def wait_for_stop(self, timeout_s: float | None = None) -> bool:
        """Block until the first request to stop; `False` if `timeout_s` ran out first.

        With no deadline it wakes every `WAIT_STEP_SECONDS` to give the service
        manager's watchdog its beat.
        """
        if timeout_s is not None:
            return self._stop_requested.wait(timeout_s)
        while not self._stop_requested.wait(WAIT_STEP_SECONDS):
            self._host_signal.watchdog()
        return True

    def drain(self) -> None:
        """Run the stop policy under the timeout, or until a second signal."""
        if self._machine.state is not HostState.SERVING:
            return
        self._machine.move_to(HostState.DRAINING)
        self._health.set_state(HostState.DRAINING)
        self._health.publish_now()
        self._host_signal.stopping()
        ledger = StopLedger()
        give_up = threading.Event()
        done = threading.Event()
        logger.info(
            "[host] stop policy %s, up to %.0f s (a second signal does not wait)",
            self._policy.name,
            self._stop_timeout_s,
        )
        worker = threading.Thread(
            target=self._apply_policy,
            args=(ledger, give_up, done),
            name="RunHostStopPolicy",
            daemon=True,
        )
        worker.start()
        outcome = self._wait_for_policy(done)
        if outcome != "finished":
            give_up.set()
        self._report(outcome, ledger)

    def fail(self, reason: str) -> None:
        """An unrecoverable error: say so in the snapshot and the log. The process
        then exits 1; the host never retries."""
        if self._machine.is_final:
            return
        self._machine.move_to(HostState.FAILED, reason)
        self._health.set_state(HostState.FAILED)
        self._health.publish_now()

    def end(self) -> None:
        """The app is closing: say `STOPPED`. Harmless twice.

        The signals stay with the host: the workers are about to close, and an impatient
        second Ctrl-C then must be absorbed, not allowed to kill the process half-way
        through `app.stop()`. `release` gives them back once the app has stopped.
        """
        if self._ended:
            return
        self._ended = True
        if self._machine.state is HostState.DRAINING:
            self._machine.move_to(HostState.STOPPED)
            self._health.set_state(HostState.STOPPED)

    def release(self) -> None:
        """Hand the process's own signal handling back. Harmless twice, and before `listen`."""
        if self._listening:
            self._listening = False
            self._signals.restore()

    # --- internals ------------------------------------------------------------

    def _on_signal(self) -> None:
        self._signals_heard += 1
        self._stop_requested.set()
        if self._signals_heard > 1:
            self._hurry.set()

    def _apply_policy(
        self, ledger: StopLedger, give_up: threading.Event, done: threading.Event
    ) -> None:
        try:
            self._policy.apply(ledger, give_up)
        except Exception:
            logger.exception("[host] stop policy %s failed", self._policy.name)
        finally:
            done.set()

    def _wait_for_policy(self, done: threading.Event) -> str:
        deadline = time.monotonic() + self._stop_timeout_s
        while not done.wait(_DRAIN_STEP_SECONDS):
            if self._hurry.is_set():
                return "second signal"
            if time.monotonic() >= deadline:
                return "stop timeout"
        return "finished"

    def _report(self, outcome: str, ledger: StopLedger) -> None:
        left = ledger.left()
        if outcome == "finished" and not left:
            logger.info("[host] stop policy %s finished", self._policy.name)
            return
        if outcome == "finished":
            logger.warning(
                "[host] stop policy %s finished and left %s",
                self._policy.name,
                _describe(left),
            )
            return
        logger.warning(
            "[host] %s: not waiting any longer; left %s. The next start reads them from "
            "their files as RECOVERING",
            outcome,
            _describe(left) if left else "none named by the policy",
        )


def _describe(left: tuple[BotLeftBehind, ...]) -> str:
    return ", ".join(
        f"{bot.bot_id} ({bot.state}"
        + (
            ""
            if bot.resting_orders is None
            else f", {bot.resting_orders} orders resting"
        )
        + (f", {bot.note}" if bot.note else "")
        + ")"
        for bot in left
    )
