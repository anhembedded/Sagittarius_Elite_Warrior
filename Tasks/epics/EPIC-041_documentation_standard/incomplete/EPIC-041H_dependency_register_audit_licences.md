# EPIC-041H — The dependency register is generated from the lock file, and CI audits vulnerabilities and licences

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — a generator, two CI steps; touches the workflow, so it waits for the owner
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041A](EPIC-041A_docs_skeleton.md)

---

## 1. Context and problem
- `requirements.lock` and `engine.ref` pin every dependency (`tests/unit/scripts/test_dependency_pins.py`), but nothing records why a library was chosen, its licence, or known vulnerabilities.
- No `pip-audit`, licence check or SBOM runs.

## 2. Acceptance criteria
- [ ] `scripts/render_dependencies.py` writes `Docs/ARCHITECTURE/dependencies.md` from `requirements.lock` and the installed metadata: name, version, licence, and the modules that import it. A hand-kept `why` column covers the top libraries only (PySide6, pyqtgraph, the Binance client, the Engine), each linking its decision.
- [ ] A guard fails when the committed register differs from a fresh render.
- [ ] CI runs `pip-audit` on the lock file and a licence check against an allowlist (MIT, BSD, Apache-2.0, PSF, LGPL for PySide6); an unknown licence or a known vulnerability fails the run.
- [ ] SBOM generation stays out of scope (owner decision, 2026-10-14).

## 3. Design
**Waits for the owner's explicit approval** before it starts: it changes `.github/workflows/` and may add `pip-audit` to the tooling (ONBOARDING §7, commit-rule §3). The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Pins: `tests/unit/scripts/test_dependency_pins.py`, `scripts/engine_pin.py`.
- Workflow step shape: `.github/workflows/ci.yml`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/render_dependencies.py`, `Docs/ARCHITECTURE/dependencies.md` | New |
| `.github/workflows/ci.yml` or `scripts/ci-local.ps1` | Audit and licence steps |
| tests for the generator | New |

## 5. Testing
Generator unit tests; a probe with a planted disallowed licence; the CI run on the PR shows both steps. Kind of pull request: code.

## Implementation notes (written when done)
