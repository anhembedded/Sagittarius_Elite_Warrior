# EPIC-004A — Đo baseline: rule Ruff `S`/`PLR2004`/`B`/`SIM`/`ERA`/`N` bắt bao nhiêu lỗi thật

**Thuộc Epic:** [`EPIC-004`](../README.md)
**Trạng thái:** ✅ **Hoàn thành (2026-08-22)**
**Phụ thuộc:** Không có — làm trước tiên, kết quả quyết định thiết kế của `EPIC-004B`.

**Báo cáo đầy đủ:** [`Tasks/reports/EPIC-004A_ruff_security_quality_baseline_audit.md`](../../../reports/EPIC-004A_ruff_security_quality_baseline_audit.md).

**Tóm tắt kết quả:** `ruff check --select S,PLR2004,B,SIM,ERA,N` trên toàn
repo ra 4491 lỗi thô — nhưng **~99% là nhiễu hệ thống có giải thích rõ ràng**,
đúng lớp phát hiện `EPIC-002A` từng gặp với mypy/`@Property`:
- `S101` (3588, "assert trần") — biến mất hoàn toàn khi loại `tests/`; idiom
  bắt buộc của pytest, không phải rủi ro thật.
- `N802`/`N815` (328) — xác nhận qua đọc code: override method bắt buộc của
  Qt (`paintEvent`, `eventFilter`) — Qt dispatch theo tên C++ camelCase, đổi
  tên sẽ phá override thật, không phải vi phạm naming.
- `S603`/`S106`/`S108` (4, toàn bộ ở `tests/`) — đọc từng dòng xác nhận false
  positive 100%: `subprocess.run([sys.executable, ...])` (interpreter tin
  cậy), chuỗi mock `"s"` cho `api_secret`, và **trớ trêu nhất** — `S108` báo
  "insecure temp file" ngay trong chính test bảo mật path-traversal
  (`test_security.py`), đường dẫn đó là fixture, không phải lỗ hổng.

**Tín hiệu thật, đáng làm gate: chỉ ~48 lỗi trong `src`+`scripts`** — 26
`PLR2004` (magic number, đúng câu hỏi gốc của user, và đúng rule đã ghi sẵn
trong `code-rule.md` §2.7 nhưng chưa từng được máy verify), 7 `S311` (dùng
`random` không phải `secrets` — toàn bộ ở 1 script demo/preview
`chart_card/__main__.py`, không phải đường production/tài chính thật, nhưng
đáng giữ rule bật để canh gác tương lai), và ~15 lỗi lặt vặt khác
(`SIM105`/`B905`/`ERA001`/...).

**Cấu hình đề xuất cho `EPIC-004B`** (per-file-ignores cho đúng 2 nguồn nhiễu
đã xác nhận, không cần cơ chế baseline-suppression phức tạp như `mypy`):

```toml
[tool.ruff.lint]
extend-select = ["S", "PLR2004", "B", "SIM", "ERA", "N"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S603", "S106", "S108"]
"src/presentation/ui/**" = ["N802", "N815"]
```

---

## 1. Mục tiêu

Trước khi nối rule set mới vào CI, cần biết **thật sự** nó sẽ báo bao nhiêu
lỗi trên codebase hiện tại. Không suy đoán — chạy thật, đếm thật, phân loại
thật, đúng phương pháp `EPIC-002A` đã chứng minh hiệu quả.

## 2. Việc đã làm

1. Xác nhận `pyproject.toml` chưa có mục `[tool.ruff]` nào — Ruff đang chạy
   rule set mặc định, chưa bật bất kỳ rule an toàn/chất lượng nào.
2. Chạy `ruff check --select S,PLR2004,B,SIM,ERA,N --statistics` trên toàn
   repo, rồi tách riêng `src`+`scripts` (loại `tests/`) để phân biệt nhiễu.
3. Đọc trực tiếp code tại từng loại lỗi tần suất cao/đáng ngờ (`N802`/`N815`,
   `S603`/`S106`/`S108`, `S311`) để xác nhận nhiễu hay thật — không suy đoán
   từ tên rule.
4. Không sửa bất kỳ lỗi nào trong task này — phạm vi chỉ đo và báo cáo, đúng
   nguyên tắc `EPIC-002A`. Sửa (nếu cần) thuộc `EPIC-004D`.

## 3. Kết quả

Xem tóm tắt ở trên và báo cáo đầy đủ tại
[`Tasks/reports/EPIC-004A_ruff_security_quality_baseline_audit.md`](../../../reports/EPIC-004A_ruff_security_quality_baseline_audit.md).
`EPIC-004B` có đủ số liệu để quyết định: bật rule set nào, ignore gì, và xác
nhận không cần baseline-suppression phức tạp vì tín hiệu thật chỉ ~48 lỗi.
