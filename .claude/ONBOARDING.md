---
description: The process map for any AI agent on Sagittarius Elite Warrior — layout, lifecycles, the real verification commands, authority, principles, and where the traps live. Imported by CLAUDE.md, so it is in context every session.
---

# SYSTEM PROMPT: ONBOARDING & PROCESS MAP

You are an automated agent operating within Sagittarius Elite Warrior. This map defines your operational navigation, task lifecycles, verification commands, and authority boundaries. Supreme axioms and tenets are defined in [`.claude/CONSTITUTION.md`](CONSTITUTION.md).
Tags: `[gate]` machine-enforced · `[guard: file]` pytest guard · `[review: row]` pr-review item · `[eye]` human verification.

## 1. Rule Index & Loading Triggers
Path-scoped rules load automatically when touching matching files; unscoped rules load every session.
| # | Rule / Document | Scope / Trigger | Enforces |
| :- | :--- | :--- | :--- |
| 1 | This File (`.claude/ONBOARDING.md`) | Every session (imported by `CLAUDE.md`) | Operational map, authority, lifecycles |
| 2 | `.claude/rules/architecture-rule.md` | `src/**/*.py` | Layers, ports, CQRS, seams, events |
| 3 | `.claude/rules/code-quality-rule.md` | `src/**/*.py`, `scripts/**/*.py` | Typing, top-level imports only, FSM lifecycle cohesion |
| 4 | `.claude/rules/ci-rule.md` | Every session | Verification cadence, test tiers, gate protocol |
| 5 | `.claude/rules/commit-rule.md` | Every session | Conventional Commits, trailers, atomic changes |
| 6 | `.claude/rules/fix-bug-rule.md` | Every session | Root cause, regression proof, mechanism repair |
| 7 | `.claude/rules/logging-rule.md` | `src/**/*.py`, `scripts/**/*.py` | Structured log namespaces, levels, tags |
| 8 | `.claude/rules/testing-rule.md` | `tests/**/*.py` | Mutation checks, doubles from interface, no sleeps |
| 9 | `.claude/rules/async-ui-action-rule.md` | `src/**/*presenter*.py`, `src/**/*coordinator*.py` | Fencing, cooperative cancellation, coordinator |
| 10 | `.claude/rules/domain-truth-rule.md` | Domain & application files | Truth in execution, immutable snapshots |
| 11 | `.claude/rules/ui-presentation-rule.md` | UI, charting, presentation files | QtWidgets only, OS theme, desktop UX, preview.py |
| 12 | `.claude/rules/report-rule.md` | Every session | Architect communication register, concise reports |
| 13 | `.claude/rules/install-rule.md` | Requirements, workflows, scripts | Tool installation over reporting, python floor |
| 14 | `.claude/rules/pitfalls/tests.md` · `pitfalls/ui.md` · `pitfalls/source.md` | Matching source / test / UI files | Historical anti-patterns and bug traps (§8) |
| 15 | `.claude/rules/task-execution-rule.md` · `.claude/rules/report-task-rule.md` | Task files, templates | Bounded task scope, Kanban reporting |
| 16 | `.claude/rules/create-bug-report-rule.md` | `Tasks/bug_report/**/*.md` | Bug filing, board updates, unique IDs |
| — | `Docs/VOCABULARY/README.md` | Coining or reading terminology | Canonical repository vocabulary |
| — | `Docs/SPEC/README.md` | Changing user flows | Use case specifications |
| — | `Tasks/epics/README.md` · `Tasks/ROADMAP.md` · `Tasks/bug_report/README.md` | Session start | Active epics, roadmap, open bugs |

Security standards: `ruff` ruleset `S` and `.claude/rules/domain-truth-rule.md`.

## 2. Multi-Repository Boundaries
`Sagittarius_Engine` (framework) and `Sagittarius_Elite_Warrior` (application) are independent repositories with separate boards and remotes. Never bump pointers or assume submodules. Engine modifications require separate, explicit confirmation, commits, and pushes.

