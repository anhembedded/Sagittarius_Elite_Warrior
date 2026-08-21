# EPIC-002B — Nối `mypy` (chế độ tối thiểu) vào `ci-local.ps1 -Full`

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-002A`](../completed/EPIC-002A_mypy_baseline_audit.md) — cần biết baseline trước khi chọn cấu hình.

---

## 1. Mục tiêu

Làm cho lớp lỗi của `BUG-026` (instantiate 1 class thiếu method abstract của
interface) **không thể lọt qua `ci-local.ps1 -Full`** nữa — đã verify thật
`mypy` bắt được lỗi này ngay cả ở cấu hình mặc định, không cần `--strict`.

## 2. Ràng buộc thiết kế (theo đúng khuyến nghị đã đưa ra, chưa tự quyết cấu
hình cụ thể — cần dựa trên kết quả `EPIC-002A`)

- **Không bật `--strict`** ở bước này — rủi ro chặn đứng mọi commit vì lỗi
  kiểu dữ liệu cũ không liên quan tới thay đổi đang làm.
- Nếu `EPIC-002A` phát hiện có lỗi baseline đáng kể: cần cơ chế **không chặn
  lỗi cũ, chỉ chặn lỗi mới** (ví dụ file baseline liệt kê lỗi đã biết tại
  thời điểm bật gate, hoặc giới hạn phạm vi ban đầu theo module sạch nhất
  tìm được ở `EPIC-002A`, mở rộng dần sau).
- Chạy **read-only** giống `ruff check`/`ruff format --check` hiện tại — CI
  không tự sửa code, chỉ báo lỗi và chặn merge.
- Thêm vào đúng vị trí trong `scripts/ci-local.ps1` cạnh 2 bước `ruff` đã có
  (§1 "Full gate" của `ci-rule.md`), không tạo cổng riêng biệt tách khỏi
  `-Full`.
- `-SkipLint` (cờ hiện có, đang chỉ tắt `ruff`) cần quyết định rõ: có tắt cả
  `mypy` cùng lúc hay tách cờ riêng — ghi rõ trong `EPIC-002C`.

## 3. Kiểm thử / Nghiệm thu

- Tái hiện đúng kịch bản `BUG-026` (1 class cố tình thiếu method abstract)
  trên nhánh test, xác nhận `ci-local.ps1 -Full` đỏ vì bước `mypy`, không
  phải vì `ruff`/`pytest`.
- Chạy `ci-local.ps1 -Full` trên `master-warrior` hiện tại (không có lỗi cố
  tình nào) — phải xanh, không có lỗi baseline nào lọt qua thành false
  positive chặn merge oan.
