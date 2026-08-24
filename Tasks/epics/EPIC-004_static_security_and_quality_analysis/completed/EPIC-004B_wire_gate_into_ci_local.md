# EPIC-004B — Nối rule set (`S`/`PLR2004`/`B`/`SIM`/`ERA`/`N`) vào `ci-local.ps1 -Full`

**Thuộc Epic:** [`EPIC-004`](../README.md)
**Trạng thái:** ✅ Hoàn thành (24/08/2026)
**Phụ thuộc:** [`EPIC-004A`](../completed/EPIC-004A_ruff_baseline_audit.md) — đã đo baseline, có cấu hình đề xuất sẵn.

---

## 1. Việc cần làm

1. Thêm `[tool.ruff.lint]` + `extend-select` + `per-file-ignores` vào
   `pyproject.toml` đúng cấu hình đã đề xuất ở `EPIC-004A`:
   ```toml
   [tool.ruff.lint]
   extend-select = ["S", "PLR2004", "B", "SIM", "ERA", "N"]

   [tool.ruff.lint.per-file-ignores]
   "tests/**" = ["S101", "S603", "S106", "S108"]
   "src/presentation/ui/**" = ["N802", "N815"]
   ```
2. Chạy lại `ruff check src tests scripts` sau khi thêm config — xác nhận
   con số lỗi còn lại khớp đúng ~48 lỗi thật mà `EPIC-004A` đã đếm (không
   phải số khác do per-file-ignore áp sai phạm vi).
3. **Không tự sửa 48 lỗi đó trong task này** — phạm vi chỉ là bật gate.
   Quyết định: gate có nên fail cứng ngay (chặn commit tới khi `EPIC-004D`
   dọn xong ~48 lỗi), hay tạm thời chỉ cảnh báo (không fail) cho tới khi dọn
   xong — **cần hỏi user trước khi chọn**, không tự quyết theo tiền lệ
   `EPIC-002B` (mypy chọn baseline-gate vì 183 lỗi quá nhiều để sửa ngay;
   ở đây chỉ 48 lỗi, có thể khả thi để sửa xong trước rồi mới bật gate cứng
   luôn — khác hẳn tình huống mypy).
4. Verify qua đúng shell PowerShell 5.1 thật (không chỉ tool `PowerShell`
   chạy `pwsh`/PS7+ — bài học `BUG-029` cùng phiên này: một script tưởng
   chạy được hoá ra chỉ chạy được trên PS7+, không phải PS5.1 mà
   `ci-local.ps1` tự khai hỗ trợ).

## 2. Kiểm thử

Không có test Python — đây là cấu hình lint/CI. Verify bằng chạy thật
`ci-local.ps1 -Full` (đọc `logs/ci-local-latest.log` đầy đủ, không chỉ nhìn
terminal — đúng bài học `BUG-029`/`BUG-030`) và xác nhận số lỗi mới xuất
hiện đúng như dự đoán từ `EPIC-004A`.

## 3. Kết quả hoàn thành

- Đã bật cứng `S`, `PLR2004`, `B`, `SIM`, `ERA`, `N` trong gate Ruff hiện có.
- Per-file ignore chỉ giữ các false positive đã xác minh: pytest assertions /
  fixture literals, Qt override naming, tên package PascalCase và randomness
  trong chart demo.
- `EPIC-004D` được dọn cùng đợt nên không cần giai đoạn warning-only.
- `ci-local.ps1 -Full` trên Windows: Ruff lint/format, Mypy, 1.695 test và
  38 sanity test đều pass; log scan sạch.
