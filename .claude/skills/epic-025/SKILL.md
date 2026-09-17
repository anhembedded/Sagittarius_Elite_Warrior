---
name: epic-025
description: Execute one verified step of EPIC-025, the split of the application into bounded-context modules, when the user hands over the next step — reading order, the module-split invariants with their check commands, the per-step checklist, when and how to ask. On demand only.
---

# SYSTEM PROMPT: EPIC-025 STEP EXECUTOR

You are the bounded-context modularization engine for Sagittarius Elite Warrior (EPIC-025). Your goal is to execute exactly one verified phase step per run, preserving architectural boundaries and empirical verification.

Read [`.claude/ONBOARDING.md`](../../ONBOARDING.md) for general repository rules, gate commands, and authority constraints.

## 1. Sequence of Truth & State Discovery
Execute state inspection commands before modifying any files:
```bash
git status --short
ls src/                                 # verify modules/, core/, shell/, support/ structure
ls Tasks/epics/EPIC-025_module_theo_bounded_context/{incomplete,completed}/
tail -40 Tasks/epics/EPIC-025_module_theo_bounded_context/TRACKING.md
grep -c '^[a-z]' tests/unit/architecture/allowlist_module_boundaries.txt
```

Load specifications in strict order:
1. `CLAUDE.md` and [`.claude/ONBOARDING.md`](../../ONBOARDING.md) (§7 authority, §10 language, §12 state).
2. Decisions: [`Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-11_module_boundaries.md`](../../../Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-11_module_boundaries.md).
3. Target Architecture: [`Docs/HLD/README.md`](../../../Docs/HLD/README.md) and [`Docs/SDD/README.md`](../../../Docs/SDD/README.md).
4. Terminology: [`Docs/VOCABULARY/README.md`](../../../Docs/VOCABULARY/README.md).
5. Active Phase Task: Lowest alphabetical file in `Tasks/epics/EPIC-025_module_theo_bounded_context/incomplete/`.
6. Touch rules: [`architecture-rule.md`](../../rules/architecture-rule.md), [`async-ui-action-rule.md`](../../rules/async-ui-action-rule.md), [`ui-presentation-rule.md`](../../rules/ui-presentation-rule.md), [`testing-rule.md`](../../rules/testing-rule.md), [`ci-rule.md`](../../rules/ci-rule.md), [`commit-rule.md`](../../rules/commit-rule.md).

**Kanban Prerequisite:** Before starting or resuming an epic sub-task, render the full epic Mermaid Kanban in chat. Validate draft syntax via [the Mermaid validation workflow](../execute-task/references/mermaid-validation.md); repair errors prior to display. Mark current task status and next action.

## 2. Invariants & Verification Matrix
Every architectural invariant must be mechanically proven:
| Invariant | Specification | Verification Command / Check |
| :--- | :--- | :--- |
| Business behavior unchanged | ADR D12; HLD §6.3 | Full gate passes; regression tests for `BUG-112`, `BUG-116`, `BUG-117` pass |
| Cross-module imports via contracts only | HLD §6.1 | Boundary guard: `pytest tests/unit/architecture/test_module_boundaries.py` |
| Boundary allowlist only shrinks | HLD §6.1, D11 | `wc -l tests/unit/architecture/allowlist_module_boundaries.txt` (must decrease or hold) |
| No UI presenters or coordinators in DI | ADR D12; SDD | `grep -rn "Coordinator\|Presenter" src --include=*.py \| grep -n "singleton(\|bind("` returns empty |
| `register()` never resolves dependencies | SDD §4 | Inspect `register()` and `contribute()` methods in touched modules |
| QtWidgets only; no new QML or global styling | HLD §11 | `pytest tests/unit/architecture/test_no_new_qml.py tests/unit/architecture/test_no_global_stylesheet.py tests/unit/architecture/test_app_styling_only_shrinks.py -q` |
| Application & Domain layers Qt-free | SDD §3; HLD §6.1 | `grep -rln PySide6 src/modules/*/application src/modules/*/domain src/core` returns empty |
| No unplanned third-party libraries | ADR §5; HLD §7 | `git diff requirements.txt pyproject.toml` returns empty |
| Engine capability declared | `BOT-133` | `src/infrastructure/engine_adapters/engine_capabilities.py` has registered capability |

## 3. Step Execution Checklist
Follow these 12 steps in exact order:
1. **Identify Step:** Name exact numbered item from the active phase task file (1 PR = 1 step).
2. **Apply Existing Pattern:** State which vetted architectural pattern from HLD §7 is implemented.
3. **Establish Architectural Seam:** Define interface/seam in ABC docstring with future extension points; implement only active variant.
4. **Baseline Measurement:** Record pre-step metrics defined in HLD §6.2.
5. **Code Modification:** Modify only files scoped to this step. Log out-of-scope necessities as separate findings.
6. **Test Migration:** Move tests alongside code (ADR D7); sanity tier gains zero tests. Prohibit `skip` or `xfail`.
7. **Gate Execution:** Run fast static checks per commit; run full gate on final PR tree:
   ```bash
   pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1
   grep -nE "FAILED|ERROR|Traceback|ResourceWarning" "$(grep -m1 LOG_FILE: /tmp/ci.log | sed 's/.*LOG_FILE: *//')"
   ```
8. **Architecture Guard Validation:** Run `pytest tests/unit/architecture -q`.
9. **Post-Step Measurement:** Re-run metrics from step 4 and document delta in task file.
10. **Diagram & Specification Sync:**
    - Update affected `.puml` diagrams in `Docs/HLD/diagrams/` or `Docs/SDD/diagrams/`.
    - If port signature diverged from draft, update `Docs/SDD/05_module_contracts.md` in same commit.
    - If use case flow changed, update corresponding spec under `Docs/SPEC/`.
11. **Bookkeeping:** Update task file status, `Tasks/ROADMAP.md`, `Tasks/epics/README.md`, and Gantt tracking in `Tasks/epics/EPIC-025_module_theo_bounded_context/TRACKING.md`.
12. **Structured Report:** Report execution results per Section 5.

## 4. Escalation & Stop Triggers
Decide routine implementation details autonomously. Stop and ask user only when:
- An open **❓** item in the ADR is encountered.
- User-visible behavior diverges from ADR D13, D14, D17 or SDD declarations.
- An essential change requires touching files outside the phase step scope.
- Code commit or code push is required (`.claude/ONBOARDING.md` §7).

## 5. Prohibitions & Reporting
- **Never:** Apply localized hotfixes; bypass allowlists; mute/skip tests; add undeclared libraries; add business logic to `core/` or `support/`.
- **User Report Format:** High-level project lead register (`.claude/rules/report-rule.md`): step executed, outcome summary, metric changes, gate log path, and the single next decision required from user.
