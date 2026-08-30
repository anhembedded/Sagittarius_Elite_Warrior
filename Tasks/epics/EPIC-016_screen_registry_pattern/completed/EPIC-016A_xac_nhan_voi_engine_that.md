# EPIC-016A — Xác nhận `PresenterManager`/`ScreenDescriptor` với `Sagittarius_Engine` thật

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30 — **mở khoá `016B`**
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

## Kết quả xác nhận (2026-08-30)

Clone thật `anhembedded/sagittarius_engine` (commit `c8b1862`), đọc trực tiếp
`sagittarius_engine/extensions/pyside_mvc/mvc/presenter_manager.py`:

```python
# presenter_manager.py:38-54
def register(self, name: str, presenter_class: type, view_factory: Callable) -> None:
    self._registry[name] = {
        "presenter_class": presenter_class, "view_factory": view_factory,
        "view_instance": None, "presenter_instance": None, "stacked_index": -1,
    }

# presenter_manager.py:56-66 — raise ValueError nếu route chưa đăng ký (không phải KeyError)
def navigate_to(self, name: str) -> None: ...

# presenter_manager.py:71-79 — lúc lazy-load thật:
view = config["view_factory"]()                       # gọi KHÔNG tham số
presenter = config["presenter_class"](view, self.container)  # gọi (view, container)
```

**Kết luận:**

1. `presenter_class(view, container)` và `view_factory()` — khớp chính xác
   với `AbstractScreenModule.build_descriptor()` trong bản thiết kế
   (`presenter_class=lambda v, c: self.create_presenter(v, c)`,
   `view_factory=lambda: self.create_view(container)`). **Không cần sửa
   thiết kế.**
2. `ScreenDescriptor` **không tồn tại** ở engine (`grep -rln "ScreenDescriptor"
   sagittarius_engine/` → rỗng). Elite định nghĩa mới là đúng, không lặp
   hợp đồng.
3. Engine đang pin `2.3.0` (`pyproject.toml:7`) — khớp version Elite đang
   dùng, **không cần bump**.
4. `navigate_to()` raise `ValueError` nếu route chưa đăng ký — đây là hành
   vi của engine, khác với `IScreenRegistry.get()` phía Elite (raise
   `KeyError`, theo ADR D5) — 2 method khác nhau, không mâu thuẫn.

**D4 trong ADR chuyển từ ❓ Open sang ✅ Established.** `016B` được mở khoá.
