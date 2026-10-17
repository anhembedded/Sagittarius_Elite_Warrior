"""The operator's side of control of a running host (`EPIC-038J`, decision O4, channel A).

@par Extension cases
  · a different transport (a socket, a chat bot) - another `IHostControl`; the verbs, the
    request and the reply are untouched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)


class IHostControl(ABC):
    """The operator's side of control: send a request, wait for the host's recorded answer."""

    @abstractmethod
    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        """Deliver `request` to the running host and wait up to `wait_s` seconds for its outcome.

        Never raises for a condition the operator can act on; each is a status. When no host
        is running nothing is written."""
