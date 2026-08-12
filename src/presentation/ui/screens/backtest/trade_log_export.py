from __future__ import annotations

import csv

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

_CSV_HEADER = [
    "index",
    "symbol",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "quantity",
    "pnl",
    "pnl_percent",
    "fees_paid",
]


def export_trades_to_csv(trades: list[Trade], path: str) -> None:
    """
    @brief Writes `trades` (1-based-indexed in the order given — callers
    pass whatever is currently filtered/visible, so the export matches what
    the user is looking at) to a CSV file at `path`.
    @details Every raw `Trade` field is written, not just the table's
    display columns — a CSV export is for taking data OUT of the app (e.g.
    into a spreadsheet for further analysis), so it should be more complete
    than the on-screen table, not a screenshot of it.
    """
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(_CSV_HEADER)
        for position, trade in enumerate(trades, start=1):
            writer.writerow(
                [
                    position,
                    trade.symbol,
                    trade.entry_time.isoformat(),
                    trade.entry_price,
                    trade.exit_time.isoformat(),
                    trade.exit_price,
                    trade.quantity,
                    trade.pnl,
                    trade.pnl_percent,
                    trade.fees_paid,
                ]
            )
