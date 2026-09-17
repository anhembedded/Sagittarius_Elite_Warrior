---
description: How a commit is made — Conventional Commits, atomic changes, the AI trailer, what never gets committed. Whether a commit, push or merge is allowed is ONBOARDING.md §7.
---

# Commits

## 0. Authority
`ONBOARDING.md` §7 decides what may be committed, pushed and merged. This file says how.

## 1. Verification
`ci-rule.md` §1 sets the cadence: the 1-second static checks, the architecture guards and the touched tests before every commit; the full gate on the final tree before a pull request. Never commit code a required check has shown red. Documentation-only commits (§7's set) need only the document guards §7 names. `[gate]`

## 2. Message
```
<type>(<scope>): <imperative subject>

<body: the reasoning — what, why, what was measured; a fix: names the root cause>

Co-Authored-By: <assistant that wrote it> <noreply@provider.example>
```
Types: `feat`, `fix`, `refactor`, `perf`, `test`, `ci`, `docs`, `chore`. Scope: a name a reader can grep — a module (`market_data`, `trading`, `strategy`, `backtesting`), `shell`/`core`, a support package, `architecture`, `tasks`, `agents`, `ci`, or the epic/bug id (`epic-025`, `bug-127`). `git log --format=%s -40` shows current usage. `[review: L1]`

The body is the record: `ONBOARDING.md` §12.2 makes `git log` the source for "what happened and why", so a body that only restates the subject is a missing record. A gate result cites its `LOG_FILE:` path. `[review: L2]`

## 3. Trailer
The assistant that actually wrote the commit, e.g. `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` (the model the harness names; plain `Claude` when none). A harness trailer such as `Claude-Session: <url>` stays. Never a name copied from an older commit — that is how a wrong trailer spread here. `[review: L3]`

## 4. Atomic and clean
- One logical change per commit; `git commit` takes the whole index, so read `git status --short` before and `git show --stat HEAD` after (`ONBOARDING.md` §8). `[review: L6]`
- Never commit scratch files, leftover `print()`, commented-out code, temporary mocks, virtualenvs, `*.db`, `database/`, `logs/`, `state/`, secrets, or `.obsidian/`. `[review: L4]`
- A dependency or tool-config change (`requirements.txt`, `pyproject.toml`, ruff/mypy settings, `.claude/settings.json`) is asked first. `[review: L5]`

## 5. Bug fixes
`bug-fix-rule.md` in full: the regression test ships in the fixing commit; the body states the root cause; the id is in the subject or body.

## 6. Pull request
The body follows `.github/PULL_REQUEST_TEMPLATE.md` — what, why, verification with the gate's `LOG_FILE:` path; GitHub fills it in. `[review: L2]`

## 7. Merging a branch an unattended agent opened
Check it is still relevant and not already merged; resolve conflicts without reintroducing old patterns; run `-Full` on the merged tree before pushing.
