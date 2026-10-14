# ADR — Documents answer one reader's question in one place, are linked both ways to the rule and the guard that hold them, and the process records the data to judge itself

**Epic:** [EPIC-041](README.md)
**Date:** 2026-10-14
**Status:** Accepted
**Decided by:** the owner. The coordinator proposed an assessment of an arc42 / C4 / ADR / SBOM suggestion. The owner then set four points: *"doc phải liên kết với rule"* (docs must be linked to the rules); *"Có tạo thư mục mới Docs/ARCHITECTURE, Docs/MODULES, Docs/DECISIONS. PlantUML cho sơ đồ kiến trúc. SBOM: để sau"* (create the new folders, use PlantUML, defer SBOM); a data section for system-thinking analysis; and *"tạo EPIC-041 ngay"* (create EPIC-041 now).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
✅ Measured on `850aef4`:
- **Two homes for the same design.** `Docs/` has nine areas. Module contracts are written twice (`Docs/HLD/03_module_contracts.md`, `Docs/SDD/05_module_contracts.md`). Diagrams live in two places with two notations (mermaid in `Docs/Diagrams/`, PlantUML in `Docs/HLD/diagrams/` and `Docs/SDD/diagrams/`). Two files say they are superseded; others carry no status at all.
- **No index of decisions.** The 24 `DECISION_*.md` records sit in their epic folders, beside 9 proposals and 5 epic `DESIGN_*.md` files.
- **Docs and rules not linked.** No rule under `.claude/rules/` cites `Docs/HLD` or `Docs/SDD`. 19 docs cite rules, and nothing checks those citations. The rule tree itself is checked by `scripts/rule_integrity/`: its `§` citations, quotes and paths.
- **No data about the process.** 213 bug reports carry free-text `Reported`, `Severity` and `Context` fields only. Nothing records which test layer found a bug, which nets it escaped, or whether the owner or live trading found it.
- **Already held by machine:** module and layer dependency direction (`tests/unit/architecture/boundaries/`, `test_module_boundaries.py`, `test_module_layers_point_inward.py`), the SPEC and case-study indexes, and dependency pins (`tests/unit/scripts/test_dependency_pins.py`).

