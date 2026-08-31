# CLAUDE.md — entry point for Claude Code

**Read [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) before writing the first
line of code.** It is the process map: task/bug lifecycle, the real verification
commands, bookkeeping, permissions, and §7 lists the traps that have **actually
produced broken code**.

---

## This file only NAVIGATES — deliberately holds no rules

Claude Code loads `CLAUDE.md` automatically; it does **not** load
`.agents/rules/*.md` on its own (the `trigger:` field in those files is this
rule set's own convention, not a Claude Code loading mechanism). That is why
this file exists: to give Claude an entry point.

**Do not copy rules in here.** A copy always drifts from the original: edit one
place, forget the other, and the wrong version still gets read. To add a rule,
edit the rule file it belongs to; here you add one line pointing at it.

## Where to read what

| Task | File |
| :--- | :--- |
| Starting, or picking up work in progress | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) — §10 is "picking up work in progress" |
| Where the last session stopped | [`.agents/Handover.md`](.agents/Handover.md) |
| Looking up a rule by topic | [`.agents/AGENTS.md`](.agents/AGENTS.md) |
| Architecture: layers, interfaces, explicit contracts, splitting by abstraction level | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Internal signal or event bus | [`.agents/rules/event-rule.md`](.agents/rules/event-rule.md) |
| Deferring work / accepting a trade-off → needs a type or a test standing for it | [`.agents/rules/design-intent-rule.md`](.agents/rules/design-intent-rule.md) |
| Code quality: typing, magic numbers, cohesion, lazy imports | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Before claiming anything is done | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Before every commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| A bug was reported (**mandatory**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| Adding or changing logs | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| Writing tests | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| User-initiated background work | [`.agents/rules/async-action-rule.md`](.agents/rules/async-action-rule.md) |
| Presentation layer | [`.agents/rules/ui-rule.md`](.agents/rules/ui-rule.md) |
| Business logic, truthful data | [`.agents/rules/domain-truth-rule.md`](.agents/rules/domain-truth-rule.md) |
| Missing tooling to run verification | [`.agents/rules/environment-rule.md`](.agents/rules/environment-rule.md) |
| Reusing this rule set in another project | [`.agents/README.md`](.agents/README.md) |

---

## Three things that cost half a day if you get them wrong once

Only what an agent can break **before it gets around to reading the rules**.
Everything else: see the table above.

1. **Never `git push` unless the user explicitly asks.** `commit` is
   ask-by-default; `push` is forbidden-by-default.

2. **Don't trust the console — read the log file.** A run can exit `0` while
   logging WARNING/ERROR describing a silently broken path. Always
   `> logfile 2>&1` then `grep`, never `| tail` — `tail` both shows you
   irrelevant trailing noise and can **cut off** the line that actually
   matters.

3. **Work is routinely left uncommitted between sessions.** A task board that
   looks untouched **plus** a dirty working tree means the work **is already
   done**, just unrecorded. Run `git status` and read the diff before concluding
   a task is untouched.
