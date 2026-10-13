"""The `run` host: serve until told to stop, then stop cleanly (`EPIC-038D`).

The host only sequences. It knows no bot, no exchange and no signal: it runs the
start-up steps it was given, installs the shutdown signal source, says
`SERVING`, waits, and when the first request to stop arrives it drains - runs
the stop policy under `--stop-timeout`, then lets the app close (`app.stop()`
closes the bots' workers, the module shutdown writes the last snapshot, the
entry point releases the lock) and the process exits 0.

@par The two signals
The first request to stop starts the drain. A second, at any moment after it - while
the policy runs, while the probes are read, while `app.stop()` closes the workers -
ends the process: the operator who presses the key twice has decided not to wait, and
the host says which bots it left and what it was doing. Neither is acted on in the
signal handler, which does one thing: it appends to a list. A Python handler runs on
the main thread between two bytecodes, including inside `Event.wait` while that call
holds the event's lock; a handler that takes any lock (an `Event.set`, a log record)
can deadlock against its own thread, and the host would never drain. The main thread
therefore waits by sleeping in short steps and looking at the list, and a second
thread, started when the drain begins, acts on the second signal.

@par One deadline
The whole stop - the policy under `--stop-timeout`, then the probes, the module
shutdowns and each worker's close - must end within `--stop-timeout` plus
`STOP_GRACE_SECONDS`. Past that the watchdog thread leaves, and says why. A service
unit's `TimeoutStopSec` must be larger than that sum.

@par What the host does not do
It does not restart anything, retry anything or catch a crash. An unhandled
exception ends the process with status 1 and the service manager restarts it;
boot recovery then does what it does after any crash (`DESIGN` §6). A restart
loop in two layers hides failures.

@par Threads
`begin`, `wait_for_stop`, `drain`, `fail`, `end` and `release` are called from the main
thread, one after another. `_on_signal` can run at any moment and touches nothing but
a list. The policy runs on a daemon worker so a stop that never finishes cannot keep the
process alive past the timeout, and the watchdog is a daemon thread too.
"""

from __future__ import annotations

import logging
import threading
import time

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_state_machine import (
    HostStateMachine,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    RunHostParts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    BotLeftBehind,
    StopLedger,
)

logger = logging.getLogger("App.Operations.Host")

#: How often a wait looks up to see whether a signal arrived, and how often the service
#: manager's watchdog gets its beat while the host serves.
WAIT_STEP_SECONDS = 0.25
#: How often the drain looks at the policy and the watchdog at the deadline and the signals.
_DRAIN_STEP_SECONDS = 0.05


