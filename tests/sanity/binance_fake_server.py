"""
`EPIC-009` D6 / `EPIC-021J` — a local server speaking Binance's REST
protocol.

Exists so the real `python-binance` client can run completely unchanged and
still never touch the network. This is a deliberate rejection of the cheaper
option: a hand-written substitute for `IExchangeClient` would bypass
`PythonBinanceClient` entirely — its kline mapping, its generator-based
pagination, its cancellation checks, all of `python-binance`'s own HTTP
behavior — and that is exactly the shape that produced `BUG-026` and
`BUG-027`: hand-written port implementations that silently fell behind the
real interface. Here, only the base URL moves; every line of the real
adapter stack still runs.

This module is a stable shim: every real caller (`tests/sanity/conftest.py`,
`tests/integration/infrastructure/binance/test_*_against_fake_server.py`,
`scripts/epic021c_metadata_probe.py`) imports it as a flat top-level module
(`sys.path.insert(..., ".../tests/sanity")` then `from binance_fake_server
import run_binance_fake_server`), so its name and signature stay fixed even
as the implementation grows — `EPIC-021J` split what used to be one 206-line
file into `fake_exchange/{spot_routes,futures_routes,order_book_state,
server}.py` once futures order-lifecycle routes pushed it past
`architecture-rule.md` §5.4's guideline, but nothing importing this module
had to change.

See `fake_exchange/futures_routes.py`'s own docstring for the full route
table (every path, verified against `python-binance`'s `client.py`, not
assumed) and `fake_exchange/order_book_state.py`'s for why order lifecycle
is the only stateful part.
"""

from __future__ import annotations

from fake_exchange.server import FakeServerUrls, run_binance_fake_server

__all__ = ["FakeServerUrls", "run_binance_fake_server"]
