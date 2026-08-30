# EPIC-016A — Xác nhận `PresenterManager`/`ScreenDescriptor` với `Sagittarius_Engine` thật

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu — **chặn `016B`** (ADR
[`DECISION_2026-08-30_screen_registry_pattern.md`](../DECISION_2026-08-30_screen_registry_pattern.md) D4)
**Phụ thuộc:** Không.

---

## Vì sao phải làm trước

`i_state_contributor.py` ghi chú `PresenterManager.register()` là **cố ý
duck-typed** — engine không ép base class cho presenter/view khi đăng ký
route. Thiết kế `AbstractScreenModule.build_descriptor()` giả định
`presenter_class`/`view_factory` khớp một hình dạng nhất định; nếu đoán sai
chữ ký thật, `016B` sẽ phải viết lại registry giữa chừng.

## Việc cần làm

1. Đọc `PresenterManager` trong repo `Sagittarius_Engine` (bản thật, không
   phải qua cách gọi suy luận từ `main_window.py`): chữ ký chính xác của
   `register()`, `navigate_to()`, `shutdown()`.
2. Tìm xem `ScreenDescriptor` hay khái niệm tương đương **đã tồn tại ở
   engine chưa**. Nếu có → `AbstractScreenModule`/`ScreenRegistry` phía
   Elite phải tái dùng type đó, không định nghĩa lại (tránh lặp hợp đồng ở
   2 repo — đúng bài học "bản sao-trôi" đã xảy ra 2 lần trong `CLAUDE.md`).
3. Xác nhận version engine đang pin ở Elite (`requirements.txt`/tương
   đương) có API này chưa, hay cần bump version trước.
4. Ghi lại kết luận vào file này (cập nhật `Trạng thái` + thêm mục "Kết
   quả xác nhận") trước khi mở khoá `016B`.

## Tiêu chí xong

- Chữ ký thật của `PresenterManager.register()`/`navigate_to()` đã trích
  dẫn `file:line` từ engine thật, không suy luận.
- Đã trả lời dứt khoát: `ScreenDescriptor` có sẵn ở engine hay phải định
  nghĩa mới ở Elite — và ghi rõ lý do.
- Nếu cần bump version engine, đã ghi thành một dòng riêng, không ẩn trong
  văn xuôi.
