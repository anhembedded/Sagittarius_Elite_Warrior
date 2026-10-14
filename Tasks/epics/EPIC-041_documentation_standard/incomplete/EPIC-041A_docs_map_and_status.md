# EPIC-041A — `Docs/README.md` maps every reader question to one file, and every doc carries a status line

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟢 — low; documents and generated indexes
**Complexity:** S — one new index and one line per existing file
**Epic:** [EPIC-041](../README.md)
**Depends on:** None

---

## 1. Context and problem
- `Docs/` has nine top-level areas and no map. Two files in `Docs/Diagrams/` say they are superseded (`architecture.md`, `ui_architecture.md`), three older notes there carry no status, and `Docs/SDD/README.md` still reads "Draft round 3" though its sections changed until 2026-10-06.
- A reader cannot tell which file answers a question, or whether it is still true.

## 2. Acceptance criteria
- [ ] `Docs/README.md` lists each reader question (what the app must do, how modules connect, how to run the host, why a decision was taken, what a word means, what the numbers say) and the one file that answers it.
- [ ] Every `.md` under `Docs/` starts with a `Status:` line: `Current`, `Superseded by <link>` or `Historical`.
- [ ] `CLAUDE.md`'s "Where to read what" table gains one row pointing at `Docs/README.md`; the rule-navigation guard passes.
- [ ] No file content other than the status line and the map changes.

## 3. Design
The map lists questions, not folders (decision D2). Status vocabulary is the three words of D6. Files whose own text already says "superseded" get that status with the link they name; files nobody can vouch for get `Historical` rather than `Current`. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Navigation table: used the `CLAUDE.md` "Where to read what" table and its guard `tests/unit/test_rule_navigation_is_complete.py`.
- Superseded markers: reused the wording already in `Docs/Diagrams/architecture.md` and `Docs/HLD/05_engine_app_split.md`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/README.md` | New map |
| every `Docs/**/*.md` | A `Status:` line |
| `CLAUDE.md` | One table row |

## 5. Testing
Documentation-only (ONBOARDING §7): `python3 scripts/check_skill_prompt_references.py`, the document guards, and the `-Full` run on the PR. A grep shows every `Docs/**/*.md` has a status line. Kind of pull request: doc.

## Implementation notes (written when done)
