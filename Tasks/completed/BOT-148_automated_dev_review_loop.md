# BOT-148 — A developer and a reviewer session run in a loop until the pull request is ready to merge

**Status:** ✅ Done (2026-10-04)
**Source:** The user, 2026-10-04, after `send_message` proved unreliable: a proposal for a Python orchestrator over headless `claude -p`, then *"ok làm theo 5 thay đổi đó, tạo PR đi. miễn sau thành 1 quy trình tự động đến lúc merge là được"* ("do those five changes and open the PR; what matters is that it becomes one automatic process up to merge").
**Risk:** 🟡 — the loop commits, pushes and posts comments on its own; a defect in its stop conditions would loop or publish too early.
**Complexity:** M — a stdlib-only package of ten modules, its tests, and the rule text that makes it the process.
**Depends on:** None

---

## 1. Context and problem
Every review round needed the user to relay it between two sessions:
- **PR comments (PR #328):** both sessions post as the user's GitHub account, and a subscription does not wake on its own account's comments.
- **`send_message` (PR #329):** the connector is not attached to new sessions, and a session without Remote Control has no reply address.

The user proposed a script that runs both roles headless. That proposal had no draft in the repository, so the package was written from the proposal and the five changes the evaluation asked for.

## 2. Acceptance criteria
- [x] **The reviewer cannot write.** It runs with `--tools Read,Glob,Grep`. The loop writes every diff and commit log it reads.
- [x] **Replies are validated.** Both roles answer through `--json-schema`, and every finding keeps a stable id across rounds. A malformed reply is asked again, in the same session, once.
- [x] **The loop runs the commit tier itself** after every developer round. A red result goes back to the developer, not to the reviewer.
- [x] **Every child call is isolated and bounded.** It runs without the parent session's variables, with a timeout and a per-call budget.
- [x] **There is an outer loop.** After a local APPROVE the loop pushes, opens the pull request, waits for `ci-local.ps1 -Full`, gives the same reviewer session the gate's logs, and posts its comment. A red gate goes back into the loop. It never merges.
- [x] **It stops for a person** on any of these:
  - the rounds run out;
  - a finding stays open after two answers;
  - the gate does not finish.

## 3. Design
- **Ports.** `ClaudeRunner` and `GitHub` are ABCs; the CLI is the composition root. Git is a thin `Workspace` over the real binary.
- **Two roles, two lifetimes.** The developer gets a fresh session each round. The reviewer keeps one session per pull request (ONBOARDING §7) through `--resume`, which keeps the session id. This was measured on 2.1.289, as was everything in the `claude_runner` docstring.
- **`FindingLedger` holds open findings by id.** It counts how many reviews in a row kept a finding open after the developer answered it; that count is the deadlock stop.
- **Gate logs.** They are served by redirect from another host, so a download tries `gh api` first and falls back to plain HTTPS (with `GH_TOKEN` when set).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/review_loop/` (new) | `replies`, `claude_runner`, `workspace`, `commit_tier`, `prompts`, `roles`, `loop`, `github`, `publish`, `cli` |
| `scripts/dev_review_loop.py` (new) | entry point |
| `tests/unit/scripts/review_loop/` (new) | doubles and four test files |
| `.gitignore` | `.review-loop/` |
| `.claude/ONBOARDING.md` §7, `.claude/skills/pr-review/SKILL.md` §9, `CLAUDE.md`, the provenance ledger | the loop is the process |

## 5. Testing
- **Unit tests, 31:**
  - against a real git repository and a bare `origin` on `tmp_path`;
  - the roles scripted through `ScriptedClaude`, GitHub through `FakeGitHub`, both subclasses of their ports;
  - a fake `claude` executable proves the scrubbed environment and the argument vector end to end.
- **Mutation checks, each turned red:**
  - the deadlock threshold;
  - the reviewer's `--resume`;
  - the environment scrub;
  - the delta's base;
  - skipping the commit tier;
  - "ready" despite a red gate;
  - the no-commit check;
  - the verdict-line strip;
  - the wait for a green head;
  - the disclosure re-ask;
  - the `--session-id` flag.

## Implementation notes (written when done)
- **Added beyond the proposal**, each because a loop without it could not finish on its own:
  - a dirty tree, or a fix claimed with no commit, goes back to the developer;
  - the first round stops with "no change" when nothing was committed;
  - the reviewer's gate-round `comment` is the durable PR comment;
  - after a red gate the loop runs again from the reviewer's open findings.
- **One mutation first survived:** "ready despite a red gate". It got its own test: a red gate that the reviewer approves still goes back to the developer.
- **Smoke test** with the real `claude` 2.1.289 through `CliClaudeRunner`:
  - the reviewer reported having only Read, Glob and Grep, and the file it was asked to write does not exist;
  - the developer appended a line and committed it.
- **Commit tier** (`ci-local.ps1 -SkipTests`) and `tests/unit/architecture`: green before the commit.
- **Made compatible with `EPIC-031`, which landed on `master-warrior` during this task:**
  - every session gets its id up front (`--session-id`), and the developer's commits end with `Claude-Session:` for that id;
  - the loop writes the reviewer's machine-read lines itself: reviewed head, the one `Verdict:` line, and the reviewer's `Claude-Session:` as the last line;
  - a gate-round review without the coverage disclosure is asked again once;
  - the commit tier runs `scripts/check_commit_messages.py` over the branch, against the freshly fetched `origin/<base>`;
  - "ready" waits until every check and status on the head is green, `independent-review` included.

  A real call confirmed that `--session-id` sets the id `-p` reports.
- **Not verified:** a full run through push, gate and comment against GitHub. The first real task run is that check.
