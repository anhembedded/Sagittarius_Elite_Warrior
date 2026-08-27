---
name: Python Code Rules (navigation stub)
description: Điểm vào lịch sử — nội dung thật đã tách thành 6 file rule chuyên biệt. File này chỉ điều hướng.
trigger: always_on
---

# PYTHON CODING STANDARDS — file này giờ chỉ ĐIỀU HƯỚNG

**Tách 2026-08-25.** File này từng chứa 9 nhóm quy tắc khác nhau trong 213
dòng: SOLID, Clean Architecture, CQRS, chất lượng code, async UI, dữ liệu
trung thực, tầng presentation, testing, pushback, git. Chúng **khác
abstraction level** với nhau — chính là thứ mà quy tắc
[Abstraction-Level Separation](architecture-rule.md) của repo này cấm gộp
chung một file. Đã tách theo đúng quy tắc đó.

> **Vì sao không xoá hẳn file này:** tại thời điểm tách, `code-rule.md` được
> tham chiếu **103 lần ở 49 file** — trong đó **7 file `.jules/*.prompt.md`
> là system prompt đang chạy** của các agent tự động (`bolt`, `doctor`,
> `janitor`, `palette`, `scout`, `scribe`, `sentinel`), mỗi file đều mở đầu
> bằng *"Read `.agents/rules/code-rule.md` before touching anything"*. Xoá
> file là 7 agent đó mất điểm vào. Đây đúng khuôn mẫu đã áp cho
> [`../AGENTS.md`](../AGENTS.md) khi file đó bị rút nội dung: giữ lại làm
> stub điều hướng thay vì xoá.
>
> **Sửa 2026-08-27 (`EPIC-012`):** 7 file đó đã dời từ `.jules/` sang
> `.agents/Skills/` (và `.jules/` bị xoá hẳn). Lý do giữ stub này không đổi;
> vị trí 7 file đọc nó thì đã đổi. Đếm lại bằng `grep -rl code-rule
> .agents/Skills/`, đừng tin con số "103 lần ở 49 file" — đó là snapshot của
> ngày tách, không phải hiện tại.

## Nội dung cũ giờ nằm ở đâu

| Nội dung cũ trong file này | Đọc ở |
| :--- | :--- |
| §1 SOLID; §2.2 Full Abstraction & ABC completeness; §2.5 Clean Architecture Layers; §2.6 Use Case/CQRS; Abstraction-Level Separation | [`architecture-rule.md`](architecture-rule.md) |
| §2.1 Typing; §2.3 Readability; §2.4 Immutability; §2.7 No Magic Numbers / No Nested Loops / No God Objects / No Lazy Imports / Single-Scope Cohesion | [`code-quality-rule.md`](code-quality-rule.md) |
| §2.8 Async UI Action Ownership & Cancellation; §3 Coordinator Pattern | [`async-ui-action-rule.md`](async-ui-action-rule.md) |
| §2.9 Truthful Data, Trading Semantics, Truthful Trading UI, Renderer benchmark, Chart host boundary, Counterintuitive Story Check | [`domain-truth-rule.md`](domain-truth-rule.md) |
| §3 UI & Presentation (trừ Coordinator) — MVP trio, responsive sizing, icon, preview.py | [`ui-presentation-rule.md`](ui-presentation-rule.md) |
| §4 Testing — cách viết test, invariant, Boundary Value Analysis, business acceptance | [`testing-rule.md`](testing-rule.md) |
| §4 phần CI — static quality, read-only gate, log scan bắt buộc | [`ci-rule.md`](ci-rule.md) §8 |
| §5 Proactive Pushback | [`../ONBOARDING.md`](../ONBOARDING.md) §7 |
| §6 Git Commits | [`commit-rule.md`](commit-rule.md) |

**Nếu bạn là agent vừa được bảo "đọc code-rule.md trước khi làm gì":** đọc
[`../ONBOARDING.md`](../ONBOARDING.md) trước, rồi mở đúng 1-2 file trong bảng
trên theo việc bạn đang làm. Không cần nạp cả 6 file.
