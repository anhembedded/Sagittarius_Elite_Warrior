# Retrospective review — the eight commits that never had a pull request (2026-09-15)

Eight commits reached `master-warrior` without passing through a pull request, so none of them was
ever read by a reviewer. They are already merged and every `claude/*` branch is level with
`master-warrior`, so GitHub cannot open a pull request for them: there is no diff left to show. The
user asked for the review anyway, and this file is it — same checklists as
[`.claude/skills/pr-review/SKILL.md`](../../.claude/skills/pr-review/SKILL.md), no pull request to
comment on.

Each finding says whether it is **still actionable today** or **overtaken** by later work, because a
retrospective review whose findings are already dead is a reading exercise rather than a review.

---

## 1. What is actually under review

Three of the eight commits carry no content of their own. Reviewing a merge means reviewing what it
brought, so the eight collapse into six pieces of work:

| Commit | Author | Date | What it really is |
| :--- | :--- | :---: | :--- |
| `f3531b34` | Claude | 09-10 | The merge of `claude/adoring-wozniak-5uio40`. Its content is `5494b09a` + `5f7eb359` below. The `BUG-116` files in its second parent arrived from `master-warrior` and were reviewed there. |
| ↳ `5494b09a` | Claude | 09-10 | **`BUG-115`** — every embedded QML scene goes through one `QuickSurface`, so it paints opaque. 66 files. |
| ↳ `5f7eb359` | Claude | 09-10 | **`BOT-133`** — a boot-time check on the installed engine build, and two guards so the QML and theme mechanisms refuse the wrong way. 12 files. |
| `17be6674` | Nathan Embedded | 09-13 | The HLD/SDD diagram refactor: eight diagrams split into an `a` high view and a `b` detail view. |
| `223d4d31` | Claude | 09-13 | The independent design review of the `EPIC-025` Phase 0 specification. 673 lines, one file. |
| `7df8d56e` | Claude | 09-14 | The merge of `bfaeec35` — the seven scheduled-agent briefings trimmed to their own content. |
| `fde93be8` | Claude | 09-14 | The merge of `b4037002` — the `.claude/rules` pointers, the `pr-review` skill, and their guard. |
| `2d13c4dd` + `b7708457` | Claude | 09-14 | `BUG-119` filed, then its root cause corrected one day later. |
| `93981500` | Claude | 09-14 | **No content.** The merge that carried `bfaeec35`, `b4037002` and the two `BUG-119` commits onto the epic branch. |

Only two of the eight touch `src/`, so the code half of the review is `5494b09a` and `5f7eb359`.
Everything else is `Docs/`, `Tasks/`, `.agents/` or `.claude/`, which `ci-rule.md` §1's exception
covers — and no commit here mixes the two, so the exception applies cleanly rather than being
argued away.

---

## 2. The one mechanism worth copying, and where its ratchet stops

`BUG-115` is the most instructive change in the set, so its picture is the one diagram here. The
defect was not a widget bug; it was that the QtWidgets ↔ QML boundary existed as a copy-paste
convention rather than as an abstraction, and the convention was wrong on every real screen.

```
BEFORE (ten hosts, ten copies of the same twelve lines)

  Panel / Overlay / Card ──paints bgCard via apply_role()
        └── QQuickWidget, hand-built here, setClearColor(transparent)
                 "so the parent SURFACE shows through"
                       │
                       ├── software path (offscreen, grab(), every test) ── looks right ✅
                       └── texture path (every real desktop session) ───── BLACK / see-through ❌
                            Qt punches a hole in the parent's backing store,
                            then composites the scene over a black clear.

AFTER (one abstraction, one source of truth for the colour)

  kit/style.py
     _STATIC_BACKGROUND_TOKENS   the one table saying which token a role paints
        │                    │
        │ read by _background()          │ read by background_token(role)
        ▼                                ▼
   the parent's QSS                qml/embed/QuickSurface
   (apply_role)                    the ONLY place this app builds a QQuickWidget
                                   clears the scene to that same token, opaque
                                        │
                                        └── both paths now agree ✅

  Guards: test_quick_widget_only_in_embed.py  — nobody else may build one
          test_style.py (agreement test)      — reads the LIVE colour, not a call
```

Two things make this worth copying into PR 1.3 rather than merely approving:

- The agreement test asserts an **observable colour** off `quick_widget.quickWindow().color()`,
  not that a function was called. It is falsifiable in the sense `pr-review` E12 asks for.
