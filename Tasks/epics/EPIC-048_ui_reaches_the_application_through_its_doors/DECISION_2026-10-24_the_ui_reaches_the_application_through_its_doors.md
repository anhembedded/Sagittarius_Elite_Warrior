# ADR — The UI reaches the application only through the command dispatcher and bus events, held by a guard that only shrinks

**Epic:** [EPIC-048](README.md)
**Date:** 2026-10-24
**Status:** Accepted
**Decided by:** the owner's delegation of 2026-10-24, through the coordinating session: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* (translated: "decide them for me, consistent with the whole Constitution"). Settled as G9 of the [EPIC-047 charter](../EPIC-047_vps_bots_tab/CHARTER.md) §4 (v0.3 asked it, v0.4 decided it, v0.5 set its baseline from the De-risk measurement). The Constitution check is §2a. The owner may veto any row.
**Supersedes / superseded by (optional):** none

| Label | Meaning |
| :--- | :--- |
| ✅ Established | measured on the code tree at `5ddbd68` ([`DERISK.md`](../EPIC-047_vps_bots_tab/DERISK.md) R7, §8); a point-in-time record, cited by section |
| 🤖 Agent decision | delegated by the owner and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The Bots screen of EPIC-047's second tab must run on a remote backend. That is possible only if the screen reaches the application through one narrow interface, which a remote adapter can stand behind. Discover's Finding E found that the UI reaches the application around the dispatcher and the bus. De-risk R7 measured how far, on every screen, not only on Bots.

**Established facts** (`5ddbd68`, DERISK §7.3, method §7.2):

- ✅ **215 imports in 82 files** under `src/modules/*/ui/` reach application services, application internals, adapters or behavioural ports outside the allowlist, spread over **18 screen areas**. 103 are ports, 82 are application internals, 28 are application services and 2 are adapter imports.
- ✅ **30 functions under `ui/` take the whole `IContainer`**: ten presenters and twenty factories and resolvers. `ScreenDescriptor.presenter_class` fixes the signature `(BaseView, IContainer)` (`screen_descriptor.py`).
- ✅ Of the 110 application imports, 78 are data (results, words, enums, constants) and 32 are computation the UI runs.
- ✅ `bots/ui/bots_screen` alone holds 45 of the 215: 24 application-service imports (10 of them computation), 17 port imports and the one plan file the screen writes itself (`plan_export_flow.py`).
- ✅ R1 rendered the Bots detail through the dispatcher alone with no visible change (DERISK §1.3, §8.2). R1 and §8.1 name what stands in the way and its target; the last proof is this epic's own work.
- ✅ Ports that are code, not host data, add 18 to the count: `IBotKind` and `IBotKindCatalog` (12 hits) are the kinds' judges and editors, identical on both sides of a link by R6; `ICandleFeed` (6 hits) is public market data the charter keeps local (DERISK §7.4).

