"""A measurement the `run` host takes before it publishes a snapshot (`EPIC-038D`).

A health contributor answers from memory and may not ask the network
(`IHealthContributor`). Some facts an operator wants - how far this machine's clock
is from the exchange's - can only be learned by asking. A module that knows how
declares a probe; the host calls every probe once per health interval, before the
snapshot, and the module's contributor reports what the probe left.

A probe may make one read-only request and must be bounded by the client's own
timeout. It never places, tests or simulates an order. It may raise: the host logs
it and goes on, because a probe that failed must never stop the snapshot.

@par Extension cases
  · another measured fact (a withdrawal-permission recheck, an outbound-address
    drift) - one probe and one `declare_probe` in the module that knows it; the
    host, the snapshot and the health line are untouched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IHealthProbe(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """A stable id: a lowercase word with hyphens, unique across probes."""

    @abstractmethod
    def measure(self) -> None:
        """Take the measurement and leave it where the module's contributor reads it."""
