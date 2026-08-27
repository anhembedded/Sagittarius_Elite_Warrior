# `.agents/Skills/` — the scheduled agents

Seven agents live here. Each runs on its own schedule, unattended, and each run
is meant to produce **one** small, verified change — or nothing at all.

| Prompt | Agent | One-line job |
| :--- | :--- | :--- |
| `bolt.prompt.md` | Bolt ⚡ | one measured performance win |
| `doctor.prompt.md` | Doctor 🩺 | one behaviour-preserving refactor |
| `janitor.prompt.md` | Janitor 🧹 | one piece of dead code removed |
| `palette.prompt.md` | Palette 🎨 | one micro-UX / accessibility improvement |
| `scout.prompt.md` | Scout 🧪 | one untested branch, now tested |
| `scribe.prompt.md` | Scribe 📝 | one typing / documentation gap closed |
| `sentinel.prompt.md` | Sentinel 🛡️ | one security or robustness fix |

This file is the **shared half** of all seven prompts. Each prompt links here
instead of restating what is below. Read this first, then your own prompt.

---

## 1. The rule that keeps these prompts alive

An agent that runs unattended on a schedule cannot notice that its own briefing
went stale. It will keep hunting for something the repo deleted months ago, keep
citing a rule file that does not exist, and keep reporting success. That has
already happened here — see [`Tasks/epics/EPIC-011_dong_bo_skill_dinh_ky_jules/README.md`](../../Tasks/epics/EPIC-011_dong_bo_skill_dinh_ky_jules/README.md)
for the full list of what had rotted and how.

So, when writing or editing anything in `.agents/Skills/`:

> **Verify, don't restate.** If a fact can change, do not write the fact — write
> the command that answers it. If a rule already exists in `.agents/rules/`,
> link to it; never copy it.

Concretely, these are **banned** in any `.agents/Skills/*.md`:

- **Counts** — "839 unit tests", "21 sanity tests", "7 rule files". Every count
  written in this repo's docs has been wrong within weeks. `CLAUDE.md` and
  `.agents/ONBOARDING.md` §8 both record this as a repeat defect.
- **Versions and dates** presented as current state.
- **A rule restated in your own words.** Link it. A copy drifts from its
  original, and this repo has shipped a wrong `Co-Authored-By` trailer exactly
  that way (`CLAUDE.md`, *"Không chép luật vào đây"*).
- **A named file, symbol, or directory used as proof that a thing exists**,
  unless you checked in this run. `scripts/check_skill_prompt_references.py`
  enforces this for the paths you write in backticks — run it before you commit
  a prompt edit.

What replaces them: a command whose output is the answer.

| Instead of writing… | Ask the tree |
| :--- | :--- |
| "the app uses QML" / "the app has no QML" | `find src -name '*.qml' \| wc -l` and `grep -rln QQuickWidget src tests --include=*.py` |
| "there are N tests" | run the gate (§3) and read its summary |
| "the widget kit is at X" | `ls src/presentation/ui/kit/` |
| "these rule files exist" | `ls .agents/rules/` |
| "this is a submodule" / "it is not" | `ls .gitmodules` |
| "the mypy debt list contains X" | read `[tool.mypy]` in `pyproject.toml` |
| "flaky UI tests are excluded from CI" | `grep -n 'IncludeFlakyUi\|BOT-038' scripts/ci-local.ps1` |

---

## 2. Repository context

- Two **independent** repos, not a superproject/submodule pair: the shared
  `sagittarius_engine/` framework, and this app — where you work by default.
  Separate remotes, separate `.agents/`, separate task boards, **no
  pointer-bump step**. `CLAUDE.md` §3 states this and names it a trap that has
  already cost real time. Confirm in one command: `ls .gitmodules`.
- **Read before touching anything**, in this order:
  1. [`CLAUDE.md`](../../CLAUDE.md) — the navigation entry point and its four
     "wrong once, costs a session" items.
  2. [`.agents/ONBOARDING.md`](../ONBOARDING.md) — process map; §8 is the
     list of traps that have genuinely produced broken code here.
  3. The rule files your change touches. `ls .agents/rules/` is the index —
     `.agents/rules/code-rule.md` is a **navigation stub only**, the content was
     split out; follow its links rather than reading it as law.
- **Language convention** (`CLAUDE.md`): task files, bug reports, `ROADMAP.md`
  and anything you write for the user are **Vietnamese**; code, identifiers,
  docstrings, comments and commit subjects are **English**; user-visible UI
  strings are **Vietnamese**.

---

## 3. The gate — non-negotiable, and stricter than these prompts used to say

`.agents/rules/ci-rule.md` §1 is the authority. It says, verbatim, that
`-UnitOnly` *"is diagnostic-only and never sufficient for handoff or commit"*.

```bash
# Linux (this is the required command before any commit that touches code)
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1
```

```powershell
# Windows
.\scripts\ci-local.ps1 -Full
```

