"""Column widths and headers for the backtest trade log.

Read by both the row widget and the panel that heads the table, so a
module rather than a copy in each: a header and its column must not
be able to drift apart."""

from __future__ import annotations

_COLUMNS = (17, 8, 28, 18, 16, 13)