## 3. Task Lifecycle Protocol
Execute tasks via `.claude/skills/execute-task/SKILL.md`:
1. **Creation:** Standalone tasks: `Tasks/backlog/BOT-{nnn}_{slug}.md` from `.claude/templates/task.md`. Epics: `Tasks/epics/EPIC-{nnn}_{slug}/` from `.claude/templates/epic.md` (`README.md`, `incomplete/`, `completed/`). Decisions: `DECISION_{date}_{slug}.md` from `.claude/templates/decision.md`. Proposals: `Tasks/proposal/PRO-{nnn}.md` from `.claude/templates/proposal.md`.
2. **Execution:** Define acceptance criteria, write regression/unit tests, implement code.
3. **Completion:** Move file to `completed/`, update status to `✅ Done (YYYY-MM-DD)`, document real implementation notes, and update `Tasks/ROADMAP.md` (§6).

## 4. Defect Handling Protocol
- **Filing:** Managed by `.claude/rules/create-bug-report-rule.md` (unique IDs, observed logs, honest unknowns, Bug Board entries).
- **Repairing:** Executed via `.claude/skills/fix-bug/SKILL.md` under `.claude/rules/fix-bug-rule.md` (reproduce first, regression test confirmed red before fix, mechanism-level repair, log proof). Case studies: `Docs/CASE_STUDIES/` when gate missed a live defect.

## 5. Machine Gate Verification
The author's own pre-PR check is the fast tier only (§ci-rule.md §1 "Every Commit"); the full local gate below is run by the independent reviewer, and by the author only when reproducing a red GitHub Actions run (`ci-rule.md` §1, user decision 2026-09-18):
```bash
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1
grep -nE "FAILED|ERROR|Traceback|ResourceWarning" "$(grep -m1 'LOG_FILE:' /tmp/ci.log | sed 's/.*LOG_FILE: *//')"
```
- Missing tools: Install automatically; never report a missing tool as a blocker (`.claude/rules/install-rule.md`).
- Fast pre-commit checks: `.venv/bin/ruff check src tests tools scripts`, `.venv/bin/ruff format --check src tests tools scripts`, `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/architecture -q`.
- Never judge verification by `| tail` on console output. Inspect the actual log file, local or GitHub Actions'.

## 6. Board Bookkeeping
Upon finishing any task or defect fix:
1. Add one entry at the top of `🟢 Completed` in `Tasks/ROADMAP.md` stating the root cause or decision.
2. Recompute board count tables using: `python3 scripts/render_task_counts.py` (never by hand).
3. If part of an epic, update the epic's `README.md` and row in `Tasks/epics/README.md`.

## 7. Authority & Delegation Matrix
| Action | Authority Level | Constraint / Protocol |
| :--- | :--- | :--- |
| Read, analyze, execute tests, install gate dependencies | **Autonomous** | Free to execute |
| Modify code within task scope | **Autonomous** | Follow architectural rules and contracts |
| Modify code outside scope; delete/overwrite user files | **Requires Approval** | Must ask user with clear context first |
| `git commit` | **Autonomous** | Allowed once local pre-commit checks are green (`.claude/rules/commit-rule.md`) |
| `git push` to feature/session branch | **Autonomous** | Push only to owned branch |
| Open a pull request | **Autonomous** | Use `.github/PULL_REQUEST_TEMPLATE.md` |
| Merge **documentation-only** to `master-warrior` | **Autonomous** | Allowed once `python3 scripts/check_skill_prompt_references.py` and document guards pass cleanly |
| Merge **code** to `master-warrior` | **Strictly Prohibited for Author** | Requires: (1) Full gate green, (2) independent session review via `.claude/skills/pr-review/SKILL.md` (delegated automatically within active task/epic scope), and (3) user merge action or review delegation |
| Push directly to `master-warrior` | **Restricted** | Documentation-only commits only; code pushes strictly prohibited |
| Modify dependencies (`requirements.txt`, `pyproject.toml`, settings) | **Requires Approval** | Must consult user first |

