"""Runs the worker on a lane per channel, off every other thread (design §4).

A housekeeping thread beside them runs the hub's periodic flush (grouped alerts
whose window ended, the quiet-hours summary). It is a thread here and not a
`Scheduler` job on purpose: every scheduled run publishes `runtime.tasks.started`
and `.completed` on the event bus, so a one-second job would put two events a
second into the Developer event log for the life of the app.

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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)

logger = logging.getLogger("App.Alerting")

#: `stop()` waits this long for a lane stuck inside a channel before moving on.
JOIN_TIMEOUT_S = 5.0

LANE_THREAD_PREFIX = "alerting-lane-"
HOUSEKEEPING_THREAD_NAME = "alerting-housekeeping"


class ThreadedDeliveryHost:
    def __init__(
        self,
        delivery: ChannelDelivery,
        channel_ids: Sequence[str],
        signal: WakeSignal,
        poll_seconds: float,
        housekeeping: Callable[[], None],
        housekeeping_seconds: float,
    ) -> None:
        self._delivery = delivery
        self._channel_ids = tuple(channel_ids)
        self._signal = signal
        self._poll_seconds = poll_seconds
        self._housekeeping = housekeeping
        self._housekeeping_seconds = housekeeping_seconds
        self._stopping = threading.Event()
        self._lanes: list[threading.Thread] = []

    def start(self) -> None:
        for channel_id in self._channel_ids:
            lane = threading.Thread(
                target=self._run_lane,
                args=(channel_id,),
                name=f"{LANE_THREAD_PREFIX}{channel_id}",
                daemon=True,
            )
            self._lanes.append(lane)
            lane.start()
        lanes = len(self._lanes)
        keeper = threading.Thread(
            target=self._run_housekeeping, name=HOUSEKEEPING_THREAD_NAME, daemon=True
        )
        self._lanes.append(keeper)
        keeper.start()
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

    def _run_lane(self, channel_id: str) -> None:
        seen = self._signal.generation()
        while not self._stopping.is_set():
            try:
                self._delivery.run_due(channel_id)
            except Exception:
                # A lane that dies is an owner who stops hearing from the bots:
                # log and carry on at the next poll.
                logger.exception("[alert-worker] pass over %s failed", channel_id)
            seen = self._signal.wait(seen, self._poll_seconds)
