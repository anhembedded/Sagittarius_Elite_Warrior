"""`EPIC-022B` — handler for `ArmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy.command import (
    ArmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    DEFAULT_LEVERAGE,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_owner import (
    STRATEGY_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    refusal_words,
)

logger = logging.getLogger("App.CommandHandler")

#: `EPIC-027N` AC5 — Phase 1 Spot trades USDT-quoted pairs only (ADR D9/O4).
#: The same literal `emergency_stop/handler.py`/`spot_account_reader.py`
#: already carry, not a new one (noted, not asked to fix, on the `EPIC-027M`
#: PR review).
_QUOTE_ASSET = "USDT"


class ArmStrategyCommandHandler(ICommandHandler[ArmStrategyCommand, ArmStrategyResult]):
    """
    @brief The only place `LiveStrategySession.arm()` is called from the UI
    — where "may this be armed at all" is decided.

    @details Order of checks is deliberate, cheapest and most important
    first:

    1. **Symbol/interval present** → an incomplete config can never be
       armed; `LiveStrategySession.arm()` would raise, and a raised
       exception is not a UI-branchable answer.
    2. **Strategy key known** → asked of the same `StrategyRegistry` the
       factory will build from, not a second one resolved separately.
    3. **`EPIC-027N`: three Spot-only refusals** (leverage fixed at 1, no
       `SHORT`-capable strategy, USDT-quoted symbols only) → checked only
       once the strategy key and symbol/interval are known good, since two
       of the three need the resolved strategy's own `supported_directions`
       or the symbol string. A no-op on every other venue.
    4. **Parameters accepted** → by building it (`validate`), before anything is
       opened or claimed. `BaseStrategy.__init__`
       already raises `ValueError` for an undeclared name and each
       `input_*()` enforces its own `minval`/`maxval`, so re-validating
       here would create a second validator free to disagree with the
       strategy's own. The build that validates is the build that gets
       armed — there is no window where a config passes validation and
       then fails to construct.
    5. **`EPIC-034C`: the order session** is opened — the account is
       reconciled first, and a position the app did not open refuses the arm
       (`SESSION_NOT_READY`). Arming is one of the three actions that start
       trading, so there is no switch to turn on first.
    6. **The symbol is claimed**, then **no open position on it** (the symbol
       being armed or already armed) → refuse (`POSITION_OPEN`) and give the
       claim back. This is the safety rule that refused arming while trading
       was ON (`EPIC-022` §4.1), restated as its cause: swapping the engine
       underneath an open position strands that position. The claim comes
       first so no manual order can open a position between the check and the arm.
    """

    def __init__(
        self,
        sessions: VenueStrategySessions,
        trading_ports: IVenueTradingPorts,
        config_store: LiveStrategyConfigStore,
        publisher: IEventPublisher,
    ) -> None:
        self._sessions = sessions
        self._trading_ports = trading_ports
        #: `EPIC-025` PR 4.3m — persisting a successful arming used to be the
        #: caller's job (`StrategyArmingCoordinator.on_arm_clicked()`), which
        #: only worked because that coordinator lived in the same legacy tree
        #: as this handler. Moved here, next to the validation and the symbol
        #: lease that already gate `arm()`, so every caller through
        #: `IStrategyArming` gets it for free and none can forget it.
        self._config_store = config_store
        #: `EPIC-033K` stage 3 — every screen drawing a venue's armed
        #: strategy hears that it changed (`ArmedStrategyChangedEvent`).
        self._publisher = publisher

    def execute(self, command: ArmStrategyCommand) -> ArmStrategyResult:
        config = command.config
        logger.debug(
            "Handling ArmStrategyCommand for '%s' on %s",
            config.strategy_key,
            command.venue.value,
        )
        # `EPIC-028B` — the venue's own session and trading switch: arming on
        # Spot is judged by Spot's rules and leaves Futures' strategy alone.
        session = self._sessions.get(command.venue)
        trading_session = self._trading_ports.get(command.venue).trading_session

        snapshot = trading_session.snapshot()
        if not config.strategy_key:
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.STRATEGY_NOT_FOUND
            )
        if not config.symbol or not config.interval:
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL,
            )
        if config.strategy_key not in session.available_strategy_keys:
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.STRATEGY_NOT_FOUND
            )

        # `EPIC-027N` — three Spot-only refusals (ADR O2/O4/D9). Checked only
        # on a Spot venue: none of them constrain Futures arming at all.
        if snapshot.market_type is MarketType.SPOT:
            if config.leverage != DEFAULT_LEVERAGE:
                return ArmStrategyResult(
                    armed=False,
                    block_reason=ArmStrategyBlockReason.SPOT_LEVERAGE_NOT_SUPPORTED,
                )
            if SignalAction.SHORT in session.declared_directions(config.strategy_key):
                return ArmStrategyResult(
                    armed=False,
                    block_reason=ArmStrategyBlockReason.SPOT_SHORT_NOT_SUPPORTED,
                )
            if not config.symbol.endswith(_QUOTE_ASSET):
                return ArmStrategyResult(
                    armed=False,
                    block_reason=ArmStrategyBlockReason.SPOT_QUOTE_ASSET_NOT_SUPPORTED,
                )

        # The strategy is built (validated) before anything is opened or claimed,
        # so a refused parameter set costs nothing and opens nothing.
        try:
            session.validate(config)
        except ValueError as exc:
            logger.info(
                "Refused to arm '%s': %s", config.strategy_key, exc, exc_info=False
            )
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.INVALID_PARAMS,
                error_message=str(exc),
            )

        # `EPIC-034C` — arming starts trading: the order session opens here,
        # after every refusal that costs nothing and before anything is claimed.
        opened = trading_session.ensure_ready()
        if not opened.ready:
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.SESSION_NOT_READY,
                error_message=refusal_words(opened),
            )

        # `EPIC-025` PR 2.1f — claim the symbol BEFORE arming, so a refused
        # claim means nothing was armed. The reverse order would arm a strategy
        # and then discover it may not have the symbol, leaving a live engine
        # to unwind. A claim cannot be refused today (one armed strategy means
        # one owner), which is exactly why the order has to be the one that
        # stays correct when ADR §7 item 15's second strategy arrives.
        armed_config = session.config
        previous_symbol = armed_config.symbol if armed_config else None
        if not trading_session.claim_symbol(config.symbol, STRATEGY_OWNER):
            logger.info(
                "Refused to arm '%s': %s is managed by another owner.",
                config.strategy_key,
                config.symbol,
            )
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.SYMBOL_LEASED
            )

        # `EPIC-034C` — the open-position check comes after the claim: the lease
        # already refuses a manual order on this symbol, so no position can open
        # on it between the check and the arm. `known_open_symbols` is read
        # after the session opened, which resets it from the account just read.
        held = {config.symbol, previous_symbol}
        if held & set(trading_session.snapshot().known_open_symbols):
            self._give_back_claim(trading_session, config.symbol, previous_symbol)
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.POSITION_OPEN
            )

        try:
            session.arm(config)
        except ValueError as exc:
            logger.info(
                "Refused to arm '%s': %s", config.strategy_key, exc, exc_info=False
            )
            self._give_back_claim(trading_session, config.symbol, previous_symbol)
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.INVALID_PARAMS,
                error_message=str(exc),
            )
        self._config_store.save(command.venue, config)
        self._publisher.publish(ArmedStrategyChangedEvent(True, venue=command.venue))
        return ArmStrategyResult(armed=True)

    @staticmethod
    def _give_back_claim(
        trading_session: ITradingSession, symbol: str, previous_symbol: str | None
    ) -> None:
        """The claim was this call's, so this call gives it back — and, because
        a claim replaces the owner's earlier one, takes the earlier symbol
        back too. Leaving the new one held would block the user's own next
        manual order on a symbol no strategy is running."""
        trading_session.release_symbol(symbol, STRATEGY_OWNER)
        if previous_symbol is not None and previous_symbol != symbol:
            trading_session.claim_symbol(previous_symbol, STRATEGY_OWNER)
