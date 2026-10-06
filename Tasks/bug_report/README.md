# 🐞 Bug Board — Sagittarius Elite Warrior

Every reported bug of the app has a file here, apart from the task board, because a task board
shows an open bug nowhere. Bugs are not counted among the tasks.

- **Folders:** `incomplete/` holds the bugs not fixed yet, and every new bug starts there;
  `completed/` holds the fixed ones, with their own screenshots and evidence.
- **Names:** `BUG-XXX_slug.md`, numbered one above the highest number in **both** folders.
  `tests/unit/test_task_board_is_consistent.py` fails on two files with one id, in every pool.
- **The board is generated.** Each bug file carries its one-line entry, its `- **Board:**`
  field, and `python3 scripts/render_board.py` lists the open and the fixed bugs from them
  (`BOT-163`). Nobody edits a shared list, so two pull requests never touch the same lines.
- **When a bug is fixed:** `git mv incomplete/BUG-XXX_*.md completed/` (with its images), set
  its `Status`, and rewrite its `Board` line to state the root cause and the fix.
- **Process:** filing follows [`create-bug-report-rule.md`](../../.claude/rules/create-bug-report-rule.md);
  fixing follows [`fix-bug-rule.md`](../../.claude/rules/fix-bug-rule.md): root cause first, a
  regression test red for the right reason before the fix, kept forever.

The board as it was written by hand until 2026-10-06, with the fixed bugs before that date, is
frozen in [`../history/BUG_BOARD_until_2026-10-06.md`](../history/BUG_BOARD_until_2026-10-06.md).
