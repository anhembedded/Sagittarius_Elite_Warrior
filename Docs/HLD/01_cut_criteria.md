# §1 — Criteria for cutting a module

A module may exist only if it passes **all six** criteria below. The criteria are there so that
the next argument — "we need a fifth module", "these two should be merged" — is settled with
evidence rather than taste.

## 1.1 The six criteria

| # | Criterion | The question to ask | Where it comes from |
| :-: | :--- | :--- | :--- |
| **C1** | **A language of its own (Ubiquitous Language)** | Is there at least one word that means something **different** here than elsewhere, to the point that the code has to keep two types? | DDD: a bounded context is the boundary of a language |
| **C2** | **Owns its own data or state** | Is there an entity, a piece of state, or a table that **only** this module is allowed to write? | DDD: the Aggregate is the unit of transactional consistency |
| **C3** | **A different lifecycle and a different reason to change** | What makes this change, who changes it, how often — and is that different from the piece next to it? | The Single Responsibility Principle at module scale (Martin: "one reason to change") |
| **C4** | **Testable on its own** | Do `domain/` and `application/` run their tests with **no** Qt and **no** other module present (only the other module's `contracts/`, which can be mocked)? | Clean Architecture: independent testability |
| **C5** | **A real consumer outside, or a screen the user actually uses** | Does at least one other module use this module's `contracts/`, **or** does it own a screen or CLI command that a user really runs? | `architecture-rule.md` §6: promote when a second consumer **actually** appears |
| **C6** | **Not purely technical** | Take away all the business meaning: is there still a reason for this piece to exist? If yes, it is **support**, not a bounded context | Distillation: Generic subdomain |

**The merge/split threshold.** Split when C1 **and** C2 both hold. If only C3 holds (the pieces change
at different rhythms), split **files or packages inside** the module (`architecture-rule.md` §5) and
leave the module boundary alone. If only C6 fails, the piece is a support package.

## 1.2 Applied to this application — evidence measured on 2026-09-10

| Candidate | C1 | C2 | C3 | C4 | C5 | C6 | Verdict |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :--- |
| `market_data` | ✅ *Candle* means market data (OHLCV, shard, gap) | ✅ SQLite shards, the catalog JSON | ✅ changes with the venue and the data format | ✅ | ✅ 4 screens and 2 CLI commands dispatch `GetHistoricalKlinesQuery` | ✅ | **Bounded context** |
| `trading` | ✅ *Position* is a `LivePosition` **reported by the exchange**, read-only (`domain/trading/live_position.py`: *"this app never computes any of its fields"*) | ✅ `TradingSessionState`, credentials, real orders | ✅ changes with safety rules and venue | ✅ | ✅ `strategy` needs `IOrderSubmission`; 3 CLI commands | ✅ | **Bounded context** |
| `strategy` | ✅ *Signal*, *Arm*, `LiveStrategyConfig` exist nowhere else | ✅ the configuration of the strategy currently armed | ✅ changes with trading ideas — **the fastest rhythm in the app** | ✅ | ✅ `backtesting` runs it; `trading` receives orders from it | ✅ | **Bounded context — Core** |
| `backtesting` | ✅ *Position* is an `OpenPosition` that is **simulated**, mutated by the app on every tick (`open_position.py`) | ✅ run results, trade log | ✅ changes with the simulation model (fees, matching) | ✅ | ✅ one screen of 12,309 lines that the user runs | ✅ | **Bounded context** |
| Account / Equity | ❌ merely derived from `ACCOUNT_UPDATE` | ❌ no state of its own | — | — | ❌ one consumer | — | **Stays inside `trading`**; a candidate to split later |
| Dev Board | ❌ no word of its own — 59 names shared with Trading | ❌ | ❌ | — | — | — | **Not a module** — it is a *surface* (§4) |
| `charting` (the 27-file chart card) | ❌ | ❌ | ✅ | — | ✅ 3 screens | ❌ **purely technical** | **Support** |
| `indicators` (indicator mathematics) | ❌ | ❌ | ✅ | ✅ | ✅ strategy, backtest, dev board | ❌ | **Support** |
| `ui_kit` | ❌ | ❌ | ✅ | — | ✅ every screen | ❌ | **Support** |
| `binance_gateway` (`exchange_session_factory`, `binance_endpoints`, credentials, error translator) | ❌ | ❌ | ✅ changes with the exchange SDK | ✅ | ✅ `market_data` **and** `trading` both build their client from one factory (the guard test *only the session factory constructs binance client*) | ❌ | **Support** — the shared Anticorruption Layer for the SDK |

**The two `Position` types are the strongest piece of evidence.** One word, two meanings, two
lifecycles, two different owners allowed to mutate — and the code **already** keeps two separate
types, before anyone had named the boundary. That is the textbook definition of two bounded
contexts. The same holds for *Order* (a real order versus a simulated fill) and *Candle* (market
data versus the model used for drawing).

## 1.3 Anti-criteria — what must **not** be used to cut

- **Do not cut by screen.** Trading and Dev Board rebuilt the same business logic twice and produced
  59 duplicated names. A screen is a place where a module's widgets are *hung* (§4); it does not own
  business logic.
- **Do not cut by technical layer at the top level.** Top-level `domain/` and `application/`
  directories are the present state, and they are what caused the disease: nobody owns a context.
  Layers exist only **inside** a module (§3.2).
- **Do not cut for elegance.** Every module must be able to point at C5: who uses it.
- **Do not cut before a consumer exists — but keep the seam open.** Account/Equity stays inside
  `trading` until a second real consumer appears; `EPIC-024C` was cancelled precisely because it
  planned to cut "Market Connector" and "Market Order" ahead of any evidence. This is a rule about
  *where code lives*, not a licence for a closed design (`architecture-rule.md` §7.2.1): the
  account read model already sits behind its own port (`IAccountSnapshot`) and its own DTO, so
  moving it into a module of its own later is a directory move plus one line in `shell/modules.py`,
  not a rewrite. Every "not yet" in this document must be checkable the same way — name the seam
  that makes the later step local.
