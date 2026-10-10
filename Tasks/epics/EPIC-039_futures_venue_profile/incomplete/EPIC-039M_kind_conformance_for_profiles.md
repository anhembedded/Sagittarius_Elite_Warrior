# EPIC-039M — Any bot kind declares the profiles it supports and a conformance suite checks it; the next kind gets Futures by declaration

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10: *"mục tiêu là tôi muốn thêm bot nào cũng sẽ có phần future vs spot"* (the goal is that every bot added has a Futures and a Spot part).
**Risk:** 🟢 — tests and a recipe; the risk is a suite too weak to catch a kind that bypasses the ports
**Complexity:** S–M — a parametrised suite, a kind checklist in the `IBotKind` docstring, one proof with a second kind
**Epic:** [EPIC-039](../README.md)
**SPEC:** none.
**Design:** [DESIGN §2, §11](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** D1
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md) (`supported_profiles`), [039H](EPIC-039H_futures_grid_long.md) (a kind that actually runs on both). Coordinates with [`EPIC-029L`](../../EPIC-029_bots_tab_grid_fast_track/incomplete/EPIC-029L_signal_and_dca_kinds.md) (Signal and DCA kinds) and [`EPIC-037`](../../EPIC-037_ai_development_leverage_points/README.md) (the capability catalog: the shared ports are listed there once 037A exists).

---

## 1. Context and problem
The seam is only real if a *new* kind gets both profiles by implementing a small checklist, and a kind that skips the ports (calls `trading` directly, branches on the market, keeps its own exposure) fails CI. `IBotKind`'s docstring has listed "Futures Grid" as an extension case since `EPIC-029B`; the other listed cases are Signal, DCA and Trailing Grid (`EPIC-029L`).

### Facts verified on `master-warrior` `076d339`
- `bots/contracts/i_bot_kind.py`: `kind_id`, `validate(inputs) -> tuple[Verdict, …]`, `overlay(inputs)`, `executor_factory()`; extension cases listed in its docstring; the registry `application/services/bot_kind_catalog.py` (`IBotKindCatalog`, `GRID_KIND_ID`).
- Contract-test pattern for ports with several implementers: `src/modules/bots/contracts/testing/` and `tests/integration/modules/bots/contracts/` (a shared suite per port).
- After 039A each kind declares `supported_profiles`; 039H makes `GridKind` support both.

## 2. Acceptance criteria
- [ ] A **kind conformance suite** (`tests/…/contracts/`, parametrised over every kind in the catalog × every profile it declares) asserts: `validate` never raises and returns verdicts through `IRiskGuard`/`ICostModel` for a Futures profile (a kind that never consults the guard on a leveraged plan fails); the kind's executor obtains exposure only through `IExposureBook`, orders only through the bot order gateway, settings only through `IVenueSettingsGate`; a plan outside the profile's directions is refused; a Spot-only kind (declaring only `SPOT`) is **not offered** a Futures venue by the picker.
- [ ] The architecture guard of 039A is extended to the *whole kind package*, not only the files existing then: a new kind's directory is scanned automatically (discovery from the catalog, not a hand-kept list; a test fails if a kind's package is not scanned — the `test_every_*_is_listed` pattern the repo already uses).
- [ ] `IBotKind`'s docstring gains a **"Adding a kind: Spot and Futures"** recipe (≤ 20 lines): declare profiles, which ports to use for what, the three tests the suite will run, the pitfalls; the extension cases list now reads "Futures Grid — done (`EPIC-039`)".
- [ ] **One proof with a second kind.** A minimal second kind (a test double, `DcaLikeKind`, in the test tree only, ~60 lines: a fixed-size periodic buyer) passes the conformance suite for both profiles with **no change to the shell, the store, the lifecycle or the shared ports**; if it needs one, the seam is wrong and the task reports which. (The real `EPIC-029L` kinds are not built here.)
- [ ] The capability catalog of `EPIC-037A` (if it exists by then) lists the shared ports with "use this instead of …"; if not, the recipe above is the only place and `037A` is told.

## 3. Design
Open/closed made executable: a kind is added by implementing `IBotKind` and registering it; the suite is the contract (Liskov for every profile a kind declares). The test double keeps the proof honest without anticipating `029L`'s design.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/contracts/testing/` and `tests/integration/modules/bots/contracts/test_kind_conformance.py` (new) | the suite |
| `tests/unit/architecture/test_bots_decide_the_market_in_one_place.py` | discovery of kind packages |
| `bots/contracts/i_bot_kind.py` | the recipe in the docstring |
| `tests/…/dca_like_kind.py` (new, test tree only) | the second kind |

## 5. Testing
Tier: contract/integration.
- `test_every_registered_kind_passes_the_conformance_suite_for_every_profile_it_declares`
- `test_a_kind_that_branches_on_the_market_fails_the_guard` (mutation)
- `test_a_second_kind_gets_both_profiles_with_no_change_to_shared_code`
- `test_a_spot_only_kind_is_not_offered_futures_venues`
Not run yet.

## Pitfalls
- The suite must fail for a kind that *bypasses* a port (mutation test: a double that calls the order submission directly), or it proves nothing.
- Do not build `EPIC-029L`'s kinds here; the double is a test fixture.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: check `EPIC-029L`'s state and whether `EPIC-037A` exists; then write the mutation test (a kind that bypasses `IExposureBook`) red.