**Forces.** A guard must not fail the build on 215 existing imports, and must not let a 216th in (P8). The same guard must cover every screen, because the debt is on every screen (P6). The rule must not move computation to the host, because the Plan re-judges 150 ms after each keystroke (`presenter_pacing.py:23`, `REJUDGE_MS`) and a re-judge over a slow link is not acceptable (DERISK §1.5).

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The rule.** A file under `src/modules/*/ui/` reaches the application through the command dispatcher (`ICommandDispatcher`) and the bus (`IEventPublisher`, `IEventBus`), and through the UI-only allowlist: `INotifier`, `IRealMoneyConsent`, `IThreadManager`, `IInstanceAccess`, `IDisplayTimezonePreference`, `IDisplayPreferences`. It imports no application service, application internal, adapter or behavioural port outside that list. The rule text goes into `.claude/rules/architecture-rule.md` in [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md). | Accepted | Agent, owner's delegation | One door for a local and a remote backend (EPIC-047 G6). Cost: a screen that read a port directly now sends a query. |
| D2 | **Pure-code ports join the allowlist.** `IBotKind`, `IBotKindCatalog` and `ICandleFeed` are code or public data, not host facts, so a screen may hold them. | Accepted | Agent, owner's delegation | DERISK §7.4 question 1. The Bots screen's port imports fall from 17 to 8 and the baseline by 18. The cost: a kind's judge and editor stay local, which R6's same-build handshake makes safe. |
| D3 | **The guard.** A test in `tests/unit/architecture/` reads the UI tree with the method of DERISK §7.2 (`ast` plus `importlib`; the classes `APP_SERVICE`, `APP_OTHER`, `ADAPTER`, `PORT`; `fn` against `data`; functions with an `IContainer` parameter) and compares each count with a committed baseline. A count may fall and never rise; a lowered count rewrites the baseline in the same pull request. The guard's first count starts from R7's **215 imports, 82 files, 30 container-taking functions**; admitting D2's three ports removes the 18 imports DERISK §7.4 counts, so the first measurement should read 197. EPIC-048A measures it and writes the number. | Accepted | Agent, owner's delegation | P1 and P8 in one file: a mechanism, not prose, and a ratchet. It mirrors the repository's existing baseline guards (`tests/unit/architecture/baseline_*.txt`, `test_module_boundaries.py`). |
| D4 | **What the rule forbids first.** The guard fails on any new `fn`, port or adapter import and counts `data` imports (78) as a second baseline line that also only falls. Data comes last: a result type or an enum is not computation. | Accepted | Agent, owner's delegation | DERISK §7.4 question 2. The ratchet bites where computation and host reads are, and the data ratchet follows without blocking EPIC-047. |
| D5 | **Computation leaves the presenter for the application layer.** The pure assessment (`detail_for`, `assess_readiness`, `assess_resume`, `field_verdicts`, `occupancy_of`, `account_view_of`, `state_words`, `failure_cause`) becomes a pure read-model builder in the application layer. It still **runs on the desktop**, over read models the screen holds. | Accepted | Agent, owner's delegation | Same wording as EPIC-047 G6. The 150 ms re-judge reads no host. Two new queries carry the host facts the screen now reads by hand: `GetBotRunFactsQuery` and `GetVenueChoicesQuery` ([EPIC-048B](incomplete/EPIC-048B_the_bots_screen_through_the_doors.md)). |
| D6 | **A narrow gateway, not the container.** A presenter receives a small application gateway for its screen instead of `IContainer`. The 30 functions of §1 stop taking the container. | Accepted | Agent, owner's delegation | The remote backend of EPIC-047 is one more gateway. The cost: the `ScreenDescriptor.presenter_class` signature changes ([EPIC-048C](incomplete/EPIC-048C_presenters_receive_a_narrow_gateway.md)). |
| D7 | **Order of work and the gate for EPIC-047.** EPIC-048A (rule, guard), then EPIC-048B (the Bots screen) and EPIC-048C. [EPIC-047](../EPIC-047_vps_bots_tab/README.md) code starts once the guard holds for the Bots screen: **048A and 048B done**. 048C and 048D run beside EPIC-047 and may finish after it. | Accepted | Agent, owner's delegation | EPIC-047 depends on 048A and 048B only. Cost: the other screens wait for 048D; EPIC-047 does not. |

<!-- The labels above qualify evidence and attribution in the prose; they are not implementation states. -->

## 2a. Constitution check (a default decision only)

