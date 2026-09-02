"""`EPIC-021J` — the local Binance-protocol fake server, split by
abstraction: `spot_routes.py`/`futures_routes.py` (static + stateful
route tables), `order_book_state.py` (the one piece of mutable state),
`server.py` (the HTTP plumbing + the public `run_binance_fake_server()`
contextmanager). Import `run_binance_fake_server`/`FakeServerUrls` from
`tests/sanity/binance_fake_server.py` — that module is the stable public
entry point every caller already uses; this package is its
implementation, not a second public surface.
"""
