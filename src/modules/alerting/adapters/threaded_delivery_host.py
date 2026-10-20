"""Runs the worker on a lane per channel, off every other thread (design §4).

A housekeeping thread beside them runs the hub's periodic flush (grouped alerts
whose window ended, the quiet-hours summary). It is a thread here and not a
`Scheduler` job on purpose: every scheduled run publishes `runtime.tasks.started`
and `.completed` on the event bus, so a one-second job would put two events a
second into the Developer event log for the life of the app.

A third thread, the beacon, runs the dead man's switch (`EPIC-036E1`). It is apart from
the lanes on purpose: a monitor that is slow or down delays no delivery. What ties it to
the worker is `WorkerLiveness`: every lane and the housekeeping pass stamp it after each
pass, and the switch pings only while the stamps are fresh.

A lane is a daemon thread that does `ChannelDelivery.run_due` for its channel,
then waits for the hub's nudge or the poll interval - the poll is what picks up a
`retry_after` that has come due. One lane per channel is the whole of "a queue per
channel, so a slow channel delays no other".
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.worker_liveness import (
    WorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)

logger = logging.getLogger("App.Alerting")

#: `stop()` waits this long for a lane stuck inside a channel before moving on.
JOIN_TIMEOUT_S = 5.0

#: A lane never sleeps less than this, so a wait that ends within it cannot spin the thread.
MIN_SLEEP_S = 0.05

LANE_THREAD_PREFIX = "alerting-lane-"
HOUSEKEEPING_THREAD_NAME = "alerting-housekeeping"
BEACON_THREAD_NAME = "alerting-beacon"


class ThreadedDeliveryHost:
    def __init__(
        self,
        delivery: ChannelDelivery,
        channel_ids: Sequence[str],
        signal: WakeSignal,
        poll_seconds: float,
        housekeeping: Callable[[], None],
        housekeeping_seconds: float,
        liveness: WorkerLiveness,
        beacon: Callable[[], None],
        beacon_seconds: float,
    ) -> None:
        self._delivery = delivery
        self._channel_ids = tuple(channel_ids)
        self._signal = signal
        self._poll_seconds = poll_seconds
        self._housekeeping = housekeeping
        self._housekeeping_seconds = housekeeping_seconds
        self._liveness = liveness
        self._beacon = beacon
        self._beacon_seconds = beacon_seconds
        self._stopping = threading.Event()
        self._lanes: list[threading.Thread] = []

    def start(self) -> None:
        for channel_id in self._channel_ids:
            self._liveness.register(f"{LANE_THREAD_PREFIX}{channel_id}")
            lane = threading.Thread(
                target=self._run_lane,
                args=(channel_id,),
                name=f"{LANE_THREAD_PREFIX}{channel_id}",
                daemon=True,
            )
            self._lanes.append(lane)
            lane.start()
        lanes = len(self._lanes)
        self._liveness.register(HOUSEKEEPING_THREAD_NAME)
        keeper = threading.Thread(
            target=self._run_housekeeping, name=HOUSEKEEPING_THREAD_NAME, daemon=True
        )
        self._lanes.append(keeper)
        keeper.start()
        beacon = threading.Thread(
            target=self._run_beacon, name=BEACON_THREAD_NAME, daemon=True
        )
        self._lanes.append(beacon)
        beacon.start()
        logger.info("[alert-worker] %s lane(s): %s", lanes, self._channel_ids)

    def stop(self) -> None:
        self._stopping.set()
        self._signal.notify()
        for lane in self._lanes:
            lane.join(JOIN_TIMEOUT_S)
            if lane.is_alive():
                logger.warning("[alert-worker] %s is still inside a channel", lane.name)
        self._lanes = [lane for lane in self._lanes if lane.is_alive()]

    def running_lanes(self) -> int:
        return sum(lane.is_alive() for lane in self._lanes)

    def _run_housekeeping(self) -> None:
        while not self._stopping.wait(self._housekeeping_seconds):
            try:
                self._housekeeping()
            except Exception:
                # Housekeeping that dies leaves grouped alerts unsent.
                logger.exception("[alert-worker] housekeeping pass failed")
            self._liveness.touch(HOUSEKEEPING_THREAD_NAME)

    def _run_beacon(self) -> None:
        """The first pass is at once, so a started app is seen by the monitor without
        waiting a poll interval."""
        while not self._stopping.is_set():
            try:
                self._beacon()
            except Exception as error:  # noqa: BLE001 - a beacon that dies is a silent monitor
                # Only the type: the message of a transport error can carry the check-in URL.
                logger.warning(
                    "[alert-worker] beacon pass failed (%s)", type(error).__name__
                )
            self._stopping.wait(self._beacon_seconds)

    def _sleep_of(self, channel_id: str) -> float:
        """The poll interval, or less when the channel's wait ends sooner (`EPIC-036C2`)."""
        remaining = self._delivery.pause_remaining(channel_id)
        if remaining is None:
            return self._poll_seconds
        return max(MIN_SLEEP_S, min(self._poll_seconds, remaining.total_seconds()))

    def _run_lane(self, channel_id: str) -> None:
        seen = self._signal.generation()
        while not self._stopping.is_set():
            try:
                self._delivery.run_due(channel_id)
            except Exception:
                # A lane that dies is an owner who stops hearing from the bots:
                # log and carry on at the next poll.
                logger.exception("[alert-worker] pass over %s failed", channel_id)
            self._liveness.touch(f"{LANE_THREAD_PREFIX}{channel_id}")
            seen = self._signal.wait(seen, self._sleep_of(channel_id))
