"""`BOT-167` — the timeframe a live chart opens on."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    timeframe_or_fallback,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

logger = logging.getLogger("App.LiveCandleChart")


def opening_interval(chart: ChartCard, ports: LiveChartPorts) -> str:
    """The timeframe to open on: `ports.interval`, or the nearest one the
    chart's market can load. The toolbar is told the market first, so its
    bar offers only what the market loads."""
    if ports.market is None:
        return ports.interval
    chart.toolbar.set_market(ports.market)
    interval = timeframe_or_fallback(ports.market, ports.interval)
    if interval != ports.interval:
        logger.info(
            "[live-chart] opening timeframe %s is not offered on %s; using %s",
            ports.interval,
            ports.market.value,
            interval,
        )
    return interval
