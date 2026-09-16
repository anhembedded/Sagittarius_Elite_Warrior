# CS-002 — The subscriber nobody built

`BUG-126` · written in `EPIC-008G`, broken the whole time · a UI slot that raised and a background
task that died reached nobody.
[report](../../Tasks/bug_report/completed/BUG-126_system_failures_reached_no_subscriber_at_runtime.md)

```python
class SystemErrorFeed(BaseFeed):   # subscribes in __init__, and no file in
    ...                            # src/ or scripts/ ever names the class
```

## Why nothing caught it

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the feed's own unit test | it constructed the feed — the one step production omitted. A test supplying the missing wiring cannot fail for missing wiring | yes — every `Feed`/coordinator test constructs its subject |
| `test_event_flow_guards.py` | checks a subscription addresses its event by **class**, not by string. True of a subscription that never runs | closed for subscribers |
| ruff (`ERA`, `F401`) / mypy | ruff sees an unused *import*, never an exported class no caller reaches; mypy checks an unreachable class as happily as a reachable one | yes — for anything but a subscriber |
| HLD §3.5's "re-measured" dead-code list | called it live: *"imported by `order_feed.py`"*. `order_feed.py` only **mentions** it in a docstring — a text search cannot tell a mention from an import | yes — every count in that table came from grep |

## The fix

- `src/shell/system_failure_log.py` — one subscriber, constructed by the composition root, before `boot()`. No Qt, so the CLI entry point gets it too; reports at `ERROR` with `[system-failure]`, the sink `--dev` writes and `ci-local.ps1`'s log scan greps.
- `SystemErrorFeed` deleted. Nothing displayed its signal, and `base_feed.py`'s own rule is to promote a fact when the **second** consumer appears — promoting before the first is what this cost.
- `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` — a class that calls `.on(...)` must be named elsewhere in `src/`+`scripts/`, read from the **AST** so a docstring cannot satisfy it. Measured: 8 reachable, 1 orphan, 0 false positives.

## Where else this is still open

- **A test that constructs its subject proves the subject, never the wiring.** `BUG-124` and this are the same sentence; only the missing half differs (a verb, a constructor).
- Every number in HLD §3.5 and `03_module_contracts.md` came from text search, so any "N importers" there may be counting prose. The new guard covers subscribers only.
- `EPIC-008`'s other two feeds were wired by screens; a screen deleted in Phase 4 silently unwires its feed, and only this guard would notice — and only if the class name leaves the tree with it.

## Take
"Written, tested, task closed" is three claims about a class and none about the program. Ask what
constructs it.