class RunHost:
    """`BOOTING -> SERVING -> DRAINING -> STOPPED`, or `FAILED` (`host_state_machine.py`).

    Not itself an Engine `IHostedService`: application code imports no Engine type.
    `HostedRunHost` (`adapters/`) is the `IHostedService` that calls `begin` and `end`.
    """

    def __init__(self, parts: RunHostParts) -> None:
        self._parts = parts
        self._machine = HostStateMachine()
        #: One entry per signal heard. A list, because `append` is the one thing a handler
        #: may do: no lock, no allocation it cannot afford, no lost update.
        self._heard: list[None] = []
        self._moves = threading.Lock()
        self._ledger = StopLedger()
        self._phase = "starting"
        self._listening = False
        self._ended = False
        self._released = False

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
        self._parts.signals.install(self._on_signal)

    def begin(self) -> None:
        """Run the steps, then serve. A step that raises fails the host and the error goes on.

        A step that trades (resumes or starts a bot) is skipped once a stop has been
        requested: the host would open orders and then drain with them resting."""
        health = self._parts.health
        health.set_state(HostState.BOOTING)
        self.listen()
        try:
            for step in self._parts.steps:
                if step.trades and self._heard:
                    logger.info(
                        "[host] step %s skipped: a request to stop arrived before the host "
                        "served, so nothing is resumed or started",
                        step.name,
                    )
                    continue
                logger.info("[host] step %s", step.name)
                step.run()
        except BaseException as failure:
            self.fail(f"step failed: {type(failure).__name__}")
            # The Engine stops only the services that started, and this one did not.
            self.end()
            self.release()
            raise
        self._machine.move_to(HostState.SERVING)
        health.set_state(HostState.SERVING)
        health.publish_now()
        self._parts.host_signal.ready()

    def wait_for_stop(self, timeout_s: float | None = None) -> bool:
        """Block until the first request to stop; `False` if `timeout_s` ran out first.

        With no deadline it also gives the service manager's watchdog its beat each step.
        Sleeping, not `Event.wait`: nothing here holds a lock a signal handler could need."""
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while not self._heard:
            if deadline is None:
                time.sleep(WAIT_STEP_SECONDS)
                if not self._heard:
                    self._parts.host_signal.watchdog()
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(WAIT_STEP_SECONDS, remaining))
        return True

    def drain(self) -> None:
        """Run the stop policy under the timeout; the watchdog bounds all that follows."""
        if self._machine.state is not HostState.SERVING:
            return
        parts = self._parts
        with self._moves:
            self._machine.move_to(HostState.DRAINING)
        self._phase = "running the stop policy"
        self._start_watchdog()
        parts.health.set_state(HostState.DRAINING)
        parts.health.publish_now()
        parts.host_signal.stopping()
        give_up = threading.Event()
        done = threading.Event()
        logger.info(
            "[host] stop policy %s, up to %.0f s, the whole stop within %.0f s "
            "(a second signal does not wait)",
            parts.policy.name,
            parts.stop_timeout_s,
            parts.stop_timeout_s + parts.stop_grace_s,
        )
        worker = threading.Thread(
            target=self._apply_policy,
            args=(give_up, done),
            name="RunHostStopPolicy",
            daemon=True,
        )
        worker.start()
        outcome = self._wait_for_policy(done)
        if outcome != "finished":
            give_up.set()
        self._report(outcome)

    def fail(self, reason: str) -> None:
        """An unrecoverable error: say so in the snapshot and the log. The process
        then exits 1; the host never retries."""
        if self._machine.is_final:
            return
        with self._moves:
            self._machine.move_to(HostState.FAILED, reason)
        self._parts.health.set_state(HostState.FAILED)
        self._parts.health.publish_now()

    def end(self) -> None:
        """The app is closing: say `STOPPED`. Harmless twice.

        The signals stay with the host, and so does the watchdog: the workers are about
        to close, and a second Ctrl-C then ends the process (named) instead of being
        lost or left to the default action. `release` gives the signals back once the
        app has stopped.
        """
        if self._ended:
            return
        self._ended = True
        self._phase = "closing the app's workers"
        with self._moves:
            moved = self._machine.state is HostState.DRAINING
            if moved:
                self._machine.move_to(HostState.STOPPED)
        if moved:
            self._parts.health.set_state(HostState.STOPPED)

    def release(self) -> None:
        """The app has stopped: hand the process's signal handling back and stand the
        watchdog down. Harmless twice, and before `listen`."""
        self._released = True
        if self._listening:
            self._listening = False
            self._parts.signals.restore()

    # --- internals ------------------------------------------------------------

    def _on_signal(self) -> None:
        # Async-signal-safe on purpose; see the class docstring. Nothing else belongs here.
        self._heard.append(None)

    def _start_watchdog(self) -> None:
        deadline = (
            time.monotonic() + self._parts.stop_timeout_s + self._parts.stop_grace_s
        )
        threading.Thread(
            target=self._watch_the_stop,
            args=(deadline,),
            name="RunHostStopWatchdog",
            daemon=True,
        ).start()

    def _watch_the_stop(self, deadline: float) -> None:
        """Leave the process when the operator asks twice or the stop outlasts its deadline."""
        while not self._released:
            if len(self._heard) > 1:
                self._leave("second signal")
                return
            if time.monotonic() >= deadline:
                self._leave("stop deadline")
                return
            time.sleep(_DRAIN_STEP_SECONDS)

    def _leave(self, reason: str) -> None:
        left = self._ledger.left()
        logger.warning(
            "[host] %s while %s: leaving now; left %s. The next start reads them from "
            "their files as RECOVERING",
            reason,
            self._phase,
            _describe(left) if left else "none named by the policy",
        )
        with self._moves:
            if self._machine.state is HostState.DRAINING:
                self._machine.move_to(HostState.STOPPED)
            stopped = self._machine.state is HostState.STOPPED
        if stopped:
            self._parts.health.set_state(HostState.STOPPED)
            self._publish_stopped()
        self._parts.leave_process(0)

    def _publish_stopped(self) -> None:
        """Write the STOPPED snapshot before `os._exit` skips the module's own last one.

        Best effort and bounded: the writer runs the probes first, and a probe on a dead
        exchange can hold it. Past `leave_publish_s` the host leaves with the snapshot as it was."""
        publisher = threading.Thread(
            target=self._parts.health.publish_now,
            name="RunHostLeavePublish",
            daemon=True,
        )
        publisher.start()
        publisher.join(self._parts.leave_publish_s)
        if publisher.is_alive():
            logger.warning(
                "[host] the STOPPED snapshot was not written within %.0f s; leaving anyway",
                self._parts.leave_publish_s,
            )

    def _apply_policy(self, give_up: threading.Event, done: threading.Event) -> None:
        policy = self._parts.policy
        try:
            policy.apply(self._ledger, give_up)
        except Exception:
            logger.exception("[host] stop policy %s failed", policy.name)
        finally:
            done.set()

    def _wait_for_policy(self, done: threading.Event) -> str:
        deadline = time.monotonic() + self._parts.stop_timeout_s
        while not done.wait(_DRAIN_STEP_SECONDS):
            if time.monotonic() >= deadline:
                return "stop timeout"
        return "finished"

    def _report(self, outcome: str) -> None:
        left = self._ledger.left()
        policy = self._parts.policy.name
        if outcome == "finished" and not left:
            logger.info("[host] stop policy %s finished", policy)
            return
        if outcome == "finished":
            logger.warning(
                "[host] stop policy %s finished and left %s", policy, _describe(left)
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
