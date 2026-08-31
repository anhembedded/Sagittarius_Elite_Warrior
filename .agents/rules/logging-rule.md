---
name: Logging Rule
description: Where to place logs so a bug report identifies its own root cause, and how to keep them readable.
trigger: always_on
---

# LOGGING RULES

The measure of logging is **not** how much it writes. It is **whether a single
reproduce-and-send-the-log cycle is enough to locate a root cause.** If the
reader has to guess, or has to ask the reporter to run it again with more
logging, the logging failed — regardless of how many lines it produced.

> **Real evidence:** three reproduce-and-send-the-log rounds were burned on a
> rendering defect, because the logs **said nothing** about which backend was
> live, whether the interaction overlay was engaged, or what was actually
> painted.

---

## 1. Every logger MUST live under one root namespace

Handlers (console/file/viewer) are attached to a single root logger
`<LOG_NAMESPACE>`, and the system root logger has nothing attached.

```python
logger = logging.getLogger("<LOG_NAMESPACE>.ChartCard")   # correct
logger = logging.getLogger(__name__)                      # SILENT below WARNING
```

A logger outside that tree has **no handler anywhere in its chain**: `info()`
and `debug()` emit **nothing at all**, and only the library's last-resort
fallback shows WARNING and above, unformatted.

**This is silence by construction — the code looks right and the call
succeeds.** A **guard test** must lock this rule; the only exemption is calling
`getLogger(name)` purely to `addHandler`/`removeHandler` on someone else's
logger.

---

## 2. Log the **decision**, not just the outcome

Log **every branch** where the system **chose** between implementations, **fell
back**, or **silently degraded** — with the reason. A reader must be able to
tell which code path ran without reading the code.

- Which backend/adapter/host was selected, **what was requested**, and why they
  differ (`backend 'python' (requested: 'auto')`, plus the fallback reason).
- Which optional mechanism is engaged this session (cache, overlay, hardware
  acceleration) — **and log the DISABLED case too**. "No line" is not evidence
  of "off"; it is indistinguishable from broken logging.
- **What is actually in effect** versus what was configured. Configured intent
  is not evidence of runtime state.

---

## 3. One-shot environment lines are mandatory for host-dependent code

A defect that reproduces on the reporter's machine and not the developer's is
**the normal case**, not the exception. Any component whose behaviour depends on
the host MUST log, **once, at construction**: the real backend in use, any
fallback reason, the device pixel ratio, the platform, and the relevant
geometry.

---

## 4. Summarise per operation, never per event

A drag emits hundreds of events. Logging each at INFO makes the report
unreadable and is self-defeating. Log:

- **one line when the interaction begins**, carrying the geometry and thresholds
  it will operate under;
- **one line per significant transition** inside it (a re-render, a fallback, a
  cancellation);
- **one summary line when it ends**, carrying counts, worst-case measurements
  and the final state.

> **Logging is not free — this is cost, not just noise.** If a handler pushes
> logs to the UI thread (a log viewer, a status bar), **every line** runs a full
> cross-thread model-update cycle. Real evidence: INFO logging on **every** fill
> → **5,028 lines in 2 seconds** → the UI froze solid, degrading **linearly with
> the number of operations**. The handler catches at the **root** logger, so
> which screen the line came from **does not matter**. Inside a loop that runs
> many times (per record, per step, per tick): lower the level, or
> coalesce/throttle before logging.

Put **numbers a reader can act on** in the summary: sizes in pixels **as well
as** percentages, elapsed milliseconds, and how far a value sat from its
threshold. *(Percentage-only reporting hid a 333px blank band behind "15%".)*

---

## 5. Log the state that lets a layer be ruled OUT

Instrument several layers at once, not only the suspected one. For **each**
layer, log what a reader needs to **exonerate** it: what it was asked to do,
what it actually applied, and what is **still pending**.

Deferred or coalesced work MUST report **whether it has been applied yet** — a
frame captured while an update is pending shows new data next to a stale
overlay, and **nothing else in the log** would reveal that.

---

## 6. Six levels, in order — pick the narrowest one that fits

`TRACE < DEBUG < INFO < WARNING < ERROR < CRITICAL`

- **`TRACE`** — detail too high-frequency even for a normal developer session:
  per frame, per pixel, per tick. Reserved for exactly the hot paths §4 forbids
  logging per event. *If you'd hesitate to leave a line on for a whole
  diagnostic session because of its volume, it's `TRACE`, not `DEBUG`.*
- **`DEBUG`** — the per-event detail §4 describes: normal diagnostics, safe to
  leave on for a whole reproduction.
- **`INFO`** — decisions, environment, per-operation summaries (§2-3).
- **`WARNING`** — a **degraded but recovered** path (a fallback engaged, a retry
  succeeded).
- **`ERROR`** — an operation failed but the process is still sound.
- **`CRITICAL`** — the process itself is compromised (unrecoverable startup
  failure, corrupted state nothing downstream can trust). Rare by design; don't
  use it for an ordinary caught exception that `ERROR` already covers.

The threshold is a **single** configuration key; a call below it is dropped
**silently**, regardless of which method was called.

---

## 7. Developer runs get more logging, automatically

| Flag | Threshold | File |
| :--- | :--- | :--- |
| `--dev` | `DEBUG` | `logs/dev-<timestamp>.log` |
| `--debug` | `TRACE` | `logs/debug-<timestamp>.log` |

Both write the **whole session** to a timestamped file. `--debug` **implies**
`--dev` — it is strictly more verbose, not a separate mode.

**Never require a configuration edit to obtain diagnostics**, and **never** rely
on the reporter copying terminal scrollback by hand — detail is lost exactly
where it matters. **Ask for the log FILE.**

---

## 8. Prefix log lines with a stable tag, and keep the format filterable

Use a bracketed subsystem tag as the first token — `[chart-env]`,
`[chart-data]`, `[cached-frame]` — or a consistent `KEY=value` style. A reporter
pastes a whole session; the reader needs **exactly one** filter command to
isolate a subsystem.

The formatter must be **fixed-field**, e.g.:

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

— specifically so a saved log file can be filtered **two ways** without touching
the app:

- **by level:** `grep -E '\- (WARNING|ERROR|CRITICAL) \-' session.log` — because
  the level field is delimited by ` - ` on both sides, this never accidentally
  matches a level name appearing **inside** a message;
- **by subsystem:** `grep '\[chart-data\]' session.log` — combine both to
  isolate one subsystem's verbose output.

**Don't change the field order or separator** without checking whether a filter
or regex depends on it (in a task document, a script, or a bug report's own
reproduction steps). The CI gate in [`ci-rule.md`](ci-rule.md) §5 **scans logs
with exactly this matcher** — changing the format breaks that gate silently.

---

## 9. A diagnostic nobody has seen emit does not exist

After adding logging, **run the path and confirm the lines actually appear**,
through the **REAL** logging configuration — not through a quick default setup
in a scratch script, which attaches a root handler the real app never has.

An entire debugging round was lost to instrumentation that **could not emit**.
