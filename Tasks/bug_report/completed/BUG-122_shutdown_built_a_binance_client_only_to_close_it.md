# BUG-122 — shutdown built a Binance client only to close it, leaking an event loop

- **Reported:** 2026-09-15
- **Severity:** 🟠 P2 — every exit of a session that never opened a chart made a
  network call it did not need, and left an asyncio event loop unclosed. No user-visible
  failure, which is why it survived: the cost was a stray traceback on stderr and one
  request to Binance per exit.
- **Status:** ✅ Fixed 2026-09-15 — root-caused (loop-creation traced to its call site),
  reproduced out of process, regression-tested at the unit tier, verified by the sanity
  tier's own process test going green.

## 1. Symptom

`tests/sanity/test_self_check_process.py::test_the_real_process_stderr_is_clean` failed:
`--self-check` wrote 25 unexpected stderr lines.

```
Exception ignored in: <function BaseEventLoop.__del__ at 0x7f013ff5e5c0>
Traceback (most recent call last):
  File "/usr/lib/python3.12/asyncio/base_events.py", line 728, in __del__
    self.close()
  File "/usr/lib/python3.12/asyncio/selector_events.py", line 111, in _close_self_pipe
    self._remove_reader(self._ssock.fileno())
  ...
ValueError: Invalid file descriptor: -1
```

The app's own log was clean end to end — `App booted successfully`, `AsyncRuntime event
loop stopped.`, `App stopped.` — and the exit code was 0. Only stderr showed it, which
is exactly the channel that sanity test exists to read.

## 2. Root cause

`MarketDataModule.shutdown()` closed the exchange client by resolving it
**unconditionally**:

```python
context.container.resolve(DatabaseManager).dispose_all()
try:
    exchange_client = context.container.resolve(IExchangeClient)
    if hasattr(exchange_client, "close"):
        exchange_client.close()
```

`IExchangeClient` is bound lazily, so a session that never asked for market data has no
client — and that `resolve()` **builds one in order to close it**. Building it runs
`ExchangeSessionFactory.create_market_data_client()` → `binance.client.Client(...)` →
`binance/ws/websocket_api.py` → `reconnecting_websocket.py:63`, which creates an asyncio
event loop. Nothing closes that loop, so Python reports it from `__del__` at interpreter
exit.

Traced rather than guessed: the loop's creation site was captured by patching
`asyncio.new_event_loop` to print a stack before delegating, and running the real
process. Two loops were created — the Engine's `AsyncRuntime.start()` (closed properly on
stop) and this one:

```
module.py:131 in shutdown
  std_container.py:186 in resolve
    adapter_bindings.py:101 in _build_exchange_client
      exchange_session_factory.py:86 in create_market_data_client
        binance/client.py:40 in __init__
          binance/ws/reconnecting_websocket.py:63 in __init__   <-- new_event_loop()
```

**The wart was known and written down** — in that method's own docstring, carried over
from `binance_bot_module.py`, ending: *"Fixing it needs a way to ask the container
whether a singleton was ever instantiated, which it does not currently offer;
`EPIC-025A` §1.5 records it."* That statement had gone stale: the Engine's
`Registration.instantiated` answers precisely this, and its own docstring says the
distinction matters *"when the question is what has actually been built so far"*.

**Why it surfaced during `EPIC-025` PR 1.2 and not before.** The leak is identical on
`master-warrior`: the same two loops are created there, traced the same way. What PR 1.2
changed is garbage-collection timing — enough that the `__del__` warning went from
occasional to every run (measured: 3/3 clean on `d6409c06`, 3/3 noisy on the PR 1.2
branch, with identical application logs). So the bug predates the PR that exposed it,
and the fix belongs to neither: it is one method's own contract.

## 3. Fix

Ask the registry, then close only what exists:

```python
registration = context.container.registrations().get(IExchangeClient)
if registration is None or not registration.instantiated:
    return
```

A registry read constructs nothing, which is the whole reason `registrations()` reports
`instantiated` instead of handing back instances (its own docstring: *"a diagnostic that
resolves things in order to describe them would construct half the application as a side
effect of being asked a question"*).

Sufficient because it removes the construction, not the symptom: no client is built, so
no loop is created, so there is nothing to leak. A client that *was* used is still closed
on exactly the path it always was.

## 4. Regression test

`tests/unit/modules/market_data/test_module_shutdown.py` — three tests at the tier where
the decision lives, driving a recording `IContainer` stand-in:

- `test_shutdown_does_not_build_a_client_that_was_never_used` — **confirmed failing before
  the fix** (`AssertionError: shutdown resolved IExchangeClient although none was ever
  built`), passing after.
- `test_shutdown_still_closes_a_client_that_was_used` — the other half, so the fix cannot
  turn into "never close anything".
- `test_shutdown_always_disposes_the_database_engines` — the unconditional half stays
  unconditional; an undisposed SQLAlchemy engine is the `ResourceWarning` the gate greps
  for.

The sanity tier's `test_the_real_process_stderr_is_clean` is the end-to-end proof and is
green again: the real process' stderr is back to one line, the Qt offscreen plugin's own
notice.