- The guard was proved to fire. Planting `QQuickWidget()` and `setClearColor(...)` in
  `src/presentation/ui/qml/host.py` turned two of the four guard tests red, naming
  `qml/host.py:70`; the tree was restored and `git diff` came back empty.

The ratchet, however, stops one directory short of the fix it guards — finding **S1** below.

---

## 3. Findings

**Blocking: none.** Nothing in these eight commits ships a defect that can be demonstrated on the
current tree.

### S1 — Should fix · still actionable · the `BOT-133` guard cannot see `scripts/`, which is where its own sixth copy lived

`tests/unit/architecture/test_quick_widget_only_in_embed.py:34` scopes the whole scan to
`src/presentation/ui`. `5f7eb359`'s own commit body says the theme wiring was *"six entry points
each [with] a partial copy … Now one function, used by the bootstrapper and all six scripts"* — so
five of the six copies it removed were **in `scripts/`**, and the guard written to stop the seventh
cannot read that directory. `ONBOARDING.md` trap 11 asks for `src/`, `scripts/` **and** `tests/`.

Proved rather than argued: planting `configure_app_qml({}, None, {})` and `get_theme_bridge({})` in
`scripts/quick_surface_desktop_probe.py` left all four guard tests green (`4 passed`). Restored.

Six palette-carrying seeding sites exist outside `theme_bootstrap.py` today, all in `tests/`:
`tests/conftest.py:32` and `:37`, `tests/unit/presentation/ui/kit/conftest.py:54`,
`tests/unit/presentation/ui/test_preview_fixtures_exist.py:94`,
`tests/unit/presentation/ui/test_app_owns_its_size_tokens.py:116` and `:214`,
`tests/unit/presentation/ui/screens/backtest/test_backtest_top_panel_layout.py:22`.

**What breaks if it ships as-is:** the next probe or E2E script under `scripts/` spells the pair out
again — the exact defect `BOT-133` was written to make impossible — and nothing says so.

**Smallest fix.** Add `scripts/` to the scanned roots. A test fixture seeding the theme before the
bootstrapper runs is legitimate, so either exempt `tests/conftest.py` and the kit fixture by name
with the reason, or leave `tests/` out and narrow the guard's docstring, which today claims the
mechanism has one entry point without enforcing it outside one directory.

### S2 — Should fix · still actionable · `SDD-06b` describes four of five `market_data` ports with signatures that never shipped

`17be6674` split `sdd-06_market_data_contracts.puml` into a high view and a detail view. The
detail view was accurate against the specification at the time. Phase 0 and Phase 1 then shipped
something else, and only one of the five divergences was written back:

| `Docs/SDD/diagrams/sdd-06b_market_data_contracts.puml` says | What `src/modules/market_data/contracts/` actually publishes |
| :--- | :--- |
| `IHistoricalKlines.load(symbol, timeframe, start, end)` | `load(...)` **plus** `load_many(...)`; the diagram lists no `load_many` (`i_historical_klines.py:51`, `:77`) |
| `ISymbolCatalog.list_symbols(quote_asset: str \| None)` | `list_symbols(*, force_refresh: bool = False)` (`i_symbol_catalog.py:66`) |
| `IMarketDataSync.sync(...) -> SyncHandle` and `cancel(handle)` | `sync(request: MarketDataSyncRequest) -> None`; there is no `cancel`, and `SyncHandle` does not exist anywhere in `src/` |
| `IRangeCoverage.coverage(...) -> RangeCoverageSnapshot` | `coverage(symbol, interval, *, start_time, end_time, now) -> BacktestRangeCoverage` (`i_range_coverage.py:50`) |
| implementer `HistoricalKlinesService` | `StoredKlinesReader` |
| `IMarketStream.start(...) -> StreamHandle`, `stop(handle)`, `stop_all(owner)` | Diverges too — **and the diagram says so**, in its own `SHIPPED IN PR 1.1b WITHOUT THE HANDLE` note ✅ |

`RangeCoverageSnapshot` does exist, but as `IMarketDataRepository`'s internal answer type
(`i_market_data_repository.py:29`), not as `IRangeCoverage`'s — so the name in the diagram points at
a real class that is the wrong one, which is worse than a name that resolves to nothing.

