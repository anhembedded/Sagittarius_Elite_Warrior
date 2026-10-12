"""`EPIC-021F` — headless `main.py order-dry-run`. The epic's most
important milestone: proves signature, key permissions, and payload are
all correct against the real exchange — with zero orders ever created
(`POST /fapi/v1/order/test`)."""

import argparse
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    exit_code_of_binance_error,
    exit_code_of_order_rejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_dry_run_formatter import (
    format_submission_accepted,
    format_submission_rejected,
    format_submission_request,
)
from sagittarius_engine import App
from sagittarius_engine.exceptions import DependencyResolutionError


def execute_order_dry_run(app: App, args: argparse.Namespace) -> CliOutcome | None:
    """Dry-run one order; `None` when the exchange accepted it.

    `EPIC-038B` — a rejected or unsendable order is a non-zero exit with the
    text this command always printed, now written to stderr by the entry point
    (the request it echoed before the failure stays on stdout): `USAGE` when the order itself is
    unusable, `CONFIGURATION` when trading is switched off, `EXCHANGE` when the
    exchange refused it or could not be reached.
    """
    try:
        quantity = Decimal(args.qty)
        reference_price = Decimal(args.price)
    except InvalidOperation:
        return CliOutcome(
            ExitCode.USAGE,
            f"Invalid number: qty={args.qty!r} price={args.price!r}",
        )

    order_request = OrderRequest(
        symbol=args.symbol,
        side=OrderSide[args.side],
        order_type=OrderType[args.type],
        quantity=quantity,
        reference_price=reference_price,
    )

    # One port for both halves of this command: what the order becomes, then
    # whether the venue itself accepts it (`EPIC-025` PR 1.3c-2).
    submission = app.container.resolve(IOrderSubmission)

    try:
        preview = submission.preview(order_request)
    except ValueError as exc:
        return CliOutcome(ExitCode.USAGE, f"Could not preview the order: {exc}")
    except (
        BinanceAPIException,
        BinanceRequestException,
        RequestException,
        SymbolRulesUnavailableError,
    ):
        return CliOutcome(
            ExitCode.EXCHANGE,
            "Could not fetch exchange rules for "
            f"{args.symbol} — check your network connection and try again.",
        )

    print(format_submission_request(preview.order))
    print()

    try:
        submission.validate(order_request)
    except DependencyResolutionError:
        return CliOutcome(
            ExitCode.CONFIGURATION,
            "Trading venue is DISABLED. Enable it by setting "
            '"exchange.trading_venue": "futures_testnet" in '
            "src/config/user_config.json, then try again.",
        )
    except OrderRejectedByExchangeError as exc:
        return CliOutcome(
            exit_code_of_order_rejection(exc.reason), format_submission_rejected(exc)
        )
    except InvalidOrderForSubmissionError as exc:
        return CliOutcome(ExitCode.USAGE, f"Order is not valid for submission: {exc}")
    except BinanceAPIException as exc:
        return _exchange_error_outcome(exc)
    except (BinanceRequestException, RequestException):
        return CliOutcome(
            ExitCode.EXCHANGE,
            "Could not send the payload to the exchange — check your network connection and try again.",
        )

    print(format_submission_accepted())
    return None


def _exchange_error_outcome(exc: BinanceAPIException) -> CliOutcome:
    """A raw Binance error from the test endpoint (`EPIC-038` D9): a key or
    signature the exchange refuses is the operator's to fix (5), anything else a
    wait (6). The code is not a secret; the exchange's own text can hold a signed
    URL, so only the code travels."""
    code = exit_code_of_binance_error(exc.code)
    if code is ExitCode.CONFIGURATION:
        return CliOutcome(
            code,
            f"The exchange refused the API key or its signature (code {exc.code}) — "
            "check the key, its permissions and its IP list; repeating the command will not help.",
        )
    return CliOutcome(
        code,
        "Could not send the payload to the exchange — check your network connection and try again.",
    )