The decisions were taken on the owner's delegation, which carries the Constitution check as its condition; every row is checked below against the evidence of §1.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D3: the guard test fails on a new import; the rule text alone would be memory. |
| P2 Verify, don't restate | ✅ | Every number is R7's measurement at `5ddbd68` with its method (§7.2); 048A re-measures and writes the first baseline, and the "197" of D3 is stated as an expectation, not a fact. |
| P3 A copy drifts | ✅ | D5 moves the assessment to one place used by the Bots tab and, later, the remote tab; D1 names the allowlist once, in `architecture-rule.md`, and the guard reads it from there. |
| P4 Green proves only what was tested | ✅ | The guard counts the real UI tree, and each child's acceptance names a positive check. R1 rendered the Bots detail through the dispatcher alone before this record was written. |
| P5 Apply before you invent | ✅ | Ports and adapters with an application gateway (hexagonal architecture); the CQRS dispatcher the repository already has; the baseline-guard shape the repository already uses. No new machinery. |
| P6 Fix the mechanism | ✅ | D1 and D3 cover all 18 screen areas, not the Bots screen only; the debt is on every screen (DERISK §7.4). |
| P7 Seam now, variant later | ✅ | D6 builds the gateway seam; a remote gateway is EPIC-047's variant. D4 leaves `data` imports to a later ratchet. |
| P8 Ratchets only fall | ✅ | D3: counts and baseline can only fall; no existing guard is loosened. |
| P9 Decide alone | ✅ | Decided under the owner's delegation; the only open item (O1) is a technical choice for 048C. |
| P10 Pyramid and units | ✅ | Conclusion first in the title; counts carry their unit (imports, files, functions, areas) and their commit. |
| P11 Prompt-grade artifacts | ✅ | Each decision names the file or test that holds it; the children carry acceptance criteria. |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | This record and its epic touch no `src/` code, no requirements file, no setting, no Engine file. Later code moves queries and presenters; each child is its own pull request and reverts alone. 048B changes where a pure function runs, not what it returns (A7 proof: the Bots screen renders the same). |

## 3. Alternatives considered

- **Do it inside EPIC-047 (the charter's other option).** Lost: 170 of the 215 imports are outside the Bots screen (`bots/ui/bots_screen` holds 45), so the mechanism would be paid for twice and EPIC-047 would carry unrelated children (P6). The remote tab needs only 048A and 048B, which D7 gates it on.
- **Fix the Bots screen only.** Lost: it clears EPIC-047's path and leaves 170 imports (215 less the Bots screen's 45) free to grow; a local patch (P6).
- **A rule in prose, no guard.** Lost: the repository has paid for rules that drifted (`CLAUDE.md`); P1 asks for a barrier.
- **A dependency-linting tool such as import-linter.** Lost on P5's order: a sound repo mechanism comes first. The repository already has the AST guards and baseline files of `tests/unit/architecture/`, and the check here needs the classification of §1 (port against data, function against constant), which a generic contract does not give. It would also add a dependency.
- **Move the computation to the host (the literal reading of G6 in charter v0.4).** Lost: R1, DERISK §1.5. Each edit would become an SSH round trip.

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | One gateway per screen, or one per module? A technical choice for 048C's own design under P9, not an owner question; recorded here so 048C answers it before it edits a presenter. | 048C | 2026-10-24 |

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md) | Done (2026-10-24) | `architecture-rule.md` §3.1; `test_ui_reaches_the_application_through_its_doors.py`. `IDisplayTimezonePreference` and `IDisplayPreferences` name no class and are not on the line (048A notes) |
| D2 | [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md) | Done (2026-10-24) | the allowlist line of §3.1; the baseline falls by 18 to 197 |
| D3 | [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md) | Done (2026-10-24) | `baseline_ui_doors.json`, measured at `96cb27c`: 197 imports, 73 files, 30 container-taking functions; mutation checks in 048A |
| D4 | [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md), [EPIC-048D](incomplete/EPIC-048D_the_other_screens_cut_down_to_the_baseline.md) | Started: the `application_data` section of the baseline (78) | 048D clears it |
| D5 | [EPIC-048B](incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) | Not started | Not yet verified |
| D6 | [EPIC-048C](incomplete/EPIC-048C_presenters_receive_a_narrow_gateway.md) | Not started | Not yet verified |
| D7 | [EPIC-048A](completed/EPIC-048A_the_doors_rule_and_its_guard.md) and [EPIC-048B](incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) | Not started | Not yet verified |
