---
name: Commit Rule
description: Never commit unasked, verify before committing, Conventional Commits, a correctly attributed AI signature, atomic commits.
trigger: always_on
---

# Git Commit Guidelines for AI Agents

Every AI assistant working on this repository MUST follow these rules strictly,
without exception.

---

## 0. Never commit unless the user asked

- **Do NOT `git commit` on your own initiative.** Always wait for explicit
  permission before writing changes into version control.
- **`git push` is forbidden by default** — only on an explicit user request,
  and each repository is its own separate confirmation.

---

## 1. Mandatory pre-commit verification

- **Never commit broken, untested, or failing code.**
- Before every `git commit`, the agent MUST run `<CI_CMD>` and ensure:
  - **all tests pass**, zero failures, zero errors;
  - **zero first-party warnings** — no resource leaks, no dangling unawaited
    coroutines, no unclosed connections;
  - lint, format, type check and coverage are all green.
- **Exception:** a commit touching no code file — see
  [`ci-rule.md`](ci-rule.md) §1 for the exact boundary.

---

## 2. Commit message format (Conventional Commits)

```
<type>(<scope>): <concise subject, present tense, imperative>

<optional body: context, rationale, specific changes>

- <module>: details of the change
- <tests>: new tests / new coverage

Co-Authored-By: <name and identity of the AI that actually authored this commit>
```

### Allowed types

| Type | Use when |
| :--- | :--- |
| `feat` | New feature or user-facing capability |
| `fix` | Bug fix — **must** reference the root cause or bug ID |
| `refactor` | Structural change: no new feature, no bug fix |
| `perf` | Performance improvement |
| `test` | Tests only |
| `ci` | CI scripts, test runners, environments |
| `docs` | Documentation only |
| `style` | Formatting/lint only, no behaviour change |
| `chore` | Maintenance, configuration, dependencies |

**Scope** is a short, project-agreed list (`<SCOPES>`).

---

## 3. The mandatory AI signature — correctly attributed

Every commit authored by an AI MUST carry a trailer as the **very last** lines,
naming the assistant that actually produced it:

```
Co-Authored-By: <Assistant Name> <noreply@assistant-provider.example>
```

**Never hard-code another tool's name, and never use a placeholder.**
Misattributing authorship to a tool that did not generate the commit is **not
acceptable**, not even for consistency with older commit history.

> **Real evidence:** in the original repository, a guidance file hard-coded the
> trailer of a **different** AI tool — directly violating this very rule — and
> survived long enough to reach the commit history. Nobody noticed, because it
> lived in a **drifted copy** of the rule rather than in the original.

*(Leave a blank line before the trailer.)*

---

## 4. Atomic, clean commits

- **One logical change per commit.** Don't bundle a feature, a large refactor
  and a bug fix into one enormous commit.
- **Never commit:**
  - scratch/temporary files, one-off test scripts, scratch directories;
  - leftover debug logging, commented-out dead code, temporary mocks;
  - virtual environments, database files, build artifacts.
- **No lazy imports**, **no magic numbers** in committed code — see
  [`code-quality-rule.md`](code-quality-rule.md).

---

## 5. Bug-fix commits

The full workflow is in [`bug-fix-rule.md`](bug-fix-rule.md). Two things are
mandatory at commit level:

- A bug-fix commit **MUST contain the regression test** — never fix without it,
  never split the test into a later commit.
- **State the root cause in the commit body:** what caused the bug, and why this
  fix resolves it cleanly.

---

## 6. Stale branches & conflict resolution

Before resolving or merging a branch (especially an automatically generated
one):

1. **Value check:** is the branch's change still relevant, or already merged?
   Discard stale, duplicate or zero-value branches.
2. **Resolve carefully:** don't reintroduce outdated patterns or duplicated
   lines while following conflict markers.
3. **Verify:** always run `<CI_CMD>` **on the merged state** before pushing.
