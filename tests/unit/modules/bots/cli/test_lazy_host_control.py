"""`PRO-014` - host control is looked up when a verb first sends, not when the verb is chosen."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.modules.bots.cli.lazy_host_control import (
    LazyHostControl,
)


def test_nothing_is_resolved_until_a_request_is_sent() -> None:
    resolve = Mock()

    LazyHostControl(resolve)

    resolve.assert_not_called()


def test_a_request_is_sent_through_what_the_container_answers() -> None:
    request = Mock(spec=HostControlRequest)
    reply = Mock(spec=HostControlReply)
    real = Mock(spec=IHostControl)
    real.send.return_value = reply

    answered = LazyHostControl(lambda: real).send(request, 2.5)

    assert answered is reply
    real.send.assert_called_once_with(request, 2.5)
