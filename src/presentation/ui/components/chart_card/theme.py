"""Shared color constants for the chart_card package — single source of truth so
candlestick, volume, price-line and crosshair rendering stay visually consistent."""

BULL_COLOR = "#26a69a"  # token-exempt: chart_card avoids Palette, see theme.py
BEAR_COLOR = "#ef5350"  # token-exempt: chart_card avoids Palette, see theme.py
CROSSHAIR_COLOR = "#aaaaaa"  # token-exempt: chart_card avoids Palette, see theme.py
#: BOT-111 — take-profit exit markers get their own color, distinct from the
#: plain bull/bear entry/exit scheme, so a broker-level TP fill reads
#: differently from a strategy-decided exit at a glance. Matches
#: Palette.ACCENT (Binance gold) — this package doesn't import the app's
#: global Palette (kept portable/standalone), so the value is duplicated
#: here rather than imported.
TAKE_PROFIT_COLOR = "#F3BA2F"  # token-exempt: chart_card avoids Palette, see theme.py
