# BOT-134 — The AI process as a system: a strategic review

**Status:** ✅ Done 2026-09-16
**Source:** the user, 2026-09-16 — *"audit, cố vấn quy trình liên quan tới AI của tôi trong dự án,
rút ra các case study, cải thiện v.v.... đưa những thứ lỏng lẻo về chuẩn"* ("audit and advise on my
AI-related process in the project, draw out case studies, improve, bring the loose parts to
standard"), then, mid-way: *"tui ko yêu cầu bạn kiểm tra lỗi, tôi muốn tính chiến lược, góc nhìn hệ
thống, triết lý"* ("I did not ask you to check for errors; I want strategy, a systems view, the
philosophy").
**Risk:** 🟢 — documentation, two guards extended by one parameter each, one CI workflow made equal
to the local gate, three scratch files deleted. No application behaviour changes.
**Complexity:** 🟡 `M` — the reading was the work.

---

## 1. What was asked, and what "done" meant

The deliverable is the review itself:
[`Tasks/reports/ai_process_strategic_review_2026-09-16.md`](../reports/ai_process_strategic_review_2026-09-16.md)
— the process drawn as one loop, its philosophy stated in one table with what enforces each
principle, seven process case studies with evidence, and ten ranked recommendations each saying
what a "yes" commits the user to. The drift found on the way was fixed in the same branch and is
listed in that report's §5, not repeated here.

## 2. Why the drift was fixed rather than only reported

`ONBOARDING.md` §7 lets an agent decide alone inside the task's scope; the user's own words were
"bring the loose parts to standard". Every fix below is a correction of a document to what a
machine or a later decision already says, or a one-parameter extension of a guard that exists:

- `commit-rule.md` now defers to `ONBOARDING` §7 for authority and to `ci-rule` §1 for the gate's
  cadence instead of restating both (it disagreed with both).
- `.agents/Skills/README.md` quotes the sentence `ci-rule` §2 actually contains.
- `fix-bug-rule.md` §6.5 no longer names the case-study length cap (it said 60; the guard holds 35).
- `ONBOARDING.md`: `report-rule`, `install-rule` and `code-rule` join the reading order; the
  QML row says retired; the "always carries a few `I001`" sentence is corrected; the traps heading
  drops its count and gains trap 14; §12.1 says what a single-repository checkout means.
- `install-rule.md`: Option 1 is the clone-then-install form that works (the previous command is
  the one `ci.yml` documents as having failed every CI run); §2b gains the Linux bootstrap as run.
- `.github/workflows/ci.yml` lints `scripts/` and ignores `tests/testnet` as the local gate does;
  `ci-rule` §7's table gains the two rows.
- `.claude/rules/testing.md` and `.claude/rules/async-ui-action.md` route those two rules by path;
  their front matter changed from `on_demand` to `on_file_change` so the pointer guard holds them.
- `README.md`: the two cells that still said QML was current.
- `.claude/skills/test-health/SKILL.md`: the rule it audits is `testing-rule.md`, not the stub; and
  whether it is scheduled is answered by a command, not a paragraph.
- `Tasks/ROADMAP.md`: this task, the recount, and rows for the eight task files that had none;
  `Tasks/epics/EPIC-005_…/README.md` names its three sub-sub-tasks by id.
- `tests/unit/test_rule_navigation_is_complete.py` covers `ONBOARDING.md`;
  `tests/unit/test_task_board_is_consistent.py` fails on a task file with no row and on an epic
  sub-task its README does not name.
- `pr_body.txt`, `message_for_reviewer.txt`, `get_file_content.py` deleted from the root.

## 3. Second round, 2026-09-17 — the recommendations applied

The user asked for the rules to be short and token-cheap and for the recommendations to be
applied (*"sửa luôn những gì bạn đề xuất"*). Report §5 carries the table; in one line each: the
twelve rules rewritten as tagged norms (1 976 → 453 lines, section numbers kept), two retired
rules deleted, six path pointers, GitHub CI runs `ci-local.ps1 -Full`, the count table is computed
and guarded, the authority table rewritten with independent review before a code merge, the
seven persona agents and their Routines retired for two audits that always leave a file. Still
left to the user: pinning `ruff` (a dependency change). No new guard file was added in either
round — report PCS-4 says why; the one new check lives in the existing board guard.

## 4. Verification

- Per commit: `scripts/ci-local.ps1 -SkipTests` (ruff, format, mypy, reference check) and
  `pytest tests/unit/architecture tests/unit/test_rule_navigation_is_complete.py tests/unit/test_task_board_is_consistent.py -q`.
- Both extended guards were confirmed red before the rows and pointers were written (eight orphan
  files, three unnamed sub-tasks, one rule missing from the reading order) and green after.
- Full gate on the final tree: `logs/ci-local-20260916-145211.log` — 4958 passed / 4 skipped,
  coverage 95.35 %, 0 log records at WARNING or above; grepped for
  `FAILED|ERROR|Traceback|ResourceWarning`, the only hits being a parametrize id.
- The environment for all of the above was built from a bare container by the sequence now in
  `install-rule.md` §2b.
