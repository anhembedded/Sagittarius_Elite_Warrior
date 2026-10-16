"""`EPIC-036G` — the fake transport passes the contract the real one does, so a
channel tested against it is tested against the port, not against a double
shaped from its calls (`CS-001`)."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.contract_webhook_transport import (
    SECRET_PATH,
    TransportUnderTest,
    WebhookTransportContract,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)


class TestTheFakeTransport(WebhookTransportContract):
    @pytest.fixture
    def impl(self) -> TransportUnderTest:
        fake = FakeWebhookTransport()

        def answer(response: WebhookResponse) -> None:
            fake.script.append(response)

        def prepare_no_answer() -> None:
            fake.script.append(WebhookUnreachableError("connection refused"))

        return TransportUnderTest(
            transport=fake,
            url="https://discord.example" + SECRET_PATH,
            answer=answer,
            last_body=lambda: json.dumps(fake.posts[-1].body),
            dead_url="https://dead.example" + SECRET_PATH,
            prepare_no_answer=prepare_no_answer,
        )
