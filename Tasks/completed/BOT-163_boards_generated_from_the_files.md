# BOT-163 — Two pull requests never edit the same board lines: the boards are generated from the files

**Status:** ✅ Done (2026-10-06)
**Board:** Decision: each task and bug file carries its own one-line `**Board:**` field, and `scripts/render_board.py` writes the count tables and the lists from the files (the towncrier "fragments" pattern), so no pull request edits a shared list. The hand-written boards until 2026-10-06 are frozen in `Tasks/history/`; a guard fails on a file with no board line, on a list or count table written back into `ROADMAP.md` or the bug board, and on an edit to the history.
**Source:** the user, 2026-10-06, after the third merge conflict in `Tasks/ROADMAP.md` in one day: "có cách nào giải quyết triệt đễ xung đột doc kiểu này ko, tào lau ghê luôn á" (is there a way to end these doc conflicts for good; this is a mess). Asked to choose, they picked "Fragment + sinh tự động (Recommended)" (fragments plus generation).
**Risk:** 🟡 — the board is how a session learns where the system stands; a file the renderer misses is a task nobody sees.
**Complexity:** M — one renderer, a migration of the open files' rows into the files, the guards, and every rule and skill that told a session to edit the boards.
**Depends on:** None

---

## 1. Context and problem

Every finished task or bug edited the same three places: the count table at the top of `Tasks/ROADMAP.md`, the top of its Completed list, and a row of its Backlog table (or the Bug Board's tables). Two pull requests open at once therefore always conflicted. On 2026-10-06 alone, PRs #384, #386, #387, #389 and #390 each needed a hand merge of `ROADMAP.md`, and one merge brought back a stale backlog row (`BOT-161`) that turned the board guard red after it was committed.

## 2. Decision

The towncrier "fragments" pattern: what a pull request adds lives in a file only it touches.

- **Fragment:** a `**Board:**` header field in each task and bug file (`- **Board:**` in a bug's bulleted header), with an optional `**Priority:**` for backlog tasks. A header field rather than YAML front matter, because every file already opens with `**Status:**`-style fields and the template says to delete front matter.
- **Generation:** `scripts/render_board.py` prints the task count table, the open bugs, In progress, the Backlog by priority, and Completed, Fixed and Cancelled newest first (by the date in `Status`); `--write` saves `Tasks/BOARD.md`, which is not tracked. Committing the output would bring the shared lines back.
- **History:** the hand-written boards are frozen verbatim in `Tasks/history/` (links rewritten to resolve from there). A closed file they list needs no board line; an open file always does.
- **What stays hand-written:** `ROADMAP.md` keeps the folder layout, how the board is made, the complexity scale and the owner's settled direction. Its epics table is dropped: `Tasks/epics/README.md` is the epic board. The bug board's README keeps the bug process.

## 3. Acceptance criteria

- [x] `python3 scripts/render_board.py` renders the real tree and exits 0: every open file carries a board line, every closed one has a line or is in the history.
- [x] `ROADMAP.md` and `bug_report/README.md` carry no count table and no list of tasks or bugs; a guard fails if one comes back.
- [x] The history is frozen by a hash pin, independent of line endings.
- [x] Every link in the hand-written boards and in the rendered board resolves.
- [x] ONBOARDING §3, §6, §12, `create-bug-report-rule.md`, the execute-task, create-epic, epic-025 and process-drift skills, both templates and `CLAUDE.md` describe the new bookkeeping; none tells a session to edit a shared list.

## 4. Testing

- `tests/unit/scripts/test_render_board.py`: 11 tests on small trees under `tmp_path` (fields, title, newest first, epic children, backlog by priority, counts, open files always need a line, history covers only closed files, an id inside another id is not a mention, history links). Mutation checks: reversing the order, dropping the closed-pool condition, ignoring the priority and dropping the mention's look-behind each turn one test red.
- `tests/unit/test_task_board_is_consistent.py`: `test_every_task_and_bug_file_carries_its_board_line`, `test_no_board_list_is_written_by_hand`, `test_the_history_is_frozen`, and the link check now covering the rendered board. Restoring the old `ROADMAP.md`, deleting `BOT-162`'s board line and appending to the history turn all three new guards red; restoring the files turns them green.

## 5. Implementation notes

- The migration copied each backlog file's description and priority out of its `ROADMAP.md` row into the file, and `BUG-143`'s row into its report. `BOT-043`, `BOT-108A` and `BOT-108B` had no row of their own; their lines are written from their headers.
- Eleven epics marked done (`BOT-042`, `BOT-073`, `BOT-078`, `BOT-086`, `BOT-095`, `BOT-105`, `BOT-106`, `BOT-107`, `BOT-109`, `BOT-112`, `BOT-115`) still sit in `backlog/`, as they did before. Their board lines say they are done; moving them changes the counts and is left to a separate clean-up.
- `scripts/render_task_counts.py` stays as the count module the renderer imports, so `.claude/settings.json`'s allow entry for it stays valid; the new script needs no settings change.
- `Tasks/epics/README.md` is still edited by hand, one row per epic. Two pull requests on one epic can still meet there; generating it from the epic READMEs is the same pattern, not done here.
