# High-Level Design — Sagittarius Elite Warrior

- **Status:** 🟢 Round 1 approved on 2026-09-11. The decision record is
  [`EPIC-025/DECISION_2026-09-11_module_boundaries.md`](../../Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-11_module_boundaries.md).
  Round 2 is still open on two points: the schema of each contribution point (§4, question O1) and
  the concrete Engine API (§5, question O2).
- **What this document is for.** It is the *north star*: the one place that answers "which modules
  exist, where their boundaries are, by what criteria, and what their APIs look like". Tasks, epics
  and bug reports **reference** it; they do not repeat it. When the code and this document disagree,
  one of them is wrong, and the pull request that discovers the disagreement fixes it. Drift is not
  allowed to survive a sprint.
- **Where it comes from.** [`PRO-004`](../../Tasks/proposal/PRO-004.md) holds the evidence and the
  argument; the ADR holds the decisions; this document holds the design. Diagrams:
  [`as_is.puml`](../../Tasks/proposal/PRO-004_assets/as_is.puml) and
  [`to_be.puml`](../../Tasks/proposal/PRO-004_assets/to_be.puml).
- **Language.** English, in the register of a self-study technical book (`ONBOARDING.md` §10).
- **Terms.** Every term this document uses is defined once, in
  [`Docs/VOCABULARY/README.md`](../VOCABULARY/README.md); look there first when a word is unfamiliar.

## How to read this document: five questions, five tools

The user framed the problem as three questions. The investigation showed there are really five,
and that each one already has a well-known tool with a name and a large body of precedent. Nothing
in this design is invented; the work is choosing the right tool for each question and showing,
with measurements from this codebase, why it fits.

| # | Question | Tool | Origin | Answered in |
| :-: | :--- | :--- | :--- | :--- |
| 1 | **Where do we cut?** | Bounded Context, with the Aggregate as the cutting criterion; Distillation into Core / Supporting / Generic | Strategic DDD (Evans) | [§1](01_cut_criteria.md), [§2](02_context_map.md) |
| 2 | **How do the pieces talk to each other?** | Context Map patterns: Customer/Supplier, Open Host Service with a Published Language, Anticorruption Layer | Strategic DDD | [§2](02_context_map.md), [§3](03_module_contracts.md) |
| 3 | **How is each piece organised inside?** | Clean Architecture (`domain` / `application` / `adapters` / `ui`), where a Port is an abstract base class | Robert Martin | [§3](03_module_contracts.md) |
| 4 | **How do we plug in pieces without knowing their number in advance?** | Microkernel plus the Dependency Inversion Principle: the Engine's `IExtension`, Martin's "Main" component as `shell/`, VS Code-style contribution points | Microkernel pattern; the VS Code extension model | [§3.1](03_module_contracts.md), [§4](04_surfaces_and_contribution_points.md), [§5](05_engine_app_split.md) |
| 5 | **How do we keep it from rotting, and get there without stopping the app?** | Architecture fitness functions (AST guards with a shrink-only allowlist); Strangler Fig with a Walking Skeleton | Ford, Parsons & Kua; Fowler | [§6](06_enforcement_and_migration.md) |

## Contents

