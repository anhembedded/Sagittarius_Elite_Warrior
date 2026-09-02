"""`OpenOrdersTable` — pending live orders, on the shared `DataTable`
skeleton (`BOT-124`).

Built for `EPIC-021I`'s Trading screen: `TradingPresenter` pushes
`OpenOrderRow`s here (via `OpenOrdersVM.set_rows`) after a successful
`EnableTradingCommand` (seeded from its `reconciled_open_orders`) and
whenever `OrderFeed` reports an `OrderFilledEvent`. No Python ViewModel
logic beyond that push — same convention `qml/DataTable/__init__.py`
documents (`qml-rule.md` §1.3).
"""
