"""`PositionsTable` — open live positions, on the shared `DataTable`
skeleton (`BOT-124`).

Built for `EPIC-021I`'s Trading screen: `TradingPresenter` pushes
`PositionRow`s here (via `PositionsVM.set_rows`) whenever `OrderFeed`
reports a `PositionChangedEvent`, or after a successful
`EnableTradingCommand`. No Python ViewModel logic beyond that push — same
convention `qml/DataTable/__init__.py` documents (`qml-rule.md` §1.3): a
component with nothing to derive, only properties/rows a caller sets,
does not grow filtering or formatting of its own.
"""