This is drift caused by pull requests 0.5, 1.1a and 1.2 — Claude's own — not by `17be6674`.
`CLAUDE.md`'s table and `pr-review` K3 both put the fix in the pull request that causes the drift.
The `IMarketStream` note proves the practice was known and applied once.

**What breaks:** `SDD-06b` is what PR 1.3 (`modules/trading`) is meant to copy the port shape from,
and four of five rows teach a shape that does not compile.

**Smallest fix.** The pattern already exists in the same file: a note under each interface saying
what shipped and why it differs. Four notes, no diagram surgery.

### S3 — Should fix · still actionable · `.claude/skills/` has no path guard, and it holds the review checklist

`scripts/check_skill_prompt_references.py:30` globs `.agents/Skills/*.md` and nothing else.
`b4037002` correctly added a `scanned_roots_registry.py` row for `.claude/rules` (`:150`) — and
none for `.claude/skills`. So `.claude/skills/pr-review/SKILL.md` carries 12 relative links into
`.agents/` and roughly 16 backticked repository paths, none of them checked by anything.

Checked by hand for this review: all 12 links and all 16 paths resolve today. That is the state, not
a guarantee.

**What breaks:** the first rename under `.agents/rules/` or `tests/unit/architecture/` sends every
future reviewer to a file that is gone, and the reviewer has no reason to doubt the checklist.
`.agents/Skills/README.md` §1 describes this rot happening once already (`EPIC-011`) — which is why
the checker exists for the other skills directory.

**Smallest fix.** Widen `SKILLS_DIR` to both roots (the script already understands
`CHECKED_ROOTS`, which includes `.claude/`), and add the registry row.

### Q1 — Question · still actionable · which language does a row on the bug board take?

`Tasks/bug_report/README.md` is a pre-2026-09-12 Vietnamese document. The two `BUG-119` rows added
on 09-14 by `2d13c4dd` and `b7708457` are Vietnamese; the `BUG-121` and `BUG-122` rows added on
09-15 are English, in the same table (`:72`, `:90`, `:93`). `CLAUDE.md`'s Language section puts every
`.md` in English but lets a pre-existing Vietnamese document stand, with **new sections** in English.
A table row is neither clearly a new section nor clearly part of the old text, and the board is
bilingual either way now. This is the user's call, not a defect in either commit.

### Q2 — Question · not actionable · was the gate's log file scanned, or only its summary?

`5494b09a` and `5f7eb359` both claim `ci-local.ps1 -Full = PASS` with a test count and a coverage
figure, plus measured X11 pixel values — strong evidence for the fix itself. Neither says the
`LOG_FILE` was grepped, which `CLAUDE.md` §2 and `ci-rule.md` §8 make the actual green claim; a
count and a coverage number come from pytest's summary, which is the thing those rules say not to
judge by. In the change's favour, `src/presentation/ui/qml/host.py:21-30` documents the benign Qt
teardown noise and cites that exact rule, which reads like an author who had opened the log.

Unanswerable now, and recorded only so the next commit body states it in one clause.

### N1 — Nit · overtaken · commit subjects

`223d4d31`'s subject is `Docs: independent design review of EPIC-025 Phase 0 spec`. `commit-rule.md`
§2 allows eight lowercase types with a scope; `docs(tasks):` was the one meant. `17be6674` carries
no type at all and no AI trailer — the trailer is correctly absent (the user wrote it), and the
subject convention on the user's own commits is the user's call. Every other commit in the set is
well-formed and every Claude-authored one carries the trailer.

### N2 — Nit · overtaken by accident · the bug board's counts were wrong for eight commits

`2d13c4dd` filed one new open bug and moved three numbers: open 1 → 2 (right), **fixed 114 → 115**
and **total 115 → 117** (both wrong by one — the tree held 116 report files). `b7708457` carried the
same +1 forward. Then `f37717ab` added a report without moving the total, and the stated number
became right again. Today the board says 118 fixed / 2 open / 120 total and the filesystem holds
exactly 118 + 2, so there is nothing to correct — the error was cancelled, never found.

`ONBOARDING.md` §6 calls bookkeeping the most commonly botched part of this repository, and
`tests/unit/test_task_board_is_consistent.py` already exists. Deriving those three numbers from the
two directory listings there is a few lines, and it is the only thing that would have caught this.

### N3 — Nit · still actionable · a count inside a briefing

