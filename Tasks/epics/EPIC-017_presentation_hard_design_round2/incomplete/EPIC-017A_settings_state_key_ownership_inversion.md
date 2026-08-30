# EPIC-017A — Đảo ngược sở hữu state-key: `SettingsPresenter` hết hard-code field 3 màn khác

**Thuộc Epic:** [`EPIC-017`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không (độc lập với `017B`).

---

## Hiện trạng

`settings_presenter.py:34-38`:

```python
_STATE_KEYS_OWNED_BY_SETTINGS: dict[str, tuple[str, ...]] = {
    "backtest": ("symbol", "timeframe"),
    "dashboard": ("symbol", "interval"),
    "data_management": ("symbol", "interval"),
}
```

Dùng ở dòng 188-189 để `discard_keys()` state của 3 màn khác khi user đổi
Default Symbol/Interval ở Settings. Có docstring giải thích (dòng 24-33,
từ `EPIC-010H`) nhưng vẫn là coupling ngầm: thêm màn mới đọc
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` mà quên thêm vào dict này → giá trị
nhớ của màn đó không bao giờ bị invalidate khi user đổi Settings.

## Việc cần làm

1. Đọc `UiStateCoordinator`/`EPIC-010` trước khi đổi bất cứ gì — cơ chế
   remember/restore hiện có phải hiểu đúng để không phá nó.
2. Mỗi Presenter (hoặc `*ScreenModule` nếu `EPIC-016` đã xong trước) tự
   khai `bound_config_keys: dict[str, ConfigKeys]` — Presenter tự nói nó
   phụ thuộc config key nào, không phải Settings đoán hộ.
3. `SettingsPresenter`/`UiStateCoordinator` đọc danh sách này (quét đăng ký
   thay vì dict cứng) để quyết định invalidate state của màn nào.
4. Xoá `_STATE_KEYS_OWNED_BY_SETTINGS`.
5. **Không** đổi bất nhất `"timeframe"` (backtest) vs `"interval"` (dashboard,
   data_management) trong task này — đó là việc của `017B`/công việc riêng,
   trộn 2 việc vào 1 PR sẽ khó review và khó revert độc lập.

## Tiêu chí xong

- `_STATE_KEYS_OWNED_BY_SETTINGS` không còn tồn tại.
- Thêm 1 test: đăng ký 1 màn giả với `bound_config_keys` mới, xác nhận
  Settings tự động invalidate đúng key mà không cần sửa `settings_presenter.py`.
- Test hành vi cũ (đổi Default Symbol ở Settings → 3 màn hiện có mất giá
  trị nhớ) vẫn xanh, không đổi assertion.
