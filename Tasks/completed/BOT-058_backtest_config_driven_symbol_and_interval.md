# Nhiệm vụ: Backtest Screen — Symbol/Interval mặc định đọc từ Config, không phụ thuộc Dev Board

> Thuộc Epic [BOT-040 — Backtest Screen Full Feature Set](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Nhóm D (nối tiếp `BOT-022`). Phụ thuộc `BOT-022` ✅.

## 1. Mục tiêu (Objective)

Backtest là **tính năng chính** của app (không phải Dev Board — Dev Board chỉ
là công cụ dev/test nội bộ). Symbol/Interval mặc định của màn Backtest hiện
đang **vô tình trùng khớp** với Dev Board (cả hai cùng hardcode module
constant riêng: `dashboard_presenter.py`'s `_DEFAULT_INTERVAL_STR = "1m"` và
`backtest_presenter.py`'s `_DEFAULT_SYMBOL = "ETHUSDT"` /
`backtest_view_model.py`'s `_DEFAULT_TIMEFRAME`), không có gì đảm bảo 2 hằng
số này luôn đồng bộ — đã từng lệch thật (`_DEFAULT_TIMEFRAME` ban đầu là
`"15m"`, khiến "Chạy Backtest" lần đầu luôn báo "No historical data found"
vì Dev Board chỉ sync `"1m"`; đã vá tạm bằng cách đổi hằng số cho khớp, xem
commit `fix(backtest): default timeframe to 1m`).

Task này thay bản vá tạm bằng cách đúng: Backtest đọc symbol/interval mặc
định từ **`IConfig`** (`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`, đã có sẵn, người
dùng chỉnh được qua màn Settings — `BOT-017`) — nguồn sự thật chung của cả
app, **không** phụ thuộc/tham chiếu ngầm vào Dev Board.

## 2. Mô tả (Description)

`IConfig` đã có 2 key này từ lâu, đọc và ghi được qua `SettingsPresenter`
(`src/presentation/ui/screens/settings/settings_presenter.py`):
```python
values = self.config.get_all()
symbols = values.get("DEFAULT_SYMBOLS") or []  # list[str], vd ["ETHUSDT"]
interval = values.get("DEFAULT_INTERVAL") or ""  # str, vd "1m"
```
Đây là 2 chuỗi key trần (`"DEFAULT_SYMBOLS"`/`"DEFAULT_INTERVAL"`), **không**
nằm trong enum `ConfigKeys` (`src/config/config_keys.py`) — dùng đúng chuỗi
này, không tự thêm vào enum ở task này (ngoài phạm vi, đổi enum ảnh hưởng
`SettingsPresenter` đang hoạt động tốt).

`BackTestPresenter` hiện có `self.config` sẵn (kế thừa từ `BasePresenter`,
xem `settings_presenter.py` làm ví dụ đọc `self.config.get_all()`) — không
cần resolve thêm gì mới.

## 3. Các bước thực hiện (Action Items)

- [ ] `backtest_presenter.py`: xoá module constant `_DEFAULT_SYMBOL =
  "ETHUSDT"`. Trong `__init__`, đọc `symbols = self.config.get_all().get(
  "DEFAULT_SYMBOLS") or []`, lấy `symbols[0]` nếu có, fallback về 1 hằng số
  **rõ ràng đặt tên là fallback** (vd `_FALLBACK_SYMBOL = "ETHUSDT"`, chỉ
  dùng khi config trống — vd cài đặt lần đầu, chưa mở Settings bao giờ) nếu
  danh sách rỗng. Symbol này dùng cho cả `view.render_symbol_cards([...])`
  lẫn mọi `RunStaticBacktestCommand`/`GetHistoricalKlinesQuery` (thay
  `_DEFAULT_SYMBOL` cũ ở toàn bộ chỗ dùng, xem `_run_backtest`,
  `_fetch_and_emit_chart_data`).
- [ ] `backtest_view_model.py`: xoá `_DEFAULT_TIMEFRAME = "1m"` hardcode.
  Thay bằng: `BackTestPresenter.__init__` đọc `interval = self.config.get_all
  ().get("DEFAULT_INTERVAL") or ""`; nếu `interval` nằm trong
  `DEFAULT_TIMEFRAMES` (`chart_toolbar.py`) thì gọi
  `self._view_model._set_selected_timeframe(interval)` (hoặc thêm setter
  công khai nếu thấy hợp lý hơn đụng private) sau khi `BackTestViewModel()`
  khởi tạo; nếu không hợp lệ/rỗng, giữ nguyên default nội tại của ViewModel
  (`DEFAULT_TIMEFRAMES[0]`, tức `"1m"` — fallback hợp lý, không phải đoán
  bừa, vì đây cũng là timeframe nhanh/nhỏ nhất nên **khả năng có dữ liệu sync
  cao nhất** trong mọi lựa chọn).
- [ ] **Không** thêm Symbol picker/dropdown ở task này — ngoài phạm vi (giữ
  đúng quyết định gốc của `BOT-022`: "chưa có symbol picker, chưa được yêu
  cầu"). Task này chỉ đổi *nguồn* của giá trị mặc định, không đổi UI.
- [ ] Unit test: `mock_config.get_all.return_value` có `DEFAULT_SYMBOLS`/
  `DEFAULT_INTERVAL` khác mặc định cũ (vd `["BTCUSDT"]`/`"5m"`) → xác nhận
  `RunStaticBacktestCommand`/`GetHistoricalKlinesQuery` dùng đúng giá trị đó,
  và `view.render_symbol_cards` được gọi với đúng symbol đó. Ca `DEFAULT_
  SYMBOLS` rỗng/thiếu key → dùng fallback, không crash. Ca `DEFAULT_INTERVAL`
  không nằm trong `DEFAULT_TIMEFRAMES` (config bẩn/gõ tay sai) → bỏ qua, giữ
  default nội tại của ViewModel, không crash.

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- Đọc config **1 lần lúc khởi tạo màn hình** (giống cách `SettingsPresenter`
  đọc 1 lần), không cần theo dõi thay đổi config real-time — nếu user đổi
  `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` ở Settings trong lúc màn Backtest đang
  mở, giá trị cũ vẫn giữ nguyên tới khi mở lại màn (đúng hành vi
  `PresenterManager`'s lazy-load-1-lần, nhất quán với toàn bộ app — không tự
  chế thêm cơ chế "live reload config" ở task này).
- Không sửa `SettingsPresenter`/`SettingsScreen.qml` — 2 key `DEFAULT_
  SYMBOLS`/`DEFAULT_INTERVAL` đã có UI edit sẵn, dùng nguyên.
