# EPIC-002C — Ghi nhận cổng `mypy` vào `ci-rule.md`/`ONBOARDING.md`

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-002B`](EPIC-002B_wire_mypy_into_ci_local.md) — tài liệu hoá đúng cấu hình đã chọn, không viết trước khi biết chốt gì.

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
