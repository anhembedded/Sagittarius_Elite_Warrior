# BOT-097 — Backtest: Chọn múi giờ hiển thị

**Ưu tiên:** P2 — UX / tránh diễn giải sai thời gian dữ liệu
**Phụ thuộc:** `BOT-095D` ✅
**Không phụ thuộc:** Không thay đổi timezone của database, Binance API, hay engine Backtest.

## 1. Vấn đề thực tế

Màn Backtest hiện dùng UTC làm nguồn thời gian đúng cho candle, sync và range
coverage. Tuy nhiên người dùng Việt Nam nhìn chart, trade log và banner như
"Thiếu nến từ 2026-08-17 04:46 UTC" phải tự quy đổi sang giờ địa phương. Điều
này vừa gây khó đọc, vừa dễ hiểu nhầm rằng dữ liệu đang thiếu ở một thời điểm
khác với thời điểm đang thấy trên chart.

Không được giải quyết bằng cách đổi datetime trong domain/database sang local
time: nến Binance, boundaries `[start, end)`, cache và PnL phải tiếp tục dùng
UTC tuyệt đối. Đây là **display concern**, không phải business-time concern.

## 2. Mục tiêu

1. Thêm nút/chọn **Múi giờ** trên Backtest toolbar, hiển thị timezone đang áp
   dụng (ví dụ `UTC`, `Asia/Ho_Chi_Minh`).
2. Người dùng chọn được ít nhất `UTC` và timezone hệ điều hành; danh sách có
   thể mở rộng bằng IANA timezone đã xác thực.
3. Cùng một timezone phải được dùng nhất quán cho mọi thời gian do Backtest
   hiển thị: trục chart/tooltip, OHLC, trade log entry/exit, range preview,
   thông báo coverage/error và export có trường thời gian đọc được.
4. Thời gian raw/persisted và thời gian truyền vào use case vẫn là UTC;
   timezone display không được làm dirty cấu hình backtest, không tự chạy lại
   backtest, sync hoặc thay đổi kết quả.

## 3. UX/Contract bắt buộc

- Giá trị mặc định phải được nêu rõ trong UI. Khuyến nghị: `UTC` để dữ liệu
  nhất quán với Binance; người dùng chủ động chọn `Giờ hệ thống`.
- Selector có tooltip giải thích: "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest
  luôn tính theo UTC."
- Không được ghi nhãn mơ hồ như `GMT+7` nếu không có IANA zone tương ứng;
  daylight-saving cần hiển thị đúng với timezone được chọn.
- Chart marker và Trade Log cùng một timestamp phải hiển thị cùng một local
  clock time. Nếu export giữ UTC để machine-readable, header phải ghi rõ
  `UTC`; nếu export theo display zone, phải có cột/metadata timezone.
- Khi không thể resolve timezone, fallback UTC có warning rõ ràng, không âm
  thầm dùng timezone khác.

## 4. Phạm vi kỹ thuật dự kiến

- Tạo display-time service/value object trung tâm, dựa trên `zoneinfo.ZoneInfo`;
  không tự nhân/cộng offset thủ công.
- `BacktestViewModel` sở hữu timezone display và signal để QML/chart/trade log
  rerender mà không làm đổi `BacktestRunConfig` hay `action_id`.
- `BackTestTopPanel.qml` thêm selector/button; `backtest_view.py` bridge vào
  chart native nếu chart renderer không đọc QML ViewModel trực tiếp.
- Chuẩn hóa formatter ở các surface hiện tại thay vì mỗi QML/Python tự gọi
  `strftime`/`toLocaleString` khác nhau.
- Lưu preference ở UI settings nếu hạ tầng settings hiện có phù hợp; không đưa
  preference này vào snapshot provenance của một backtest run.

## 5. Ngoài phạm vi

- Không resample candle, thay đổi timeframe, session market hoặc cách xác định
  nến đã đóng.
- Không thay đổi `start_time`/`end_time` UTC, SQLite schema, request Binance,
  `GetBacktestRangeCoverageQuery`, `SyncMarketDataCommand` hay engine PnL.
- Không làm timezone selector chung cho toàn bộ app trong task này; có thể tách
  thành hạ tầng global sau khi Backtest chứng minh được contract.

## 6. Acceptance criteria và regression tests

1. Unit test formatter: cùng UTC instant được format đúng cho `UTC` và
   `Asia/Ho_Chi_Minh`; test một IANA zone có daylight-saving để chặn cách cộng
   offset thủ công.
2. Unit/Presenter test: đổi display timezone không đổi `BacktestRunConfig`,
   không dispatch run/sync/query và không chuyển FSM sang `CONFIG_DIRTY`.
3. Integration test với fixture có chart marker + trade: đổi timezone qua
   public ViewModel/QML signal, rồi assert chart/trade log/banner cùng đổi
   nhất quán; raw UTC timestamp, số candle, lệnh và PnL giữ nguyên.
4. QML construction test xác nhận selector accessible/clickable, label nói rõ
   timezone hiện hành và tooltip nêu đây chỉ là display setting.
5. Desktop E2E opt-in mở app thật, đổi `UTC` ↔ `Asia/Ho_Chi_Minh`, kiểm tra
   chart tooltip và một dòng trade log lệch đúng 7 giờ nhưng nút Run không đổi
   sang "Cập nhật lại" và không chạy background action.
6. Regression tests được giữ vĩnh viễn; không dùng assertion yếu kiểu chỉ
   kiểm tra selector tồn tại.

## 7. Files dự kiến

- `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`
- `src/presentation/ui/screens/backtest/backtest_view_model.py`
- `src/presentation/ui/screens/backtest/backtest_presenter.py`
- `src/presentation/ui/screens/backtest/backtest_view.py`
- chart/trade-log formatter và QML liên quan
- `tests/unit/presentation/ui/screens/`
- `tests/integration/presentation/`
- Desktop E2E opt-in

## 8. Definition of Done

Người dùng có thể đọc toàn bộ thời gian của màn Backtest bằng timezone đã chọn,
không phải tự đổi UTC trong đầu. Một lần đổi timezone chỉ rerender presentation:
database/API/coverage/backtest result/PnL/FSM action và cấu hình chạy không đổi.
