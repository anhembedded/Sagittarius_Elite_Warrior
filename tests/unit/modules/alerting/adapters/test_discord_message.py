"""`EPIC-036G` — the body of a Discord webhook message for an alert."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    MAX_CONTENT,
    SUPPRESS_NOTIFICATIONS,
    discord_payload,
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

_AT = datetime(2026, 10, 16, 2, 30, tzinfo=UTC)


def _halt(detail: str = "price feed silent for 64 s", name: str = "eth-grid") -> Alert:
    return Alert.raised(
        AlertKind.BOT_HALTED,
        AlertSubject.bot("g3n092", name, "grid", "spot_mainnet", "ETHUSDT"),
        f"Bot halted: {name}",
        detail,
        _AT,
    )


def test_a_halt_names_the_severity_the_bot_and_the_reason() -> None:
    content = str(discord_payload(_halt(), Loudness.LOUD)["content"])

    assert "CRITICAL" in content
    assert "Bot halted: eth-grid" in content
    assert "spot_mainnet ETHUSDT" in content
    assert "price feed silent for 64 s" in content
    assert "2026-10-16 02:30:00 UTC" in content


def test_a_loud_message_carries_no_flag_and_a_silent_one_suppresses_the_push() -> None:
    assert "flags" not in discord_payload(_halt(), Loudness.LOUD)
    assert discord_payload(_halt(), Loudness.SILENT)["flags"] == SUPPRESS_NOTIFICATIONS


def test_no_mention_is_ever_parsed() -> None:
    """A bot named `@everyone` must not ping a server."""
    body = discord_payload(_halt(name="@everyone"), Loudness.LOUD)

    assert body["allowed_mentions"] == {"parse": []}


def test_a_long_detail_is_cut_to_what_discord_accepts() -> None:
    content = str(discord_payload(_halt(detail="x" * 5000), Loudness.LOUD)["content"])

    assert len(content) == MAX_CONTENT
    assert content.endswith("\N{HORIZONTAL ELLIPSIS}")


@pytest.mark.parametrize(
    "value",
    [
        "https://discord.com/api/webhooks/123456/abc_DEF-ghi",
        "https://discordapp.com/api/webhooks/123456/abc",
        "https://canary.discord.com/api/v10/webhooks/123456/abc",
    ],
)
def test_a_discord_webhook_url_is_recognised(value: str) -> None:
    assert is_discord_webhook_url(value)


@pytest.mark.parametrize(
    "value",
    [
        "http://discord.com/api/webhooks/123456/abc",  # not https
        "https://discord.com.evil.example/api/webhooks/123456/abc",
        "https://discord.com/api/webhooks/123456/abc?x=1",
        "https://discord.com/api/webhooks/abc/abc",  # the id is a number
        "https://discord.com/api/webhooks/\u0661\u0662\u0663/abc",  # Arabic-Indic digits
        "https://hooks.slack.com/services/T/B/x",
        "",
    ],
)
def test_anything_else_is_not_posted_to(value: str) -> None:
    assert not is_discord_webhook_url(value)
