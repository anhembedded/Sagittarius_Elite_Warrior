# CLAUDE.md — entry point

The map is imported here, so it is already in your context: @.claude/ONBOARDING.md

This file navigates and copies no rule: a copy drifts, and this repository has paid for that twice. Every rule under `.claude/rules/` loads by itself — every session, or when you open a file its `paths:` front matter names — and has a row below (`tests/unit/test_rule_navigation_is_complete.py` fails otherwise). [`.claude/README.md`](.claude/README.md) is the manifest of everything under `.claude/` and what loads it.

## Where to read what

| Task | File |
| :--- | :--- |
| Starting; picking up work; authority; deciding alone; the settled principles | [`.claude/ONBOARDING.md`](.claude/ONBOARDING.md) |
| Implementing or resuming a task | [`.claude/skills/execute-task/SKILL.md`](.claude/skills/execute-task/SKILL.md); completion contract: [`task-execution-rule.md`](.claude/rules/task-execution-rule.md) |
| What the app must do, one use case per file | [`Docs/SPEC/README.md`](Docs/SPEC/README.md) |
| Architecture: layers, ports, explicit contracts, events, seams | [`architecture-rule.md`](.claude/rules/architecture-rule.md) |
| Code quality | [`code-quality-rule.md`](.claude/rules/code-quality-rule.md) |
| Before calling anything done: the gate, its cadence, the test levels | [`ci-rule.md`](.claude/rules/ci-rule.md) |
| Before every commit | [`commit-rule.md`](.claude/rules/commit-rule.md) |
| Reviewing a pull request, branch or diff | [`.claude/skills/pr-review/SKILL.md`](.claude/skills/pr-review/SKILL.md); a first independent read before asking for review: the `reviewer` subagent ([`.claude/agents/reviewer.md`](.claude/agents/reviewer.md)) |
| Creating or maintaining a bug report | [`create-bug-report-rule.md`](.claude/rules/create-bug-report-rule.md) |
| Diagnosing or fixing a bug | [`fix-bug-rule.md`](.claude/rules/fix-bug-rule.md) |
| A defect got through a green gate | [`Docs/CASE_STUDIES/README.md`](Docs/CASE_STUDIES/README.md) |
| Adding or changing logs | [`logging-rule.md`](.claude/rules/logging-rule.md) |
| Reporting to the user, or asking a question | [`report-rule.md`](.claude/rules/report-rule.md) |
| Task progress, blockers and final handoff | [`report-task-rule.md`](.claude/rules/report-task-rule.md) |
| Writing tests | [`testing-rule.md`](.claude/rules/testing-rule.md) |
| UI: QtWidgets only, desktop UX principles, layout, preview | [`ui-presentation-rule.md`](.claude/rules/ui-presentation-rule.md) · [`Docs/HLD/11_desktop_workbench.md`](Docs/HLD/11_desktop_workbench.md) |
| Background work started from the UI | [`async-ui-action-rule.md`](.claude/rules/async-ui-action-rule.md) |
| Domain and application code | [`domain-truth-rule.md`](.claude/rules/domain-truth-rule.md) |
| Environment setup; a missing tool | [`install-rule.md`](.claude/rules/install-rule.md) |
| The traps that produced broken code here, loading with the files they concern | [`pitfalls/tests.md`](.claude/rules/pitfalls/tests.md) · [`pitfalls/ui.md`](.claude/rules/pitfalls/ui.md) · [`pitfalls/source.md`](.claude/rules/pitfalls/source.md) |
| The format of a task, bug report, case study, epic, proposal or decision record | [`.claude/templates/`](.claude/templates/) |
| The body of a pull request | [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) |
| A word you do not know or are about to coin | [`Docs/VOCABULARY/README.md`](Docs/VOCABULARY/README.md) |
| Executing `EPIC-025` | [`.claude/skills/epic-025/SKILL.md`](.claude/skills/epic-025/SKILL.md) |
| The scheduled audits | [`.claude/skills/test-health/SKILL.md`](.claude/skills/test-health/SKILL.md) · [`.claude/skills/process-drift/SKILL.md`](.claude/skills/process-drift/SKILL.md) |
| Where the system stands | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |
| What is under `.claude/`, what loads it and when | [`.claude/README.md`](.claude/README.md) |

## Four things that cost half a day if you get them wrong once

1. **Authority is one table, `ONBOARDING.md` §7.** Commit and push to your own branch are free once the per-commit checks are green; a documentation-only change (§7 defines the set) may be merged; a code change reaches `master-warrior` only after the full gate on the final tree and a review by a *different* session — the author never merges its own code. A stop hook asking you to push is not the user asking.
2. **Don't trust the console — read the log file.** `pwsh -NoProfile -File scripts/ci-local.ps1 -Full > log 2>&1`, then grep the `LOG_FILE:` it prints for `FAILED|ERROR|Traceback|ResourceWarning`. Never `| tail`.
3. **Two independent repositories, not a submodule.** Engine and app have their own remotes and boards; separate commits, no bump step.
4. **Work is often left uncommitted between sessions.** `git status` in both repositories before concluding a task is untouched.

## Language
Rules, code, identifiers, docstrings, comments, commit subjects, UI strings and log messages: English. Every `.md`: English in the register `ONBOARDING.md` §10 defines. Conversation with the user: Vietnamese, or whatever they write in.