`-Full` is what runs lint, format, `mypy`, the Ruff security/quality gate
(`EPIC-004`), the primary tests, Sanity, and the coverage threshold. Use
`-UnitOnly` while iterating if you like; finish with `-Full`.

**Do not trust the console.** `CLAUDE.md` §2: the script prints a `LOG_FILE:`
line — `grep` that file for `FAILED|ERROR|Traceback|ResourceWarning` before
claiming anything is green. Under offscreen Qt, harmless `TypeError` noise is
flushed to stderr *after* pytest's summary line, so `| tail` shows you the noise
instead of the result. Always redirect (`> file 2>&1`), never pipe to `tail`.

**If you cannot run the gate** — no PowerShell, no virtualenv, no engine
installed — then you have not verified anything. Say so plainly and do not
commit code. Prompt/task/`.agents/`-only edits are exempt: see `ci-rule.md` §1
*"Exception — commits that touch no code file"*.

---

## 4. Commits

- Read [`.agents/rules/commit-rule.md`](../rules/commit-rule.md) before
  every commit. Conventional Commits, atomic changes, and pre-commit
  verification are enforced there.
- The mandatory `Co-Authored-By` trailer is **defined in that file**. Read it
  there and name the assistant that actually authored the commit. Do **not**
  copy a trailer into any `.agents/Skills/` file — a hardcoded one is how this repo
  shipped a wrong attribution before.
- If you were not asked to commit, don't. `commit-rule.md` §0 and `CLAUDE.md`
  make `commit` ask-first and `push` forbidden-by-default.

---

## 5. Journals

Each agent has a journal at `.agents/Skills/<agent>.md`.

**Check whether yours exists — do not assume either way, in either direction.**

```bash
ls .agents/Skills/*.md          # which journals exist right now
```

The history here is the reason that command is the answer and no sentence is.
Earlier prompts asserted a journal was already written when none had ever
existed, and told the agent not to "rediscover" entries nobody wrote. This file
then asserted the opposite — *"none of them exist yet"* — and was **false within
hours**, because Bolt wrote its first real entries the same day. Both sentences
were accurate when typed. Neither survived. Run the command.

Create yours on your first real learning.

A journal is **not a run log**. Add an entry only for something that will change
a future decision:

- a behaviour specific to *this* architecture that surprised you;
- something that looked right and was not, and why;
- a rejected change worth not re-proposing.

Do not journal "did X today", or generic Python/Qt advice available in any
textbook.

```markdown
## YYYY-MM-DD - [Title]
**Learning:** [what you discovered about this codebase]
**Action:** [how to apply it next time]
```

---

## 6. Boundaries every one of the seven shares

✅ **Always**
- One change per run, small enough to review in one sitting (< ~50 lines).
- Run the gate in §3 and read its log file before claiming a result.
- Keep the change inside this repo unless the cause is genuinely in the engine.
- Stay inside your own lane — the seven overlap, and two agents fixing the same
  thing on the same day is how merge conflicts get generated unattended.

⚠️ **Ask first** (open a draft PR with the question rather than merging)
- Any new dependency, or any edit to `requirements.txt` / `pyproject.toml` /
  Ruff or mypy configuration.
- Any change under `sagittarius_engine/` — separate repo, separate remote,
  separate board; it affects every app built on the engine. Commit and push it
  there separately. Beware the drift this creates: the engine installed in the
  virtualenv can lag the engine repo while both claim the same version
  (`BUG-054`/`BUG-055` in `Tasks/bug_report/` carry the account and the
  reinstall command).
- Architectural changes, and anything crossing a layer boundary.

🚫 **Never**
- Commit without the §3 gate passing, when your change touches code.
- Weaken, skip, delete, or `xfail` a test to make your change pass.
- Break a public contract, or change behaviour in a run whose stated job is not
  to change behaviour.
- Touch the Obsidian vault under `Tasks/` (the `.obsidian/` directory — it
  exists only on the maintainer's machine and must never be committed).
- Commit secrets, `.db` files, `database/`, `logs/`, `state/`, or a virtualenv.

---

## 7. Staying meaningful — where each agent's work actually is

A scheduled agent is only worth its run if the repo still contains the kind of
work it was written to find. Each prompt names its own hunting ground and, where
one exists, the live epic it feeds. Re-derive the target list each run by
scanning; never work from a list written into a prompt.

If, after an honest scan, there is nothing worth doing: **stop and open
nothing.** An empty run is a correct outcome and always better than a
manufactured change. If a whole agent goes several runs with nothing to find,
that is a signal about the agent, not about the repo — say so in your journal,
and let a human decide whether the agent still has a job.

---

## 8. Before committing an edit to any file in here

```bash
python3 scripts/check_skill_prompt_references.py
```

It re-reads every backticked repo-relative path in `.agents/Skills/*.md` and fails on
any that no longer exists. It is the mechanical half of §1 — it cannot tell you
that a claim went stale, but it does catch the class of rot that has actually
shipped here: a prompt pointing at a file that is not there.
