"""Runs the worker on a lane per channel, off every other thread (design §4).

A lane is a daemon thread that does `ChannelDelivery.run_due` for its channel,
then waits for the hub's nudge or the poll interval - the poll is what picks up a
`retry_after` that has come due. One lane per channel is the whole of "a queue per
channel, so a slow channel delays no other".
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

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


class ThreadedDeliveryHost:
    def __init__(
        self,
        delivery: ChannelDelivery,
        channel_ids: Sequence[str],
        signal: WakeSignal,
        poll_seconds: float,
    ) -> None:
        self._delivery = delivery
        self._channel_ids = tuple(channel_ids)
        self._signal = signal
        self._poll_seconds = poll_seconds
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
        logger.info(
            "[alert-worker] %s lane(s): %s", len(self._lanes), self._channel_ids
        )

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
