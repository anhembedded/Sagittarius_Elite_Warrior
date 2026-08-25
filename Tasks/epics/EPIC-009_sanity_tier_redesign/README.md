# EPIC-009 — Sanity Tier Redesign

**Status:** 🟢 **Sanity tier redesign closed** — 4/6 sub-tasks done, 1 deferred
(`EPIC-009D`, no confirmed need), 1 folded into ratification (`EPIC-009F`).
ADR *Approved*.
**Type:** Testing architecture / quality gates
**Priority:** P1 — actively closing real gaps: `BUG-045` and `BUG-048` found
and closed, `BUG-049` found and open (non-blocking)

> Still **not** registered in [`Tasks/ROADMAP.md`](../../ROADMAP.md) — see
> `Tasks/epics/README.md`'s own convention. Add the line once `EPIC-009F`
> ratifies the design this work is actually built against.

---

## 1. Why this epic exists

The Sanity tier reported green while proving substantially less than it
claimed. Evidence: [`sanity_tier_audit_and_remediation.md`](../../reports/sanity_tier_audit_and_remediation.md).

## 2. Design

[`DECISION_2026-08-25_sanity_model_and_execution.md`](DECISION_2026-08-25_sanity_model_and_execution.md)
— the ADR. Model, decisions (D1-D6), constraints (C1-C4), the 12-mode
failure catalogue (still Draft — `EPIC-009F`), open questions.

**Honest ordering note:** `EPIC-009A/B/C` below were built against the
catalogue's *draft* form, before `EPIC-009F` formally ratifies it. Each is
independently verified by real runs and fault injection, not just by
matching the draft — but the design itself is not yet the project's agreed
position. Treat `EPIC-009F` as retroactively validating, not blocking, the
work already shipped.

## 3. Sub-tasks

| ID | What | Status |
| :--- | :--- | :---: |
| [`EPIC-009A`](completed/EPIC-009A_composition_root_scan_and_diagnostic_guard.md) | Retire legacy tier, rebuild as composition-root scans + `diagnostic_guard` | ✅ Done |
| [`EPIC-009B`](completed/EPIC-009B_out_of_process_layer_and_self_check.md) | `build()`/`teardown()` split, `--self-check`, OUT-of-process tests | ✅ Done |
| [`EPIC-009C`](completed/EPIC-009C_fake_binance_rest_server.md) | D6 REST — fake Binance server, closes `BUG-045` | ✅ Done |
| [`EPIC-009D`](cancelled/EPIC-009D_fake_binance_websocket_server.md) | D6 continued — fake Binance WebSocket server | ⚪ Deferred — no confirmed need |
| [`EPIC-009E`](completed/EPIC-009E_fix_uncaught_exception_hang_bug048.md) | Fix `BUG-048` — uncaught exception hangs the process | ✅ Done |
| [`EPIC-009F`](completed/EPIC-009F_ratify_failure_mode_catalogue.md) | Ratify the 12-mode catalogue (ADR Q1) | ✅ Done |

## 4. Findings this epic has produced so far

| Bug | Severity | Status |
| :--- | :---: | :---: |
| `BUG-044` — published engine unimportable (Python-2 syntax) | P1 | ✅ Closed |
| `BUG-045` — Sanity reached the real network | P2 | ✅ Closed (`EPIC-009C`) |
| `BUG-048` — uncaught exception after boot hangs the process | P1 | ✅ Closed (`EPIC-009E`) |
| `BUG-049` — fake server thread leaves 5 uncollectable GC objects | P3 | 🔴 Open |
| `BUG-046`/`BUG-047` — pre-existing Dashboard test failures, surfaced by `BOT-038`'s re-verification (not this epic — filed under that task) | P2 | 🔴 Open, out of this epic's scope |

## 5. What "done" for this epic looks like

Per the ADR's own §7 metrics: sanity test count stays flat as the app grows,
every route constructs, all 5 diagnostic channels are observed (Qt, Python
logging, `warnings`, stderr via `--self-check`, and — once `EPIC-009D` lands
— the websocket boundary too), zero assertions reference a business name, and
every mandatory rule clause has a `test-health` `contract.json` entry that is
actually enforced.
