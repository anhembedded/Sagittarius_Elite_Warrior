"""`EPIC-021E` — headless `main.py order-preview`. Builds and validates a
normalized order (rounding + minNotional) without sending it: the domain
decision behind an order, visible before `EPIC-021F` wires a real
placement adapter onto `ITradingClient`."""

import argparse
import json
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_formatter import (
    format_order_preview,
    order_preview_to_dict,
)
from sagittarius_engine import App


def execute_order_preview(app: App, args: argparse.Namespace) -> None:
    try:
        quantity = Decimal(args.qty)
        reference_price = Decimal(args.price)
    except InvalidOperation:
        print(f"Invalid number: qty={args.qty!r} price={args.price!r}")
        return

    query = PreviewOrderQuery(
        symbol=args.symbol,
        side=OrderSide[args.side],
        order_type=OrderType[args.type],
        quantity=quantity,
        reference_price=reference_price,
    )

    try:
        preview = app.dispatch(PreviewOrderQuery, query)
    except ValueError as exc:
        print(f"Could not preview the order: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        # `IMarketMetadataProvider`, unlike `ITradingAccountReader`
        # (EPIC-021D), makes no "never raises" promise — this is the one
        # network call this task's CLI makes, and this is where its
        # failure is classified and shown, not inside the domain/handler.
        print(
            "Could not fetch exchange rules for "
            f"{args.symbol} — check your network connection and try again."
        )
        return

    if args.json:
        print(json.dumps(order_preview_to_dict(preview), ensure_ascii=False, indent=2))
    else:
        print(format_order_preview(preview))
