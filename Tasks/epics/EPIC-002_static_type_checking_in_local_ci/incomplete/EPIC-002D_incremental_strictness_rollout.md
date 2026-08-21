# EPIC-002D — Lộ trình siết `--strict` dần theo module

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** 🔴 Chưa làm — backlog dài hạn, không chặn `EPIC-002A`/`B`/`C`.
**Phụ thuộc:** [`EPIC-002B`](EPIC-002B_wire_mypy_into_ci_local.md).

---

## 1. Mục tiêu

`EPIC-002B` chỉ bật `mypy` ở mức tối thiểu (đủ bắt lớp lỗi `BUG-026`). Task
này là nơi quyết định **có** đáng siết dần lên `--strict` hay không, module
nào trước — không tự quyết ở đây, cần bàn khi tới lượt.

## 2. Việc cần làm (khi bắt đầu, không phải bây giờ)

1. Dựa trên phân loại lỗi theo layer ở `EPIC-002A`, chọn 1 module Domain
   sạch nhất làm thí điểm bật `--strict` riêng cho module đó (mypy hỗ trợ
   cấu hình per-module qua `[[tool.mypy.overrides]]`).
2. Domain layer là ứng viên tự nhiên nhất để bắt đầu: đã theo nguyên tắc
   "Strong Typing & Immutability" của `AGENTS.md` từ trước (annotation đầy
   đủ, `dataclass(frozen=True)`, không `Any`) — nhiều khả năng đã gần đạt
   `--strict` sẵn mà không cần sửa nhiều.
3. Mở rộng dần sang Application, rồi Infrastructure/Presentation (2 layer
   sau có nhiều phụ thuộc bên ngoài — PySide6, SQLAlchemy — dễ cần
   `# type: ignore` có chủ đích hơn là sửa thật).
4. Mỗi module bật `--strict` thành công thì xoá khỏi baseline-suppression
   (nếu `EPIC-002B` có dùng cơ chế đó), không giữ mãi.

## 3. Không thuộc phạm vi task này

Quyết định "có nên đạt `--strict` toàn bộ `src/` hay không, và bao giờ" —
đó là quyết định kiến trúc dài hạn, để ngỏ, bàn lại khi `EPIC-002A`/`B`/`C`
đã xong và có đủ dữ liệu thật để cân nhắc.
