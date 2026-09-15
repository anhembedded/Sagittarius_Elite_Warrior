# `.agents/Skills/` — the scheduled agents

Each agent here runs on its own schedule, unattended, and each run produces **one**
small, verified change — or nothing at all.

| Prompt | Agent | One-line job |
| :--- | :--- | :--- |
| `bolt.prompt.md` | Bolt ⚡ | one measured performance win |
| `doctor.prompt.md` | Doctor 🩺 | one behaviour-preserving refactor |
| `janitor.prompt.md` | Janitor 🧹 | one piece of dead code removed |
| `palette.prompt.md` | Palette 🎨 | one micro-UX / accessibility improvement |
| `scout.prompt.md` | Scout 🧪 | one untested branch, now tested |
| `scribe.prompt.md` | Scribe 📝 | one typing / documentation gap closed |
| `sentinel.prompt.md` | Sentinel 🛡️ | one security or robustness fix |
| `epic-025.prompt.md` | EPIC-025 executor 🧱 | **on demand, not scheduled** — one verified step of the module-split epic, by whichever AI the user hands it to |

This file is the **shared half** of every prompt here. Each prompt links to it
instead of restating what is below. Read this first, then your own prompt.

---

## 1. The rule that keeps these prompts alive

An agent running unattended cannot notice that its own briefing went stale. It
will keep hunting for something the repo deleted months ago, keep citing a rule
file that does not exist, and keep reporting success. That has already happened
here — [`EPIC-011`](../../Tasks/epics/EPIC-011_dong_bo_skill_dinh_ky_jules/README.md)
has the full list of what had rotted.

> **Verify, don't restate.** If a fact can change, write the command that answers
> it, not the fact. If a rule exists in `.agents/rules/`, link it; never copy it.

**Banned** in any `.agents/Skills/*.md`:

- **Counts** — "839 unit tests", "7 rule files". Every count written into this
  repo's docs has been wrong within weeks.
- **Versions and dates** presented as current state.
- **A rule restated in your own words.** Link it. A copy drifts, and this repo
  shipped a wrong `Co-Authored-By` trailer exactly that way.
- **A named file, symbol or directory used as proof that a thing exists**, unless
  you checked in this run.

What replaces them — a command whose output is the answer:

| Instead of writing… | Ask the tree |
| :--- | :--- |
| "the app uses QML" / "has no QML" | `find src -name '*.qml' \| wc -l` and `grep -rln QQuickWidget src tests --include=*.py` |
| "there are N tests" | run the gate (§3) and read its summary |
| "the widget kit is at X" | `ls src/presentation/ui/kit/` |
| "these rule files exist" | `ls .agents/rules/` |
| "this is a submodule" / "it is not" | `ls .gitmodules` |
| "the mypy debt list contains X" | read `[tool.mypy]` in `pyproject.toml` |
| "flaky UI tests are excluded from CI" | `grep -n 'integration/presentation/ui' scripts/ci-local.ps1` — an `--ignore` only counts if it is reached; one sat inside `if ($false)` for two weeks and a scan reported the tier as excluded |

---

## 2. Repository context

- Two **independent** repos, not a superproject/submodule pair: the shared
  `sagittarius_engine/` framework, and this app, where you work by default.
  Separate remotes, separate `.agents/`, separate task boards, **no pointer-bump
  step**. Confirm in one command: `ls .gitmodules`.
- **Read before touching anything**, in this order:
  [`CLAUDE.md`](../../CLAUDE.md) (its four "wrong once, costs a session" items),
  [`ONBOARDING.md`](../ONBOARDING.md) (§8 is the list of traps that have genuinely
  produced broken code here), then the rule files your change touches —
  `ls .agents/rules/` is the index, and `code-rule.md` is a navigation stub whose
  content was split out, so follow its links rather than reading it as law.
- **Language** (`CLAUDE.md`, "Language"): every `.md` document is English in the
  register `ONBOARDING.md` §10 defines; conversation follows the user's language;
  code, identifiers, docstrings, comments, commit subjects, UI strings and log
  messages are English.

---

## 3. The gate — non-negotiable

[`ci-rule.md`](../rules/ci-rule.md) §1 is the authority, and it says `-UnitOnly`
is *"diagnostic-only and never sufficient for handoff or commit"*.

```bash
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1   # Linux
```
```powershell
.\scripts\ci-local.ps1 -Full                                          # Windows
```

