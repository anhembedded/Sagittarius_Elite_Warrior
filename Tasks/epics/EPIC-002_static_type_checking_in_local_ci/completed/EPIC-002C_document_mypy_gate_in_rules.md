# EPIC-002C — Ghi nhận cổng `mypy` vào `ci-rule.md`/`ONBOARDING.md`

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** ✅ **Hoàn thành (2026-08-21)**
**Phụ thuộc:** [`EPIC-002B`](../completed/EPIC-002B_wire_mypy_into_ci_local.md) — tài liệu hoá đúng cấu hình đã chọn, không viết trước khi biết chốt gì.

**Đã làm cả 4 việc mục 2, cộng 1 sửa lỗi thời phát hiện thêm khi làm:**
`ci-rule.md` §1 thêm mô tả bước `mypy` đúng scope thật đã chọn. `ONBOARDING.md` §5 thêm lệnh Linux tương đương, **và sửa luôn 1 câu sai**: mục này từng ghi "PowerShell không chạy được trên máy Linux hiện tại" — sai, `pwsh` có sẵn qua snap, đã tự verify bằng cách chạy thật `ci-local.ps1 -Full` (kể cả bước `mypy` mới) qua `pwsh` thành công. `ONBOARDING.md` §8 thêm bẫy thứ 11 kể lại `BUG-026` (đổi tên mục thành "Mười một cái bẫy"). `BUG-026` report đã trỏ ngược sang epic này từ trước (làm lúc filing epic).

---

## 1. Mục tiêu

Một agent (người hoặc AI) mới vào repo phải biết `mypy` là một phần bắt buộc
của "Full gate" — không lặp lại đúng lỗ hổng đã dẫn tới `BUG-026`: công cụ có
sẵn nhưng không ai biết phải chạy nó.

## 2. Việc cần làm

1. `.agents/rules/ci-rule.md` §1 ("Full gate") — thêm dòng mô tả bước `mypy`
   đúng vị trí 2 bước `ruff` hiện có, kèm phạm vi/cấu hình thật đã chọn ở
   `EPIC-002B` (không viết chung chung "có chạy mypy" mà không nói rõ scope).
2. `.agents/ONBOARDING.md` §5 ("Chạy verification THẬT") — thêm lệnh `mypy`
   tương đương cho Linux (đúng tinh thần mục đó: mọi rule file chỉ ghi lệnh
   PowerShell, phải có bản dịch Linux đi kèm).
3. `.agents/ONBOARDING.md` §8 ("Mười cái bẫy...") — cân nhắc thêm 1 mục mới
   kể lại chính `BUG-026` làm ví dụ, theo đúng phong cách các mục khác trong
   danh sách đó (mỗi mục đều là chuyện thật đã xảy ra, kèm dẫn chứng).
4. Cập nhật `Tasks/bug_report/completed/BUG-026_*.md` thêm 1 dòng trỏ ngược
   sang epic này (bug report → giải pháp hạ tầng do nó sinh ra), giữ đúng
   mạch tài liệu.
