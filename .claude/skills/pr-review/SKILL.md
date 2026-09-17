---
name: pr-review
description: Review a pull request, a branch, or an uncommitted diff in this repository against the repository's own rules — scope, architecture, code quality, tests, verification evidence, guards and baselines, bookkeeping. Use when asked to review a PR, to check a diff before merging, or to audit a branch somebody else wrote.
---

# PR Review

Answer two questions, in order: **does this obey the rules already written down**, and **is the
evidence that it works real or merely claimed**. "Looks fine" is not a review — a green suite here
has shipped defects before.

**This file holds no rule text.** Each row is a question, how to check it, and the rule that
decides it. Read the clause in its own file before citing it; never quote a rule from memory or
from here. And never treat any list of rules as complete: `CLAUDE.md` records an agent reading the
seven rules a table listed, calling that the whole set, and violating three of the six it never
saw. Your first command is `ls .claude/rules/`, the directory, not a table.

## Rule keys

| Key | File | | Key | File |
| :-- | :--- | :-- | :-- | :--- |
| `arch` | [architecture-rule.md](../../../.claude/rules/architecture-rule.md) | | `log` | [logging-rule.md](../../../.claude/rules/logging-rule.md) |
| `cq` | [code-quality-rule.md](../../../.claude/rules/code-quality-rule.md) | | `ui` | [ui-presentation-rule.md](../../../.claude/rules/ui-presentation-rule.md) |
| `ci` | [ci-rule.md](../../../.claude/rules/ci-rule.md) | | `async` | [async-ui-action-rule.md](../../../.claude/rules/async-ui-action-rule.md) |
| `test` | [testing-rule.md](../../../.claude/rules/testing-rule.md) | | `truth` | [domain-truth-rule.md](../../../.claude/rules/domain-truth-rule.md) |
| `bug` | [bug-fix-rule.md](../../../.claude/rules/bug-fix-rule.md) | | `onb` | [ONBOARDING.md](../../../.claude/ONBOARDING.md) |
| `commit` | [commit-rule.md](../../../.claude/rules/commit-rule.md) | | `pit` | [rules/pitfalls/](../../rules/pitfalls/tests.md) (`tests.md`, `ui.md`, `source.md`) |

`ls .claude/rules/` is the real index — read every file the diff's paths touch, including any not
keyed above. Unknown word → `Docs/VOCABULARY/README.md`. Every rule clause carries an enforcer tag
(`[gate]`, `[guard: file]`, `[review: row]`, `[eye]`); the rows below are the `[review: …]` half.

## 1. Load

```bash
git fetch origin <pr-branch> <base-branch>
BASE=origin/<base-branch>; HEAD=origin/<pr-branch>   # HEAD=HEAD for a working diff
git log --oneline "$BASE..$HEAD"
git diff --stat -M "$BASE...$HEAD"    # -M so a pure move shows as a rename
git diff -M "$BASE...$HEAD"
which pwsh ruff python3; ls .venv 2>/dev/null
```

Read the **whole** diff; if a tool truncates, page through it and say in the report what you could
not read. The description is a claim to test, never a substitute. A diff hunk cannot show that its
file is now 420 lines or that a Port's other implementers broke — work against the fetched tree.
No checkout (web session, another AI): use the GitHub MCP tools or `gh` if `which gh` finds it, and
still fetch whole files when a check needs more than the hunk. A missing tool is something
`install-rule.md` says to install, not to report as unverifiable; what you truly cannot run becomes
a question about the author's evidence (§B), never an invented finding and never a skipped one.

Read `CLAUDE.md` and `onb` §7 (what an author may decide alone), §8 (traps that really broke code
here), §10 (language/register), §11 (reporting), §12.5 (settled principles).

## 2. Triage — which checklists fire

