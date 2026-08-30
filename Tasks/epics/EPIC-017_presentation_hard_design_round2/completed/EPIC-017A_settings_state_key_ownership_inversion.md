# EPIC-017A — Đảo ngược sở hữu state-key: `SettingsPresenter` hết hard-code field 3 màn khác

**Thuộc Epic:** [`EPIC-017`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30
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

## Kết quả (2026-08-30) — thiết kế thật khác với dự kiến ban đầu ở §2/#2

Bản thiết kế gốc của task này (mỗi Presenter tự gọi
`register_config_binding()` trong `__init__`) có **1 lỗi thời điểm nghiêm
trọng phát hiện khi cài đặt**: `PresenterManager` là *true lazy router* —
`view_factory()`/`presenter_class(view, container)` chỉ chạy khi user
thật sự điều hướng tới màn đó (`presenter_manager.py:71-79`, xem
`EPIC-016A`). Nếu binding chỉ đăng ký trong `__init__` của Backtest/Dashboard/
Database, một màn **chưa từng được mở** sẽ không đăng ký gì — Settings đổi
Default Symbol trước khi user mở màn đó lần đầu sẽ **không discard được**
giá trị nhớ cũ, và lần đầu mở màn đó `restore_into()` sẽ phục hồi giá trị
**cũ, đã lỗi thời** thay vì default mới. Đây là hồi quy thật so với dict
tĩnh cũ (vốn discard được ngay cả khi chưa mở màn nào).

**Sửa:** đăng ký **eager, một lần**, trong `app_bootstrapper.py` — ngay sau
khi `state_coordinator` được tạo, **trước khi** bất kỳ Presenter nào được
dựng — bằng dữ liệu string thuần (`scope_key`, `config_key`, tuple field
name), **không** import class Presenter (tránh phá lazy-loading, và tránh
kéo theo toàn bộ cây import nặng của Backtest/Data Management ngay lúc
boot). `UiStateCoordinator` được thêm 2 method mới:
`register_config_binding(scope, config_key, state_keys)` và
`discard_for_config_key(config_key)`.

**Nơi tri thức "field nào thuộc màn nào" cư trú:** không còn ở
`SettingsPresenter` (đúng mục tiêu gốc — nó chỉ còn biết 2 config key nào
"outrank" state, không biết field name/scope của screen khác), nhưng cũng
không nằm rải rác ở từng Presenter (không khả thi do lazy-loading) — mà tập
trung ở `app_bootstrapper.py`, đúng vị trí composition root đã được chấp
nhận cho pattern tương tự ở `EPIC-017` ADR D2 (đăng ký strategy/indicator
tường minh tại bootstrap thay vì auto-discovery).

**File đã sửa:**
- `state/ui_state_coordinator.py` — thêm `register_config_binding()`/`discard_for_config_key()`.
- `screens/settings/settings_presenter.py` — xoá `_STATE_KEYS_OWNED_BY_SETTINGS`,
  thay bằng `_CONFIG_KEYS_THAT_OUTRANK_REMEMBERED_STATE = ("DEFAULT_SYMBOLS", "DEFAULT_INTERVAL")`
  và gọi `discard_for_config_key()` theo từng key.
- `app_bootstrapper.py` — đăng ký 6 binding (3 màn × 2 config key) ngay sau khi tạo `state_coordinator`.
- `tests/.../test_settings_presenter_precedence.py` — fixture `coordinator`
  giờ tự đăng ký binding (mô phỏng đúng việc bootstrap làm trong production),
  **không đổi assertion nào** của 2 test đã có.

**Verify:** `ruff check`/`format --diff` sạch trên 4 file + 1 test file.
Test suite thật (venv 3.12 + engine thật) — 572 test xanh
(`state/`, `test_settings_presenter*.py`, cả 3 màn Backtest/Dashboard/Database
+ presenter/state test), cộng `tests/sanity/test_composition_root.py` (8 test)
xác nhận `app_bootstrapper.build()` vẫn dựng đúng, không đổi assertion nào.
