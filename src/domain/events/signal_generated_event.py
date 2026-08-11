from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal


@dataclass(frozen=True)
class SignalGeneratedEvent:
    signal: Signal
