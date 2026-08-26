# EPIC-010A — `StateScope`, `IStateStore` and the ConfigManager-backed store

**Status:** 🔵 Not started
**Repo:** **Engine** (`sagittarius_engine`) — see design §8 step 1
**Depends on:** nothing

## What

Pure types plus three small stores. No consumer, so no risk.

| Symbol | Notes |
| :--- | :--- |
| `Lifetime` | `enum.Enum` — `PERSISTENT`, `SESSION` |
| `StateScope` | `dataclass(frozen=True)` — `key: str`, `instance_id: str \| None`, `lifetime: Lifetime`, plus `is_singleton()` / `as_default()` |
| `IStateStore` | ABC — `read(scope)`, `write(scope, data)`, `discard(scope)`, `flush()` |
| `ConfigManagerStateStore` | wraps a **second** `ConfigManager` pointed at `state/ui_state.json` |
| `InMemoryStateStore` | the `SESSION` store **and** the test double — one class, two jobs |
| `NullStateStore` | boundary rule 2 fallback, and the Sanity tier's store |
| `IStateStoreLocator` | ABC + a repo-root implementation; owns path, filename and `reset()` |

`state/` goes into `.gitignore` beside `logs/` and `database/`.

## Why so little code

Design §5.6.6's audit: slice-merge, dirty tracking and fail-safe corruption
handling all come free from `ConfigManager` — measured by
`scripts/ui_state_store_feasibility_probe.py` (H1, H2, H3). This task writes the
wrapper, not the mechanism.

## Acceptance

Unit tests covering every failure mode in the first design's §2.1 that a store
can reach:

- missing file → empty document, no error (mode 8)
- **truncated JSON → empty document, does NOT raise** (mode 9) — this one is
  mandatory: it locks the accepted cost in design §4.1.3, and
  `architecture-rule.md` §7.1 requires an accepted cost to have a test, not a note
- `schema_version` newer than the code → ignored wholesale (mode 10)
- `OSError` on write → swallowed, never propagates (mode 7)
- **writing one slice leaves unrelated slices intact** (D2) — the lazy-presenter
  guarantee
- a slice containing a non-JSON type raises at capture time, not at shutdown (mode 4)
- the store cannot read `API_KEY`, and writing state never touches
  `user_config.json` (probe H4)

Plus `ruff`, `ruff format`, and `mypy` clean under the engine's own gate.

## Out of scope

No presenter touches this yet. No debounce (that is `010B`).
