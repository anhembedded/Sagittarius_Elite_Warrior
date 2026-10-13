"""`EPIC-036A` — a scripted `IAlertChannel` for tests: it records what it was
asked and answers from a script, so no test touches a network.

Passes the same contract a real channel is held to: it answers with a
`DeliveryResult`. It can also be told to *raise*, to prove the worker contains
a channel that breaks the rule. Its extras are plain attributes (`received`,
`script`, `default`, `gate`, `entered`, `done`), not methods.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

#: A blocked fake gives up after this long, so a broken test ends rather than hangs.
GATE_TIMEOUT_S = 30.0


@dataclass(frozen=True, slots=True)
class ReceivedAlert:
    alert: Alert
    loudness: Loudness


class FakeAlertChannel(IAlertChannel):
    """Answers `script` in order, then `default` (a result, or an exception to raise)."""

    def __init__(
        self,
        script: Sequence[DeliveryResult | BaseException] = (),
        default: DeliveryResult | BaseException | None = None,
    ) -> None:
        self.script: list[DeliveryResult | BaseException] = list(script)
        self.default: DeliveryResult | BaseException = (
            default if default is not None else DeliveryResult.sent()
        )
        self.received: list[ReceivedAlert] = []
        #: When set, `deliver` waits for this event first: a slow channel.
        self.gate: threading.Event | None = None
        self.entered = threading.Event()
        self.done = threading.Event()

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        self.received.append(ReceivedAlert(alert, loudness))
        self.entered.set()
        if self.gate is not None:
            self.gate.wait(GATE_TIMEOUT_S)
        outcome = self.script.pop(0) if self.script else self.default
        self.done.set()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
