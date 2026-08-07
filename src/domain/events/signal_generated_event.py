from dataclasses import dataclass

from Binace_Bot.src.domain.value_objects.signal import Signal


@dataclass(frozen=True)
class SignalGeneratedEvent:
    signal: Signal
