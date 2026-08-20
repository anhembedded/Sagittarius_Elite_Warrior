# EPIC-001A — Chuẩn hoá Broker Simulator config cho phép so sánh công bằng với TradingView

**Thuộc:** [EPIC-001](../README.md)
**Trạng thái:** ✅ Hoàn thành (20/08).

## Mục tiêu

Trước khi chạy backtest để đối chiếu với TradingView, xác nhận (và nếu cần,
set đúng) toàn bộ config sau trên Backtest screen của app khớp với khai báo
`strategy(...)` gốc trong Pine Script (`BOT-109` §1):

- `pyramiding = 1`.
- Position sizing = 100% equity (`PositionSizingType.PERCENT_OF_EQUITY`,
  giá trị `100.0`) — không phải `RISK_PERCENT`/`FIXED`.
- Commission = 0, slippage = 0 (Broker Simulator modal, `BOT-104`).
- `BrokerSimulationConfig.take_profit_pct` set **riêng**, khớp giá trị với
  `take_profit_percent` của strategy input — nhắc lại gap đã ghi trong
  `BOT-110`: khai báo input không tự động enforce TP, đây là 2 field độc
  lập phải tự đồng bộ tay.
- `BrokerSimulationConfig.stop_loss_pct` = không set (Pine gốc không có SL,
  chỉ có TP + touch-exit) — nếu app đang có SL mặc định nào đó phải tắt đi,
  không thì kết quả lệch vì lý do không liên quan đến strategy.

## Việc cần làm

1. Đọc lại `BrokerSimulationConfig` hiện tại (default trong code +
   giá trị đang set qua Broker Simulator modal) — so với danh sách trên,
   liệt kê cái nào đã đúng sẵn, cái nào cần đổi.
2. Nếu UI đã đủ chỗ để set hết (`OrderExecutionModal.qml`/Broker Simulator
   modal của `BOT-104`) thì không cần code gì — chỉ cần ghi lại đúng các
   bước bấm để tái lập config này mỗi lần so sánh (đưa vào `EPIC-001B`).
3. Nếu thiếu chỗ set 1 trong các field trên qua UI, ghi rõ field nào thiếu
   — quyết định có cần thêm task code riêng hay không, đừng tự ý thêm code
   ngoài phạm vi task này.

## Ngoài phạm vi

Không tự sync lại dữ liệu, không tự chạy backtest — task này chỉ chuẩn hoá
config, việc chạy + đối chiếu là `EPIC-001B`.

## Kết quả

Đọc `BrokerSimulationConfig`/`PositionSizing` xác nhận **4/5 đã đúng sẵn ở
default, không cần đổi gì**: `pyramiding=1`, sizing 100% equity
(`PERCENT_OF_EQUITY`/`100.0`), `slippage_ticks=0`, `stop_loss_pct=None`.
Commission **không** mặc định = 0 (`commission_value=0.1`) — người dùng tự
đổi trong tab "Đặc tính" của `StrategyPropertiesModal.qml` (đã có ô nhập
sẵn) mỗi lần chuẩn bị so sánh.

**Gap thật tìm ra**: `BrokerSimulationConfig.take_profit_pct` **không có ô
nhập nào trong UI cả** — `grep` toàn bộ `src/` không thấy chỗ nào build
`BrokerSimulationConfig(take_profit_pct=...)` từ input người dùng, chỉ có
trong test. Nghĩa là TP% của `EmaTrendPullbackStrategy` chưa từng có tác
dụng thật trong app — quyết định của user: thêm ô nhập luôn (không bỏ qua
TP cho epic này).

**Đã thêm**: `StrategyPropertiesModal.qml` — group mới "CHỐT LỜI TỰ ĐỘNG
(TAKE PROFIT %)" (checkbox `propTakeProfitEnabled` + `TextField
propTakeProfitPct`, mirror đúng pattern Commission/Slippage đã có).
`BackTestViewModel` — `takeProfitPctEnabled`/`takeProfitPctText` Property
mới. `BackTestPresenter._on_strategy_properties_save_requested()` đọc 2
key mới từ payload; `_build_run_config()` parse `take_profit_pct` chỉ khi
bật checkbox VÀ text hợp lệ (`> 0`) — fallback `None` khi tắt hoặc text rác
(không crash `BrokerSimulationConfig.__post_init__`'s `<= 0` guard), mirror
đúng kiểu lenient-fallback đã có sẵn cho `order_size_type`/`commission_type`
trong cùng hàm.

**Test**: 3 test mới trong `test_backtest_presenter.py` (save áp đúng vào
view_model, `_build_run_config` chỉ set `take_profit_pct` khi bật, text rác
không crash) + mở rộng `test_strategy_properties_modal.py` (default
ViewModel, save-and-rerun end-to-end qua `_build_run_config`, và quan
trọng nhất — `findChild()` trên QML thật xác nhận `propTakeProfitEnabled`/
`propTakeProfitPct` thật sự render đúng, không chỉ suy từ code Python).
Toàn bộ `test_backtest_presenter.py` (164 test) + `test_strategy_properties_modal.py`
pass, `ruff` sạch trên mọi file sửa.

**Chưa làm** (đúng phạm vi, để `EPIC-001B`): tự tắt SL nếu đang bật (không
cần vì default đã `None`, không có UI nào bật nó lên hiện tại).