1. [Criteria for cutting a module (C1–C6), applied to this application](01_cut_criteria.md)
2. [Context map: four bounded contexts, four support packages, a kernel; distillation; integration patterns; the Published Language](02_context_map.md)
3. [Module contracts: `BoundedContextModule`, the internal layout, each module's contracts, the mapping from today's code](03_module_contracts.md)
4. [Surfaces and contribution points: Trading, Dev Board (`dev_probe`), Settings, CLI — and §4.6, the workbench rule for where a new module's UI goes](04_surfaces_and_contribution_points.md)
5. [Engine owns mechanism, application owns policy: the split with `EPIC-001D`](05_engine_app_split.md)
6. [Enforcement and migration: three guards, the allowlist ratchet, six phases](06_enforcement_and_migration.md)
7. [Build or buy: what already exists for each thing we plan to build (survey 2026-09-12)](07_build_vs_buy.md)
8. [The Engine track: what the Engine gets, when, and by what criterion a piece moves there](08_engine_track.md)
9. [What happens to the tests: move, rewrite, delete, retarget — per phase, with the safety net](09_test_migration.md)
10. [The test philosophy for the module architecture: what each layer proves, and how — contract suites and verified fakes](10_test_strategy.md)
11. [The desktop workbench: QtWidgets only, the OS theme, panels and dialogs instead of cards — how the places are rendered](11_desktop_workbench.md)

## Diagrams (PlantUML sources; syntax-checked)

| # | File | Shows |
| :-: | :--- | :--- |
| HLD-01a | [`diagrams/hld-01a_layer_map.puml`](diagrams/hld-01a_layer_map.puml) | **Package diagram**, high view — the five layers and every `«import»` / `«access»` dependency between them (§2) |
| HLD-01b | [`diagrams/hld-01b_module_dependencies.puml`](diagrams/hld-01b_module_dependencies.puml) | **Component diagram**, detail — each module's provided interfaces (lollipops) and the `«use»` dependency of every consumer, annotated with Evans' pattern per pair (§2.3) |
| HLD-02a | [`diagrams/hld-02a_module_layers.puml`](diagrams/hld-02a_module_layers.puml) | **Package diagram**, high view — the dependency rule between a module's five packages, with the `{forbidden}` constraint on `ui → adapters` (§3.2) |
| HLD-02b | [`diagrams/hld-02b_module_internals.puml`](diagrams/hld-02b_module_internals.puml) | **Package diagram**, detail — each layer's contents and the outside packages it may import (§3.2, §3.3) |
| HLD-03a | [`diagrams/hld-03a_place_vocabulary.puml`](diagrams/hld-03a_place_vocabulary.puml) | **Class diagram**, high view — the `Place` and `SizeHint` enumerations, `ContributionDescriptor`, `Surface`, and the constraints binding them (§4.6.1) |
| HLD-03b | [`diagrams/hld-03b_contribution_matrix.puml`](diagrams/hld-03b_contribution_matrix.puml) | **Object diagram**, detail — every contribution in the application as an instance specification with its slot values, grouped by `surface_id` (§4.6.2, §4.6.4) |
| HLD-04a | [`diagrams/hld-04a_engine_track_zones.puml`](diagrams/hld-04a_engine_track_zones.puml) | **Package diagram**, high view — the Engine, the lift-ready staging area and the policy that never moves, joined by `«trace»` (§8.1–8.3) |
| HLD-04b | [`diagrams/hld-04b_engine_track_schedule.puml`](diagrams/hld-04b_engine_track_schedule.puml) | **Package diagram**, detail — every element and the `«trace»` that lifts it, tagged with its step E0–E3 (§8.4) |
| HLD-05a | [`diagrams/hld-05a_window_containment.puml`](diagrams/hld-05a_window_containment.puml) | **Class diagram**, high view — `MainWindow` and its parts by composition, the `Surface` hierarchy, and the registry each part consults (§4) |
| HLD-05b | [`diagrams/hld-05b_trading_devboard_slots.puml`](diagrams/hld-05b_trading_devboard_slots.puml) | **Object diagram**, detail — Trading and Dev Board widget by widget, coloured by owning module, with a link on every same-factory pair (§4.5) |
| as-is / to-be | [`../../Tasks/proposal/PRO-004_assets/`](../../Tasks/proposal/PRO-004_assets/) | The measured current structure and the target structure (from `PRO-004`) |

Each numbered diagram comes in two views: **`a` is the high view** — the shape of the thing, small
enough to hold in your head — and **`b` is the detail view**, which answers "and concretely, which
one?" for the same subject. Read `a` first; open `b` only when you need the names. A diagram that
tried to be both was unreadable, which is why the pair exists.

**Every diagram is a named UML diagram kind, drawn in that kind's own notation** — package,
component, class or object — and its title says which. That is not decoration: it fixes what each
symbol means, so a reader can check the picture against UML rather than against a private
convention of this repository. A dashed open arrow is a UML dependency and carries a keyword
(`«import»`, `«access»`, `«use»`, `«trace»`); a filled diamond is composition; a hollow triangle is
generalisation; a lollipop is a provided interface and a socket a required one; braces mark a UML
constraint, as in `{forbidden}` and `{gated by dev.mode}`. Free-form boxes with prose inside them
are **not** used — explanation belongs in a note, which is itself a UML element.

The class, sequence and state diagrams of the Phase 0 design are in the
[SDD](../SDD/README.md).

## Reading conventions

| Mark | Meaning |
| :--- | :--- |
| ✅ | Exists in the code today (cited as `file:line`); the design **reuses** it |
| 🔵 | New design, not yet implemented |
| ❓ | Open; the phase it blocks is named alongside |
| ⚠️ | A place that is easy to get wrong, and where this repository has already paid for the mistake once |
