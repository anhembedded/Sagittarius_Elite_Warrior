# CLAUDE.md — điểm vào cho Claude Code

**Đọc [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) trước khi viết dòng code đầu tiên.**
Nó là bản đồ quy trình: bố cục 2 repo, vòng đời task/bug, lệnh verification thật trên Linux,
bookkeeping, và §8 liệt kê những cái bẫy **đã thật sự gây ra code lỗi** trong repo này.

---

## File này chỉ ĐIỀU HƯỚNG — cố ý không chép nội dung

Claude Code tự nạp `CLAUDE.md`; nó **không** tự nạp `.agents/rules/*.md` (trường
`trigger: always_on` trong frontmatter các file đó là quy ước riêng của
[`.agents/Skills/`](.agents/Skills/README.md) — 7 file `*.prompt.md` là system
prompt cho các agent chạy định kỳ không người trông, không phải cơ chế nạp tự
động của Claude Code). Vì vậy file này tồn tại để Claude có điểm vào, đúng vai
trò [`.agents/AGENTS.md`](.agents/AGENTS.md) đang đóng cho các agent đó.

> **Sửa 2026-08-27 (`EPIC-012`):** 7 file này từng nằm ở `Sagittarius_Elite_Warrior/.jules/`
> (một thư mục tách biệt, quy ước riêng — xem lịch sử ở
> [`EPIC-011`](Tasks/epics/EPIC-011_dong_bo_skill_dinh_ky_jules/README.md)). Đã dời hẳn
> sang `.agents/Skills/`, xoá `.jules/`, và thiết lập Routine chạy mỗi 2
> ngày/agent thay vì phụ thuộc lịch của một dịch vụ ngoài. Xem
> [`EPIC-012`](Tasks/epics/EPIC-012_di_chuyen_skills_ve_agents_va_lich_2_ngay/README.md).

**Không chép luật vào đây.** Repo này đã dính bệnh bản-sao-trôi **hai lần**: `AGENTS.md` từng
gần như là bản sao nguyên văn của `code-rule.md` và trôi độc lập (kèm một lỗi thật: ghi cứng sai
trailer `Co-Authored-By`); `code-rule.md` phải tách làm 6 file vì gộp 9 nhóm luật khác
abstraction level. Bản sao thứ ba cũng sẽ trôi. Cần thêm luật thì **sửa file rule gốc**, ở đây
chỉ thêm một dòng trỏ.

## Cần gì đọc ở đâu

| Việc | File |
| :--- | :--- |
| Bắt đầu, hoặc tiếp việc đang dở | [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md) — §12 là "bắt tay vào việc đang dở" |
| Kiến trúc: tầng, Port/ABC, hợp đồng tường minh (cấm duck-typing ngầm), Shared Kernel, đặt chỗ event, abstraction | [`.agents/rules/architecture-rule.md`](.agents/rules/architecture-rule.md) |
| Chất lượng code: typing, magic number, cohesion, lazy import | [`.agents/rules/code-quality-rule.md`](.agents/rules/code-quality-rule.md) |
| Trước khi tuyên bố "xong" bất cứ thứ gì | [`.agents/rules/ci-rule.md`](.agents/rules/ci-rule.md) |
| Trước mọi commit | [`.agents/rules/commit-rule.md`](.agents/rules/commit-rule.md) |
| User báo bug (**bắt buộc**) | [`.agents/rules/bug-fix-rule.md`](.agents/rules/bug-fix-rule.md) |
| Thêm/sửa log | [`.agents/rules/logging-rule.md`](.agents/rules/logging-rule.md) |
| Viết test | [`.agents/rules/testing-rule.md`](.agents/rules/testing-rule.md) |
| Hệ thống đang ở đâu, còn bug nào mở | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) |

---

## Bốn thứ sai một lần là mất cả buổi

Chỉ giữ ở đây những cái mà agent có thể phá **trước khi kịp đọc rule**. Mọi thứ khác: xem bảng trên.

1. **Không `git push` nếu user không yêu cầu rõ ràng.** `commit` là mặc định-hỏi; `push` là
   mặc định-cấm. Mỗi repo là một lần xác nhận riêng.

2. **Không tin console — đọc file log.** Cổng bắt buộc là
   `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`. Nó in ra `LOG_FILE:`; phải `grep` file đó
   cho `FAILED|ERROR|Traceback|ResourceWarning` rồi mới được nói "xanh". Ở chế độ offscreen, Qt
   xả rất nhiều `TypeError` **vô hại** ra stderr **sau** dòng tổng kết pytest, nên `| tail` sẽ
   cho bạn xem nhầm đống nhiễu đó. Luôn `> logfile 2>&1`, đừng `| tail`.

3. **Hai repo độc lập, không phải submodule.** `Sagittarius_Engine` (framework) và
   `Sagittarius_Elite_Warrior` (app, thư mục này) có remote riêng, `.agents/` riêng, bảng task
   riêng. Commit/push tách biệt, **không** có bước "bump" nào. Đừng ghi task của app vào
   `Tasks/README.md` của engine và ngược lại.

4. **Việc thường bị để lại chưa commit giữa các phiên.** Bảng task trông như chưa ai đụng cộng
   với cây làm việc bẩn nghĩa là việc **đã làm rồi**, chỉ chưa ghi lại. Chạy `git status` ở
   **cả hai** repo và đọc diff trước khi kết luận một task còn nguyên.

---

## Ngôn ngữ

Trao đổi với user, task file, bug report, ROADMAP: **tiếng Việt**.
Code, tên biến, docstring, comment, commit subject: **tiếng Anh**.
Chuỗi hiển thị trên UI: **tiếng Việt**.
