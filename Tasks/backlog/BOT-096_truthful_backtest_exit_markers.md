# BOT-096 — Backtest: Marker/Icon thoát LONG trung thực

**Ưu tiên:** P1 — product-truth / ngăn người dùng diễn giải sai kết quả backtest
**Phụ thuộc:** `BOT-056` ✅, `BOT-057` ✅
**Không phụ thuộc và không thay thế:** `BOT-050` (Short-selling)

## 1. Vấn đề thực tế

Trong Backtest hiện tại, `MultiEmaTrendFollowerStrategy` phát `SELL` khi cấu
trúc EMA bị phá. Với `PaperExchange` long-only, đó chỉ là **đóng vị thế LONG**;
nó không mở lệnh SHORT. Tuy nhiên chart đang dựng marker entry/exit với nhãn
`Buy` / `Sell`. Kết hợp với tab UI `Bán (SHORT)`, người dùng có cơ sở hợp lý để
đọc marker đỏ `Sell` như một lệnh short đã khớp, dù bảng Trade Logs chỉ chứa
LONG và engine không hề có short position.

Đây là lỗi trung thực của contract UI: marker chart phải nói đúng **execution
semantic**, không tái sử dụng một biểu tượng “Sell” mơ hồ cho cả “đóng LONG”
và “mở SHORT”.

## 2. Mục tiêu

1. Khi engine còn long-only, biểu đồ phân biệt bằng hình dạng/icon, màu và
   nhãn giữa `LONG ENTRY` và `LONG EXIT`.
2. `LONG EXIT` không dùng icon hoặc nhãn được dành cho `SHORT ENTRY`.
3. Giữ đường nâng cấp sạch cho `BOT-050`: lúc short được triển khai, marker
   `SHORT ENTRY` mới được thêm với semantic riêng, không đổi nghĩa marker exit
   đã phát hành.
4. Bảng Trade Logs, marker và filter không được làm người dùng suy ra có short
   trade khi engine/result long-only không hề biểu diễn một short position.

## 3. Phạm vi bắt buộc

- Tạo model/constant semantic rõ ràng cho marker thực thi, tối thiểu gồm
  `LONG_ENTRY` và `LONG_EXIT`; để chỗ rõ ràng cho `SHORT_ENTRY`/`SHORT_EXIT`
  của `BOT-050` nhưng không giả lập chúng bằng string `Sell`.
- Đổi render Backtest từ cặp nhãn chung `Buy` / `Sell` sang visual riêng:
  entry long (mua/mở LONG) và exit long (thoát/đóng LONG). Icon phải là SVG
  chuẩn qua `image://icons/...` khi renderer hỗ trợ icon; fallback label phải
  ghi rõ `EXIT` hoặc `ĐÓNG LONG`, không ghi `SELL`/`SHORT`.
- Cập nhật tooltip/legend/toggle name nếu cần để người dùng hiểu marker đang
  biểu diễn **fill/position transition**, không chỉ strategy signal.
- Đối chiếu Trade Log: một `LONG_EXIT` trên chart phải có một trade LONG tương
  ứng, đúng giá/thời điểm fill (next-bar fill), trừ marker signal được trình
  bày ở layer khác và ghi nhãn là *signal*.
- Rà UI placeholder `Bán (SHORT)`: nếu vẫn xuất hiện trước `BOT-050`, phải
  hiển thị rõ “Chưa hỗ trợ short-selling” hoặc disable/hide theo quyết định UX;
  không được khiến empty tab trông như không có short signal trong một engine
  đã hỗ trợ short.

## 4. Ngoài phạm vi

- Không thêm leverage, margin, borrowing, liquidation, short PnL hoặc reverse
  position vào `PaperExchange`.
- Không đổi `SELL` strategy signal thành tự động đảo LONG → SHORT.
- Không mở tab SHORT thành dữ liệu thật. Các thay đổi domain đó thuộc `BOT-050`
  sau khi chốt contract execution.

## 5. Acceptance criteria và regression tests

1. Fixture deterministic có ít nhất một LONG entry và một strategy-driven LONG
   exit. Unit test marker builder phải xác nhận hai marker mang hai semantic/
   icon/label khác nhau; exit không chứa `SELL` hoặc `SHORT`.
2. Integration test chạy Backtest qua tín hiệu nút QML với repository seed
   local, rồi assert:
   - kết quả chỉ có LONG khi `PaperExchange` là long-only;
   - marker `LONG_EXIT` khớp exit fill của Trade (thời gian và giá next-bar);
   - UI không render marker/tên `SHORT` cho exit long;
   - Trade Log “SHORT” không được quảng cáo như capability hiện có.
3. Visual/Desktop E2E opt-in chụp hoặc inspect app thật: một entry LONG và
   exit LONG hiển thị khác nhau, dễ phân biệt bằng màu **và** icon/label (không
   chỉ dựa vào màu).
4. Regression test phải tồn tại vĩnh viễn. Không được thay bằng assertion
   “chart có marker” chung chung.

## 6. Files dự kiến

- `src/presentation/ui/screens/backtest/logic/chart_canvas_view.py`
- `src/presentation/ui/components/chart_card/marker_layer.py` và renderer liên
  quan
- `src/presentation/ui/assets/icons/`
- `src/presentation/ui/screens/backtest/BackTestTradeLogs.qml`
- `tests/unit/presentation/ui/screens/`
- `tests/integration/presentation/` và Desktop E2E opt-in

## 7. Definition of Done

Người dùng mở Backtest long-only không thể nhầm một marker đóng LONG với một
lệnh SHORT. Test business acceptance chứng minh đúng semantics xuyên suốt
domain result → chart marker → trade table. `BOT-050` vẫn có thể thêm short
entry mà không đổi ý nghĩa hoặc phá regression của `LONG_EXIT`.