**Do not trust the console.** The script prints a `LOG_FILE:` line; `grep` that
file for `FAILED|ERROR|Traceback|ResourceWarning` before claiming anything is
green. Under offscreen Qt, harmless `TypeError` noise is flushed to stderr *after*
pytest's summary, so `| tail` shows you the noise instead of the result. Always
redirect, never pipe to `tail`.

**A missing `pwsh`, virtualenv, engine or system library is not a reason to skip
the gate** — install it ([`install-rule.md`](../rules/install-rule.md) §3) and run
it for real. Only once an install itself fails for a reason outside your control
have you hit a wall: say so plainly and do not commit code. Prompt/task/`.agents/`-only
edits are exempt — `ci-rule.md` §1, *"Exception — commits that touch no code file"*.

---

## 4. Commits

Read [`commit-rule.md`](../rules/commit-rule.md) before every commit; Conventional
Commits, atomic changes and pre-commit verification are enforced there, and the
mandatory `Co-Authored-By` trailer is **defined there** — read it there and name
the assistant that actually authored the commit. Never copy a trailer into a file
here; a hardcoded one is how this repo shipped a wrong attribution before. If you
were not asked to commit, don't.

---

## 5. Journals

Each agent has a journal at `.agents/Skills/<agent>.md`.

**Check whether yours exists — do not assume, in either direction.**

```bash
ls .agents/Skills/*.md          # which journals exist right now
```

That command is the answer because no sentence survived: an earlier prompt
asserted a journal was already written when none existed, and this file then
asserted the opposite and was false within hours. Both were accurate when typed.

Create yours on your first real learning. A journal is **not** a run log — add an
entry only for something that will change a future decision: a behaviour specific
to *this* architecture that surprised you; something that looked right and was
not, and why; a rejected change worth not re-proposing. Never "did X today", and
never generic Python/Qt advice from any textbook.

```markdown
## YYYY-MM-DD - [Title]
**Learning:** [what you discovered about this codebase]
**Action:** [how to apply it next time]
```

---

## 6. Boundaries every agent here shares

✅ **Always**
- One change per run, small enough to review in one sitting (< ~50 lines).
- Run the gate (§3) and read its log file before claiming a result.
- Keep the change inside this repo unless the cause is genuinely in the engine.
- Stay in your own lane — the agents overlap, and two fixing the same thing on the
  same day is how merge conflicts get generated unattended.

⚠️ **Ask first** (open a draft PR with the question rather than merging)
- Any new dependency, or any edit to `requirements.txt` / `pyproject.toml` / Ruff
  or mypy configuration.
- Any change under `sagittarius_engine/` — separate repo, separate remote,
  separate board, affecting every app built on the engine. Beware the drift this
  creates: the engine installed in the virtualenv can lag the engine repo while
  both claim the same version (`BUG-054`/`BUG-055` carry the account and the
  reinstall command).
- Architectural changes, and anything crossing a layer boundary.

🚫 **Never**
- Commit without the §3 gate passing, when your change touches code.
- Weaken, skip, delete or `xfail` a test to make your change pass.
- Break a public contract, or change behaviour in a run whose stated job is not to
  change behaviour.
- Touch the Obsidian vault under `Tasks/` (`.obsidian/` — it exists only on the
  maintainer's machine and must never be committed).
- Commit secrets, `.db` files, `database/`, `logs/`, `state/`, or a virtualenv.

---

## 7. Staying meaningful

A scheduled agent is only worth its run if the repo still contains the kind of
work it was written to find. Re-derive your target list by scanning every run;
never work from a list written into a prompt.

If, after an honest scan, there is nothing worth doing: **stop and open nothing.**
An empty run is a correct outcome and always better than a manufactured change. If
a whole agent goes several runs with nothing to find, that is a signal about the
agent, not the repo — say so in your journal and let a human decide.

---

## 8. Before committing an edit to any file in here

```bash
python3 scripts/check_skill_prompt_references.py
```

It re-reads every backticked repo-relative path and every markdown link in the
trees its own `PROMPT_TREES` lists — these prompts, plus `.claude/skills/` and
`.claude/rules/`, which are the same kind of followed-without-doubting document
— and fails on any that no longer exists. It is the mechanical half of §1. It
cannot tell you a claim went stale, but it does catch the rot that has actually
shipped here: a
prompt pointing at a file that is not there.
