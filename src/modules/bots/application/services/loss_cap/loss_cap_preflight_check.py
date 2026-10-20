"""Pre-flight: the account-level loss cap is set, readable and not tripped (`EPIC-026L`).

The figure is the owner's and has no default, so an unset cap is not an error everywhere: on a
host that runs a mainnet bot it is a **WARN** that says the host will run real money with nothing
that stops the day's loss (decision N3), and on testnet it is a PASS that says the cap is off.
Three findings are always worth a line:

  · a figure that is set and cannot be read is a **FAIL** (`CONFIGURATION`): the host would not
    start anyway, and it would rather say why here;
  · a record that cannot be read is a **WARN**: the cap starts tripped;
  · a tripped cap is a **WARN**: no bot starts or resumes until the owner acknowledges it, so a
    `run --resume-recovering` that follows will be refused for every bot.

A venue is judged mainnet when the operator named one (`--venue`) or when a stored bot is
defined on one; a bot file this build refuses is not counted (the bot-files check says so).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
    LossCapRecordUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    LossCapFigure,
    LossCapFigureError,
    parse_loss_cap_figure,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

CHECK_ID = "account-loss-cap"

_SUBJECT = "account loss cap"
_KEY = ConfigKeys.BOTS_ACCOUNT_LOSS_CAP.value
_ACKNOWLEDGE = "Acknowledge it with `main.py bot loss-cap-ack` on the running host."


class LossCapPreflightCheck(IPreflightCheck):
    check_id = CHECK_ID
    title = "Account-level loss cap"

    def __init__(
        self, config: IConfigReader, record: ILossCapStore, bots: IBotStore
    ) -> None:
        self._config = config
        self._record = record
        self._bots = bots

    def run(self, scope: PreflightScope) -> CheckResult:
        try:
            figure = parse_loss_cap_figure(self._config.get(_KEY))
        except LossCapFigureError as invalid:
            return self._result(
                CheckFinding(
                    _SUBJECT,
                    CheckStatus.FAIL,
                    f"{_KEY} is set and cannot be used: {invalid}",
                    f"Set {_KEY} to an amount and its quote asset (for example '500 USDT'), "
                    "or empty it to switch the cap off.",
                    CheckCause.CONFIGURATION,
                )
            )
        findings = [self._figure_finding(figure, scope)]
        findings.extend(self._record_findings())
        return CheckResult(self.check_id, self.title, tuple(findings))

    def _result(self, finding: CheckFinding) -> CheckResult:
        return CheckResult.single(self.check_id, self.title, finding)

    def _figure_finding(
        self, figure: LossCapFigure | None, scope: PreflightScope
    ) -> CheckFinding:
        if figure is not None:
            return CheckFinding(
                _SUBJECT,
                CheckStatus.PASS,
                f"set to {figure.text()} (the day's loss, UTC)",
            )
        if not self._runs_mainnet(scope):
            return CheckFinding(
                _SUBJECT,
                CheckStatus.PASS,
                f"off: {_KEY} is not set (no mainnet bot here)",
            )
        return CheckFinding(
            _SUBJECT,
            CheckStatus.WARN,
            f"off: {_KEY} is not set, and this host runs a mainnet venue; nothing stops the "
            "day's loss across the bots",
            f"Set {_KEY} to the most you accept to lose in one UTC day, e.g. '500 USDT'.",
        )

    def _record_findings(self) -> list[CheckFinding]:
        try:
            record = self._record.read()
        except LossCapRecordUnreadableError as unreadable:
            return [
                CheckFinding(
                    _SUBJECT,
                    CheckStatus.WARN,
                    f"{unreadable}; the cap starts tripped",
                    _ACKNOWLEDGE,
                )
            ]
        if record is None or record.trip is None:
            return []
        return [
            CheckFinding(
                _SUBJECT,
                CheckStatus.WARN,
                f"tripped: {record.trip.detail}; no bot starts or resumes until acknowledged",
                _ACKNOWLEDGE,
            )
        ]

    def _runs_mainnet(self, scope: PreflightScope) -> bool:
        if scope.venue is not None:
            return _is_mainnet(scope.venue)
        return any(
            stored.bot.definition.venue.is_mainnet
            for stored in self._bots.load_all().bots
        )


def _is_mainnet(name: str) -> bool:
    try:
        return TradingVenue(name).is_mainnet
    except ValueError:
        return False
