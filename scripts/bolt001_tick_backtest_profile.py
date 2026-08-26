"""Profile a real Historical Tick Backtest run, end to end.

    PYTHONPATH=.. python scripts/bolt001_tick_backtest_profile.py [tick_count]

@par Why this exists as a committed script and not a scratch file
`BOLT-001` optimised `_bar_bounds()` out of the per-tick path on the strength
of a micro-benchmark of that function alone. A micro-benchmark answers "is the
new code faster than the old code" — it cannot answer "did that function
matter", and the two are different questions. The one that decides whether an
optimisation was worth doing is the second.

Run against the pre-`BOLT-001` handler this reports `_bar_bounds` at ~17% of
the whole run; run against the current handler, ~0.3%. Those two numbers are
what justify the change, and neither came from the micro-benchmark.

Keep it runnable: an optimisation whose measurement cannot be reproduced from
the repo is an optimisation nobody can re-check.
"""

import cProfile
import io
import pstats
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

N = int(sys.argv[1]) if len(sys.argv) > 1 else 120_000
BASE = datetime(2026, 1, 1, tzinfo=UTC)


class _Hold(BaseStrategy):
    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


ticks = []
for i in range(N):
    ot = BASE + timedelta(seconds=i)
    px = 100.0 + (i % 50)
    ticks.append(
        MarketData(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_SECOND.value,
            open_time=ot,
            open_price=px,
            high_price=px,
            low_price=px,
            close_price=px,
            volume=1.0,
            close_time=ot + timedelta(milliseconds=999),
            quote_asset_volume=px,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.5,
            taker_buy_quote_asset_volume=px * 0.5,
        )
    )

repo = Mock()
repo.count_klines.side_effect = lambda **k: (
    len(ticks) if k.get("limit") is None else min(k["limit"], len(ticks))
)
repo.stream_klines.side_effect = lambda **k: iter(ticks[: k.get("limit")])
reg = StrategyRegistry()
reg.register("hold", _Hold)
handler = RunHistoricalTickBacktestCommandHandler(
    repository=repo, strategy_registry=reg, event_publisher=Mock()
)
cmd = RunHistoricalTickBacktestCommand(
    symbol="BTCUSDT",
    interval=TimeFrame.FIVE_MINUTES,
    tick_resolution=TimeFrame.ONE_SECOND,
    strategy_key="hold",
)

pr = cProfile.Profile()
pr.enable()
handler.execute(cmd)
pr.disable()

st = pstats.Stats(pr, stream=io.StringIO())
# `Stats.total_tt` and `Stats.stats` exist at runtime — cProfile's own
# documented output — but typeshed declares neither, so mypy (which this
# repo runs over `scripts/` too) rejects both. There is no public
# alternative that returns the numbers this report needs.
total = st.total_tt  # type: ignore[attr-defined]
print(f"{N:,} tick, bar 5 phút — tổng {total:.2f}s\n")
print(f"{'cumtime':>8} {'%tổng':>7}  {'ncalls':>10}  hàm")
rows = []
for (fn, ln, name), (_cc, nc, _tt, ct, _) in st.stats.items():  # type: ignore[attr-defined]
    rows.append((ct, nc, f"{fn.split('/')[-1]}:{ln}({name})"))
for ct, nc, label in sorted(rows, reverse=True)[:14]:
    print(f"{ct:8.3f} {ct / total * 100:6.1f}%  {nc:10,}  {label}")
print()
bb = [r for r in rows if "_bar_bounds" in r[2]]
if bb:
    ct, nc, label = bb[0]
    print(
        f">>> _bar_bounds: {nc:,} lần gọi, cumtime {ct:.3f}s = {ct / total * 100:.2f}% tổng"
    )
else:
    print(">>> _bar_bounds KHÔNG xuất hiện trong profile")
