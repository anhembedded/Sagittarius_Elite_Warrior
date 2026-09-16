# CS-003 — The port nobody bound

`BUG-127`. `BOT-095E1`'s market-rule check answered *"not verified against exchange rules"* for
every symbol since it shipped: nothing calls the parser that makes the metadata, and nothing binds
the port that stores it, so `resolve()` raises on every construction and lands in an `except` that
builds an empty cache — what reads as a fallback is the only path.

## Why nothing caught it

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| The parser's unit test | Builds its own payload, asserts the parse. A producer's test cannot notice it has no callers. | **yes** |
| The cache adapter's unit test | Builds its own cache, asserts `put`/`get`. Same shape. | **yes** |
| The consumer's tests | Inject `get_market_metadata` directly, proving both branches; none asks who fills the cache in production. | **yes** |
| `mypy` | `IContainer.resolve()` returns `Any`, and `src/presentation/` is excluded wholesale (`EPIC-002A` §2) — both of `CS-001`'s conditions. | **yes** |
| `ruff` + `test_a_bus_subscriber_is_constructed.py` | `ruff` sees an unused *import*, never an uncalled function. `CS-002`'s guard was written for this disease and scoped to **bus subscribers**; an unbound port is the same disease in another organ. | **closed** below |

A unit test supplies the wiring production forgot, so each part proves itself and the feature proves
nothing — `CS-002`'s lesson, whose guard was narrow enough to miss the next instance.

## The fix

- `tests/unit/architecture/test_every_resolved_type_is_bound.py` — every type the app `resolve()`s
  must be bound in `src/` or `scripts/`. Measured: 43 resolved, 3 unbound — `IThreadManager` and
  `Scheduler` (**Engine**-registered, exempted as a category) and this bug.
- Probed both ways; it names `backtest_presenter.py:406` once the exemption is removed. Unbound is
  fine — unbound **and resolved** is the defect, so `ISizingPolicy` never reaches the guard.
- The wiring is `BUG-127`'s own fix, which deletes the guard's one-entry ratchet.

## Where else this is still open

- **An uncalled producer has no check at all** — `parse_binance_symbol_metadata()` had zero callers,
  and that is true of any parser, policy or factory.
- **`resolve()` returning `Any` is the seam all three guards circle**, and `except Exception`
  around one turns a wiring defect into silence — that pair is a one-line grep nobody wrote.
