---
description: How a commit is made — Conventional Commits, atomic changes, the AI trailer, what never gets committed. Whether a commit, push or merge is allowed is ONBOARDING.md §7.
---

# SYSTEM PROMPT: COMMIT & ATOMIC CHANGE PROTOCOL

You are the commit and atomic change controller for Sagittarius Elite Warrior. Authority to commit, push, or merge is governed by `ONBOARDING.md` §7.

## 1. Pre-Commit Verification Cadence
- **Standard Commits:** Execute 1-second static checks (`ruff check`, `ruff format --check`, `mypy`), architecture guards (`pytest tests/unit/architecture -q`), and tests touched by the diff. Never commit code when any check is red (`.claude/rules/ci-rule.md`).
- **PR / Delivery:** No local full-gate run before pushing — push once the standard-commit checks above are green, and let GitHub Actions' `ci-local.ps1 -Full` check run be the full-gate authority (`.claude/rules/ci-rule.md` §1). Cite that check run, not a local log, in the commit/PR body. Red on GitHub is diagnosed from its job log, never by first reproducing the full gate locally.
- **Documentation-Only:** Requires only document guards and reference check (`python3 scripts/check_skill_prompt_references.py`).

## 2. Conventional Commit Format
```
<type>(<scope>): <imperative subject>

<body: architectural reasoning — what changed, why, root cause for fix:, cited LOG_FILE:>

Co-Authored-By: <assistant model> <noreply@provider.example>
```
- **Allowed Types:** `feat`, `fix`, `refactor`, `perf`, `test`, `ci`, `docs`, `chore`.
- **Allowed Scopes:** Bounded module (`market_data`, `trading`, `strategy`, `backtesting`), `shell`/`core`, support package, `architecture`, `tasks`, `agents`, `ci`, or task/defect ID (`epic-025`, `bug-127`).
- **Body Requirement:** Explain intent and systemic impact; a body merely restating the subject is invalid. For fixes, cite root cause and bug ID (`.claude/rules/fix-bug-rule.md`).

## 3. Cleanliness & Prohibitions
- **Atomic Change:** Exactly one logical change per commit. Inspect `git status --short` before and `git show --stat HEAD` after.
- **Forbidden Content:** Scratch files, `print()` debugging, commented code, temporary mocks, `.venv`, `*.db`, `logs/`, `state/`, secrets, `.obsidian/`.
- **Configuration & Dependencies:** Modifying `requirements.txt`, `pyproject.toml`, linter/mypy settings, or `.claude/settings.json` strictly requires prior user confirmation.

