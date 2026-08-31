---
name: Agents Navigation
description: Stub điều hướng — chủ đề nào đọc file rule nào. Cố ý không chứa nội dung luật.
trigger: always_on
---

# Development Guidelines — file này chỉ ĐIỀU HƯỚNG

> **Agent mới bắt đầu ở đây:** đọc [`ONBOARDING.md`](ONBOARDING.md) trước file
> này. Nó là bản đồ quy trình; file này chỉ là mục lục theo chủ đề.

**Không chép luật vào file này.** Đây là chỗ dễ sinh bản sao trôi nhất: một
agent thấy tiện, chép vài mục "cho gọn", vài tuần sau bản chép và bản gốc mâu
thuẫn nhau và không ai biết bản nào đang được đọc. Cần thêm luật → sửa file
rule gốc, ở đây chỉ thêm một dòng trỏ.

## Chủ đề → file

| Chủ đề | Đọc ở |
| :--- | :--- |
| SOLID, tầng kiến trúc, Port/interface, hợp đồng tường minh, use case, tách file theo abstraction level, đặt chỗ event | [`rules/architecture-rule.md`](rules/architecture-rule.md) |
| Typing, readability, immutability, magic number, God object, lazy import, cohesion | [`rules/code-quality-rule.md`](rules/code-quality-rule.md) |
| Signal nội bộ hay Event Bus — ai sở hữu sự thật này | [`rules/event-rule.md`](rules/event-rule.md) |
| Hoãn một việc / chấp nhận một đánh đổi → phải có type hoặc test đại diện | [`rules/design-intent-rule.md`](rules/design-intent-rule.md) |
| Sở hữu tác vụ nền, stale callback, cancellation, Coordinator | [`rules/async-action-rule.md`](rules/async-action-rule.md) |
| Dữ liệu trung thực, ngữ nghĩa nghiệp vụ, snapshot, benchmark | [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) |
| Tầng presentation: view thuần khai báo, responsive, icon, injection defense, preview | [`rules/ui-rule.md`](rules/ui-rule.md) |
| Cách **viết** test | [`rules/testing-rule.md`](rules/testing-rule.md) |
| Cách **chạy** cổng CI, 4 tầng test, xử lý khi đỏ | [`rules/ci-rule.md`](rules/ci-rule.md) |
| Trước mọi commit | [`rules/commit-rule.md`](rules/commit-rule.md) |
| User báo bug (**bắt buộc**) | [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) |
| Thêm/sửa log | [`rules/logging-rule.md`](rules/logging-rule.md) |
| Thiếu công cụ/thư viện để chạy verification | [`rules/environment-rule.md`](rules/environment-rule.md) |
| Quy trình, quyền hạn, bookkeeping, các bẫy đã gây lỗi thật | [`ONBOARDING.md`](ONBOARDING.md) |
| Phiên trước dừng ở đâu | [`Handover.md`](Handover.md) |
