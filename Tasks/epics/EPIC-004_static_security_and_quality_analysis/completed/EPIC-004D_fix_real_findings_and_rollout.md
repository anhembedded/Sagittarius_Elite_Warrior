# EPIC-004D — Sửa ~48 lỗi thật (`EPIC-004A`) + lộ trình mở rộng rule set

**Thuộc Epic:** [`EPIC-004`](../README.md)
**Trạng thái:** ✅ Hoàn thành (24/08/2026)
**Phụ thuộc:** [`EPIC-004A`](../completed/EPIC-004A_ruff_baseline_audit.md) cho danh sách lỗi.

---

## 1. Việc cần làm

1. Sửa 26 `PLR2004` (magic number) trong `src`/`scripts` — đặt tên hằng số
   theo đúng `code-rule.md` §2.7 đã có sẵn. Từng file 1 commit nhỏ, không
   gộp thành 1 commit khổng lồ khó review.
2. Xem lại 7 `S311` ở `chart_card/__main__.py` — xác nhận lại đây thật sự là
   script demo (không phải đường production) trước khi quyết định sửa
   (đổi `random` → `secrets`, dù không cần thiết về bảo mật) hay chỉ
   per-file-ignore kèm comment giải thích ngay tại chỗ.
3. Dọn ~15 lỗi lặt vặt còn lại (`SIM105`, `B905`, `ERA001`, `B007`, `B027`,
   `N803`, `N806`, `N812`, `N818`, `SIM102`, `SIM108`, `N999`).
4. **Sau khi dọn sạch:** cân nhắc siết gate ở `EPIC-004B` từ "cảnh báo" sang
   "fail cứng" nếu ban đầu chọn hướng mềm.
5. Lộ trình mở rộng dài hạn (không cấp thiết): xem xét bật thêm `PLR`
   (Pylint refactor rules rộng hơn `PLR2004`) hoặc `C901`
   (mccabe complexity) — cả hai đều **chưa đo baseline**, cần lặp lại đúng
   quy trình `EPIC-004A` trước khi bật, không đoán.

## 2. Kết quả hoàn thành

- Đã thay magic number production/script bằng constant có tên rõ nghĩa.
- Đã sửa các finding thật thuộc `SIM105`, `B905`, `ERA001`, `B007`, `B027`,
  `N806`, `N812`, `N818`, `SIM102` và `SIM108`.
- Đã xác minh `chart_card/__main__.py` là visual demo và ignore `S311` đúng
  một file, có comment giải thích trong cấu hình.
- Đã mở gate fail-cứng; `ruff check src tests scripts` sạch.
- Full CI pass: Mypy 134 source files, 1.695 test, 38 sanity test, coverage
  93,05%, không có WARNING/ERROR/CRITICAL trong run log.
- Việc cân nhắc toàn bộ `PLR`/`C901` vẫn phải bắt đầu bằng một epic baseline
  riêng; không bật thêm trong task này.
