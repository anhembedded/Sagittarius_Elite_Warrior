# ADR — Presentation Hard-Design Round 2: 6 điểm từ report bên ngoài, verify độc lập

**Thuộc Epic:** [`EPIC-017`](README.md)
**Ngày:** 2026-08-30
**Trạng thái:** 🟢 **Approved** — 6 điểm đã verify độc lập; quyết định theo
từng điểm ở §3.

> [!IMPORTANT]
> Đọc cột trạng thái, không đọc văn xuôi.
>
> | Nhãn | Ý nghĩa |
> | :--- | :--- |
> | ✅ **Established** | Đã xác nhận trên cây code thật; trích `file:line` |
> | 🔵 **Proposed** | Đã chốt hướng, chưa implement |
> | ❌ **Rejected** | Đề xuất gốc bị từ chối, ghi lý do để không ai đề lại |

---

## 1. Bối cảnh

Một report từ 1 phiên làm việc khác (Windows, không phải phiên hiện tại)
liệt kê 6 "Hard Design" trong `src/presentation/`, `src/binance_bot_module.py`,
`scripts/run-ui.ps1`. Report đó **không được tin theo lời** — mọi claim đã
verify độc lập bằng cách đọc code thật trong phiên này (2026-08-30), đối
chiếu `.agents/rules/architecture-rule.md` và `.agents/rules/code-quality-rule.md`.

## 2. Bảng verify (tóm tắt)

| # | Chủ đề | Verdict | Ghi chú |
| :-: | :--- | :--- | :--- |
| 1 | `SettingsPresenter` hard-code field 3 màn khác | ✅ Đúng, không phóng đại | Có chủ đích (`EPIC-010H`), có docstring, nhưng vẫn coupling ngầm bằng string |
| 2 | Strategy/Indicator đăng ký hard-code ở `binance_bot_module.py` | ✅ Đúng nội dung | Đề xuất auto-discovery **bị từ chối** — xem D2 |
| 3 | Magic string `"1m"` rải rác | ✅ Đúng có thật, nhưng **report sai** claim "chưa có Value Object" | `src/domain/value_objects/timeframe.py:4` đã có `class TimeFrame(str, Enum)` — vấn đề thật là UI không dùng nó, không phải thiếu type |
| 4 | Boilerplate lặp ở "cả 4 presenter" | ⚠️ Phóng đại | Chỉ 3/4 (Settings không có phần `find_symbol_preferences`/`_mark_state_dirty`); phần lõi đã factor vào `container_lookup.py` |
| 5 | God Presenters vượt ngưỡng 400 dòng | ✅ Đúng, report còn báo **thấp hơn** số thật | `backtest_presenter.py` 1945 dòng, `backtest_view_model.py` 1429, `dashboard_presenter.py` 1144, `data_management_presenter.py` 850 (đo 2026-08-30) |
| 6 | Junction hack trong `run-ui.ps1` | ✅ Đúng dòng, đúng nội dung | Đề xuất "bỏ Junction, dùng relative import" **bị từ chối** — xem D6 |

---

## 3. Quyết định từng điểm

### D1 — Đảo ngược sở hữu state-key của Settings ✅ Established (2026-08-30) → `EPIC-017A`

Chấp nhận và đã làm. **Cơ chế thật khác với dự kiến ban đầu ở đây** (mỗi
Presenter tự gọi `register_config_binding()` trong `__init__`): `PresenterManager`
là true lazy router (xem `EPIC-016A`) — đăng ký trong `__init__` chỉ chạy
khi màn đó đã được mở, nên một màn chưa từng mở sẽ không đăng ký được gì,
tạo hồi quy (Settings đổi default trước khi mở màn đó lần đầu sẽ không
discard được, và lần mở đầu tiên phục hồi giá trị cũ đã lỗi thời). Sửa
bằng cách đăng ký eager, một lần, tại `app_bootstrapper.py` (composition
root) bằng string thuần — không import class Presenter, giữ nguyên lazy
loading. Chi tiết: `EPIC-017A`'s "Kết quả" section. Giữ nguyên bất nhất
`"timeframe"`/`"interval"` **không** phải việc của task này — đó là hệ quả
của D3 (điểm 3), sửa cùng lúc dễ nhầm 2 việc khác nhau thành 1 PR.

### D2 — Auto-discovery cho Strategy/Indicator ❌ Rejected

`_register_strategies`/`_register_indicator_scripts` ở
`binance_bot_module.py:269-296` là composition root. Danh sách tường minh
dễ `grep`/trace, đúng tinh thần "code tự nói lên chính nó"
(`architecture-rule.md` §7). Auto-scan package hoặc decorator sẽ **giấu**
thông tin đăng ký, khó test tĩnh, đi ngược triết lý cấm ngầm định của rule
này. **Không mở task.** Giữ nguyên hiện trạng.

### D3 — Dùng `TimeFrame` Enum có sẵn thay vì literal `"1m"` 🔵 Proposed → `EPIC-017B`