`.agents/Skills/palette.prompt.md:46` writes of `BUG-008` *"which recurred four more times"*.
`.agents/Skills/README.md` §1 bans counts in these files. It is historical rather than current
state, so it is borderline — but a fifth recurrence would make it wrong, which is precisely the
failure mode the ban describes. Everything else in the seven trimmed briefings is clean: the only
other digits are `head -N` in commands, epic ids, and the "~50 lines" size guidance.

### A note on two things that are **not** findings

Both look like rule violations and are not, and saying so is cheaper than having someone "fix" them:

- `engine_capabilities.py:115` uses `getattr` and `inspect.signature`. `architecture-rule.md` §2.1
  forbids probing a **boundary contract** for capabilities. This probes a third-party module for
  whether an API exists at all, which is the module's entire purpose and cannot be expressed as a
  named type.
- `engine_capability_validator_extension.py:67`/`:73` probe `getattr(context, "logger", None)`, and
  the class types its context as `IExtension[Any]`. Both are the established convention here:
  `asset_validator_extension.py:76` does the same with `hasattr`, and all three
  `IExtension[...]` implementations in `src/` use `Any`. A faithful copy of the sibling it names in
  its own docstring is not this commit's finding. Worth knowing for whoever does fix it: the
  engine's `EngineContext.logger` (`kernel/context.py:133`) is a property that falls back to
  `NullLogger`, so the probe can never be falsy against the real context, the `print()` fallback is
  unreachable in production, and the report is emitted twice into the run log the gate scans.

---

## 4. What was verified, and what could not be

| Check | Result |
| :--- | :--- |
| `ruff check src tests scripts` | All checks passed |
| `ruff format --check src tests scripts` | 1241 files already formatted |
| `python3 scripts/check_skill_prompt_references.py` | OK — every `.agents/Skills/` path resolves |
| Guard mutation (`pr-review` E12) | Planted violation in `qml/host.py` → 2 of 4 guard tests red, naming `qml/host.py:70`; restored, `git diff` empty |
| Guard scope probe (S1) | Planted violation in `scripts/` → 4 passed, guard blind; restored |
| Diagram references after the `a`/`b` split | 20 of 20 `.puml` names referenced across `Docs/`, `Tasks/`, `.agents/` resolve; no dangling old name |
| `pr-review` skill's own links | 12 of 12 relative links and 16 of 16 repository paths resolve |
| Bug board arithmetic, today | 118 completed + 2 incomplete = 120 files, matching the stated 118 / 2 / 120 |
| Design review's blocker 2.1 (`dev.mode = false` cannot boot) | Closed in the specification: `Docs/SDD/README.md:97` now carries the "dropped with one log line, whatever its place" clause the review proposed |
| Design review is reachable | Linked from `Docs/SDD/README.md:4` and from the module-boundary decision (`:8`, `:286`) |
| The current head is gated | `logs/ci-local-20260915-064433.log` — 4495 passed, 4 skipped; the four `FAILED\|ERROR\|Traceback\|ResourceWarning` hits are a `[ERROR]` parametrize id and the gate's own scan header; its run-log scan reports no `WARNING/ERROR/CRITICAL`. Written 06:47 UTC against head `b6e16275` (06:48 UTC), working tree clean |

Not verified, and it matters:

- The six PNG screenshots under `Tasks/bug_report/completed/BUG-115_assets/` are binary. The
  report's on-screen claims — three sample pixels `#000000` → `#111318`, a grab-versus-screen pixel
  diff of 24.12% → 0.00% — rest on them and on a real X11 session. Neither can be re-measured from
  this container.
- `5494b09a`'s 11 migrated `preview.py` files and 9 changed `QTest` call sites were read as a group
  in the diff rather than one at a time. The mechanism and the guard were checked; each call site
  was not.
- No `plantuml` binary is installed, so `17be6674`'s 24 diagrams were checked for existence and
  reference integrity, and the two `sdd-06*` sources were read in full. That they all **render** is
  unverified.

---

## 5. What the reader has to decide

1. **S1, S2, S3** are three small, independent changes. S2 is the one with a deadline: PR 1.3 is
   supposed to read `SDD-06b` as its template.
2. **Q1** — one sentence in `CLAUDE.md` settles whether a bug-board row is Vietnamese or English.
   Until then the board stays bilingual.
3. **N2** suggests one guard (three derived counts in an existing test file) that would have caught
   a class of error `ONBOARDING.md` §6 already calls the most common one here.
