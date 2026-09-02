# Development Guidelines

> **New agents start here:** read [`ONBOARDING.md`](ONBOARDING.md) before this
> file. It is the process map — the 2-repo layout, the task/bug lifecycle, the real
> test commands per OS, `ROADMAP.md` bookkeeping, and the list of traps that have
> actually produced broken code in this repo.

**Correction 2026-08-21:** this file previously contained almost verbatim
content that already existed elsewhere — SOLID, Clean Architecture, Typing, QML, Async Action
Ownership, Testing… all of it a copy (many passages word for word) of
[`rules/code-rule.md`](rules/code-rule.md); the 2 installation lines were a copy of
[`rules/install-rule.md`](rules/install-rule.md). A copy drifts away from
the original over time — you fix one place, forget the other, and the 2 files diverge.
**Worse:** the "Git Commits & Version Control" section hard-coded
`Co-Authored-By: Antigravity <noreply@google.com>` — wrong, and a direct violation of
[`rules/commit-rule.md`](rules/commit-rule.md), which states explicitly: the trailer must match
the AI that actually created the commit, and misattributing it to another tool is "not acceptable,
even for consistency with older commit history". Why that line was in the file is unclear —
possibly a session running on Antigravity (Google) once edited this file.
All duplicated/incorrect content was deleted rather than "moved" — there was nothing to
move, a fuller version already existed in the corresponding `rules/` files.

## What to read instead of this file

| Topic | Read in |
| :--- | :--- |
| **Decision doctrine / when you may decide alone, when you must ask** | [`ONBOARDING.md`](ONBOARDING.md) §7 |
| SOLID, Clean Architecture, Port/ABC, CQRS, Abstraction-Level Separation | [`rules/architecture-rule.md`](rules/architecture-rule.md) |
| Typing, immutability, magic numbers, God object, lazy import, Single-Scope Cohesion | [`rules/code-quality-rule.md`](rules/code-quality-rule.md) |
| Async UI action ownership, cancellation, Coordinator Pattern | [`rules/async-ui-action-rule.md`](rules/async-ui-action-rule.md) |
| Truthful data, trading semantics, snapshots, benchmarks | [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) |
| The presentation layer (Python), the MVP trio, `preview.py` | [`rules/ui-presentation-rule.md`](rules/ui-presentation-rule.md) |
| How to write tests, invariants, Boundary Value Analysis | [`rules/testing-rule.md`](rules/testing-rule.md) |
| Installing `sagittarius_engine` (2 options) | [`rules/install-rule.md`](rules/install-rule.md) |
| Commit rules, the correct `Co-Authored-By` trailer | [`rules/commit-rule.md`](rules/commit-rule.md) |
| CI/CD, the 4 test tiers | [`rules/ci-rule.md`](rules/ci-rule.md) |
| The bug-fixing process | [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) |
| Logging | [`rules/logging-rule.md`](rules/logging-rule.md) |
| QML in detail | [`rules/qml-rule.md`](rules/qml-rule.md) |

**Rule split 2026-08-25:** `rules/code-rule.md` (213 lines, 9 groups of rules at different
abstraction levels) was split into 6 dedicated files — the first 6 rows of the table
above. `code-rule.md` itself is **kept as a navigation stub, not deleted**: the
files in `.agents/Skills/` (system prompts for automated agents) read it as a mandatory
entry point, for the same reason this `AGENTS.md` was kept.

**Correction 2026-08-26 (`EPIC-011`):** the paragraph above previously said "7
`.jules/*.prompt.md` files". `EPIC-011` extracted the shared part of the 7 prompts into
`.jules/README.md`, so now **only that file** points to `code-rule.md`. The reason for keeping
the stub is unchanged. Count with `grep -rl code-rule .agents/Skills/`.

**Correction 2026-08-27 (`EPIC-012`):** `.jules/` no longer exists — all 7 prompts and
`README.md` moved to `.agents/Skills/` (with `.jules/` deleted and a Routine set up to
run every 2 days per agent). Every `.jules/...` path in the paragraphs above and below
has been updated to the new location. See
[`Tasks/epics/EPIC-012_di_chuyen_skills_ve_agents_va_lich_2_ngay/README.md`](../Tasks/epics/EPIC-012_di_chuyen_skills_ve_agents_va_lich_2_ngay/README.md).

**Correction 2026-08-25:** the table above used to have an extra row "Security →
`rules/sentinel-rule.md`" — that file has **never existed** in
`.agents/rules/` (there were 7 rule files at the time; 13 after the split done the same day — always
confirm with `ls .agents/rules/`).
That broken link row was removed. The real security content lives in
`.agents/Skills/sentinel.prompt.md` (the Sentinel agent's system prompt) and
`Tasks/epics/EPIC-004_static_security_and_quality_analysis/`.

This file is kept (rather than deleted outright) because `AGENTS.md` is a filename many
automated AI tools look for and read by default — without it those tools would have no
entry point at all. Its role now is purely **navigation**, not a
source of content.
