# EPIC-004C — Ghi nhận cổng rule mới vào `code-rule.md`/`ci-rule.md`/`ONBOARDING.md`

**Thuộc Epic:** [`EPIC-004`](../README.md)
**Trạng thái:** ✅ **Hoàn thành (2026-09-02)**
**Phụ thuộc:** [`EPIC-004B`](../completed/EPIC-004B_wire_gate_into_ci_local.md)

**Lệch khỏi §1 điểm 1, có chủ đích:** `code-rule.md` §4 không còn tồn tại — file đó đã bị tách
thành 6 file con từ trước (xem chính `code-rule.md`, giờ chỉ còn là navigation stub trỏ sang
`ci-rule.md`/`code-quality-rule.md`/...). Viết vào một §4 không tồn tại sẽ tái tạo đúng loại drift
mà `CLAUDE.md` tự cảnh báo ("mỗi bản copy rule đều trôi độc lập"). Nội dung thật đi đúng chỗ file
đã tách sẵn: mô tả cổng vào `ci-rule.md` §1 (đúng vị trí mô tả `ruff check`, cạnh mypy), ghi nhận
magic-number giờ máy verify được vào `code-quality-rule.md` §4. Đã làm cả 4 việc mục 1, cộng phát
hiện: `ONBOARDING.md` §5's dòng lệnh `ruff check`/`ruff format` sẵn có **đã tự động phủ** cả 6
nhóm rule mới (`extend-select` ở `pyproject.toml`, không phải tool/lệnh thứ hai như `mypy`) — nên
không thêm dòng lệnh mới, chỉ thêm 1 dòng chú thích nói rõ điều đó, tránh nhân bản một lệnh giống
hệt lệnh đã có.

---

## 1. Việc cần làm

Mirror đúng những gì `EPIC-002C` đã làm cho cổng `mypy`:

1. `.agents/rules/code-rule.md` §4 (Testing & Quality Assurance) — thêm 1
   bullet mô tả cổng mới, tương tự cách mypy được ghi (`EPIC-002B` note).
2. `.agents/rules/ci-rule.md` — nếu file này liệt kê từng bước của
   `ci-local.ps1 -Full`, thêm bước mới vào danh sách.
3. `.agents/ONBOARDING.md` §5 — thêm dòng lệnh verify nhanh (không qua toàn
   bộ `ci-local.ps1`) cho rule set mới, giống cách mypy đã có dòng lệnh bash
   riêng.
4. Xác nhận per-file-ignores đã ghi rõ **lý do** (assert-trong-test,
   Qt-override-camelCase) ngay tại chỗ dùng, không chỉ trong report — để
   agent sau không tưởng nhầm đây là "tắt rule vì ngại sửa".