| Diff touches | Run |
| :--- | :--- |
| anything | A, K, L |
| `src/` `tests/` `scripts/` `pyproject.toml` `requirements.txt` | + B, C, D |
| `src/domain/**` `src/application/**` | + F |
| `src/presentation/**` | + G, H, and C4 |
| tests, or source that should have brought one | + E |
| logging, or any new failure path | + I |
| `tests/unit/architecture/**`, a baseline/allowlist, a new top-level `src/` package | + J |
| `CLAUDE.md`, anything under `.claude/` | + `python3 scripts/check_skill_prompt_references.py`, and for a rule, skill, agent or template: `python3 -m pytest tests/unit/architecture/test_claude_tree_is_wired.py tests/unit/test_rule_navigation_is_complete.py -q` |
| `Docs/CASE_STUDIES/**` | + E14, and `python3 -m pytest tests/unit/architecture/test_case_study_index_is_consistent.py -q` |
| only the documentation-only paths `onb` §7 defines | A, K — see `ci` §1's exception first |

The exception is narrow: one file able to affect build, lint, types, runtime or tests brings the
whole gate back. A mixed commit is a code commit.

## 3. Checklists

`gate` = a machine already decides it; your job is to confirm the gate ran (§B), not re-lint by eye.
`eye` = nothing checks this but you.

