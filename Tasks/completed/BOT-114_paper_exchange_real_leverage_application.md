# Nhiệm vụ: Áp Dụng Đòn Bẩy Thật Vào PaperExchange (Real Leverage Application)

**Mã Task:** `BOT-114`  
**Độ phức tạp:** 🔴 **L (Thinking)**  
**Trạng thái:** ✅ **Hoàn thành (2026-08-20)**  
**Phụ thuộc:** `BOT-050` (Short-Selling) ✅, `BOT-104` (Position Sizing & Broker Simulator Modal) ✅

---

## 1. Bối Cảnh & Vấn Đề

User phát hiện: `BrokerSimulationConfig.long_leverage`/`short_leverage` và `BackTestViewModel.longLeverage`/`shortLeverage` đã tồn tại từ trước (mặc định 1.0x, có validate > 0), và `BackTestPresenter` đã thread chúng vào config — **nhưng `PaperExchange`, engine thực thi backtest, không hề đọc 2 field này ở đâu cả** (`grep "leverage" paper_exchange.py` = 0 kết quả). Đặt đòn bẩy 5x trên UI không có tác dụng gì lên kết quả backtest — một tính năng "nửa vời": có input, có validate, nhưng không có lõi tính toán thật. Đào sâu hơn còn phát hiện **chính bản thân input UI cũng chưa tồn tại** — không QML file nào bind `longLeverage`/`shortLeverage` (property được chuẩn bị sẵn nhưng chưa ai làm ô nhập).

---

## 2. Thiết Kế

Đòn bẩy mang **2 ý nghĩa khác nhau** tuỳ loại Position Sizing đang dùng — đây là quyết định thiết kế quan trọng nhất của task, không hiển nhiên nên cần giải thích rõ:

- **`PERCENT_OF_EQUITY`/`FIXED_CASH`** (chỉ định một khoản VỐN): đòn bẩy NHÂN vốn đó thành notional lớn hơn — đúng y hệt cách mọi sàn thật hoạt động (5x trên 100% vốn $1,000 điều khiển vị thế $5,000, chỉ dùng $1,000 làm margin).
- **`FIXED_CONTRACTS`/`RISK_PERCENT`** (chỉ định một SỐ LƯỢNG chính xác — số hợp đồng, hoặc số lượng khiến dừng lỗ lỗ đúng risk%): đòn bẩy **không được** thay đổi số lượng đó, chỉ giảm margin cần giữ — nếu không, bất biến đã ghi sẵn trong code của `RISK_PERCENT` ("risk_amount = số tiền mất nếu dính stop") sẽ bị đòn bẩy âm thầm nhân lên, khiến user tưởng đang risk 2%/lệnh nhưng thực ra risk 2%×leverage.

Vì LONG trước đây tính PnL kiểu "spot" (`quantity * mark_price`, giả định toàn bộ notional đã "mua đứt"), còn SHORT tính kiểu "margin" (`margin + (entry-mark)*quantity`) — dưới đòn bẩy, LONG **bắt buộc** phải chuyển sang công thức margin giống SHORT (margin không còn bằng notional nữa). Để không đổi kết quả của **mọi backtest không dùng đòn bẩy đang chạy production** (leverage mặc định 1.0x), công thức cũ được giữ nguyên y hệt qua nhánh `if pos.leverage == 1.0` — công thức margin mới chỉ áp dụng khi leverage thật sự khác 1.0x.

---

## 3. Thay Đổi

1. **`PaperExchange`** (`_calculate_entry_capital`, `_open`, `_mark_to_market`, `_close_one_position`):
   - `_OpenPosition` thêm field `leverage: float = 1.0`, snapshot tại lúc mở lệnh (không đọc lại config sau này — cùng lý do với `stop_loss_price`/`take_profit_price`).
   - `_calculate_entry_capital()` viết lại: tách rõ `margin` (rút từ `self._balance`) và `notional_capital` (dùng để tính phí + số lượng) theo đúng logic ở mục 2. Phí tính trên **notional** (đúng hành vi sàn thật: phí theo quy mô vị thế, không theo margin).
   - `_mark_to_market()`/`_close_one_position()`: LONG rẽ nhánh theo `leverage == 1.0` (giữ công thức spot cũ nguyên vẹn) hoặc dùng công thức margin (khi có đòn bẩy thật).
2. **UI** (`StrategyPropertiesModal.qml`): thêm "Group 4: Đòn bẩy (Leverage)" — 2 `SpinBox` (Long/Short, 1x-125x, khớp trần đòn bẩy Binance Futures) — trước đây comment đầu file đã liệt kê "Leverage" trong scope của tab Properties nhưng chưa ai làm ô nhập thật.
3. **`BackTestPresenter._on_strategy_properties_save_requested`**: nhận `long_leverage`/`short_leverage` từ payload lưu, áp vào `view_model`.
4. **`BacktestRunConfig.compute_diff_summary()`**: thêm so sánh đòn bẩy — đổi đòn bẩy giờ hiện trong banner "Cấu hình đã thay đổi" giống pyramiding/slippage/commission.
5. **`backtest_limitations_view.py`**: xoá dòng giới hạn cũ *"All-in sizing, chỉ 1 vị thế tại 1 thời điểm, chỉ Long — chưa hỗ trợ đòn bẩy hay Short"* — **mọi khẳng định trong dòng này đã sai từ trước cả task này** (pyramiding + flexible sizing đã có từ `BOT-104`, Short đã có từ `BOT-050`), giờ đòn bẩy cũng xong nốt nên xoá hẳn theo đúng quy tắc §5 của `BOT-081`: *"mỗi task đó xoá bớt một dòng khỏi danh sách"*.

---

## 4. Kiểm Thử

- `test_paper_exchange.py`: 9 test mới — notional/quantity nhân theo leverage cho `PERCENT_OF_EQUITY` nhưng margin không đổi; PnL% khuếch đại đúng hệ số leverage; mặc định 1.0x không đổi hành vi cũ; mark-to-market tại đúng giá vào lệnh = margin (không lãi ảo); **bất biến an toàn quan trọng nhất**: `RISK_PERCENT` giữ đúng $ risk bất kể leverage; `FIXED_CONTRACTS` giữ đúng số lượng bất kể leverage; `long_leverage`/`short_leverage` đọc độc lập; phí tính trên notional (không phải margin); margin bị giới hạn theo balance khả dụng vẫn giữ đúng tỷ lệ đòn bẩy.
- `test_backtest_fsm_matrix.py`: 2 test mới cho `compute_diff_summary()` phát hiện đổi đòn bẩy.
- `test_backtest_limitations_view.py`: sửa 1 test đang assert dòng giới hạn vừa xoá.
- `test_backtest_presenter.py`: 1 test mới xác nhận payload lưu đòn bẩy chảy đúng vào `view_model`.
- Toàn bộ **47 test `test_paper_exchange.py` cũ pass y nguyên** (bằng chứng leverage mặc định 1.0x không đổi bất kỳ kết quả backtest nào đang chạy production). Toàn bộ **1546 test `tests/unit/` + 41 sanity pass**, `ruff` sạch trên mọi file đã sửa.