**Sửa lại claim gốc của report:** `TimeFrame` **đã tồn tại**
(`src/domain/value_objects/timeframe.py:4`, `str, Enum`, 16 giá trị từ
`"1s"` đến `"1M"`). Việc cần làm **không phải** "tạo Value Object mới" mà là
thay các default literal (`_DEFAULT_TIMEFRAME = "1m"` ở
`backtest_view_model.py:51` và tương tự ở `dev_board_panel.py`,
`time_range_card.py`, `data_management_view_model.py`) bằng
`TimeFrame.ONE_MINUTE` — vì là `str` subclass nên so sánh/serialize không
đổi hành vi. Xoá các comment kiểu "Must match dashboard_presenter.py's own
..." vì import chung 1 hằng số khiến chúng thừa.

### D4 — Boilerplate 4 presenter: không mở task riêng ❌ Rejected (scope-corrected)

Verify cho thấy phần lõi (`find_state_coordinator`/`find_symbol_preferences`)
**đã** factor vào `container_lookup.py` — không phải logic trùng lặp. Phần
còn "lặp" là lời gọi wiring signal `_mark_state_dirty`, khác nhau vì mỗi
screen có tên signal khác nhau — khó trừu tượng hoá thêm mà không ép
`SettingsPresenter` (vốn không cần 2/3 phần kia) vào 1 base-class chung.
**Không mở task.** Ghi nhận là residual chấp nhận được.

### D5 — God Presenters: route sang `EPIC-003`, không mở epic trùng 🔵 Proposed

`EPIC-003` (Phân rã Presenter/File quá tải) đã tồn tại, đang chạy, và đúng
là chủ sở hữu của vấn đề này — mở epic mới sẽ là bản-sao-trôi thứ 2 cho
cùng 1 vấn đề. Quyết định:

- `backtest_presenter.py` (1945 dòng) → đã có `EPIC-003E` (✅ xong, 6
  coordinator). Không mở lại.
- `backtest_view_model.py` (1429 dòng) → đã có `EPIC-003F` (🟡 mở khoá,
  chưa code). Không mở lại, không trùng lặp.
- `dashboard_presenter.py` (1144 dòng, 0 coordinator, chỉ có 3 controller
  phẳng không theo Coordinator Pattern) → **chưa có task nào** — mở task
  mới **`EPIC-003G`** trong `EPIC-003` (không phải epic này).
- `data_management_presenter.py` (850 dòng) → đã qua pilot `EPIC-003B`
  (coordinator pattern đã áp dụng, 4 coordinator tồn tại). Vẫn >400 dòng
  nhưng đã giảm đáng kể từ 919; không mở task mới ngay — ghi nhận residual,
  chỉ mở lại nếu file tiếp tục phình.

### D6 — Junction hack trong `run-ui.ps1` ❌ Rejected

Convention `from Sagittarius_Elite_Warrior...` (absolute, underscore) dùng
ở 222 file / 726 chỗ import trong `src/`, có 2 test khoá cấu trúc
(`test_no_cross_screen_imports.py`, `test_screen_layer_structure.py`).
Junction là workaround hợp lý cho tên thư mục clone không khớp, không phải
lỗi kiến trúc. Đổi sang relative import sẽ phá cả test suite lẫn hàng trăm
import hiện có — rủi ro cao hơn lợi ích. **Không mở task.**

---

## 4. Hệ quả

**Được:** Settings hết hard-code tên field 3 màn khác (D1); 4 file
presentation ngừng dùng `"1m"` literal, dùng chung `TimeFrame` (D3);
`dashboard_presenter.py` được đưa vào cùng kỷ luật Coordinator Pattern đã
áp dụng cho 2 presenter kia (D5 → `EPIC-003G`).

**Trả giá:** D1 cần đối chiếu lại với cơ chế `UiStateCoordinator` hiện có
của `EPIC-010` — không phải viết mới từ đầu, nhưng phải đọc kỹ trước khi
đổi. D3 chạm 4 file, cần test bao phủ default value không đổi khi refactor.

**Không làm:** D2, D4, D6 — mỗi cái ghi rõ lý do ở trên để không ai đề lại
mà không đọc ADR này trước.

## 5. Tham chiếu

- Report gốc (Windows session, dán trong hội thoại 2026-08-30) — không lưu
  file, chỉ tồn tại làm input cho ADR này.
- `src/presentation/ui/screens/settings/settings_presenter.py:24-38`
- `src/binance_bot_module.py:269-296`
- `src/domain/value_objects/timeframe.py`
- `src/presentation/ui/state/container_lookup.py`
- [`EPIC-003`](../EPIC-003_presenter_and_god_file_decomposition/README.md), [`EPIC-010`](../EPIC-010_ghi_nho_gia_tri_cuoi/README.md)
- `scripts/run-ui.ps1:42-53`, `tests/unit/presentation/ui/test_no_cross_screen_imports.py`
