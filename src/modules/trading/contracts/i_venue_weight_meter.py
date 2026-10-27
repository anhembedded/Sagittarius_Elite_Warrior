"""`EPIC-047H` — what a venue's request weight is, as the host's own sessions last saw it.

@details The exchange puts the weight its IP has used this minute on every answer
(`X-MBX-USED-WEIGHT-1M`); the venue's call policy reads it after each answer to close its gate
(`ExchangeCallPolicy`). This port lets a second reader, the host's refresh of exchange facts, see
the same number and the gate's state without asking the exchange anything: reading it costs no
weight. The refresh holds its own ceiling on this number, not on an estimate.

@par What it cannot say
The header is the IP's total for the minute, bots included, and the last answer's: between two
answers it is as old as the quietest moment. `seen_at` says when, so a reader compares two
readings of the same minute only.

@par Extension cases
  · a second window (the 10-second orders limit) - one more field in `WeightReading`;
  · a venue whose sessions the policy does not cover (`market_data`'s own REST client) - one more
    implementation of this port that sums the readers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)


class IVenueWeightMeter(ABC):
    @abstractmethod
    def read(self) -> WeightReading:
        """The venue's weight now, from what its sessions last heard. Costs the exchange nothing; never raises."""
