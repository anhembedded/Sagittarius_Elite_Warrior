# EPIC-004C — Ghi nhận cổng rule mới vào `code-rule.md`/`ci-rule.md`/`ONBOARDING.md`

**Thuộc Epic:** [`EPIC-004`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-004B`](../incomplete/EPIC-004B_wire_gate_into_ci_local.md)

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
