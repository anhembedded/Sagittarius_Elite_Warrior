"""`EPIC-047E` - its queries: the Bots screen's doors on the far side of the real bridge session.

The business promise: a screen that asks its dispatcher what it always asked gets the host's published answer, with the
host's words where the host never published; a command reaches the host's own gate as the request the `bot` verb of the
same name sends, once, only while the link is up, and the host's answer comes back in the screen's result.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_queries import (
    UNKNOWN_BOT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_requests import (
    NotOfferedInVpsTabError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    AssessBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices import (
    GetVenueChoicesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    KEY_SAVED,
    NO_KEY,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    BTC,
    ETH,
    LOCAL_ANSWER,
    ask,
    build_dispatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsTabWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_fills,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_facts,
)

# -- queries ---------------------------------------------------------------------------------


def test_the_list_is_the_hosts_list(tab: VpsTabWorld) -> None:
    dispatcher, _ = build_dispatcher(tab)

    listed = ask(dispatcher, ListBotsQuery())

    assert isinstance(listed, BotList)
    assert {bot.bot_id for bot in listed.bots} == {BTC.bot_id, ETH.bot_id}


def test_the_exchange_facts_of_a_bot_are_the_snapshot_the_host_published(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)
    published = {r.bot_id: r.snapshot for r in full_host_facts().facts.exchange_reads}

    assert ask(dispatcher, GetExchangeFactsQuery(ETH.bot_id)) == published[ETH.bot_id]
    assert ask(dispatcher, GetExchangeFactsQuery("b-9999")) == ExchangeUnavailable(
        UNKNOWN_BOT
    )


def test_a_fill_list_the_host_never_read_says_so(tab: VpsTabWorld) -> None:
    dispatcher, _ = build_dispatcher(tab)

    read = ask(dispatcher, GetBotFillsQuery(BTC.bot_id))
    unread = ask(dispatcher, GetBotFillsQuery("b-9999"))

    assert read == full_fills()
    assert unread.problem == UNKNOWN_BOT  # type: ignore[attr-defined]


def test_run_facts_come_from_the_hosts_venues_and_leases(tab: VpsTabWorld) -> None:
    dispatcher, _ = build_dispatcher(tab)
    held = full_host_facts().facts

    on_enabled = ask(
        dispatcher,
        GetBotRunFactsQuery(ETH.bot_id, TradingVenue.SPOT_TESTNET, "BTCUSDT"),
    )
    on_closed = ask(
        dispatcher,
        GetBotRunFactsQuery(ETH.bot_id, TradingVenue.SPOT_MAINNET, "BTCUSDT"),
    )

    assert on_enabled.facts.venue_problem == ""  # type: ignore[attr-defined]
    assert on_enabled.facts.lease_holder == "grid:b-0001"  # type: ignore[attr-defined]
    assert on_enabled.caps == held.caps  # type: ignore[attr-defined]
    assert "not enabled" in on_closed.facts.venue_problem  # type: ignore[attr-defined]


def test_the_venue_choices_say_which_venue_the_host_holds_a_key_for(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)

    choices = ask(dispatcher, GetVenueChoicesQuery())

    by_venue = {c.venue: c.connection for c in choices.choices}  # type: ignore[attr-defined]
    assert by_venue[TradingVenue.SPOT_TESTNET] == KEY_SAVED
    assert by_venue[TradingVenue.FUTURES_TESTNET] == NO_KEY


def test_the_assessment_runs_where_the_screen_runs(tab: VpsTabWorld) -> None:
    dispatcher, local = build_dispatcher(tab)

    answer = dispatcher.dispatch(AssessBotQuery, object())

    assert answer is LOCAL_ANSWER
    assert local.asked == [AssessBotQuery]
    assert tab.host.door.sent == []


def test_a_query_the_tab_does_not_offer_is_refused_in_words(tab: VpsTabWorld) -> None:
    dispatcher, _ = build_dispatcher(tab)

    with pytest.raises(NotOfferedInVpsTabError, match="RunBacktestQuery"):
        dispatcher.dispatch(RunBacktestQuery, object.__new__(RunBacktestQuery))
