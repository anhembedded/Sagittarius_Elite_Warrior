"""`EPIC-021F` — headless `main.py order-dry-run`. The epic's most
important milestone: proves signature, key permissions, and payload are
all correct against the real exchange — with zero orders ever created
(`POST /fapi/v1/order/test`)."""

import argparse
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.application.use_cases.commands.submit_order import (
    SubmitOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.presentation.cli.order_dry_run_formatter import (
    format_submission_accepted,
    format_submission_rejected,
    format_submission_request,
)
from sagittarius_engine import App
from sagittarius_engine.exceptions import DependencyResolutionError


def execute_order_dry_run(app: App, args: argparse.Namespace) -> None:
    try:
        quantity = Decimal(args.qty)
        reference_price = Decimal(args.price)
    except InvalidOperation:
        print(f"Invalid number: qty={args.qty!r} price={args.price!r}")
        return

    order_request = PreviewOrderQuery(
        symbol=args.symbol,
        side=OrderSide[args.side],
        order_type=OrderType[args.type],
        quantity=quantity,
        reference_price=reference_price,
    )

    try:
        preview = app.dispatch(PreviewOrderQuery, order_request)
    except ValueError as exc:
        print(f"Could not preview the order: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        print(
            "Could not fetch exchange rules for "
            f"{args.symbol} — check your network connection and try again."
        )
        return

    print(format_submission_request(preview.order))
    print()

    try:
        app.dispatch(
            SubmitOrderCommand, SubmitOrderCommand(order_request=order_request)
        )
    except DependencyResolutionError:
        print(
            "Trading venue is DISABLED. Enable it by setting "
            '"exchange.trading_venue": "futures_testnet" in '
            "src/config/user_config.json, then try again."
        )
        return
    except OrderRejectedByExchangeError as exc:
        print(format_submission_rejected(exc))
        return
    except InvalidOrderForSubmissionError as exc:
        print(f"Order is not valid for submission: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        print(
            "Could not send the payload to the exchange — check your network connection and try again."
        )
        return

    print(format_submission_accepted())
