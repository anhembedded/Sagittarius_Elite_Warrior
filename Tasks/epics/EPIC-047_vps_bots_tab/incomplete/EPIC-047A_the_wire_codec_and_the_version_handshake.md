# EPIC-047A — Every record behind the Bots queries crosses a JSON wire and back equal, and a build difference is refused in words

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24 (*"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"*, "decide them for me, consistent with the whole Constitution"), settled as G10; [the remote link record](../DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D5 and D6.
**Risk:** 🟡 — a wrong wire form shows a wrong number on a real-money screen; the contract tests and the same-build handshake are what hold it.
**Complexity:** M — about 140 lines of codec in the spike (R4), 15 root types behind 45 records, plus the handshake.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-048A](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048A_the_doors_rule_and_its_guard.md) and [EPIC-048B](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) (the epic's prerequisite)

---

## 1. Context and problem
The link carries the Bots queries' results and the bus events as JSON. De-risk R4 counted **45 records, 225 fields, 14 enums and 3 tagged unions** behind the 15 roots, and measured about 110 hand-written lines per type, about 550 lines in all, against about 140 lines of reflective codec (DERISK §4). R6 showed that a handshake hashing Python module paths changes when a class moves with the wire unchanged, and that one contract hash can only say "same" or "different" (DERISK §6.4). The hand-written codecs of the stored files (`bot_record_codec.py`, `host_command_codec.py`) stay: a stored file must read across versions.

## 2. Acceptance criteria
- [ ] One reflective codec encodes and decodes the roots of the Bots queries and events from their type hints; it adds no dependency.
- [ ] One round-trip contract test per root type: types are asserted, with a full and a minimal instance; `decode(encode(x)) == x` for every instance. A new root without a test fails a guard.
- [ ] Every tagged union and enum carries an explicit wire name (a `schema` string such as `sew.bot-snapshot/1`, as `host_command_codec.py` and `health_snapshot.py` carry); moving a class to another module changes no wire name or hash (a test moves a class in a fixture).
- [ ] Every message carries a per-bot revision; a receiver applies a record only when its revision is greater (a test delivers an event before the snapshot that it overtakes, and the result is the same).
- [ ] The handshake exchanges the app version and a hash of the wire names; on a difference the bridge answers "refused" naming what differs and exits 3, before any read. The desktop's words name both builds and `sudo sew-update` (charter Scenario 4; record D6): "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`". There is no read-only mode in v1.
- [ ] An unknown wire name, a missing field or a wrong type is a typed decode error, never a silently defaulted value.
- [ ] A mutation check: change a field's type in one record, and the root's contract test fails.

## 3. Design
Apply the "schema from type hints" shape (P5; DERISK §4.5): the codec reads the dataclass fields and their annotations, with explicit wire names for unions. The spike (`wire.py`, outside the repository, DERISK §1.2) is the starting point. The codec lives in a technical support package; the wire names live with the contract types, so renaming a class does not change the link. The per-bot revision that De-risk R5 asks for (DERISK §5.4) belongs in each bot's record and the codec only carries it; the task checks at start whether the record has one today and, if not, adds it with a version-tolerant file codec.

## 3a. Reuse
`.claude/rules/capabilities.md` and `grid_ladder_payload.py` (which already serialises one record to JSON) checked; `used` as the pattern for the first root, `not used because …` if its shape differs. `host_command_codec.py` and `health_snapshot.py`: `used` for the `schema` naming convention only.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/…` (a wire package, name chosen at start) | the codec, the handshake, the revision rule |
| `src/modules/*/contracts/…` | wire names on the roots and unions |
| `tests/unit/…` | one contract test per root; the handshake and revision tests; the guard for a root without a test |

## 5. Testing
Tier: unit, then the full gate. The contract tests carry the codec criteria; the handshake and revision criteria have their own tests; the mutation check is run by hand and recorded. Not run.

## 6. Docs touched
`Docs/MODULES/<module>/` for each module whose contracts gain wire names, if it has a folder; the wire protocol's page is written by [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md).

## Implementation notes (written when done)
Not written: not started.
