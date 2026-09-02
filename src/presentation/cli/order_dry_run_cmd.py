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
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_order_payload_mapper import (
    InvalidOrderForSubmissionError,
)
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
        print(f"Số không hợp lệ: qty={args.qty!r} price={args.price!r}")
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
        print(f"Không xem trước được lệnh: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        print(
            "Không lấy được luật giao dịch (exchange rules) cho "
            f"{args.symbol} — kiểm tra kết nối mạng rồi thử lại."
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
            "Trading venue đang tắt (DISABLED). Bật lên bằng cách đặt "
            '"exchange.trading_venue": "futures_testnet" trong '
            "src/config/user_config.json, rồi thử lại."
        )
        return
    except OrderRejectedByExchangeError as exc:
        print(format_submission_rejected(exc))
        return
    except InvalidOrderForSubmissionError as exc:
        print(f"Order chưa hợp lệ để gửi: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        print("Không gửi được payload tới sàn — kiểm tra kết nối mạng rồi thử lại.")
        return

    print(format_submission_accepted())
