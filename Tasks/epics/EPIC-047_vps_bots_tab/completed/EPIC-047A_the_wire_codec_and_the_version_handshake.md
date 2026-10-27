# EPIC-047A — Every record behind the Bots queries crosses a JSON wire and back equal, and a build difference is refused in words

**Status:** ✅ Done (2026-10-26) — two criteria narrowed with their reasons (the revision's source and the bridge's exit status go to EPIC-047C), see §2
**Source:** the owner's delegation of 2026-10-24 (*"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"*, "decide them for me, consistent with the whole Constitution"), settled as G10; [the remote link record](../DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D5 and D6.
**Risk:** 🟡 — a wrong wire form shows a wrong number on a real-money screen; the contract tests and the same-build handshake are what hold it.
**Complexity:** M — about 140 lines of codec in the spike (R4), 14 roots behind 47 records, plus the handshake.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-048A](../../EPIC-048_ui_reaches_the_application_through_its_doors/completed/EPIC-048A_the_doors_rule_and_its_guard.md) and the first pull request of [EPIC-048B](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) (`GetBotRunFactsQuery`, `AssessBotQuery` and the readiness read models, merged as #731). 047A needs the contract types that exist, not the second pull request (`GetVenueChoicesQuery`), which joins the codec as one entry when it lands.

---

## 1. Context and problem
The link carries the Bots queries' results and the bus events as JSON. De-risk R4 counted **45 records, 225 fields, 14 enums and 3 tagged unions** behind the 15 roots, and measured about 110 hand-written lines per type, about 550 lines in all, against about 140 lines of reflective codec (DERISK §4). R6 showed that a handshake hashing Python module paths changes when a class moves with the wire unchanged, and that one contract hash can only say "same" or "different" (DERISK §6.4). The hand-written codecs of the stored files (`bot_record_codec.py`, `host_command_codec.py`) stay: a stored file must read across versions.

## 2. Acceptance criteria
- [x] One reflective codec encodes and decodes the roots of the Bots queries and events from their type hints; it adds no dependency. *Evidence:* `src/support/wire/wire_codec.py` and `wire_shape.py`, standard library only; `requirements.txt` and `pyproject.toml` untouched. 14 roots (§Implementation notes, "What changed since R4"). Bus events are not roots yet: the bridge (047C) decides which it forwards and adds them as entries.
- [x] One round-trip contract test per root type: types are asserted, with a full and a minimal instance; `decode(encode(x)) == x` for every instance. A new root without a test fails a guard. *Evidence:* `tests/unit/support/wire/contract/test_root_*.py` (14 files); `round_trip.py` asserts equality, the same form (enum member, `Decimal` digits, datetime offset), exactly the record's fields on the wire, no field left empty across the full instances, and every union member covered; `tests/unit/architecture/test_every_wire_root_has_a_contract_test.py` was red against the 14 roots before the tests existed and is green after.
- [x] Every tagged union carries an explicit wire name for each member; moving a class to another module changes no wire name or hash. *Evidence:* `@wire_name` on eight union members; `test_wire_schema_hash.py::test_the_same_wire_in_classes_of_another_module_hashes_the_same` builds the same wire in classes of another module (red with a module path in the hash, mutation M6); `test_wire_names_are_pinned.py` writes down all 22 names. **Enums carry no separate name:** an enum is typed by the field that holds it and its wire is its members' values, which the hash reads, so renaming or moving the enum class changes nothing and adding a member changes the hash (`test_wire_schema_hash.py`, "enum-grew"/"enum-shrank"). A second name per enum would be a second thing to keep in step with the values.
- [~] Every message carries a per-bot revision; a receiver applies a record only when its revision is greater. *Delivered:* the envelope carries `revision` (`WireRoots.encode(..., revision=n)`, `revision_of`), and `RevisionGate` applies a record only when greater, remembers a deletion, and gives the same state in either order of the snapshot and the event that overtook it (`test_revision_gate.py`, a real bot snapshot through the codec). **Deferred, with its reason:** the bot record has no revision today (checked: `BotSnapshot`, `bot_record_codec.py`), and adding one changes the bot store the host writes, which EPIC-047B is changing in parallel and which this task was told not to touch. The sender's revision (a counter in the record, or the bridge's own sequence per bot) is decided in [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md), which builds the sender; the gate and the envelope do not change with that choice.
- [~] The handshake exchanges the app version and a hash of the wire names; on a difference the bridge answers "refused" naming what differs and exits 3, before any read. The desktop's words name both builds and `sudo sew-update`. There is no read-only mode in v1. *Delivered:* `link_handshake.py`: `Hello` carries the protocol, the app version and one digest per root; `judge` returns `None` for the same build, otherwise a `Refusal` whose `differs` names what changed (`app_version`, `protocol`, `wire:<root>` with the side that lacks it) and whose `words` read "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`" (`test_link_handshake.py`). **Deferred:** the bridge's process, its refused message on stdout and its exit status 3 belong to [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md), since the bridge does not exist yet and this task has no host and no network; `Refusal.to_wire()` is the message it sends.
- [x] An unknown wire name, a missing field or a wrong type is a typed decode error, never a silently defaulted value. *Evidence:* `test_wire_codec.py` (unknown name, missing field with a default on the type, extra field, eleven wrong types, a value the type's own rule refuses); `WireDecodeError` names the path.
- [x] A mutation check: change a field's type in one record, and the root's contract test fails. *Evidence:* Implementation notes, "Mutation checks" (M4).

## 3. Design
Apply the "schema from type hints" shape (P5; DERISK §4.5): the codec reads the dataclass fields and their annotations, with explicit wire names for unions.

**Where the codec lives (decided at start, from `architecture-rule.md` §3 and the remote link record).** Three constraints: "support packages import no module", "a module imports another only through its `contracts/`", and the shell is the only place that may import every module's entry point. So:

| Piece | Where | Why |
| :--- | :--- | :--- |
| The codec, the closed registry, the schema hash, the handshake, the revision gate | `src/support/wire/` (a technical package) | no host and no network in it; imports the standard library and `core/contracts` only, so the bridge (047C) and the desktop transport (047D) both use it without a module importing it |
| The mark `@wire_name` and the entry `WireRoot` | `src/core/contracts/` | a module may import `core`, and may not import a support package's non-contract files (`boundaries/rules.py` `_module_may_import`); the contract types need the mark |
| Each module's list of roots | `modules/bots/composition/wire_roots.py` → `BOTS_WIRE_ROOTS`, exposed by `modules/bots/module.py` → `wire_roots` | a root such as `BotList` lives in `application/queries/`, which the shell may not import; the module's own `composition/` may, and `module.py` is the one file the shell may import |
| The meeting point | `src/shell/wire_roots.py` → `link_roots` | the only place that sees every module's list; it builds the registry, which refuses a bad graph at once |

*Rejected:* a registry list inside `support/wire` (it would import modules); the roots in `shell/` directly (it cannot import `BotList`); moving `BotList`, `BotFills` and `PlannerMarket` to `contracts/` (EPIC-048B's second pull request touches that, and it is outside this task).

**The wire never carries a secret, a key or an unfiltered exception.** Three mechanisms, none of them a convention: (1) the list is closed, a message naming a type outside it is `unknown wire name` and a value of such a type cannot be encoded; (2) `WireRoots` refuses at registration a graph holding a field whose name reads like a secret (`secret`, `password`, `passphrase`, `private_key`, `api_key`, `token`, `credential`), tested on a direct and a nested field; (3) the codec has no wire form for an exception, a float or any class that is not a dataclass, an enum or a scalar, so an exception object cannot become a field. The one free-text field a failure carries, `ConnectFailure.detail` and `.reply`, holds words the application wrote (`"the price"`, `describe_failure`); the cause exception goes to the log only (`composed_venue_account_reader.py` `_failed`).

**Money.** A `Decimal` is text on the wire and keeps every digit and the exponent form (`12.3400`, `1E-8`); a non-finite one is refused; a JSON number for a decimal is a decode error. A duration (`OwnerBudgetCaps.min_order_spacing`, new since R4) is whole microseconds, an integer.

## 3a. Reuse
`.claude/rules/capabilities.md` and `grid_ladder_payload.py` (which already serialises one record to JSON) checked. `grid_ladder_payload.py`: `not used because` it is a hand-written payload for one record (the ladder the chart draws), without enums, optionals, unions or a decoder; the codec covers its case by construction but replaces nothing of it here. `host_command_codec.py` and `health_snapshot.py`: `used` for the `schema` naming convention only (`sew.<words>/<n>`). No catalog row covers "carry a value over a link as JSON"; the codec adds one (`Capability:` block in `src/support/wire/__init__.py`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/wire/` | new: `wire_shape.py` (what a hint means), `wire_codec.py`, `wire_roots.py` (the closed registry, the envelope, the secret scan), `wire_schema.py` (canonical schema and digests), `link_handshake.py`, `revision_gate.py`, `wire_errors.py` |
| `src/core/contracts/wire_name.py`, `wire_root.py` | new: the mark and the entry |
| `src/modules/bots/composition/wire_roots.py`, `src/modules/bots/module.py` | the list of 14 roots and the function that hands it over |
| `src/shell/wire_roots.py` | `link_roots()` |
| union members (`exchange_facts.py`, `futures_facts.py`, `plan_risk_read.py`, `bot_kind_inputs.py`, trading's `connect_failure.py` and `venue_account_snapshot.py`) | `@wire_name` |
| `tests/unit/support/wire/`, `tests/unit/architecture/test_every_wire_root_has_a_contract_test.py` | the codec, registry, hash, handshake and revision tests; one contract test per root; the guard and its row in the scanned-roots registry |
| `Docs/MODULES/bots/05-building-blocks.md`, `.claude/rules/capabilities.md` | the types that cross the link; the generated catalog row |

## 5. Testing
Tier: unit. The commit tier (`ci-local.ps1 -SkipTests`), `tests/unit/architecture` and `tests/unit/support/wire` ran locally and were green; the full gate is GitHub Actions' `ci-local.ps1 -Full` run on the pull request's head (job logs cited in the pull request). The mutation checks were run by hand (below). Not run: a real link; the codec has no host and no network, and no integration or sanity test applies to it yet (047C's bridge is the first real boundary).

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (the new section "Built: the types that cross the remote link"). The wire protocol's page is written by [EPIC-047G](../incomplete/EPIC-047G_the_runbook_for_the_vps_link.md).

## Implementation notes (written when done)
**What changed since R4's count (R4 at `5ddbd68`, this at `15b5876`).** The 15 types R4 listed are 14 roots today, over **47 records, 230 fields, 14 enums and 3 tagged unions** (`VenueSnapshot` with four members, `PlanRiskRead`, and the venue connection's answer). Differences: (1) `RunFacts` is no longer a root: EPIC-048B's `BotRunFacts` carries it with `OwnerBudgetCaps` (+2 records, and the first `timedelta`, a type R4 did not find; it crosses as whole microseconds); (2) `VenueAccountSnapshot` and `ConnectFailure` are the two answers of one query (`GetVenueConnectionQuery`) and one root, a union, rather than two roots; (3) `BotAssessment` and `AssessBotQuery` do not cross: the pure assessment runs on the desktop (`EPIC-047` D1) and `AssessBotQuery` holds an `IBotKind`, code, not data; (4) `BotStatusReport` (14 records, a recursive `JsonValue` and a float) is read by the command line only and is left out, so none of that reaches the wire; (5) `GetVenueChoicesQuery` does not exist yet (EPIC-048B's second pull request); adding it is one `WireRoot` entry and one `test_root_*.py` (the guard fails until both exist). The counts come from a probe run once over the roots at `15b5876`; no test asserts a number (`testing-rule.md`: no hard-coded counts), the contract tests and the guard follow the registry.

**Mutation checks (run by hand, each restored; the test that went red first is named).**
| # | Mutation | Red |
| :-- | :--- | :--- |
| M1 | the encoder drops the last field of every record | `test_root_bot_command_result.py::test_a_full_instance_round_trips` |
| M2 | a `Decimal` is encoded as a float | `test_root_bot_fills.py::test_a_full_instance_round_trips` |
| M2b | a `Decimal` is decoded through `float` | `test_root_bot_fills.py::test_a_full_instance_round_trips` |
| M3 | a union member's wire name changes (`sew.connect-failure/1` → `/2`) | `test_wire_names_are_pinned.py` |
| M3b | a root is renamed in the list | `test_root_bot_list.py` and `test_wire_names_are_pinned.py` |
| M4 | one field retyped in one record (`BotFill.side: str` → `int`) | `test_root_bot_fills.py::test_a_full_instance_round_trips` |
| M5 | a field added to a record without being set in any full instance | `test_root_bot_fills.py::test_the_full_instances_set_every_field` |
| M6 | the schema hash reads the module path (R6's spike) | `test_wire_schema_hash.py::test_the_same_wire_in_classes_of_another_module_hashes_the_same` |
M6 first passed vacuously: `make_dataclass(..., namespace={"__module__": ...})` does not move the class on Python 3.12 (the call overwrites it from the caller's frame), so the fixture "moved" nothing. It uses `module=` now and the mutation turns it red.

**Decisions made on the way.** An enum has no wire name of its own (above). Unknown and extra fields are refused, not ignored: the link is same-build, a stored file is not. A `Mapping` decodes to a read-only `MappingProxyType` (`BotSnapshot.config` was one). The registry's per-root digests are 16 hex characters of SHA-256, enough to tell two builds apart and short enough for a log line.

**Left for the next children.** The revision's source and the bridge's exit status 3 (047C); the heartbeat and idle watchdog (047C, 047D); `GetVenueChoicesQuery` as a root (with 048B's second pull request); the bus events the bridge forwards (047C).
