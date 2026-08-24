---
name: Logging Rules
description: Where to place logs so a bug report identifies its own root cause, and how to keep them readable.
trigger: always_on
---

# LOGGING RULES

The measure of this project's logging is not how much it writes. It is
whether a single reproduce-and-send-log cycle is enough to locate a root
cause. If a reader has to guess, or ask the reporter to run it again with
more logging, the logging failed — regardless of how many lines it produced.

`BUG-009` is the worked example these rules come from: three
reproduce-and-send-log rounds were spent on a chart defect because the logs
said nothing about which chart backend was live, whether the interaction
overlay was engaged, or what was actually painted. The full case study is
[`Tasks/reports/BUG-009_logging_and_test_gap_case_study.md`](../../Tasks/reports/BUG-009_logging_and_test_gap_case_study.md).

---

## 1. Every logger MUST live under the `"App."` namespace

`StdLogger` attaches its console/file/viewer handlers to the `"App"` logger
and sets `propagate = False`. Nothing is attached to the root logger.

```python
logger = logging.getLogger("App.ChartCard")      # correct
logger = logging.getLogger(__name__)             # SILENT below WARNING
```

A `__name__`-based logger has no handler anywhere in its chain: `info()` and
`debug()` emit **nothing at all**, and only Python's last-resort fallback
shows WARNING and above, unformatted. This is silent by construction — the
code looks right and the call succeeds. Enforced by
`tests/unit/test_logging_namespace_guard.py`; the only exemption is calling
`getLogger(name)` purely to `addHandler`/`removeHandler` on a logger owned by
someone else.

## 2. Log the decision, not just the outcome

Log every branch where the app *chose* between implementations, fell back, or
silently degraded — with the reason. A reader must be able to tell which code
path ran without reading the code.

- Which backend/adapter/host was selected, what was requested, and why they
  differ (`backend 'python' (requested: 'auto')`, plus the fallback reason).
- Which optional mechanism is engaged for this session (cache, overlay,
  OpenGL, LOD) — and log the **disabled** case too. "No line" is not evidence
  of "off"; it is indistinguishable from broken logging.
- What is actually in effect versus what was configured: real render backend,
  real DPR, real platform. Configured intent is not evidence of runtime state.

## 3. One-shot environment lines are mandatory for UI and rendering code

A defect that reproduces on the reporter's machine and not the developer's is
the normal case, not the exception. Any component whose behaviour depends on
the host MUST log, once, at construction: the real backend in use, any
fallback reason, device pixel ratio, Qt platform, and the relevant widget or
screen geometry. `ChartCard._log_environment` (`[chart-env]`) is the
reference implementation.

## 4. Summarise per gesture or per operation — never per event

A drag emits hundreds of mouse-move events. Per-event logging at INFO makes
the report unreadable and is self-defeating. Log:

- one line when an interaction begins, carrying the geometry and thresholds
  it will operate under;
- one line per *significant transition* inside it (a re-render, a fallback, a
  cancellation);
- one summary line when it ends, carrying counts, worst-case measurements and
  the final state.

Put numbers a reader can act on in the summary — sizes in pixels as well as
percentages, elapsed milliseconds, and how far a value sat from its
threshold. `%`-only reporting hid a 333px blank band behind "15%".

## 5. Log the state that would let a layer be ruled OUT

Instrument several layers at once, not only the suspected one. For each
layer, log what a reader needs to exonerate it: what it was asked to do, what
it actually applied, and what is still pending. Deferred or coalesced work
MUST report whether it had been applied yet — a frame captured while a
coalesced range update is pending shows candles at the new range and
indicators at the old one, and nothing else in the log would reveal that.

## 6. Six levels, in order — pick the narrowest one that fits

