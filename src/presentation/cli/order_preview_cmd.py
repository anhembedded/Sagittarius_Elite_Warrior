"""`EPIC-021E` — headless `main.py order-preview`. Builds and validates a
normalized order (rounding + minNotional) without sending it: the domain
decision behind an order, visible before `EPIC-021F` wires a real
placement adapter onto `ITradingClient`."""

import argparse
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_formatter import (
    order_preview_report,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import emit_report
from sagittarius_engine import App


def execute_order_preview(app: App, args: argparse.Namespace) -> CliOutcome | None:
    """Preview one order; the exit code says whether it could be sent.

    `EPIC-038B` — an unusable request (a number that is not one, a symbol the
    rules reject, an order below minNotional) is `USAGE`: the arguments cannot
    form an order, and a script gating on `$?` must not carry on to trade it.
    The exchange rules not being fetchable is `EXCHANGE`. The report of a
    rejected preview is still printed first, in the format asked for.
    """
    try:
        quantity = Decimal(args.qty)
        reference_price = Decimal(args.price)
    except InvalidOperation:
        return CliOutcome(
            ExitCode.USAGE,
            f"Invalid number: qty={args.qty!r} price={args.price!r}",
        )

    request = OrderRequest(
        symbol=args.symbol,
        side=OrderSide[args.side],
        order_type=OrderType[args.type],
        quantity=quantity,
        reference_price=reference_price,
    )

    try:
        preview = app.container.resolve(IOrderSubmission).preview(request)
    except ValueError as exc:
        return CliOutcome(ExitCode.USAGE, f"Could not preview the order: {exc}")
    except (
        BinanceAPIException,
        BinanceRequestException,
        RequestException,
        SymbolRulesUnavailableError,
    ):
        # `IMarketMetadataProvider`, unlike `ITradingAccountReader`
        # (EPIC-021D), makes no "never raises" promise — this is the one
        # network call this task's CLI makes, and this is where its
        # failure is classified and shown, not inside the domain/handler.
        return CliOutcome(
            ExitCode.EXCHANGE,
            "Could not fetch exchange rules for "
            f"{args.symbol} — check your network connection and try again.",
        )

    refused = emit_report(
        order_preview_report(preview), args, app.container.resolve(IReportFormats)
    )
    if refused is not None:
        return refused
    if preview.notional_check is not NotionalCheck.SUFFICIENT:
        return CliOutcome(ExitCode.USAGE)
    return None
