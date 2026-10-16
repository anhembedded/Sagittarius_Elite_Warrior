"""The contract suite for `IWebhookTransport` (HLD §10.3).

What a channel relies on: every status the server sends comes back as a
`WebhookResponse` with its headers readable in lower case, the body arrives as
JSON, and "no answer" is a `WebhookUnreachableError` whose message carries no
part of the URL.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
    WebhookUnreachableError,
)

#: A path shaped like a webhook's, so a leak of it into an error is visible.
SECRET_PATH = "/api/webhooks/123456789/s3cr3t-T0KEN_value"  # noqa: S105 - a made-up path a leak test looks for, not a credential


@dataclass(frozen=True, slots=True)
class TransportUnderTest:
    """The transport, the URL a test POSTs to, what the server answers next, and
    what it received."""

    transport: IWebhookTransport
    url: str
    #: Make the next POST answer `response`.
    answer: Callable[[WebhookResponse], None]
    #: The body of the last POST the server received, as JSON text.
    last_body: Callable[[], str]
    #: A URL nobody answers at, carrying `SECRET_PATH`.
    dead_url: str
    #: Arrange for the next POST to `dead_url` to get no answer (a real transport
    #: needs nothing: nobody listens there).
    prepare_no_answer: Callable[[], None]


class WebhookTransportContract:
    """Inherit this and provide `impl`."""

    @pytest.fixture
    def impl(self) -> TransportUnderTest:
        raise NotImplementedError

    def test_a_2xx_comes_back_accepted(self, impl: TransportUnderTest) -> None:
        impl.answer(WebhookResponse(204))
        assert impl.transport.post_json(impl.url, {"content": "hi"}).accepted

    def test_the_body_is_sent_as_json(self, impl: TransportUnderTest) -> None:
        impl.answer(WebhookResponse(204))
        impl.transport.post_json(impl.url, {"content": "hi", "flags": 4096})
        assert json.loads(impl.last_body()) == {"content": "hi", "flags": 4096}

    def test_a_429_is_an_answer_with_its_headers_in_lower_case(
        self, impl: TransportUnderTest
    ) -> None:
        impl.answer(WebhookResponse(429, {"Retry-After": "2"}, b'{"retry_after": 1.5}'))
        response = impl.transport.post_json(impl.url, {"content": "hi"})
        assert response.status == 429
        assert not response.accepted
        assert response.headers["retry-after"] == "2"
        assert json.loads(response.body) == {"retry_after": 1.5}

    def test_a_404_is_an_answer_not_an_error(self, impl: TransportUnderTest) -> None:
        impl.answer(WebhookResponse(404))
        assert impl.transport.post_json(impl.url, {"content": "hi"}).status == 404

    def test_no_answer_raises_without_the_url(self, impl: TransportUnderTest) -> None:
        impl.prepare_no_answer()
        with pytest.raises(WebhookUnreachableError) as caught:
            impl.transport.post_json(impl.dead_url, {"content": "hi"})
        assert "s3cr3t" not in str(caught.value)
        assert "webhooks" not in str(caught.value)
