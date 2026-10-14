# EPIC-041G — Runtime scenarios, crosscutting concepts (as a rule table), a threat model and quality risks exist at app level

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — four docs, one of them a table over the rules
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041D](EPIC-041D_app_context_and_module_map.md)

---

## 1. Context and problem
- Cross-module runtime is described only per epic (design 038 §5, design 039 §9) and in `Docs/SDD/04_boot_and_configuration.md`.
- Crosscutting rules live in `.claude/rules/` with no human-facing index.
- No threat model exists although the app holds API keys, places real-money orders and runs on a VPS.
- Quality goals and known risks are scattered across PRO-005, PRO-008 and case studies.

## 2. Acceptance criteria
- [ ] `Docs/ARCHITECTURE/runtime.md`: boot, shutdown, a real-money order from a bot to Binance, loss of the user stream, and a host restart, in PlantUML sequences that cross modules.
- [ ] `Docs/ARCHITECTURE/crosscutting.md`: one table, topic → rule clause → guard or gate → reason doc. No prose rule is restated (D1).
- [ ] `Docs/ARCHITECTURE/security.md`: a short STRIDE over API keys, the VPS, the order path and the plan file, each threat with its existing mitigation (code, rule or runbook step) or marked open. A rule clause asks for its review on any PR touching `support/binance_gateway`, credentials or `deploy/`.
- [ ] `Docs/ARCHITECTURE/quality-risks.md`: 3–5 quality goals with measurable scenarios, the known risks and the debt ratchets, linked to PRO-005/PRO-008 and `Docs/METRICS/REPORT.md`.
- [ ] `Docs/ARCHITECTURE/deployment.md`: desktop on Windows and host on a systemd VPS, linking `Docs/OPERATIONS/headless_runbook.md`; no runbook step copied.

## 3. Design
Only the crosscutting topics this app has (D7, thin first). Crosscutting is a join over the rules, never a second rulebook (D1). Security is scoped to what can lose money or a key. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Sequences: design 038 §5, design 039 §9, `Docs/SDD/04_boot_and_configuration.md`.
- Threats: `Docs/OPERATIONS/headless_runbook.md` §3 (credentials), `test_order_submission_mode_live_is_restricted.py`, `test_every_secret_store_is_in_the_contract_suite.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/ARCHITECTURE/runtime.md`, `crosscutting.md`, `security.md`, `quality-risks.md`, `deployment.md`, `diagrams/*.puml` | New |
| one rule clause for the security review trigger | New clause, tagged `[review]` |

## 5. Testing
Documentation-only except the one rule clause; the 041B checker passes on every new file; PlantUML syntax-checked. Kind of pull request: doc.

## Implementation notes (written when done)
