"""`IPublicAddressReader` over the standard library's `urllib` (`BOT-224`).

No new dependency: one GET per service, as `alerting`'s webhook transport sends
its POST. The process's proxy settings (`HTTPS_PROXY`) apply, as they do to
every `urllib` request. Services are asked in order and the first usable answer
wins; a lookup fails only when none gave one.

The address is not logged here: it is the operator's, and `logging-rule.md`
keeps it out of INFO and above.
"""

from __future__ import annotations

import http.client
import ipaddress
import logging
import urllib.request
from collections.abc import Sequence
from urllib.parse import urlsplit

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_public_address_reader import (
    IPublicAddressReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressFailure,
    PublicAddressLookup,
)

logger = logging.getLogger("App.PublicAddress")

#: The primary echo service and one fallback, both answering the bare address as text.
SOURCES = ("https://api.ipify.org", "https://checkip.amazonaws.com")

#: How long one service may take. The user is waiting on a button, and a dead
#: connection must not hold it for the OS default.
REQUEST_TIMEOUT_S = 5.0

#: An IPv4 address is at most 15 characters; a longer body is not one.
MAX_BODY_BYTES = 64

USER_AGENT = "SagittariusEliteWarrior-trading/1"


class UrllibPublicAddressReader(IPublicAddressReader):
    def __init__(
        self,
        sources: Sequence[str] = SOURCES,
        timeout_s: float = REQUEST_TIMEOUT_S,
    ) -> None:
        self._sources = tuple(sources)
        self._timeout_s = timeout_s

    def read(self) -> PublicAddressLookup:
        failure = PublicAddressFailure.UNREACHABLE
        for source in self._sources:
            asked = self._ask(source)
            if asked.address is not None:
                logger.info("public address read from a service [public-ip]")
                return asked
            if asked.failure is PublicAddressFailure.UNREADABLE:
                failure = PublicAddressFailure.UNREADABLE
        logger.info(
            "public address not read from %d services: %s [public-ip]",
            len(self._sources),
            failure.value,
        )
        return PublicAddressLookup.failed(failure)

    def _ask(self, source: str) -> PublicAddressLookup:
        request = urllib.request.Request(  # noqa: S310 - the sources are this module's own https constants
            source, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as reply:  # noqa: S310 - see above
                body = reply.read(MAX_BODY_BYTES)
        except (OSError, http.client.HTTPException) as error:
            logger.info(
                "public address service %s gave no answer (%s) [public-ip]",
                urlsplit(source).hostname,
                type(error).__name__,
            )
            return PublicAddressLookup.failed(PublicAddressFailure.UNREACHABLE)
        return _parse(body)


def _parse(body: bytes) -> PublicAddressLookup:
    try:
        address = ipaddress.IPv4Address(body.decode("ascii").strip())
    except ValueError:
        return PublicAddressLookup.failed(PublicAddressFailure.UNREADABLE)
    if not address.is_global:
        return PublicAddressLookup.failed(PublicAddressFailure.UNREADABLE)
    return PublicAddressLookup.found(str(address))
