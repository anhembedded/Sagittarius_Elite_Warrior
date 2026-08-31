# CLAUDE.md — điểm vào cho Claude Code

**Đọc [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) trước khi viết dòng code đầu tiên.**
Nó là bản đồ quy trình: vòng đời task/bug, lệnh verification thật, bookkeeping, quyền hạn,
và §7 liệt kê những cái bẫy **đã thật sự gây ra code lỗi**.

---

## File này chỉ ĐIỀU HƯỚNG — cố ý không chép nội dung

Claude Code tự nạp `CLAUDE.md`; nó **không** tự nạp `.agents/rules/*.md` (trường
`trigger:` trong frontmatter các file đó là quy ước riêng của bộ rule, không phải cơ chế
nạp tự động của Claude Code). Vì vậy file này tồn tại để Claude có điểm vào.

**Không chép luật vào đây.** Bản sao rule luôn trôi khỏi bản gốc: sửa một nơi, quên nơi
kia, rồi bản sai vẫn được đọc. Cần thêm luật thì **sửa file rule gốc**, ở đây chỉ thêm
một dòng trỏ.

## Cần gì đọc ở đâu

| Việc | File |
| :--- | :--- |
| Bắt đầu, hoặc tiếp việc đang dở | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) — §10 là "bắt tay vào việc đang dở" |
| Phiên trước dừng ở đâu | [`.agents/Handover.md`](.agents/Handover.md) |
| Tìm luật theo chủ đề | [`.agents/AGENTS.md`](.agents/AGENTS.md) |
| Kiến trúc: tầng, interface, hợp đồng tường minh, tách theo abstraction level, đặt chỗ event | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Chất lượng code: typing, magic number, cohesion, lazy import | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Trước khi tuyên bố "xong" bất cứ thứ gì | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Trước mọi commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| User báo bug (**bắt buộc**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| Thêm/sửa log | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| Viết test | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| Tác vụ nền do user khởi tạo | [`.agents/rules/async-action-rule.md`](.agents/rules/async-action-rule.md) |
| Tầng presentation | [`.agents/rules/ui-rule.md`](.agents/rules/ui-rule.md) |
| Logic nghiệp vụ, dữ liệu trung thực | [`.agents/rules/domain-truth-rule.md`](.agents/rules/domain-truth-rule.md) |
| Thiếu công cụ để chạy verification | [`.agents/rules/environment-rule.md`](.agents/rules/environment-rule.md) |
| Cách dùng lại bộ rule này ở dự án khác | [`.agents/README.md`](.agents/README.md) |

---

## Ba thứ sai một lần là mất cả buổi

Chỉ giữ ở đây những cái mà agent có thể phá **trước khi kịp đọc rule**. Mọi thứ khác: xem
bảng trên.

1. **Không `git push` nếu user không yêu cầu rõ ràng.** `commit` là mặc định-hỏi; `push`
   là mặc định-cấm.

2. **Không tin console — đọc file log.** Một lần chạy có thể exit `0` trong khi ghi
   WARNING/ERROR mô tả một đường chạy đã hỏng lặng lẽ. Luôn `> logfile 2>&1` rồi `grep`,
   đừng `| tail` — `tail` vừa cho bạn xem nhầm nhiễu ở cuối, vừa có thể **cắt mất** đúng
   dòng lỗi thật.

3. **Việc thường bị để lại chưa commit giữa các phiên.** Bảng task trông như chưa ai đụng
   **cộng với** cây làm việc bẩn nghĩa là việc **đã làm rồi**, chỉ chưa ghi lại. Chạy
   `git status` và đọc diff trước khi kết luận một task còn nguyên.
