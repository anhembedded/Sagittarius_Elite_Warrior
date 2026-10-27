"""`EPIC-047H` — the host reads each bot's exchange facts again, on a schedule, under a weight ceiling (decision record 2026-10-27, D4).

@details The VPS tab opens no connection to Binance, so what a running bot's facts say is as old as
the host's last read of them. This is the schedule of that read. A call to `step()` does at most one
read and returns how long to sleep: the worker (`FactsRefreshing`) is the only caller, so nothing
here is shared with the trading threads except through the venue's gate.

**What bounds it.** (1) *Priority*: every read is `RequestPriority.ROUTINE` (`ExchangeBotReadRefresh`),
so it waits at the 70 % line and never touches the exit reserve. (2) *Ceiling*: before a read the
venue's `WeightLedger` must have room for its expected cost under `ceiling_pct` of the venue's minute
weight, and after it the cost is what the used-weight header says (`measured_weight`); the interval
therefore stretches with the number of bots (`n` bots at `c` weight a read hold `n * c / ceiling` minutes
between two reads of one bot) and a wrong estimate lengthens it, never overspends. (3) *No burst*: a
closed gate, a full ledger or a read that cannot be measured *holds the whole venue* and spreads its
overdue bots over the interval again, so reopening queues nothing.

**Failure** leaves the last good snapshot and its `read_at` (`ExchangeBotReadRefresh` records only a
read that happened) and is logged once per cause until a read succeeds.

**Rounds.** A bot's round is its facts read, and on every `fills_every_rounds`-th round (the fifth) its planner
inputs and its fills too, each a read of its own that the ceiling paces and charges on its own. An asked-for
refresh is a round with all three. An account-history read is 20 weight a day window, which is why the
fills are not on every round, and why the first connect of a tab asks for the bot it selects.

@par Threads
`step` runs on the worker only. `request` is called from the control poller's thread and touches
the queue and the last-read memory under `_lock`; it never reads the exchange.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
    RefreshOutcome,
    RefreshTarget,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_budget import (
    VenueBudget,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_costs import (
    UNMEASURED_KINDS,
    ReadKind,
    measured_weight,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_report import (
    RefreshReport,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_work import (
    ASKED_ROUND,
    BETWEEN_READS_S,
    CANDLES_EVERY_S,
    IDLE_S,
    MIN_SPACING_S,
    SCOPE_OF,
    SLOW_KINDS,
    STARTUP_GRACE_S,
    STATIC_EVERY_S,
    Job,
    Meters,
    Read,
    Slot,
    State,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    ON_DEMAND_MIN_INTERVAL_S,
    IFactsRefreshRequests,
    RefreshRequestAnswer,
    RefreshRequestVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_weight_meter import (
    IVenueWeightMeter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Operations.VpsRefresh")
_READ_RAISED = "the read raised"


class FactsRefresher(IFactsRefreshRequests):
    def __init__(
        self,
        source: IBotReadRefresh,
        meters: Meters,
        settings: VpsFeedSettings,
        clock: Callable[[], float],
        wall: Callable[[], float],
        wake: Callable[[], None] = lambda: None,
    ) -> None:
        """@param clock Monotonic seconds. @param wall Epoch seconds, for the minute the gate closes to.
        @param wake Asked when a request is queued, so the worker does not sleep through it."""
        self._source = source
        self._meters = meters
        self._settings = settings
        self._clock = clock
        self._wall = wall
        self._wake = wake
        self._state = State()
        self._slots: dict[str, Slot] = {}
        #: Asked-for rounds being worked through, by bot.
        self._asked: dict[str, list[ReadKind]] = {}
        #: The targets of this step, and when each symbol's candles were last synced (monotonic seconds).
        self._targets: dict[str, RefreshTarget] = {}
        self._candles_at: dict[tuple[TradingVenue, str], float] = {}
        #: A slow read that found no room waits until then; the key is the bot and whether the tab asked.
        self._deferred: dict[tuple[str, bool], float] = {}
        self._budgets: dict[TradingVenue, VenueBudget] = {}
        self._static_due: dict[TradingVenue, float] = {}
        self._report = RefreshReport(settings.ceiling_pct)

    # -- the requesting thread -------------------------------------------------------------

    def request(self, bot_id: str) -> RefreshRequestAnswer:
        if not self._settings.refresh_enabled:
            return RefreshRequestAnswer(RefreshRequestVerdict.OFF)
        with self._state.lock:
            if bot_id not in self._state.known:
                return RefreshRequestAnswer(RefreshRequestVerdict.UNKNOWN_BOT)
            last = self._state.last_read.get(bot_id)
            if (
                last is not None
                and self._clock() - last.at_s < ON_DEMAND_MIN_INTERVAL_S
            ):
                return RefreshRequestAnswer(
                    RefreshRequestVerdict.ALREADY_FRESH, last.read_at
                )
            if bot_id not in self._state.pending:
                self._state.pending.append(bot_id)
        self._wake()
        return RefreshRequestAnswer(
            RefreshRequestVerdict.QUEUED, None if last is None else last.read_at
        )

    # -- the worker --------------------------------------------------------------------------

    def step(self) -> float:
        """At most one read; the seconds to sleep before the next step."""
        now = self._clock()
        if not self._settings.refresh_enabled:
            return IDLE_S
        targets = {target.bot_id: target for target in self._source.targets()}
        self._targets = targets
        self._sync(targets, now)
        job = self._next_job(targets, now)
        if job is None:
            return self._sleep_until_next_due(now)
        return self._attempt(job, now)

    def _sync(self, targets: dict[str, RefreshTarget], now: float) -> None:
        with self._state.lock:
            self._state.known = dict(targets)
            self._state.pending = [b for b in self._state.pending if b in targets]
        for gone in self._asked.keys() - targets.keys():
            del self._asked[gone]
        exposed = [t for t in targets.values() if t.exposure]
        for gone in self._slots.keys() - {t.bot_id for t in exposed}:
            del self._slots[gone]
            self._report.forget(gone)
        newcomers = [t for t in exposed if t.bot_id not in self._slots]
        spacing = self._spacing(len(exposed))
        for index, target in enumerate(newcomers):
            self._slots[target.bot_id] = Slot(now + STARTUP_GRACE_S + index * spacing)
        for venue in {t.venue for t in exposed}:
            self._static_due.setdefault(venue, now + STARTUP_GRACE_S)

    def _next_job(self, targets: dict[str, RefreshTarget], now: float) -> Job | None:
        self._take_requests()
        job = self._candidate(targets, now)
        while job is not None and self._candles_are_recent(job, now):
            self._advance_over(job, now)
            job = self._candidate(targets, now)
        return job

    def _candidate(self, targets: dict[str, RefreshTarget], now: float) -> Job | None:
        for bot_id, queue in self._asked.items():
            if self._ready(bot_id, targets[bot_id].venue, now, asked=True):
                return Job(queue[0], targets[bot_id].venue, bot_id, asked=True)
        for venue, due in sorted(self._static_due.items(), key=lambda item: item[1]):
            if due <= now and self._venue_free(venue, now):
                return Job(ReadKind.STATIC, venue)
        running = sorted(
            (slot.due_s, bot_id)
            for bot_id, slot in self._slots.items()
            if (slot.queue or slot.due_s <= now)
            and self._ready(bot_id, targets[bot_id].venue, now, asked=False)
        )
        if not running:
            return None
        slot = self._slots[running[0][1]]
        if not slot.queue:
            slot.queue = self._round_of(slot)
        return Job(slot.queue[0], targets[running[0][1]].venue, running[0][1])

    def _take_requests(self) -> None:
        with self._state.lock:
            asked, self._state.pending = self._state.pending, []
        for bot_id in asked:
            self._asked.setdefault(bot_id, list(ASKED_ROUND))

    def _round_of(self, slot: Slot) -> list[ReadKind]:
        every = self._settings.fills_every_rounds
        return (
            [ReadKind.FACTS, ReadKind.CANDLES, ReadKind.PLANNER, ReadKind.FILLS]
            if slot.rounds % every == every - 1
            else [ReadKind.FACTS]
        )

    def _ready(
        self, bot_id: str, venue: TradingVenue, now: float, *, asked: bool
    ) -> bool:
        deferred = self._deferred.get((bot_id, asked), 0.0)
        return self._venue_free(venue, now) and now >= deferred

    def _venue_free(self, venue: TradingVenue, now: float) -> bool:
        return now >= self._budget(venue).held_until

    def _budget(self, venue: TradingVenue) -> VenueBudget:
        if venue not in self._budgets:
            self._budgets[venue] = VenueBudget(self._settings.ceiling_pct)
        return self._budgets[venue]

    def _attempt(self, job: Job, now: float) -> float:
        meter = self._meters(job.venue)
        if meter is None:
            self._hold_unmeasured(job.venue, now)
            return IDLE_S
        reading = meter.read()
        budget = self._budget(job.venue)
        verdict = budget.judge(job.kind, reading, now, self._wall())
        if not verdict.may_go:
            if verdict.reason == "ceiling" and job.kind in SLOW_KINDS:
                self._deferred[(job.bot_id, job.asked)] = now + verdict.wait_s
                return BETWEEN_READS_S
            if verdict.reason == "too_dear":
                budget.reprobe(job.kind, now)
            self._hold(job.venue, verdict.wait_s, verdict.reason, now)
            return min(verdict.wait_s, IDLE_S)
        self._read(job, meter, now)
        return BETWEEN_READS_S

    def _read(
        self,
        job: Job,
        meter: IVenueWeightMeter,
        now: float,
    ) -> None:
        budget = self._budget(job.venue)
        before = meter.read()
        outcome = self._do_charged(job)
        after = meter.read()
        planned = budget.costs.expected(job.kind)
        cost = (
            planned
            if job.kind in UNMEASURED_KINDS
            else measured_weight(before, after, planned)
        )
        budget.ledger.charge(cost, self._clock())
        budget.costs.observe(job.kind, cost)
        budget.pace(cost, after, self._clock())
        self._report.spent(cost)
        if outcome.read_at is None and not after.routine_open:
            self._hold(
                job.venue,
                budget.judge(job.kind, after, now, self._wall()).wait_s,
                "gate",
                now,
            )
            return
        self._deferred.pop((job.bot_id, job.asked), None)
        self._settle(job, outcome, now)

    def _do_charged(self, job: Job) -> RefreshOutcome:
        """A read that raises has still spent what its requests cost: it is a failed read, charged and paced like
        any other, never a job retried at once (`IBotReadRefresh` says it does not raise; this is the seam that
        keeps the ceiling true if one does)."""
        try:
            return self._do(job)
        except Exception as failure:  # noqa: BLE001 - the seam to the exchange reads: a raise is a word, and the weight spent is still charged
            # the exception's words may carry what a key store or a URL said: DEBUG only; the report logs the cause once
            logger.debug(
                "a %s read of %s raised: %s",
                job.kind.value,
                job.bot_id or job.venue.value,
                failure,
            )
            return RefreshOutcome(None, _READ_RAISED)

    def _do(self, job: Job) -> RefreshOutcome:
        if job.kind is ReadKind.STATIC:
            return self._source.refresh_static(job.venue)
        return self._source.refresh(job.bot_id, SCOPE_OF[job.kind])

    def _settle(self, job: Job, outcome: RefreshOutcome, now: float) -> None:
        key = job.bot_id or job.venue.value
        if job.kind is ReadKind.STATIC:
            self._static_due[job.venue] = now + STATIC_EVERY_S
        else:
            self._advance(job, outcome, now)
        if job.kind is ReadKind.CANDLES and outcome.read_at is not None:
            self._candles_at[self._candles_key(job)] = now
        if job.kind is ReadKind.FACTS and outcome.read_at is not None:
            with self._state.lock:
                self._state.last_read[job.bot_id] = Read(self._clock(), outcome.read_at)
        self._report.read(key, job.kind.value, outcome.problem, outcome.read_at)

    def _advance(self, job: Job, outcome: RefreshOutcome, now: float) -> None:
        """The read is done, well or badly: the round moves on, or ends when its facts could not be read."""
        self._advance_over(
            job,
            now,
            facts_failed=job.kind is ReadKind.FACTS and outcome.read_at is None,
        )

    def _advance_over(
        self, job: Job, now: float, *, facts_failed: bool = False
    ) -> None:
        asked = self._asked.get(job.bot_id) if job.asked else None
        queue = asked if asked is not None else self._slots[job.bot_id].queue
        queue.pop(0)
        if facts_failed:
            queue.clear()
        if queue:
            return
        if asked is not None:
            del self._asked[job.bot_id]
            return
        slot = self._slots[job.bot_id]
        slot.due_s = now + self._settings.refresh_interval_s
        if not facts_failed:
            slot.rounds += 1

    def _candles_are_recent(self, job: Job, now: float) -> bool:
        """A symbol's candles synced a few minutes ago are not synced again, whoever asks and however many bots share it."""
        if job.kind is not ReadKind.CANDLES:
            return False
        last = self._candles_at.get(self._candles_key(job))
        return last is not None and now - last < CANDLES_EVERY_S

    def _candles_key(self, job: Job) -> tuple[TradingVenue, str]:
        return (job.venue, self._targets[job.bot_id].symbol)

    def _hold(
        self,
        venue: TradingVenue,
        wait_s: float,
        reason: str,
        now: float,
    ) -> None:
        """Nothing on `venue` is read for `wait_s`. The overdue bots keep their places: the oldest is read first."""
        self._budget(venue).hold(wait_s, now)
        self._report.held(venue, wait_s, reason)

    def _hold_unmeasured(self, venue: TradingVenue, now: float) -> None:
        self._report.unmeasured(venue)
        self._hold(venue, IDLE_S * 12, "unmeasured", now)

    def _spacing(self, count: int) -> float:
        return max(self._settings.refresh_interval_s / max(count, 1), MIN_SPACING_S)

    def _sleep_until_next_due(self, now: float) -> float:
        dues = [slot.due_s for slot in self._slots.values()]
        dues += list(self._static_due.values()) + list(self._deferred.values())
        return (
            IDLE_S if not dues else max(min(min(dues) - now, IDLE_S), MIN_SPACING_S / 2)
        )
