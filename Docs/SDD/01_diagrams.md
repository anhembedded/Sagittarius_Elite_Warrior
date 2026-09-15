# SDD §1 — The diagrams, and what each one is the authority on

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

## Diagrams

| # | File | Specifies |
| :-: | :--- | :--- |
| SDD-01a | [`diagrams/sdd-01a_module_contract_shape.puml`](diagrams/sdd-01a_module_contract_shape.puml) | **Class diagram**, high view — who owns what across the Engine, `core/contracts`, the shell and the first module, and the three seams a module author touches: `IExtension`, `contribute()`, `subscribe()` |
| SDD-01b | [`diagrams/sdd-01b_module_contract_members.puml`](diagrams/sdd-01b_module_contract_members.puml) | **Class diagram**, detail — every field and signature: `BoundedContextModule`, `IContributionRegistry`, `ContributionDescriptor`, `ScreenContribution`, `Place`, `SizeHint`, and the shell's `ModuleList`, `ContributionRegistry`, `Surface`, `DoubleClaimCheck` |
| SDD-02a | [`diagrams/sdd-02a_boot_phases.puml`](diagrams/sdd-02a_boot_phases.puml) | **Sequence diagram**, high view — the seven steps of the boot procedure, and why they are in that order |
| SDD-02b | [`diagrams/sdd-02b_boot_sequence.puml`](diagrams/sdd-02b_boot_sequence.puml) | **Sequence diagram**, detail — boot call by call: config read once, `QApplication` before `boot()`, `register()` with no `resolve()`, the double-claim check, `contribute()` / `subscribe()`, the `dev.mode` gate, the first surface |
| SDD-03 | [`diagrams/sdd-03_contribution_render.puml`](diagrams/sdd-03_contribution_render.puml) | **Sequence diagram** — how a surface renders a place; one factory contributed to two surfaces yields two independent panel instances (each with its own Presenter and Coordinator), sharing only the module's feed |
| SDD-04a | [`diagrams/sdd-04a_order_path.puml`](diagrams/sdd-04a_order_path.puml) | **Sequence diagram**, high view — a tick becoming an order in six messages, and the one guard on the path |
| SDD-04b | [`diagrams/sdd-04b_order_flow_sequence.puml`](diagrams/sdd-04b_order_flow_sequence.puml) | **Sequence diagram**, detail — the same path call by call across `market_data → strategy → trading → gateway → exchange → trading feed → surfaces`, and the symbol lease refusing a manual order |
| SDD-05 | [`diagrams/sdd-05_dev_mode_state.puml`](diagrams/sdd-05_dev_mode_state.puml) | **State machine diagram** — `dev.mode` read once at boot; the Welcome switch writes `user_config.json`; restart applies it (ADR D14) |
| SDD-06a | [`diagrams/sdd-06a_market_data_ports.puml`](diagrams/sdd-06a_market_data_ports.puml) | **Class diagram**, high view — the Walking Skeleton's five ports and which bounded context requires each |
| SDD-06b | [`diagrams/sdd-06b_market_data_contracts.puml`](diagrams/sdd-06b_market_data_contracts.puml) | **Class diagram**, detail — every signature, the two DTOs, the two signals, and the implementing service behind each port |

Each numbered diagram comes in two views where the subject warranted it: **`a` is the high view**
and **`b` is the detail view** of the same thing; read `a` first. SDD-03 and SDD-05 are single
diagrams because they are already at high-view density.

**Every diagram is a named UML diagram kind — class, sequence or state machine — and its title says
which**, so each symbol has a defined meaning rather than a private one. The same convention holds
for the HLD diagrams, and it is stated in full in [`../HLD/README.md`](../HLD/README.md).

The HLD-level diagrams live next to the HLD: [`../HLD/diagrams/`](../HLD/diagrams/) (context map,
inside a module, the workbench places, the Engine track).

