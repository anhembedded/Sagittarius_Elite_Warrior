"""Research probe: do "market maker manipulation" footprints predict anything?

Standalone script, not a test — nothing here is imported by `src/`.

WHY THIS EXISTS
---------------
"Market maker is manipulating the price" is not a falsifiable statement: no
feed exposes a `is_manipulating` flag, so a strategy built directly on that
belief can only ever confirm itself. This probe replaces the belief with four
*measurable* footprints computable from stored 1-second klines, and then asks
the only question that matters:

    after each footprint fires, does price actually move the way the theory
    says it should — MORE OFTEN THAN IT DOES ON A RANDOM BAR?

The baseline comparison is the entire point. An event that "works 55% of the
time" is worthless if a coin flip on every bar in the same window also works
55% of the time. This script always reports both numbers, plus the round-trip
fee threshold the edge has to clear before it is tradeable at all.

THE FOUR FOOTPRINTS
-------------------
1. LIQUIDITY SWEEP  - price pokes past the recent extreme (where stop-loss
   orders cluster), then closes back inside the range. The classic stop hunt.
   Directional by construction: a swept low predicts UP.
2. VOLUME CLIMAX    - volume spikes far above its rolling baseline with
   aggression lopsided to one side. Direction is the OPEN QUESTION (follow the
   aggression, or fade it?) — see "SIGN CONVENTION" below.
3. ABSORPTION       - heavy one-sided aggression that price refuses to follow.
   The strongest single footprint of a large passive participant soaking up
   flow. Predicts a move AGAINST the aggression.
4. LARGE-TRADE SPIKE- average trade size (volume / number_of_trades) jumps far
   above baseline: few big participants rather than the retail crowd.

SIGN CONVENTION
---------------
Every forward return is signed in the direction the footprint's "follow"
reading predicts. So a POSITIVE mean return means following the footprint
works; a consistently NEGATIVE one means the FADE reading is the correct one.
This is how the follow-vs-fade question gets settled by data instead of by
opinion.

WHAT THIS PROBE CANNOT SEE
--------------------------
Spoofing (large orders placed then cancelled) and iceberg orders live in the
L2 order book, which this repo does not ingest and which Binance does not
serve historically — so they cannot be replayed or backtested, only observed
going forward. Every footprint here is a trade-print proxy, not the book
itself. See the report this feeds for the full argument.

HOW TO RUN
----------
Against klines already in the local DB (needs the project venv):

    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/manipulation_footprint_probe.py \
        --source db --symbol BTCUSDT

Fetching a fresh window from Binance public REST (no API key needed; burns
real API weight, so keep the window small):

    ... manipulation_footprint_probe.py --source binance --symbol BTCUSDT --days 2

Self-test on synthetic bars — needs no venv, no DB, no network. Verifies the
detectors fire on hand-built footprints and stay silent on flat noise:

    PYTHONPATH=. python3 Sagittarius_Elite_Warrior/scripts/manipulation_footprint_probe.py --self-test
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)

# --------------------------------------------------------------------------- #
# Tunables. Every one of these is a knob that can overfit a result, which is
# exactly why they are named constants at the top of the file instead of
# literals buried in the detectors: the report prints them, so any number this
# script produces can be reproduced against the settings that produced it.
# --------------------------------------------------------------------------- #

#: Bars of history used as the "normal" baseline for volume and trade size.
#: 300 x 1s = 5 minutes — long enough to smooth per-second noise, short enough
#: to still track the current session's activity level (overnight volume and
#: US-open volume differ by multiples, so an ABSOLUTE volume threshold would be
#: either mute or screaming depending on the hour).
BASELINE_BARS = 300

#: Bars looked back for the swing high/low a sweep has to pierce.
SWEEP_LOOKBACK_BARS = 60

#: Volume must exceed baseline by this multiple to count as a spike.
VOLUME_SPIKE_MULT = 4.0

#: Average trade size must exceed its baseline by this multiple.
TRADE_SIZE_SPIKE_MULT = 3.0

#: |delta| above this counts as "lopsided aggression". delta is
#: (aggressive_buy - aggressive_sell) / volume, so 0.4 means roughly a 70/30
#: split between the two sides.
DELTA_IMBALANCE = 0.4

#: For ABSORPTION: aggression is lopsided this hard...
ABSORPTION_DELTA = 0.5

#: ...yet the bar's close travels less than this fraction of its own range.
#: Heavy one-sided pressure that moves nothing = something is absorbing it.
ABSORPTION_BODY_RATIO = 0.25

#: A sweep bar's rejection wick must be at least this fraction of its range,
#: so a bar that simply closed at its low does not read as a "rejection".
SWEEP_WICK_RATIO = 0.5

#: How far past the swing level price must actually travel, as a multiple of
#: the average bar range over the lookback window. Without this the detector
#: fires on a bar that pierced the prior high by a single tick — which is not a
#: stop hunt, it is quantisation noise, and it floods the sample with events
#: that have no stops behind them. Scaled to recent range rather than a fixed
#: price amount so the same threshold works on a $0.60 altcoin and a $90k BTC.
SWEEP_MIN_PENETRATION_RANGES = 0.5

#: Seconds ahead to measure. 1s bars, so these are literally seconds.
FORWARD_HORIZONS_SEC = (5, 15, 30, 60)

#: Round-trip cost assumption, in basis points (1 bp = 0.01%). Binance futures
#: taker is ~4 bp a side, so ~8 bp in and out, plus slippage — and entering on
#: a volume spike is the worst possible moment for slippage. An edge smaller
#: than this is not an edge, it is a donation.
ROUND_TRIP_COST_BPS = 10.0

#: Below this many events, any hit rate reported is noise. Printed as a warning
#: rather than enforced, so a thin sample is visible instead of silently absent.
MIN_EVENTS_FOR_SIGNIFICANCE = 30

_BPS_PER_UNIT = 10_000.0
_DEFAULT_DAYS = 2
_EPSILON = 1e-12


class Footprint(str, Enum):
    """The four measurable events this probe looks for."""

    LIQUIDITY_SWEEP = "liquidity_sweep"
    VOLUME_CLIMAX = "volume_climax"
    ABSORPTION = "absorption"
    LARGE_TRADE_SPIKE = "large_trade_spike"


@dataclass(frozen=True)
class BarFeatures:
    """Per-bar derived quantities every detector reads, computed in one pass.

    Kept separate from `MarketData` because these are *relative* to a rolling
    baseline — they are properties of a bar within its recent context, not of
    the bar itself, and they change meaning if the baseline window changes.
    """

    index: int
    #: (aggressive_buy - aggressive_sell) / volume, in [-1, 1]. Positive means
    #: buyers were the ones crossing the spread.
    delta: float
    #: This bar's volume as a multiple of the rolling baseline. 1.0 == normal.
    volume_ratio: float
    #: Average trade size as a multiple of its own rolling baseline.
    trade_size_ratio: float
    #: |close - open| / (high - low). Near 0 means price went nowhere despite
    #: whatever happened inside the bar.
    body_ratio: float
    #: Lower wick as a fraction of range — how far price was pushed down and
    #: rejected. Upper wick is the mirror.
    lower_wick_ratio: float
    upper_wick_ratio: float


@dataclass(frozen=True)
class Event:
    """One footprint firing on one bar, with the direction it predicts."""

    footprint: Footprint
    index: int
    at: datetime
    price: float
    #: +1 when the "follow" reading predicts price UP, -1 when DOWN. Forward
    #: returns are multiplied by this, so a positive result always means "the
    #: follow reading was right" regardless of which way the bar pointed.
    direction: int
    detail: str


@dataclass
class HorizonStats:
    """Forward-return statistics for one footprint at one horizon."""

    horizon_sec: int
    sample_count: int
    mean_bps: float
    median_bps: float
    hit_rate: float
    baseline_hit_rate: float
    baseline_mean_bps: float

    @property
    def edge_bps(self) -> float:
        """Mean return minus what a random bar in the same window returned.

        Subtracting the baseline is what separates a real signal from a window
        that simply trended: in a rising market EVERY long-biased event looks
        profitable until this subtraction is done.
        """
        return self.mean_bps - self.baseline_mean_bps

    @property
    def edge_after_cost_bps(self) -> float:
        return self.edge_bps - ROUND_TRIP_COST_BPS

    @property
    def hit_rate_edge(self) -> float:
        return self.hit_rate - self.baseline_hit_rate


@dataclass
class ProbeReport:
    """Everything the run produced, ready to print or serialise."""

    symbol: str
    bar_count: int
    window_start: datetime | None
    window_end: datetime | None
    events_by_footprint: dict[Footprint, list[Event]] = field(default_factory=dict)
    stats: dict[Footprint, list[HorizonStats]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Feature computation
# --------------------------------------------------------------------------- #


def _rolling_mean_ratio(value: float, window: deque[float]) -> float:
    """`value` as a multiple of the mean of `window`, or 1.0 while warming up.

    Returns 1.0 (== "perfectly normal") rather than None during warm-up so
    detectors never have to branch on a missing baseline; a warm-up bar simply
    cannot clear any spike threshold, which is the correct behaviour.
    """
    if not window:
        return 1.0
    mean = sum(window) / len(window)
    if mean <= _EPSILON:
        return 1.0
    return value / mean


def compute_features(klines: Sequence[MarketData]) -> list[BarFeatures]:
    """One pass over the bars producing every derived quantity the detectors need.

    The baseline windows deliberately hold only bars STRICTLY BEFORE the bar
    being described — including the current bar in its own baseline would dilute
    exactly the spike we are trying to measure, and worse, would leak the
    present into a number a strategy would have to compute live.
    """
    volume_window: deque[float] = deque(maxlen=BASELINE_BARS)
    trade_size_window: deque[float] = deque(maxlen=BASELINE_BARS)
    features: list[BarFeatures] = []

    for index, bar in enumerate(klines):
        price_range = bar.high_price - bar.low_price
        volume = bar.volume

        if volume > _EPSILON:
            aggressive_buy = bar.taker_buy_base_asset_volume
            aggressive_sell = volume - aggressive_buy
            delta = (aggressive_buy - aggressive_sell) / volume
        else:
            delta = 0.0

        trade_size = volume / bar.number_of_trades if bar.number_of_trades > 0 else 0.0

        if price_range > _EPSILON:
            body_ratio = abs(bar.close_price - bar.open_price) / price_range
            lower_wick = min(bar.open_price, bar.close_price) - bar.low_price
            upper_wick = bar.high_price - max(bar.open_price, bar.close_price)
            lower_wick_ratio = lower_wick / price_range
            upper_wick_ratio = upper_wick / price_range
        else:
            body_ratio = 0.0
            lower_wick_ratio = 0.0
            upper_wick_ratio = 0.0

        features.append(
            BarFeatures(
                index=index,
                delta=delta,
                volume_ratio=_rolling_mean_ratio(volume, volume_window),
                trade_size_ratio=_rolling_mean_ratio(trade_size, trade_size_window),
                body_ratio=body_ratio,
                lower_wick_ratio=lower_wick_ratio,
                upper_wick_ratio=upper_wick_ratio,
            )
        )

        volume_window.append(volume)
        if trade_size > 0.0:
            trade_size_window.append(trade_size)

    return features


# --------------------------------------------------------------------------- #
# Detectors. Each returns the bars where its footprint fired, with the
# direction the "follow" reading predicts.
# --------------------------------------------------------------------------- #


def detect_liquidity_sweep(
    klines: Sequence[MarketData], features: Sequence[BarFeatures]
) -> list[Event]:
    """Price pierces the recent extreme, then closes back inside it.

    The direction is not a choice here: a bar that swept the lows and closed
    back above them is a failed breakdown, which predicts UP. This is the one
    footprint where follow-vs-fade does not apply — the "fade" of the sweep IS
    the signal.
    """
    events: list[Event] = []
    for index in range(SWEEP_LOOKBACK_BARS, len(klines)):
        bar = klines[index]
        window = klines[index - SWEEP_LOOKBACK_BARS : index]
        prior_low = min(candle.low_price for candle in window)
        prior_high = max(candle.high_price for candle in window)
        feature = features[index]

        average_range = statistics.fmean(
            candle.high_price - candle.low_price for candle in window
        )
        min_penetration = average_range * SWEEP_MIN_PENETRATION_RANGES

        swept_low = (
            prior_low - bar.low_price >= min_penetration
            and bar.close_price > prior_low
            and feature.lower_wick_ratio >= SWEEP_WICK_RATIO
        )
        if swept_low:
            events.append(
                Event(
                    footprint=Footprint.LIQUIDITY_SWEEP,
                    index=index,
                    at=bar.close_time,
                    price=bar.close_price,
                    direction=1,
                    detail=f"swept low {prior_low:.2f}, closed {bar.close_price:.2f}",
                )
            )
            continue

        swept_high = (
            bar.high_price - prior_high >= min_penetration
            and bar.close_price < prior_high
            and feature.upper_wick_ratio >= SWEEP_WICK_RATIO
        )
        if swept_high:
            events.append(
                Event(
                    footprint=Footprint.LIQUIDITY_SWEEP,
                    index=index,
                    at=bar.close_time,
                    price=bar.close_price,
                    direction=-1,
                    detail=f"swept high {prior_high:.2f}, closed {bar.close_price:.2f}",
                )
            )
    return events


def _is_absorption(feature: BarFeatures) -> bool:
    """Whether this bar is heavy one-sided flow that price refused to follow.

    Shared by both detectors that care, because the two footprints would
    otherwise overlap and CONTRADICT each other: an absorbed sell climax is a
    volume spike with lopsided delta (so `detect_volume_climax` claims it,
    predicting DOWN) *and* an absorption bar (so `detect_absorption` claims it,
    predicting UP). The same bar cannot be evidence for both sides, so
    absorption — the more specific reading, since it adds the "price did not
    follow" condition — wins and the climax detector stands down.
    """
    return (
        feature.volume_ratio >= VOLUME_SPIKE_MULT
        and abs(feature.delta) >= ABSORPTION_DELTA
        and feature.body_ratio <= ABSORPTION_BODY_RATIO
    )


def detect_volume_climax(
    klines: Sequence[MarketData], features: Sequence[BarFeatures]
) -> list[Event]:
    """Volume far above baseline with aggression lopsided to one side.

    Direction is signed toward the aggression (the "follow the whale" reading).
    If the measured returns come back negative, the fade reading is the right
    one — that is the question this footprint exists to answer.

    Bars that qualify as ABSORPTION are excluded — see `_is_absorption()`.
    """
    events: list[Event] = []
    for feature in features:
        if feature.volume_ratio < VOLUME_SPIKE_MULT:
            continue
        if abs(feature.delta) < DELTA_IMBALANCE:
            continue
        if _is_absorption(feature):
            continue
        bar = klines[feature.index]
        events.append(
            Event(
                footprint=Footprint.VOLUME_CLIMAX,
                index=feature.index,
                at=bar.close_time,
                price=bar.close_price,
                direction=1 if feature.delta > 0 else -1,
                detail=(
                    f"volume x{feature.volume_ratio:.1f} baseline, "
                    f"delta {feature.delta:+.2f}"
                ),
            )
        )
    return events


def detect_absorption(
    klines: Sequence[MarketData], features: Sequence[BarFeatures]
) -> list[Event]:
    """Heavy one-sided aggression that price refuses to follow.

    Signed AGAINST the aggression: if sellers hit the bid relentlessly and
    price will not go down, whoever is taking the other side is the one who
    matters, and price tends to go their way.
    """
    events: list[Event] = []
    for feature in features:
        if not _is_absorption(feature):
            continue
        bar = klines[feature.index]
        events.append(
            Event(
                footprint=Footprint.ABSORPTION,
                index=feature.index,
                at=bar.close_time,
                price=bar.close_price,
                direction=-1 if feature.delta > 0 else 1,
                detail=(
                    f"delta {feature.delta:+.2f} absorbed, "
                    f"body {feature.body_ratio:.2f} of range"
                ),
            )
        )
    return events


def detect_large_trade_spike(
    klines: Sequence[MarketData], features: Sequence[BarFeatures]
) -> list[Event]:
    """Average trade size jumps: few large participants, not the retail crowd."""
    events: list[Event] = []
    for feature in features:
        if feature.trade_size_ratio < TRADE_SIZE_SPIKE_MULT:
            continue
        if abs(feature.delta) < DELTA_IMBALANCE:
            continue
        bar = klines[feature.index]
        events.append(
            Event(
                footprint=Footprint.LARGE_TRADE_SPIKE,
                index=feature.index,
                at=bar.close_time,
                price=bar.close_price,
                direction=1 if feature.delta > 0 else -1,
                detail=(
                    f"avg trade size x{feature.trade_size_ratio:.1f}, "
                    f"delta {feature.delta:+.2f}"
                ),
            )
        )
    return events


DETECTORS = {
    Footprint.LIQUIDITY_SWEEP: detect_liquidity_sweep,
    Footprint.VOLUME_CLIMAX: detect_volume_climax,
    Footprint.ABSORPTION: detect_absorption,
    Footprint.LARGE_TRADE_SPIKE: detect_large_trade_spike,
}


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #


def _forward_return_bps(
    klines: Sequence[MarketData], index: int, horizon: int, direction: int
) -> float | None:
    """Signed move from bar `index` to bar `index + horizon`, in basis points.

    Returns None when the horizon runs past the end of the data, so trailing
    events are dropped rather than silently measured against a shorter horizon
    than every other event in the sample.
    """
    target = index + horizon
    if target >= len(klines):
        return None
    entry = klines[index].close_price
    if entry <= _EPSILON:
        return None
    raw = (klines[target].close_price - entry) / entry
    return raw * direction * _BPS_PER_UNIT


def _baseline_at_horizon(
    klines: Sequence[MarketData], horizon: int
) -> tuple[float, float]:
    """What a random bar returned over the same horizon: (mean bps, hit rate).

    Measured LONG-ONLY and unsigned on purpose. This is the null hypothesis the
    events have to beat: if the window simply drifted up, every long-biased
    footprint inherits that drift and looks skilful without being skilful.
    """
    returns: list[float] = []
    for index in range(len(klines) - horizon):
        value = _forward_return_bps(klines, index, horizon, direction=1)
        if value is not None:
            returns.append(value)
    if not returns:
        return 0.0, 0.0
    hits = sum(1 for value in returns if value > 0.0)
    return statistics.fmean(returns), hits / len(returns)


def measure(
    klines: Sequence[MarketData], events: Sequence[Event], horizon: int
) -> HorizonStats:
    """Forward-return statistics for one footprint at one horizon."""
    returns: list[float] = []
    for event in events:
        value = _forward_return_bps(klines, event.index, horizon, event.direction)
        if value is not None:
            returns.append(value)

    baseline_mean, baseline_hit = _baseline_at_horizon(klines, horizon)

    if not returns:
        return HorizonStats(
            horizon_sec=horizon,
            sample_count=0,
            mean_bps=0.0,
            median_bps=0.0,
            hit_rate=0.0,
            baseline_hit_rate=baseline_hit,
            baseline_mean_bps=baseline_mean,
        )

    hits = sum(1 for value in returns if value > 0.0)
    return HorizonStats(
        horizon_sec=horizon,
        sample_count=len(returns),
        # Median alongside mean because a single 200 bp outlier drags the mean
        # into looking like a strategy. When the two disagree badly, the mean
        # is describing one lucky bar, not a repeatable edge.
        mean_bps=statistics.fmean(returns),
        median_bps=statistics.median(returns),
        hit_rate=hits / len(returns),
        baseline_hit_rate=baseline_hit,
        baseline_mean_bps=baseline_mean,
    )


def run_probe(symbol: str, klines: Sequence[MarketData]) -> ProbeReport:
    """Detect every footprint and measure all of them at every horizon."""
    features = compute_features(klines)
    report = ProbeReport(
        symbol=symbol,
        bar_count=len(klines),
        window_start=klines[0].open_time if klines else None,
        window_end=klines[-1].close_time if klines else None,
    )
    for footprint, detector in DETECTORS.items():
        events = detector(klines, features)
        report.events_by_footprint[footprint] = events
        report.stats[footprint] = [
            measure(klines, events, horizon) for horizon in FORWARD_HORIZONS_SEC
        ]
    return report


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def print_report(report: ProbeReport) -> None:
    print("=" * 78)
    print(f"MANIPULATION FOOTPRINT PROBE - {report.symbol}")
    print("=" * 78)
    print(f"Bars analysed : {report.bar_count}")
    print(f"Window        : {report.window_start} -> {report.window_end}")
    print(
        f"Settings      : baseline={BASELINE_BARS} sweep_lookback={SWEEP_LOOKBACK_BARS} "
        f"vol_mult={VOLUME_SPIKE_MULT} delta={DELTA_IMBALANCE}"
    )
    print(f"Round-trip cost assumption: {ROUND_TRIP_COST_BPS:.1f} bps")
    print()

    for footprint in Footprint:
        events = report.events_by_footprint.get(footprint, [])
        print("-" * 78)
        print(f"{footprint.value.upper()}  -  {len(events)} events")
        if len(events) < MIN_EVENTS_FOR_SIGNIFICANCE:
            print(
                f"  !! only {len(events)} events "
                f"(< {MIN_EVENTS_FOR_SIGNIFICANCE}); treat every number below as noise"
            )
        if not events:
            print()
            continue

        header = (
            f"  {'horizon':>8} {'n':>6} {'mean':>9} {'median':>9} "
            f"{'hit':>7} {'base hit':>9} {'edge':>9} {'after cost':>11}"
        )
        print(header)
        for stats in report.stats.get(footprint, []):
            verdict = "OK" if stats.edge_after_cost_bps > 0.0 else "no"
            print(
                f"  {stats.horizon_sec:>7}s {stats.sample_count:>6} "
                f"{stats.mean_bps:>8.2f}b {stats.median_bps:>8.2f}b "
                f"{stats.hit_rate:>6.1%} {stats.baseline_hit_rate:>8.1%} "
                f"{stats.edge_bps:>8.2f}b {stats.edge_after_cost_bps:>9.2f}b {verdict}"
            )
        print(f"  sample: {events[0].detail}")
        print()

    print("=" * 78)
    print("HOW TO READ THIS")
    print("  mean/median  : forward move signed toward the 'follow' reading.")
    print("                 Consistently NEGATIVE means FADE is the right side.")
    print("  edge         : mean minus what a random bar did over the same")
    print("                 horizon. This is the only column that means")
    print("                 anything on its own.")
    print("  after cost   : edge minus round-trip fees. Anything <= 0 is not")
    print("                 tradeable no matter how good the hit rate looks.")
    print("=" * 78)


def report_to_dict(report: ProbeReport) -> dict[str, object]:
    """Flattened form for saving, so a later run can be diffed against this one."""
    return {
        "symbol": report.symbol,
        "bar_count": report.bar_count,
        "window_start": report.window_start.isoformat()
        if report.window_start
        else None,
        "window_end": report.window_end.isoformat() if report.window_end else None,
        "settings": {
            "baseline_bars": BASELINE_BARS,
            "sweep_lookback_bars": SWEEP_LOOKBACK_BARS,
            "volume_spike_mult": VOLUME_SPIKE_MULT,
            "trade_size_spike_mult": TRADE_SIZE_SPIKE_MULT,
            "delta_imbalance": DELTA_IMBALANCE,
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        },
        "footprints": {
            footprint.value: {
                "event_count": len(report.events_by_footprint.get(footprint, [])),
                "horizons": [
                    {
                        "horizon_sec": stats.horizon_sec,
                        "sample_count": stats.sample_count,
                        "mean_bps": stats.mean_bps,
                        "median_bps": stats.median_bps,
                        "hit_rate": stats.hit_rate,
                        "baseline_hit_rate": stats.baseline_hit_rate,
                        "edge_bps": stats.edge_bps,
                        "edge_after_cost_bps": stats.edge_after_cost_bps,
                    }
                    for stats in report.stats.get(footprint, [])
                ],
            }
            for footprint in Footprint
        },
    }


# --------------------------------------------------------------------------- #
# Data loading. Imported lazily so --self-test runs with no venv and no deps.
# --------------------------------------------------------------------------- #


def load_from_db(symbol: str, days: int) -> list[MarketData]:
    from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
    from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
        DatabaseConfig,
        DatabaseManager,
    )
    from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
        SQLAlchemyMarketDataRepository,
    )

    bot_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo = SQLAlchemyMarketDataRepository(
        DatabaseManager(DatabaseConfig(db_dir=os.path.join(bot_root, "database")))
    )
    end = datetime.now(UTC)
    return repo.get_klines(
        symbol=symbol,
        interval=TimeFrame.ONE_SECOND,
        start_time=end - timedelta(days=days),
        end_time=end,
    )


def load_from_binance(symbol: str, days: int) -> list[MarketData]:
    end = datetime.now(UTC).replace(microsecond=0)
    client = ExchangeSessionFactory(
        MarketDataVenue.MAINNET_PUBLIC
    ).create_market_data_client()
    return client.get_historical_klines(
        symbol, TimeFrame.ONE_SECOND, end - timedelta(days=days), end
    )


# --------------------------------------------------------------------------- #
# Self-test: synthetic bars with footprints planted at known indices.
# --------------------------------------------------------------------------- #


def _bar(
    index: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    taker_buy: float,
    trades: int,
) -> MarketData:
    base = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
    return MarketData(
        symbol="SYNTH",
        interval="1s",
        open_time=base,
        open_price=open_price,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=volume,
        close_time=base + timedelta(milliseconds=999),
        quote_asset_volume=volume * close,
        number_of_trades=trades,
        taker_buy_base_asset_volume=taker_buy,
        taker_buy_quote_asset_volume=taker_buy * close,
    )


def _build_synthetic() -> tuple[list[MarketData], dict[str, int]]:
    """Flat noise with one of each footprint planted at a known index."""
    bars: list[MarketData] = []
    price = 100.0
    total = BASELINE_BARS + SWEEP_LOOKBACK_BARS + 200
    sweep_at = BASELINE_BARS + SWEEP_LOOKBACK_BARS + 10
    climax_at = sweep_at + 40
    absorption_at = climax_at + 40
    trade_spike_at = absorption_at + 40

    for index in range(total):
        # Baseline bar: tiny range, balanced flow, ordinary size.
        open_price = price
        close = price
        high = price + 0.02
        low = price - 0.02
        volume, taker_buy, trades = 100.0, 50.0, 100

        if index == sweep_at:
            # Deep spike below the prior range, closing back above it: the
            # lower wick has to dominate the bar for this to read as rejection.
            low = price - 2.0
            high = price + 0.02
            close = price + 0.01
            open_price = price
        elif index == climax_at:
            volume, taker_buy, trades = 900.0, 810.0, 900
            close = price + 0.5
            high = price + 0.55
        elif index == absorption_at:
            # Massive selling, price does not move: body stays tiny.
            volume, taker_buy, trades = 900.0, 90.0, 900
            close = price + 0.001
            high = price + 0.5
            low = price - 0.5
        elif index == trade_spike_at:
            # Same volume as normal, but a handful of huge prints.
            volume, taker_buy, trades = 100.0, 90.0, 5
            close = price + 0.1
            high = price + 0.12

        bars.append(
            _bar(index, open_price, high, low, close, volume, taker_buy, trades)
        )
        price = close

    return bars, {
        "sweep": sweep_at,
        "climax": climax_at,
        "absorption": absorption_at,
        "trade_spike": trade_spike_at,
    }


def run_self_test() -> int:
    """Verifies each detector fires on its planted bar and not on flat noise.

    Returns a process exit code so this doubles as a smoke check.
    """
    bars, planted = _build_synthetic()
    features = compute_features(bars)
    failures: list[str] = []

    checks = [
        ("sweep", Footprint.LIQUIDITY_SWEEP, detect_liquidity_sweep, 1),
        ("climax", Footprint.VOLUME_CLIMAX, detect_volume_climax, 1),
        # The planted absorption bar is heavy SELLING that price refused to
        # follow, so whoever took the other side is the buyer: +1, not -1.
        ("absorption", Footprint.ABSORPTION, detect_absorption, 1),
        ("trade_spike", Footprint.LARGE_TRADE_SPIKE, detect_large_trade_spike, 1),
    ]

    for label, footprint, detector, want_direction in checks:
        events = detector(bars, features)
        indices = [event.index for event in events]
        expected = planted[label]

        if expected not in indices:
            failures.append(f"{footprint.value}: planted bar {expected} NOT detected")
            continue
        if len(events) != 1:
            failures.append(
                f"{footprint.value}: expected exactly 1 event, got {len(events)} "
                f"at {indices} - firing on flat noise"
            )
            continue
        got_direction = events[0].direction
        if got_direction != want_direction:
            failures.append(
                f"{footprint.value}: direction {got_direction:+d}, "
                f"expected {want_direction:+d}"
            )
            continue
        print(
            f"  OK  {footprint.value:<20} fired at {expected}, "
            f"direction {got_direction:+d}"
        )

    # A signed forward return has to reverse when the direction flips, or every
    # fade/follow number in the report is meaningless.
    up = _forward_return_bps(bars, planted["climax"], horizon=5, direction=1)
    down = _forward_return_bps(bars, planted["climax"], horizon=5, direction=-1)
    if up is None or down is None or not math.isclose(up, -down, abs_tol=1e-9):
        failures.append(f"signed forward return not symmetric: {up} vs {down}")
    else:
        print("  OK  signed forward return flips with direction")

    print()
    if failures:
        for failure in failures:
            print(f"  FAIL {failure}")
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("All self-test checks passed.")
    return 0


# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--source", choices=("db", "binance"), default="db")
    parser.add_argument("--days", type=int, default=_DEFAULT_DAYS)
    parser.add_argument("--save-json", default=None)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run detector checks on synthetic bars; no venv/DB/network needed.",
    )
    args = parser.parse_args()

    if args.self_test:
        print("Self-test: detectors against synthetic bars\n")
        return run_self_test()

    loader = load_from_db if args.source == "db" else load_from_binance
    klines = loader(args.symbol, args.days)

    if not klines:
        print(
            f"No 1s klines for {args.symbol}. Sync them first, "
            f"or re-run with --source binance.",
            file=sys.stderr,
        )
        return 1
    if len(klines) <= BASELINE_BARS + SWEEP_LOOKBACK_BARS:
        print(
            f"Only {len(klines)} bars; need more than "
            f"{BASELINE_BARS + SWEEP_LOOKBACK_BARS} just to warm the baselines up.",
            file=sys.stderr,
        )
        return 1

    report = run_probe(args.symbol, klines)
    print_report(report)

    if args.save_json:
        with open(args.save_json, "w", encoding="utf-8") as handle:
            json.dump(report_to_dict(report), handle, indent=2)
        print(f"\nSaved: {args.save_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