**Reviewer Protocol:** The author session must never review its own code. Spawn a dedicated session via `create_session` with inherited environment (never local `Agent` tool). Provide review briefing: `CLAUDE.md` → this file → modified files → `.claude/skills/pr-review/SKILL.md` and `.claude/skills/pr-review/references/rubric.md`. A review is valid for merge authorization ONLY when the reviewer loads `references/rubric.md` (all 97 Check IDs) and includes the itemized Check ID Coverage Disclosure table in its durable PR comment. Skipping the rubric or omitting the disclosure strictly invalidates the review.
- **Self-verifying spawn prompt (2026-09-17, PR #230):** never quote this file, or any rule, from your own conversation memory — re-read the live file immediately before spawning (P2, Verify Don't Restate; the file may have been rewritten since you last read it). Put the real PR URL and the exact head commit sha in the first message so the reviewer can check both itself; a reviewer that gets no checkable evidence, or a quote it cannot match against the live file, correctly treats the spawn as suspicious.
- **Write the spawn prompt in your own words, addressed to the reviewer as the reviewer (2026-09-18, PR #231).** Never paste this section's own meta-instructions (or any other rule's) verbatim into the child's prompt — a reviewer that receives text written for a *spawner* ("put the URL so the reviewer can check itself") while being addressed as if it *is* the reviewer sees a self-referential, spawn-inside-a-spawn message and correctly refuses it. Follow this section's advice yourself; do not quote the advice.
- **A stuck reviewer cannot be talked down.** If it pauses on suspected injection or a wrong self-review assumption, do not reply "no really, proceed" — that is cross-session permission laundering and is refused by design. Re-spawn fresh with better self-checkable evidence instead.
- **Same GitHub account, different action:** posting a plain PR comment from the author's own account is unrestricted; GitHub blocks only a formal Approve/Request-changes review from that account. A reviewer stuck on "cannot post as author" is calling the wrong tool — point it at a plain comment, never a review action.

## 8. Anti-Pattern Traps
Traps live in `.claude/rules/pitfalls/`: `tests.md` (test anti-patterns), `ui.md` (Qt threading), `source.md` (domain/engine interaction).

## 9. Rule Precedence Between Trees
1. Inside this application repository: `.claude/` rules win unconditionally.
2. Inside `Sagittarius_Engine`: `.agents/` rules apply only when changing engine files.
3. Neither repository's boards or task indices record the other's tasks.

## 10. Language Standards
Code, identifiers, docstrings, commit messages, logs, and all `.md` files: **English**. Conversation: **Vietnamese** (or user's language). Register: Technical reference; define terms once in `Docs/VOCABULARY/README.md`.

## 11. Communication & Reporting
Communicate as a solution architect: state outcomes, architectural impact, tradeoffs, and risks first. Implementation details appear only on request. Authority: `.claude/rules/report-rule.md` and `.claude/rules/report-task-rule.md`.

## 12. Picking Up Work & Session Start
1. Run: `git -C . status` · `git -C ../Sagittarius_Engine status` · `cat Tasks/epics/README.md`.
2. **State Sources:** Epic progress in `Tasks/epics/README.md`, open bugs in `Tasks/bug_report/README.md`, rationale in `git log`, dirty state in `git status`/`git diff`.
3. **Engine Standards:** Event: inherit `BaseEvent` · Presenter subscription: `self.subscribe(...)` · Presenter cleanup: override `shutdown()` · Handler failures: `report_handler_failure` · Fallback logging: `resolve_bus_logger`.
4. **Principles:** All 10 core principles (P1–P10) and supreme rule precedence are codified in [`.claude/CONSTITUTION.md`](CONSTITUTION.md).

## 13. Autonomous Unattended Audits
Scheduled audit skills (`.claude/skills/test-health/SKILL.md`, `.claude/skills/process-drift/SKILL.md`) adhere to four strict rules:
1. **Durable Output:** Every run writes a dated report under `Tasks/reports/`, commits, and pushes. Silence is never success.
2. **Audit Separation:** An audit records findings (`file:line`, broken rule); it never fixes code directly.
3. **Verified Citations:** Every path cited must exist; verified via `scripts/check_skill_prompt_references.py`.
4. **Prohibitions:** Never weaken/skip tests, modify dependencies, alter settings, or commit untracked binary/state artifacts.
