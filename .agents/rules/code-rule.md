---
name: Python Code Rules (navigation stub)
description: Điểm vào lịch sử — nội dung thật đã tách thành 6 file rule chuyên biệt. File này chỉ điều hướng.
trigger: always_on
---

# PYTHON CODING STANDARDS — file này giờ chỉ ĐIỀU HƯỚNG

Nội dung đã tách theo abstraction level. Stub được giữ vì `.agents/Skills/`
vẫn trỏ vào đây.

| Nội dung cũ | Đọc ở |
| :--- | :--- |
| SOLID; Full Abstraction & ABC completeness; Clean Architecture Layers; Use Case/CQRS; Abstraction-Level Separation | [`architecture-rule.md`](architecture-rule.md) |
| Typing; Readability; Immutability; No Magic Numbers / Nested Loops / God Objects / Lazy Imports; Single-Scope Cohesion | [`code-quality-rule.md`](code-quality-rule.md) |
| Async UI Action Ownership & Cancellation; Coordinator Pattern | [`async-ui-action-rule.md`](async-ui-action-rule.md) |
| Truthful Data, Trading Semantics, Renderer benchmark, Chart host boundary, Counterintuitive Story Check | [`domain-truth-rule.md`](domain-truth-rule.md) |
| UI & Presentation — MVP trio, responsive sizing, icon, `preview.py` | [`ui-presentation-rule.md`](ui-presentation-rule.md) |
| Testing — invariant, Boundary Value Analysis, business acceptance | [`testing-rule.md`](testing-rule.md) |
| CI — static quality, read-only gate, log scan bắt buộc | [`ci-rule.md`](ci-rule.md) §8 |
| Proactive Pushback | [`../ONBOARDING.md`](../ONBOARDING.md) §7 |
| Git Commits | [`commit-rule.md`](commit-rule.md) |

**Được bảo "đọc code-rule.md trước khi làm gì":** đọc
[`../ONBOARDING.md`](../ONBOARDING.md) trước, rồi mở đúng 1-2 file trên theo
việc đang làm. Không cần nạp cả 6 file.