`TRACE(5) < DEBUG(10) < INFO(20) < WARNING(30) < ERROR(40) < CRITICAL(50)`.
`TRACE` is not a standard Python `logging` level; `sagittarius_engine`'s
`StdLogger`/`LoggerConfig` register it (`ILogger.trace()`/`.critical()` exist
alongside the four you'd expect). Threshold is a single `log.level` config
key — a call below it is silently dropped, regardless of which method was
called.

- **`TRACE`** — detail too high-frequency even for a normal `--dev` session:
  per-frame, per-pixel, per-tick. Reserve it for exactly the hot paths rule 4
  already says never to log per-event at `INFO`. If you'd hesitate to leave
  a log line on for an entire `--dev` diagnostic session because of the
  volume, it's `TRACE`, not `DEBUG`.
- **`DEBUG`** — the per-event detail rule 4 describes: normal dev-session
  diagnostics, safe to run for a whole reproduction without drowning it.
- **`INFO`** — decisions, environment, per-operation summaries (rules 2-3).
- **`WARNING`** — a degraded-but-recovered path (fallback engaged, retry
  succeeded).
- **`ERROR`** — an operation failed but the process is still sound.
- **`CRITICAL`** — the process itself is compromised (unrecoverable startup
  failure, a corrupted state nothing downstream can trust). Rare by design;
  don't use it for an ordinary caught exception `ERROR` already covers.

## 7. Developer runs get more logging, automatically — `--dev` vs `--debug`

Both flags write the whole session to a timestamped file under `logs/` and
set `DEV_MODE`; they differ only in threshold and file prefix:

| Flag | `log.level` | File |
| --- | --- | --- |
| `--dev` | `DEBUG` | `logs/dev-<timestamp>.log` |
| `--debug` | `TRACE` | `logs/debug-<timestamp>.log` |

`--debug` **implies** `--dev` — it is strictly more verbose, not a separate
mode; there is no flag that gets `DEV_MODE` without at least `DEBUG`. Never
require a config edit to obtain diagnostics, and never rely on the reporter
copying console scrollback by hand — detail is lost exactly where it
matters. Ask for the log **file**. The resolution itself
(`sagittarius_engine.infrastructure.logging.dev_verbosity.resolve_dev_verbosity`)
is generic engine behavior any app on this engine gets for free; an app's own
bootstrapper only decides what else `--dev`/`--debug` additionally turns on
(this app: `ConfigKeys.DEV_MODE`, enabling button-click auto-logging).

## 8. Prefix log lines with a stable, greppable tag — and keep the format filterable

Use a bracketed subsystem tag as the first token — `[chart-env]`,
`[chart-data]`, `[cached-frame]` — or the existing `KEY=value` trace style
(`BACKTEST_TRACE action=...`). A reporter pastes a whole session; the reader
needs one `Select-String` to isolate a subsystem.

`StdLogger`'s formatter is fixed-field —
`%(asctime)s - %(name)s - %(levelname)s - %(message)s` — specifically so a
saved log file can be filtered two ways without touching the app:

- **By level:** `Select-String "- (WARNING|ERROR|CRITICAL) -" session.log`
  (PowerShell) or `grep -E '\- (WARNING|ERROR|CRITICAL) \-' session.log`
  (POSIX) — the `levelname` field is fixed-width-delimited by ` - ` on both
  sides, so this never accidentally matches a level name appearing inside a
  message.
- **By subsystem tag:** `Select-String "\[chart-data\]" session.log` /
  `grep '\[chart-data\]'` — combine with the level filter
  (`grep -E '\- (DEBUG|TRACE) \-' session.log | grep '\[cached-frame\]'`) to
  isolate one subsystem's high-verbosity output from a `--debug` session
  without reading the rest.

Do not change the formatter's field order or separator without checking
whether an existing filter/regex (in a task doc, a script, or a bug report's
own reproduction steps) depends on it.

## 9. A diagnostic that has never been seen to emit does not exist

After adding logging, run the path and confirm the lines actually appear
through the **real** logging configuration — not `logging.basicConfig` in a
scratch script, which attaches a root handler the real app never has. An
entire debugging round was lost to instrumentation that could not emit.
