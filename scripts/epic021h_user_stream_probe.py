"""EPIC-021H runnable milestone — see task §5.

Opens the real Binance Futures Testnet User Data Stream and prints every
`ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE` the exchange sends, for `--seconds`
seconds, by subscribing to the same `OrderFilledEvent`/`PositionChangedEvent`
domain events `OrderFeed` re-emits — the exchange's own account of what
happened to an order, not this app's guess. Meant to run in a second
terminal alongside `main.py trade-once --live` (task §5's own two-terminal
picture): this probe is the listener, that command is the thing worth
listening to.

Calls `FuturesUserDataStream._run_stream()` directly (`asyncio.run`, wrapped
in `asyncio.wait_for` for the time budget) rather than going through
`ITaskManager.spawn()` — that manager needs a fully booted `App` context
(async runtime, trace recorder, container) this standalone script has no
reason to stand up, and `_run_stream()` is exactly the coroutine `.start()`
would have handed it anyway.

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/epic021h_user_stream_probe.py \
        --seconds 120

This sandbox's egress to every `*.binance.*` domain is policy-blocked, so
this milestone cannot be demonstrated running *here* — it needs a machine
with real network access and testnet credentials configured (env var or
`secrets.local.json`, same resolution `main.py` uses).
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from sagittarius_engine.utils.path_utils import PathUtils

from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120.0)
    return parser.parse_args()


def _on_order_filled(event: OrderFilledEvent) -> None:
    print(
        f"ORDER_TRADE_UPDATE  {event.order.client_order_id}  "
        f"{event.order.status.name}  fill {event.fill_quantity} @ {event.fill_price}"
    )


def _on_position_changed(event: PositionChangedEvent) -> None:
    position = event.position
    print(
        f"ACCOUNT_UPDATE      {position.symbol}  pos {position.position_amt}  "
        f"entry {position.entry_price}  uPnL {position.unrealized_pnl}"
    )


async def _run(seconds: float) -> None:
    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "src", "config", "secrets.local.json"
    )
    credentials_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(secrets_file_path)
    )
    session_factory = ExchangeSessionFactory(MarketDataVenue.FUTURES_TESTNET)
    metadata_provider = FuturesMetadataProvider(
        session_factory, InMemoryFuturesSymbolMetadataCache()
    )
    event_bus = MemoryEventBus()
    event_bus.on(OrderFilledEvent, _on_order_filled)
    event_bus.on(PositionChangedEvent, _on_position_changed)

    stream = FuturesUserDataStream(
        event_bus,
        # `_run_stream()` is awaited directly below, never through
        # `.start()`/`.stop()` — those are the only methods that touch
        # `task_manager`, so this probe never needs a real one.
        None,  # type: ignore[arg-type]
        session_factory,
        credentials_provider,
        metadata_provider,
        TradingSessionState(),
        EquityCurveRecorder(),
    )

    print(f"Listening for {seconds:.0f}s — Ctrl+C to stop early.")
    try:
        # `BUG-094` — `_run_stream()` only processes messages while its own
        # `generation` argument still matches `stream._generation`; this
        # probe bypasses `start()` (which is what normally bumps it), so it
        # must pass the instance's current value directly, not a literal.
        await asyncio.wait_for(
            stream._run_stream(CancellationToken(), generation=stream._generation),
            timeout=seconds,
        )
    except TimeoutError:
        print(f"Done — listened for {seconds:.0f}s.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = _parse_args()
    asyncio.run(_run(args.seconds))


if __name__ == "__main__":
    main()
