# `.agents/` — working rules for AI agents (project-agnostic template)

This directory is a **template**. Copy it into any repository, replace the
placeholders in §2, delete what you don't need, and you're done.

It is not a collection of best practices copied from a book. Every rule here
exists because a real class of defect went through it. The *specific examples*
have been genericised; the *mechanism* is intact.

---

## 1. What's in here

| File | Contents | When to read |
| :--- | :--- | :--- |
| [`ONBOARDING.md`](ONBOARDING.md) | Process map: task/bug lifecycle, verification, bookkeeping, permissions, the traps | **Always, first** |
| [`AGENTS.md`](AGENTS.md) | Navigation stub: topic → rule file | When looking up a rule by topic |
| [`Handover.md`](Handover.md) | State of the last session — **replaced every session** | Right after `ONBOARDING.md` |
| [`rules/architecture-rule.md`](rules/architecture-rule.md) | SOLID, layers, ports/interfaces, explicit contracts, abstraction-level separation | Anything architectural |
| [`rules/event-rule.md`](rules/event-rule.md) | Internal signal or event bus — decided by who owns the truth, never by counting signals | Adding a notification path |
| [`rules/design-intent-rule.md`](rules/design-intent-rule.md) | Deferred work and accepted trade-offs need a type or a test; a class is a contract | Deferring work, accepting a trade-off |
| [`rules/code-quality-rule.md`](rules/code-quality-rule.md) | Typing, readability, immutability, magic numbers, God objects, cohesion | Every code change |
| [`rules/testing-rule.md`](rules/testing-rule.md) | How to **write** a test properly | Writing tests |
| [`rules/ci-rule.md`](rules/ci-rule.md) | How to **run** the gate, the four test levels, handling red | Before claiming anything is done |
| [`rules/commit-rule.md`](rules/commit-rule.md) | Conventional Commits, pre-commit verification, AI signature | Before every commit |
| [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) | The mandatory bug-fix workflow | **When a bug is reported** |
| [`rules/logging-rule.md`](rules/logging-rule.md) | Where to log so a bug report names its own root cause | Adding or changing logs |
| [`rules/async-action-rule.md`](rules/async-action-rule.md) | Background-action ownership, stale callbacks, cancellation | User-initiated background work |
| [`rules/ui-rule.md`](rules/ui-rule.md) | Presentation layer: declarative views, responsive sizing, injection defense | Touching UI |
| [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) | The system may not lie about what it actually did | Touching business logic |
| [`rules/environment-rule.md`](rules/environment-rule.md) | Setting up the environment is the agent's job; install vs. add-a-dependency | Missing tooling to verify |
| [`check-agents-docs.sh`](check-agents-docs.sh) | Guard: broken `.md` links + unreplaced placeholders | After adopting, and in CI |

Delete any file the project doesn't need (no UI → delete `ui-rule.md` and
`async-action-rule.md`). **If you delete a file, delete every line pointing at
it** in `AGENTS.md` and `ONBOARDING.md` §1 — a broken link in agent
documentation is the quietest failure there is: the agent finds nothing and
invents a rule instead.

---

## 2. Placeholders to replace before use

```sh
sh .agents/check-agents-docs.sh
```

It lists everything still to be replaced (the table below always matches
itself, so it is excluded) and checks for broken `.md` links at the same time.
**On the pristine template it FAILS — by design.** Green means you're adopted;
at that point wire it into the project's CI gate
([`rules/ci-rule.md`](rules/ci-rule.md) §1) so the rule set doesn't rot later.

| Placeholder | Meaning | Example |
| :--- | :--- | :--- |
| `<SRC_DIR>` | Main source directory | `src/`, `app/`, `lib/` |
| `<TEST_DIR>` | Test directory | `tests/`, `spec/` |
| `<CI_CMD>` | The **single** command that runs the whole gate | `make ci`, `npm run ci`, `./scripts/ci-local.sh` |
| `<LINT_CMD>` | Lint + format in **read-only** mode | `ruff check . && ruff format --check .` |
| `<TYPECHECK_CMD>` | Static type check (drop if the language has none) | `mypy src scripts`, `tsc --noEmit` |
| `<TASKS_DIR>` | Where tasks and bugs live | `Tasks/`, `docs/tasks/` |
| `<TASK_ID>` | Task ID prefix | `TASK`, `PROJ` |
| `<BUG_ID>` | Bug ID prefix | `BUG` |
| `<LOG_NAMESPACE>` | The app's root logger namespace | `App`, `acme` |
| `<SCOPES>` | Allowed commit scopes | `ui, api, domain, infra, ci` |
| `<DOC_LANG>` / `<UI_LANG>` | Language for docs / for UI strings | `English` / `English` |

---

## 3. Three rules not to edit when you take this elsewhere

They are the most expensive things in this set — everything else is detail:

1. **Don't trust the exit code, read the log file.** A command can exit `0`
   while logging WARNING/ERROR describing a silently broken path.
   (`ci-rule.md` §5)
2. **Write the regression test BEFORE fixing a bug, and confirm it fails for
   the right reason.** A test written afterwards proves nothing.
   (`bug-fix-rule.md` §3)
3. **Never `commit` unless asked; never `push` unless explicitly asked.**
   (`ONBOARDING.md` §6)

---

## 4. How this rule set rots — and how to stop it

Real experience from the repository this came from, kept because it will
happen in yours too:

- **The drifted copy.** Copy a rule's content into a second file (`CLAUDE.md`,
  a README, an agent prompt) → edit one, forget the other → two contradictory
  versions, and the wrong one still gets read. **Always link, never copy.**
- **Hard-coded counts in prose.** "9 rule files", "1641 tests", "14 lint
  errors" — stale within hours. Write the **command that counts** instead of
  the number.
- **Links to files that don't exist.** A prompt once pointed at a rule file
  that had never existed and ran for months unnoticed, because an unattended
  agent still reports success. If the repo runs automated agents, add a test
  that walks every path mentioned under `.agents/` and goes red on a dead one.
- **Rules that live only in prose.** See `design-intent-rule.md`: anything
  deferred or traded away needs a **type or a test** standing for it, not just
  a paragraph.