The suggestion assessed was: arc42 at app level, C4 context and container views, a central ADR folder, per-module design docs, crosscutting concepts written once, a hand-kept third-party register with an SBOM, a threat model, and build/release docs.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Doc ↔ rule ↔ guard.** A doc states why and what shape. A rule states what must be done. A guard or gate holds the rule. A normative statement in a doc cites the rule clause that holds it, and never restates it. A rule clause that encodes a design choice carries a `Why:` link to the doc or decision that explains it. `scripts/rule_integrity/` checks both directions, so changing one side without the other turns CI red | Accepted | 🟢 the owner (*"doc phải liên kết với rule"*) | A change to the system's shape touches all three corners in one PR (`041B`) |
| D2 | **One fact, one place.** Detail lives at the lowest level that owns it: code, then the module doc, then the app doc. Upper levels summarise and link. Rules are cited, never copied into `Docs/` | Accepted | 🤖 agent, under CONSTITUTION P3 (a copy drifts) | Removes the duplicate contracts and diagrams (`041D`, `041I`) |
| D3 | **Two levels.** The app is the system and a module is a component. App docs live in `Docs/ARCHITECTURE/` (arc42-lite: context, module map, runtime, deployment, crosscutting, quality and risks, security, dependencies). Module docs live in `Docs/MODULES/<module>.md`, never inside `src/`. Files are named by the reader's question, not by arc42 section numbers | Accepted | 🟢 the owner (folders) · 🤖 agent (naming) | A stable layout; arc42 sections that have no content are left out |
| D4 | **The machine keeps what it can.** Indexes, dependency registers, FSM diagrams and quality data are generated and guarded. Hand-written text is kept for reasons and trade-offs | Accepted | 🤖 agent, under P1 | Generators: `041C`, `041E`, `041F`, `041H` |
| D5 | **Three kinds of document, three lifecycles.** *Descriptions* are true of `master` and change in the PR that changes the code. *Decisions* are immutable once accepted; a new record supersedes them. *Operations* docs are true of what runs on the VPS and are tested where possible (`test_headless_runbook.py`) | Accepted | 🤖 agent | Reviewers know which docs a PR must touch |
| D6 | **Every doc has a status:** `Current`, `Superseded by <link>` or `Historical`. A doc that is no longer true is marked or removed, never left silent | Accepted | 🤖 agent | `041A` |
| D7 | **Thin first.** A section with nothing to say is left out, never filled with "N/A". A doc starts by naming its reader and the question it answers | Accepted | 🤖 agent | Smaller docs that grow when a real question appears |
| D8 | **Notation.** PlantUML for architecture diagrams. Mermaid only for short diagrams in tasks and epics. Each diagram answers one question and names its source | Accepted | 🟢 the owner (*"PlantUML cho sơ đồ kiến trúc"*) | The `Docs/Diagrams/` mermaid notes become `Historical` (`041I`) |
| D9 | **Process data for system thinking.** From now on every bug report records a closed vocabulary: `Detected by` (unit, integration, sanity, e2e, CI gate, reviewer, author self-test, owner field test, live trading, scheduled audit), `Introduced in`, `Phase introduced` (design, code, config, dependency, engine), `Phase detected` (dev, PR, post-merge, testnet, mainnet), `Escaped nets`, `User-visible`, `Money at risk`, and the fix PR. Existing reports are backfilled by script with `Unknown` where nothing can be derived; values are never guessed. A generated report and a data dictionary live in `Docs/METRICS/`. The data to collect next is listed with its source before it is needed: review rounds and findings per PR, flaky reruns, surviving mutants, host resources, bot halts, task lead time. `process-drift` reads the report, and its findings become decisions | Accepted | 🟢 the owner (the data request) · 🤖 agent (fields) | `041F`; process changes argued from numbers |
| D10 | **Supply chain.** The dependency register is generated from `requirements.lock`, with a hand-kept "why" for the main libraries only. `pip-audit` and a licence allowlist run in CI. SBOM is deferred | Accepted | 🟢 the owner (*"SBOM: để sau"*) · 🤖 agent (audit) | `041H`, which waits for the owner's approval because it changes the workflow |

## 3. Alternatives considered
- **A new lowercase `docs/` tree with arc42-numbered files.** Rejected: moving everything breaks every `file:line` citation the checker holds, and arc42's numbers lose meaning once unused sections are dropped.
- **Moving the 24 decisions into one ADR folder.** Rejected: rules, tasks and docs cite them where they are. A generated index gives one entry point without moving anything (the approach CPython and Kubernetes docs take for their enhancement records).
- **A hand-kept third-party register.** Rejected: it drifts from the lock file by construction (P3).
- **Crosscutting concepts as prose.** Rejected: that would be a second rulebook beside `.claude/rules/`. Crosscutting is a table that joins topic, rule, guard and reason (D1).
- **SBOM now.** Deferred by the owner. The app is not distributed, so an audit and a licence check give the safety value at a fraction of the cost.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Approve the CI change for `pip-audit` and the licence check | `041H` | 2026-10-14 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-041B](incomplete/EPIC-041B_doc_rule_links_checked_both_ways.md) | Not started | Not yet verified |
| D2, D3, D8 | [EPIC-041D](incomplete/EPIC-041D_app_context_and_module_map.md), [EPIC-041E](incomplete/EPIC-041E_bots_module_doc.md), [EPIC-041G](incomplete/EPIC-041G_runtime_crosscutting_security_quality.md), [EPIC-041I](incomplete/EPIC-041I_retire_hld_sdd_and_guard_vocabulary.md) | Not started | Not yet verified |
| D4 | [EPIC-041C](incomplete/EPIC-041C_decisions_index.md), 041E, 041F, 041H | Not started | Not yet verified |
| D5, D6, D7 | [EPIC-041A](incomplete/EPIC-041A_docs_map_and_status.md) | Not started | Not yet verified |
| D9 | [EPIC-041F](incomplete/EPIC-041F_quality_metrics_data.md) | Not started | Not yet verified |
| D10 | [EPIC-041H](incomplete/EPIC-041H_dependency_register_audit_licences.md) | Waiting for O1 | Not yet verified |
