"""`EPIC-047B` - a running host writes the facts only it holds, and the file follows them.

The composed app over the fake exchange: a lease, a venue's key and the exchange's answer for a bot
change, and the file named `state/host-facts.json` follows within `WITHIN_SECONDS`; the host stops
and the file stops with it, its age growing. The unit tests build the publisher from doubles and so
prove nothing about wiring (`CS-002`): the scheduler job, the module's `boot()` and the tap on the
venue-facts reader are all the real ones here.
"""

from __future__ import annotations

import json
import stat
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_source import (
    FileHostFactsSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_watch import (
    LIVE_AFTER_HEARTBEATS,
    HostFactsWatch,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    FACTS_HEARTBEAT_SECONDS,
    FACTS_POLL_SECONDS,
    HOST_FACTS_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)

from ..operations.run_command_support import heard
from .grid_fake_exchange import SPOT, SYMBOL, BootedApp, FakeExchange, booted

#: The stated time: a change reaches the file within one look (`FACTS_POLL_SECONDS`) and the time one
#: write takes; three looks is the room a loaded CI machine is given.
WITHIN_SECONDS = 3 * FACTS_POLL_SECONDS

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")


def _file() -> Path:
    return data_root() / "state" / HOST_FACTS_FILE_NAME


def _content() -> dict[str, object]:
    return json.loads(_file().read_bytes())


def _wait_for(what: str, condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + WITHIN_SECONDS
    while time.monotonic() < deadline:
        if _file().exists() and condition():
            return
        threading.Event().wait(0.05)
    pytest.fail(f"within {WITHIN_SECONDS} s the file did not show: {what}")


def _seed_bot(app: BootedApp) -> None:
    app.store.save(
        StoredBot(
            Bot(
                BotId("aaaaaa"),
                BotDefinition("paper", "grid", SPOT, SYMBOL, {"lower": "1"}),
                BotLifecycle(BotLifecycleState.STOPPED),
                datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
    )


def _lease_of(content: dict[str, object]) -> str:
    leases = content["leases"]
    assert isinstance(leases, list)
    return next(
        (
            str(row["holder"])
            for row in leases
            if row["symbol"] == SYMBOL and row["venue"] == SPOT.value
        ),
        "",
    )


def _spot_key_saved(content: dict[str, object]) -> object:
    keys = content["venue_keys"]
    assert isinstance(keys, list)
    return next((row["key_saved"] for row in keys if row["venue"] == SPOT.value), None)


def test_a_host_publishes_its_facts_and_the_file_follows_a_lease_a_key_and_an_exchange_read(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    with booted(exchange) as app:
        container = app.engine.context.container
        _seed_bot(app)

        # 1. The first write happens at boot, before any look has been asked for.
        _wait_for("the first write", lambda: True)
        first_revision = _content()["revision"]
        assert _content()["schema"] == "sew.host-facts/1"
        assert SPOT.value in _content()["enabled_venues"]  # type: ignore[operator]
        assert _content()["heartbeat_s"] == FACTS_HEARTBEAT_SECONDS

        # 2. A lease changes in the host's memory.
        assert app.scope.session_state.claim_symbol(SYMBOL, "strategy:ema")
        _wait_for("the lease", lambda: _lease_of(_content()) == "strategy:ema")
        assert _content()["revision"] > first_revision  # type: ignore[operator]

        # 3. A venue's key goes: the file says a key is no longer saved - and never the key.
        raw_before = _file().read_bytes()
        assert b"fake-key" not in raw_before
        assert b"fake-secret" not in raw_before
        monkeypatch.delenv(SPOT_ENV_API_KEY)
        monkeypatch.delenv(SPOT_ENV_API_SECRET)
        _wait_for(
            "the key gone",
            lambda: _spot_key_saved(_content()) is False,
        )
        # `EPIC-047C`: every enabled venue shows its key state, a venue nothing built included.
        assert {row["venue"] for row in _content()["venue_keys"]} == set(  # type: ignore[attr-defined]
            _content()["enabled_venues"]  # type: ignore[arg-type]
        )

        # 4. An exchange read the host's own reader takes is carried, with its own `read_at`.
        dispatcher = container.resolve(ICommandDispatcher)
        dispatcher.dispatch(GetExchangeFactsQuery, GetExchangeFactsQuery("aaaaaa"))
        _wait_for("the exchange read", lambda: bool(_content()["exchange_reads"]))
        [read] = _content()["exchange_reads"]  # type: ignore[misc]
        assert read["bot_id"] == "aaaaaa"
        assert read["state"] in {"spot", "unavailable"}
        assert b"fake-key" not in _file().read_bytes()


def test_the_host_says_in_its_log_where_and_how_often_it_writes(
    exchange: FakeExchange,
) -> None:
    """A diagnostic never seen to emit does not exist: this goes through the real logging
    configuration the composed app sets up."""
    with heard() as lines, booted(exchange):
        _wait_for("the first write", lambda: True)

    [line] = [text for text in lines if "[host-facts] writing" in text]
    assert "INFO" in line
    assert HOST_FACTS_FILE_NAME in line
    assert f"at least every {FACTS_HEARTBEAT_SECONDS}s" in line


@posix_only
def test_the_file_a_running_host_writes_is_owner_only(exchange: FakeExchange) -> None:
    with booted(exchange):
        _wait_for("the first write", lambda: True)

        assert stat.S_IMODE(_file().stat().st_mode) == 0o600


def test_a_stopped_host_stops_writing_and_the_files_age_grows(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        _wait_for("the first write", lambda: True)
        app.engine.stop()
        stopped_at = _content()["written_at"], _content()["revision"]

    assert not [t for t in threading.enumerate() if t.name == "host-facts-writer"]
    assert (_content()["written_at"], _content()["revision"]) == stopped_at

    clock = _AdjustableClock()
    watch = HostFactsWatch(
        FileHostFactsSource(_file(), JsonHostFactsCodec()),
        clock,
    )
    reading = watch.refresh()
    assert reading.header is not None
    clock.set(reading.header.written_at)
    assert watch.refresh().live is True
    clock.advance(FACTS_HEARTBEAT_SECONDS * LIVE_AFTER_HEARTBEATS + 1)
    gone = watch.refresh()
    assert gone.live is False
    assert gone.age_s == FACTS_HEARTBEAT_SECONDS * LIVE_AFTER_HEARTBEATS + 1


def test_deleting_the_file_is_harmless_the_host_writes_it_again(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        _wait_for("the first write", lambda: True)
        revision = _content()["revision"]

        _file().unlink()
        assert app.scope.session_state.claim_symbol(SYMBOL, "strategy:ema")
        _seed_bot(app)

        _wait_for("the file again", lambda: _lease_of(_content()) == "strategy:ema")
        assert _content()["revision"] > revision  # type: ignore[operator]


class _AdjustableClock(IOperationsClock):
    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)