### A. Scope and intent
1. Does the diff do what the description says — no more, no less? Anything unmentioned is an unstated decision or scope creep.
2. One logical change? (`commit` §4)
3. Claims to be a pure move? `git diff -M --stat` — a real move is a rename with a similarity index; then read every non-rename hunk and ask what behaviour it changes.
4. Any decision taken that belonged to the user? (`onb` §7's three groups) Outside those three, deciding alone is correct and is not a finding.
5. New mechanism invented without surveying existing solutions? (`onb` §12.5 principle 5) "We surveyed and built our own" is a legitimate outcome; no survey is a finding.
6. Is a deferral written down with its reason and its row in the plan, or silently dropped?

### B. Verification evidence
1. Full gate, not a diagnostic mode? (`ci` §1–§2 — `-UnitOnly`/`-SanityOnly`/`-SkipLint`/`-SkipTests` are never sufficient)
2. Was the **log file** scanned, or only the console? (`CLAUDE.md` §2, `ci` §8) "Tests passed" is not that claim.
3. Every `WARNING`/`ERROR`/`CRITICAL` hit named and explained — real defect (then `bug` in full) or justified expected condition? "Already there before" means search `Tasks/bug_report/incomplete/`, not move on.
4. A failure called flaky without evidence? (`ci` §3, §5)
5. Whatever you *can* run, did you? `ruff check src tests`, `ruff format --check src tests`, the `python3` guards in `tests/unit/architecture/`, `python3 scripts/check_skill_prompt_references.py`.
6. Was the gate run on **the tree under review**, or on an earlier one? `ci` §1's two-tier clause (user decision 2026-09-16) makes this the whole question: one full gate per pull request is correct and expected — several commits sharing it is not a finding — but it must be the **last** commit's tree, and each intermediate commit must show the 1-second static checks plus `pytest tests/unit/architecture -q`. A green run proves nothing about commits made after it, and "I ran the gate, then fixed one more thing" is the ordinary way a branch ends up unverified. Compare the run's own timestamp with the head commit's, and check that nothing is left uncommitted:

```bash
# B2/B3 — the scan the evidence must contain. Offscreen Qt noise lands after
# pytest's summary, so never judge by `| tail`; redirect and grep the LOG_FILE.
grep -nE '\b(FAILED|ERROR|Traceback|ResourceWarning)\b' <LOG_FILE>
grep -E '\- (WARNING|ERROR|CRITICAL) \-' <LOG_FILE>

# B6 — the gate's log against the commit it is offered as evidence for.
ls -l --time-style=+%Y-%m-%dT%H:%M logs/ci-local-latest.log
git log -1 --date=iso --format='%H %ad %s'
git status --short          # anything here was never in the verified tree
```

### C. Architecture (`arch`) — almost all `eye`
1. Layer crossed the wrong way? §3 — `grep -rn "sagittarius_engine" src/domain src/application --include=*.py`; only the two Shared Kernel symbols named there are allowed.
2. A new-tree package importing the legacy tree? Boundary guards in `tests/unit/architecture/`; read `tests/unit/architecture/allowlist_module_boundaries.txt` and J1.
3. A Port gained an `@abstractmethod` with implementers left behind? §2, `onb` trap 11 — grep implementers in **`src/`, `scripts/` and `tests/`**.
4. Every boundary contract a named type? §2.1 — `hasattr`/`getattr` probing and unannotated `view` are the forbidden shape; `typing.Protocol` is **not**.
5. `Protocol` chosen over ABC — does the docstring name which of the three reasons applies? §2.1.
6. Two abstraction levels sharing a file or a directory? §5 rules 1–2.
7. File over 400 lines, class over 15 public methods? §5 rule 4 — commands under D. Applies to `tests/` and `tools/` too.
8. New event on the bus or on a Qt signal? §6.2's one question: would another screen wanting this be absurd? Absurd → private signal; reasonable → bus + exactly one normalising Feed.
9. A known extension point existing as a seam in code, not only in prose? §7, §7.2.1. Tell of a closed design: *"to add X we must touch N existing files."*
10. Multiple inheritance, or a hard-coded instantiation where a port was expected? §2.

### D. Code quality (`cq`)
1. `gate` Magic numbers/strings — `ruff check` (`PLR2004`).
2. `gate` Mutable defaults, bug patterns, dead code, unsafe `subprocess`, hardcoded secrets, naming — `ruff check` (`B`, `ERA`, `S`, `N`, `SIM`; `ci` §1).
3. `eye` A bare suppression or a new per-file-ignore with no reason — check the `pyproject.toml` diff; each one there carries an inline reason.
4. `eye` Function-local/lazy imports — grep below. It also matches top-level `if TYPE_CHECKING:` and `if __name__ == "__main__":`; read §4's clause and decide per hit, and a hit predating the branch is not this change's finding.
5. `eye` `Any` where `Union`/`Optional`/`TypeVar`/`Generic` fits; an unannotated signature. `mypy` gates `src`+`scripts` at a baseline and **excludes `src/presentation/` wholesale** — there you are the only check.
6. `eye` File over 400 lines — command below.
7. `eye` Class over 15 public methods — command below.
8. `eye` Single-Scope Cohesion vs Abstraction-Level Separation: was a merge justified by *the same lifecycle*, or only by "same feature"? `cq` §4 **and** `arch` §5 rule 3 — read both; this is the one place they genuinely collide.
9. `eye` A God object — a class or module with a second reason to change.
10. `eye` A mutated argument, or a nested loop that should be a named helper.
11. `eye` Low-level `os.path`/byte work inline in an application or composition-root layer.

```bash
# D4
grep -rnE '^[ \t]+(import [A-Za-z_]|from [A-Za-z_.]+ import)' src scripts tests --include=*.py
# D6
git diff --name-only "$BASE...$HEAD" -- '*.py' | xargs -r wc -l | sort -rn | head
# D7 — prints UNPARSED rather than skipping quietly; pyproject's requires-python
# is above 3.11, and PEP 695 generics fail to parse on an older interpreter.
git diff --name-only "$BASE...$HEAD" -- '*.py' | xargs -r python3 -c '
import ast, sys
for path in sys.argv[1:]:
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError as exc:
        print(f"UNPARSED {path}: {exc}"); continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            pub = [n.name for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and not n.name.startswith("_")]
            if len(pub) > 15:
                print(f"{path}:{node.lineno} {node.name}: {len(pub)} public methods")
'
```

### E. Tests
1. Proof named at the right level, or an existing test shown to already cover it? (`ci` §6, `test` §1; module work: `Docs/HLD/10_test_strategy.md`)
2. Does a test prove the **business** promise or only that a private call happened? (`truth`)
3. Any `sleep` used to synchronise? `grep -rn "sleep(" tests/ --include=*.py` on changed files — wait on a named signal/state/`qtbot.waitUntil`, at every tier.
4. A test weakened, skipped, `xfail`ed or deleted to get green? `git diff --stat -M "$BASE...$HEAD" -- tests/`. Blocking wherever it appears.
5. A **new** test added under `tests/sanity/`? (`test` §1 — a feature adds zero; a new one means the existing ones were written wrong)
6. A port hand-substituted instead of drawing the boundary at configuration? (same section)
7. Counts, full-dict equality, or float `== 0` in a new assertion? (`onb` §8 traps 1–4)
8. A new field on a frozen dataclass without a default? (trap 5)
9. Bug fix: regression test written **first**, confirmed failing for the right reason, at a tier that actually reaches the failure? (`bug` §4 — a `Mock` standing in for the crashing method cannot reproduce it)
10. Bug fix: does it fix the mechanism or patch the one reported call site? (`bug` §2, `onb` §12.5 principle 1 — the general solution is required; cost is not a reason to prefer local)
11. A widget or module **rewritten together with its tests**? Then E4's file-level check is not enough: the new tests can be more numerous and still cover less. List what the deleted tests asserted, say where each guarantee now lives, and name the ones deliberately dropped with the reason (a framework now does it; the feature is gone).
12. Where a new test pins a **wiring or a rule** — a signal connection, an enable/disable gate, a guard's threshold, a confirmation before a destructive act — **would it fail if that line were removed?** Do not reason about it; break the line and run. (Not every test needs this: one that feeds a pure function its own inputs already shows it can fail. It is the tests whose subject is *that two things are connected* which pass just as happily when they are not.) `EPIC-025` PR 0.4b shipped a search box whose two `textEdited` connections could be deleted with all 22 tests in the file still green — every test drove the setter method, and typing is a different code path. Three commands, and the answer is evidence rather than opinion:

```bash
# E12 — the test that cannot fail is not a test (`onb` §8 traps 1-4 are the
# same disease). Break the one line the test names, run only that file,
# restore. Copy first: an interrupted review must not leave the break behind.
cp src/<path>.py /tmp/keep.py
sed -i 's/^\(\s*\)<the line the test relies on>/\1pass  # broken on purpose/' src/<path>.py
python3 -m pytest tests/<its test file> -q   # expect exactly the one failure
cp /tmp/keep.py src/<path>.py && git diff --stat -- src/<path>.py   # empty
```
13. **Does every hand-written double name the interface it implements?** (`test` §2, [`CS-001`](../../../Docs/CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md)) A double assembled from the calls the code makes always passes — `BUG-124`'s `_Bus` had `publish` **and** `on` **and** `subscribe`, the union of two interfaces plus an invented verb, and the Start button shipped dead with the file green. Read each double's methods against the real collaborator's; where the real thing is in-memory and free, ask why it was doubled at all. The tell is a double whose shape matches the test, not the production object.
14. **Defect got through a green gate?** Then `bug` §6.5 wants a case study in the same commit — `Docs/CASE_STUDIES/`, one screen, naming which net was silent and what checks it now — and the check it names must exist, not be advice. `python3 -m pytest tests/unit/architecture/test_case_study_index_is_consistent.py -q` is the mechanical half.
15. **Does the diff add a class that acts at construction — subscribes, registers, starts a timer — and does anything in `src/`/`scripts/` construct it?** (`test` §2, [`CS-002`](../../../Docs/CASE_STUDIES/CS-002_the_subscriber_nobody_built.md)) A test always constructs its subject, so a green test file says nothing about whether production does. `BUG-126`'s `SystemErrorFeed` subscribed to the two failure events `EPIC-008` had found unsubscribed, passed its own tests, and was constructed by nobody for two epics. `python3 -m pytest tests/unit/architecture/test_a_bus_subscriber_is_constructed.py -q` is the mechanical half for bus subscribers; for anything else, ask where the construction is and read that line. Grepping the class name is **not** the check — that is how HLD §3.5 came to list a dead class as live, off a docstring mention.

### F. Domain truth (`truth`)
1. Anything presenting a convenience as a fact — coverage proven by row count, a universal hard-coded exchange filter, an ETA stated as certainty?
2. Signal, order intent, fill, position entry/exit and short entry kept as distinct facts, not one `BUY`/`SELL` label doing two jobs?
3. Does the UI promise a capability the engine does not yet deliver?
4. Snapshot immutable, bounded, carrying enough provenance to describe itself honestly?
5. A benchmark claim with stated workload, cache condition and measurement method?

### G. Async UI / action ownership (`async` — read all of it, it says so itself)
1. Every user-initiated background action carrying an immutable action identity, and every receiving slot verifying it is still active before touching state?
2. Cancellation cooperative and idempotent — no success/failure published after a cancel, no blind force to `IDLE`?
3. A Coordinator owning FSM state or its own action-id bookkeeping? (It must not — one owner.)
4. A Coordinator DI-registered or self-resolving instead of constructor-injected and Presenter-owned?
5. Important work placed *after* a call that can throw inside a `@safe_ui_action` slot? (`onb` traps 7–8)

### H. UI presentation (`ui`)
1. A new `.qml` file, global stylesheet, palette or theme library? Run the guards in `tests/unit/architecture/`.
2. New per-widget styling where the baseline may only shrink? (also J1)
3. A hand-drawn substitute for a standard `QMainWindow` part, or a rebound standard shortcut? ("Desktop UX principles"; `Docs/HLD/11_desktop_workbench.md`)
4. Fixed pixel size on a container holding text or widgets? (a leaf glyph may be; a container may not)
5. A new UI package without its `preview.py`? (`tests/unit/presentation/ui/test_preview_fixtures_exist.py`)
6. Table column widths declared once and bound to both header and rows?
7. Every dialog cancellable, every long operation showing progress, every error naming what failed?

### I. Logging (`log`)
1. Every new logger under `"App."`? `grep -rn 'getLogger(' src --include=*.py`, read each non-`"App"` hit; `tests/unit/test_logging_namespace_guard.py` is the mechanical half.
2. A new `logger.info()` inside a hot loop (per trade/candle/tick/frame)? (`onb` trap 9)
3. Does it log the **decision** — which backend, which fallback, why — not just the outcome? (§2–§3)
4. Narrowest level that fits, and a stable bracketed tag? (§6, §8)
5. Has the new diagnostic been seen to emit through the **real** logging config? (§9)

### J. Guards, baselines, allowlists
1. Did an allowlist or baseline **grow**? `git diff "$BASE...$HEAD" -- tests/unit/architecture/`, then `wc -l` before/after each `allowlist_*.txt` / `baseline_*` file `ls tests/unit/architecture/` prints. Shrink-only ratchets: a new line needs an argued justification and usually means the change is wrong.
2. Does a removed line correspond to a real fix, or to a rule that stopped being checked? A line removed because the import became legal is a retirement; removed with the violation intact is a hole.
3. A new top-level `src/` package registered in `tests/unit/architecture/scanned_roots_registry.py` and covered by the relevant guards? Without a row an empty scan passes quietly forever.
4. A guard's own file moved — did its path constant follow?
5. A new abstract method, config key or engine API arriving without its declaration/registry row? (`Docs/HLD/`, `src/infrastructure/engine_adapters/`; `.claude/skills/epic-025/SKILL.md` §2 lists the module-split invariants with their check commands)
6. Does a guard the diff runs into encode a rule a **newer ADR reversed** — a ratchet written under a doctrine a later decision overturned? Read `ci` §5.5, which says what the author must have done: the guard's own documented exemption naming the ADR, the ceiling *not* raised, the reversal recorded in that guard's docstring. A raised ceiling, or a guard quietly loosened to get the diff through, is a finding even when the new code is correct.

### K. Bookkeeping and documents
1. Board reflects the work? (`Tasks/ROADMAP.md`, `Tasks/epics/README.md`; `onb` §6 calls this the most commonly botched part)
2. Bug fix: report filed, moved to `completed/`, row moved on `Tasks/bug_report/README.md`? (`bug` §7)
3. Code and design drifted? (`Docs/HLD/`, `Docs/SDD/` — when they disagree, the PR is where it is fixed)
4. **Behaviour drifted?** A diff that changes a flow, adds a named failure, or stops promising something updates that use case's own file under `Docs/SPEC/` — and its *Proven by* row moves with the test. `grep -rln '<the port or screen the diff touches>' Docs/SPEC/` finds the affected ones; `tests/unit/architecture/test_spec_index_is_consistent.py` catches only the mechanical half (a missing section, an unlisted id, a cited test path that no longer exists), never a flow that silently changed under an unchanged description.
5. A term coined without its `Docs/VOCABULARY/README.md` entry in the same change?
6. Every `.md` English, book register — why before what, a worked example over adjectives? (`onb` §10)
7. A rule file added without its row in `CLAUDE.md`'s table? (an unlisted rule is an unread rule)
8. `CLAUDE.md` or anything under `.claude/` edited — `python3 scripts/check_skill_prompt_references.py` still clean, and `.claude/README.md`'s inventory re-rendered rather than hand-edited? (an empty tree is an error, not a skip)
9. A count, version or date written into a briefing as current state? (`onb` §13)

### L. Commits (`commit`)
1. Conventional Commits — allowed type, real scope, imperative subject? (§2)
2. A `fix:` body stating the root cause? (§5, `bug` §6)
3. The AI trailer present, naming the assistant that actually wrote it? (§3 — read the trailer there, never copy one)
4. Any scratch file, `.db`, virtualenv, `logs/`, `state/`, secret or leftover `print()`? (§4; read a suspicious file's contents before calling it harmless)
5. A dependency or tool-config change nobody asked for? `git diff "$BASE...$HEAD" -- requirements.txt pyproject.toml` (`onb` §7 puts this in ask-first)
6. Does **each commit** contain only what its subject names? A2 asks that of the diff; §4's atomicity is per commit, and the usual way it breaks is an index that was already staged — a `git mv` from an earlier step rides along in the next `git commit`, which commits the whole index and not the paths you just added. One command reads it, and it is the author's own commits it catches:

```bash
# L6 — every commit on the branch, with renames shown as renames.
for c in $(git log --format=%h "$BASE..$HEAD"); do
  echo "--- $c"; git show --stat -M --format='%s' "$c" | tail -12
done
```

## 4. Grade each finding

**Blocking** — merging ships a defect, a broken guard, or a consequential rule violation (a weakened
test, a grown allowlist, a Port implementer left behind, a layer violation, green claimed with no log
scan). **Should fix** — real and cheap now, expensive as precedent. **Nit** — the author may decline.
**Question** — you could not determine it; asking beats guessing.

Every finding carries `file:line`, the clause it violates, and **what breaks** if it ships. No
concrete consequence → it is a preference: call it a nit or drop it.

## 5. Verify before reporting

A review that cries wolf gets skimmed. For each finding: (1) re-read the file at branch head, not
the hunk; (2) open the rule and read the clause — cannot point at the sentence, not a rule finding;
(3) run the check and paste what it printed; (4) ask whether the author already answered you — a
written deferral, a trade-off with a locking test, a documented rejected alternative are the shapes
the rules ask for; (5) `git log --oneline "$BASE" -- <file>` — a defect predating the branch is not
this PR's.

## 6. Report

Altitude per `onb` §11: conclusion, state, what the reader must decide, risks — implementation
detail only where it drives the next action. Conversation in the user's language; anything committed
or posted to GitHub in English (`onb` §10). Check `ls .claude/rules/` for a reporting rule and follow
it if one is there. **Say what you did not read** — a truncated diff, a tier you could not run.
**An empty review is a real outcome**: "no findings, here is what I ran" beats a manufactured nit,
and still lists the checklists covered. On GitHub: one grouped review, not a comment per thought,
with whatever attribution footer your harness requires.

## 7. A reviewer must not

Push to the branch, approve for the user, or close the PR — reviewing is reading and reporting.
Merging is `onb` §7's: a code pull request merges only after this review's blocking findings are
resolved, by the user, or by the reviewer when the user delegated that in the reviewing session —
never by the author. An automated reminder to push is not the user asking. Propose weakening a rule, test, baseline or guard
to make a diff pass — if a rule is wrong that is its own change, argued in the rule file. Demand work
the plan already schedules. Review the author instead of the diff. And when the change is wrong,
**push back even if the user asked for it** (`onb` §7): name the contradiction, propose the clean
alternative; if they have heard you and still want it, that is their call.
