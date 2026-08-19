# Nhiệm vụ: Backtest screen — thêm cơ chế đổi symbol (hiện đang bị khoá cứng)

**Trạng thái:** Hoàn thành (19/08)

> Không thuộc epic nào. Phát hiện khi rà lại `BackTestPresenter` lúc chuẩn bị
> làm [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md) §3.3.
> Không chặn, không bị chặn bởi `BOT-076`.

## 1. Triệu chứng

Màn Backtest không có cách nào đổi cặp giao dịch từ UI. Đã verify trong
[`backtest_presenter.py`](../../src/presentation/ui/screens/backtest/backtest_presenter.py):

```python
self._symbol: str = default_symbols[0] if default_symbols else _FALLBACK_SYMBOL
```

`self._symbol` được set **đúng 1 lần** trong `__init__`, đọc từ
`DEFAULT_SYMBOLS` trong config (`user_config.json` — mặc định
`["BTCUSDT", "ETHUSDT"]`, luôn lấy phần tử đầu tiên) và dùng xuyên suốt cho
mọi lệnh gọi backtest/sync/chart. Không có property, signal, hay modal nào
đọc/ghi giá trị này sau đó — muốn backtest `ETHUSDT` thay vì `BTCUSDT`, cách
duy nhất là sửa thứ tự trong `user_config.json` rồi khởi động lại app.

## 2. Vì sao đáng làm

Người dùng backtest nhiều cặp khác nhau trong một phiên làm việc bình thường
(so sánh chiến thuật trên `BTCUSDT` vs `ETHUSDT` chẳng hạn) — hiện tại việc
đó đòi hỏi sửa file config + khởi động lại app.

## 3. Quyết định thiết kế (đã chốt với user trước khi code)

Câu hỏi mở duy nhất — nguồn danh sách symbol lấy từ đâu — được hỏi lại trước
khi code: **(a) danh sách tĩnh từ config** vs **(b) gọi Binance exchange-info
thật**. User chọn **(b)**, chấp nhận effort/rủi ro cao hơn để có trải nghiệm
đúng nhu cầu (liệt kê mọi symbol khả dụng trên sàn, không giới hạn những gì
đã liệt kê sẵn trong config).

## 4. Triển khai

**Application/Infrastructure (mới, chưa có trước đây — đã verify repo chưa
từng gọi Binance exchange-info dưới bất kỳ hình thức nào):**
- `IExchangeClient.get_available_symbols() -> list[str]` (port mới) +
  `PythonBinanceClient.get_available_symbols()` — gọi `Client.get_exchange_info()`
  thật, lọc `status == "TRADING"`, sort. Tái dùng `BinanceMetadataKey`/
  `DEFAULT_STATUS` từ `market_metadata_parser.py` (BOT-095E1) thay vì hard-code
  lại chuỗi field.
- `ListAvailableSymbolsQuery`/`ListAvailableSymbolsQueryHandler` (CQRS, đúng
  khuôn mẫu `GetDatabaseStatusQuery`), đăng ký trong `binance_bot_module.py`.

**Presentation:**
- `BackTestViewModel`: `symbolOptions`/`selectedSymbol` (Property + Signal),
  `openSymbolPickerRequested`/`requestOpenSymbolPicker()` — đúng khuôn mẫu
  `strategyOptions`/`selectedStrategyKey` đã có. `selectedSymbol` chỉ là kênh
  ghi từ modal; **`self._symbol` trên Presenter vẫn là nguồn sự thật duy nhất**
  mọi command/query thật sự đọc — giữ đúng luật "background worker không bao
  giờ đụng ViewModel trực tiếp" đã có sẵn trong codebase.
- `BackTestPresenter`: `_on_symbol_picker_open_requested` fetch qua
  `IThreadManager` (cache trong phiên, không fetch lại mỗi lần mở modal);
  `_on_symbol_selection_changed` cập nhật `self._symbol`, rebuild chart đúng
  quy trình dùng chung với BOT-098F6D's fallback path
  (`render_symbol_cards()` → `_reset_indicator_bookkeeping_after_host_rebuild()`
  → `_connect_chart_controls()`), **cố ý không gọi `refresh_chart()`** (sẽ
  replay dữ liệu cũ của symbol trước) — để `_request_chart_preview()` tự fetch
  dữ liệu mới cho symbol mới.
- `SymbolPickerModal.qml` (mới) — grid + ô tìm kiếm client-side (Binance trả
  về hơn 1300 symbol, khác hẳn Strategy/Timeframe picker chỉ vài chục mục),
  wiring vào `BackTestModals.qml`/`BackTestTopPanel.qml` đúng khuôn mẫu 10
  modal đã có.
- `BacktestRunConfig.compute_diff_summary()`: thêm nhánh so sánh `symbol` —
  trường này vốn đã có trong dataclass (Dirty Tracking qua `__eq__` đã đúng
  từ trước), chỉ thiếu hiển thị trong thông báo diff cho user.

## 5. Verify (không chỉ test tự động)

Theo đúng nguyên tắc đã lặp lại nhiều lần trong phiên làm việc này — chạy
app thật, không chỉ tin test pass:
- Script real-window (`QApplication` thật, DI container thật qua
  `create_app()`, không mock dispatcher) bấm đúng nút `btnBacktestSymbol`
  bằng `QTest.mouseClick` thật (không gọi thẳng hàm Python) → modal mở →
  **gọi Binance exchange-info thật qua mạng thật**, nhận về 1361 symbol thật
  → gõ "BTC" vào ô tìm kiếm, lọc đúng còn các cặp chứa "BTC" → set
  `selectedSymbol = "ETHUSDT"` → xác nhận `presenter._symbol`,
  `view.chart_cards[0].symbol`, và nút toolbar đều đổi đúng, QML/Qt log sạch
  (`errors() == []`, không warning). 2 ảnh chụp màn hình thật xác nhận UI
  render đúng.
- Full test suite: 1496 pass, 3 fail — cả 3 fail đều **đã xác nhận có từ
  trước** (fail giống hệt trên cây sạch chưa có thay đổi này, qua
  `git stash`/`git stash pop`), thuộc Dashboard/Dev Board
  (`test_dashboard_integration.py`, `test_dashboard_live_stream.py`,
  `test_dev_board_async_race_conditions.py`), không liên quan Backtest/Symbol
  Picker — cùng loại flakiness đã ghi nhận ở `BOT-038`.
- `ruff check` sạch trên toàn bộ file đã sửa/thêm.
- Mutation-test thủ công: tạm bỏ dòng so sánh `symbol` trong
  `compute_diff_summary()`, xác nhận test mới fail đúng lý do, khôi phục lại.

## 6. Test mới

`tests/unit/application/use_cases/test_list_available_symbols.py` (2),
`tests/unit/infrastructure/binance/test_python_binance_client_unit.py` (+2),
`tests/unit/application/ports/test_i_exchange_client.py` (cập nhật fake theo
method mới), `tests/unit/presentation/ui/screens/test_backtest_presenter.py`
(+9: fetch/cache, chọn symbol cập nhật đúng chỗ, no-op khi chọn lại chính nó,
submit preview mới, Dirty Tracking hiện diff "Symbol (...)").
