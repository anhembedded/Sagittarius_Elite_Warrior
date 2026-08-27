# Development Guidelines

> **Agent mới bắt đầu ở đây:** đọc [`ONBOARDING.md`](ONBOARDING.md) trước file
> này. Nó là bản đồ quy trình — bố cục 2 repo, vòng đời task/bug, lệnh chạy
> test thật trên từng OS, bookkeeping `ROADMAP.md`, và danh sách các bẫy đã
> thật sự gây ra code lỗi trong repo này.

**Sửa 2026-08-21:** file này trước đây chứa gần như nguyên văn nội dung đã
có sẵn ở nơi khác — SOLID, Clean Architecture, Typing, QML, Async Action
Ownership, Testing... đều là bản sao (nhiều đoạn từng chữ) của
[`rules/code-rule.md`](rules/code-rule.md); 2 dòng cài đặt là bản sao của
[`rules/install-rule.md`](rules/install-rule.md). Bản sao trôi độc lập khỏi
bản gốc theo thời gian — sửa 1 nơi, quên nơi kia, 2 file dần lệch nhau.
**Nghiêm trọng hơn:** mục "Git Commits & Version Control" ghi cứng
`Co-Authored-By: Antigravity <noreply@google.com>` — sai, và vi phạm thẳng
[`rules/commit-rule.md`](rules/commit-rule.md) tự nói rõ: trailer phải khớp
đúng AI thực sự tạo ra commit, gán nhầm cho tool khác là "not acceptable,
even for consistency with older commit history". Không rõ vì sao dòng đó có
trong file — có thể một phiên chạy bằng Antigravity (Google) từng sửa file
này. Đã xoá toàn bộ nội dung trùng lặp/sai thay vì "move" — không có gì để
move, bản đầy đủ hơn đã tồn tại sẵn ở các file `rules/` tương ứng.

## Đọc gì thay vì file này

| Chủ đề | Đọc ở |
| :--- | :--- |
| SOLID, Clean Architecture, Port/ABC, CQRS, Abstraction-Level Separation | [`rules/architecture-rule.md`](rules/architecture-rule.md) |
| Typing, immutability, magic number, God object, lazy import, Single-Scope Cohesion | [`rules/code-quality-rule.md`](rules/code-quality-rule.md) |
| Async UI action ownership, cancellation, Coordinator Pattern | [`rules/async-ui-action-rule.md`](rules/async-ui-action-rule.md) |
| Dữ liệu trung thực, ngữ nghĩa giao dịch, snapshot, benchmark | [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) |
| Tầng presentation (Python), MVP trio, `preview.py` | [`rules/ui-presentation-rule.md`](rules/ui-presentation-rule.md) |
| Cách viết test, invariant, Boundary Value Analysis | [`rules/testing-rule.md`](rules/testing-rule.md) |
| Cài đặt `sagittarius_engine` (2 phương án) | [`rules/install-rule.md`](rules/install-rule.md) |
| Quy tắc commit, trailer `Co-Authored-By` đúng | [`rules/commit-rule.md`](rules/commit-rule.md) |
| CI/CD, 4 tầng test | [`rules/ci-rule.md`](rules/ci-rule.md) |
| Quy trình sửa bug | [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) |
| Logging | [`rules/logging-rule.md`](rules/logging-rule.md) |
| QML chi tiết | [`rules/qml-rule.md`](rules/qml-rule.md) |

**Tách rule 2026-08-25:** `rules/code-rule.md` (213 dòng, 9 nhóm quy tắc khác
abstraction level) đã được tách thành 6 file chuyên biệt — 6 dòng đầu bảng
trên. Bản thân `code-rule.md` **được giữ làm stub điều hướng, không xoá**: nó
đang được các file trong `.jules/` (system prompt của agent tự động) đọc như
điểm vào bắt buộc, cùng lý do `AGENTS.md` này từng được giữ lại.

**Sửa 2026-08-26 (`EPIC-011`):** đoạn trên trước đây ghi "7 file
`.jules/*.prompt.md`". `EPIC-011` đã rút phần chung của 7 prompt ra
`.jules/README.md`, nên giờ **chỉ file đó** trỏ tới `code-rule.md`. Lý do giữ
stub không đổi. Đếm bằng `grep -rl code-rule .jules/`.

**Sửa 2026-08-25:** bảng trên trước đây có thêm dòng "Bảo mật →
`rules/sentinel-rule.md`" — file đó **chưa bao giờ tồn tại** trong
`.agents/rules/` (lúc đó có 7 file rule; sau đợt tách cùng ngày là 13 — luôn
xác nhận bằng `ls .agents/rules/`).
Đã xoá dòng link gãy đó. Nội dung bảo mật thật nằm ở `.jules/sentinel.prompt.md`
(system prompt của agent Sentinel) và `Tasks/epics/EPIC-004_static_security_and_quality_analysis/`.

File này giữ lại (không xoá hẳn) vì `AGENTS.md` là tên file nhiều công cụ
AI tự động tìm và đọc theo mặc định — mất file này thì công cụ đó không còn
điểm vào nào cả. Vai trò của nó bây giờ chỉ là **điều hướng**, không phải
nguồn nội dung.
