# BUG-086 — `PositionChangedEvent` không bắn khi một vị thế đóng về flat: bảng Vị thế trên màn Giao dịch có thể "sống" sau khi vị thế đã chết

**Reported date:** 2026-09-02
**Severity:** 🟠 **P2** — không crash, không mất tiền, nhưng UI **nói sai sự thật** đúng lúc
người vận hành cần tin nó nhất (đang có giao dịch thật chạy).
**Status:** ✅ **Đã đóng (2026-09-02)** — xem §5.

---

## 1. Hiện tượng (Symptom)

Phát hiện khi dựng `EPIC-021I` (màn Giao dịch): bảng "Vị thế đang mở" được nạp lúc bật giao dịch
(`EnableTradingCommandHandler`'s reconciliation) và sau đó chỉ cập nhật qua `OrderFeed`'s
`positionChanged` signal (mang `PositionChangedEvent`) — đúng thiết kế "OrderFeed-only, không tự
gọi `ITradingClient`" của chính epic này (§2.4). Đọc `futures_user_data_stream.py` để xác nhận
signal đó bắn đúng lúc thì thấy nhánh vị thế **đóng về 0** không bắn gì cả.

## 2. Root cause

`src/infrastructure/binance/futures_user_data_stream.py::_handle_account_update()` — khi
`self._trading_client.get_positions(symbol)` trả về danh sách rỗng (vị thế đã đóng), nhánh xử lý
là:

```python
else:
    logger.info("ACCOUNT_UPDATE %s position closed", symbol)
```

Chỉ log, **không** publish `PositionChangedEvent`. Nhánh còn lại (vị thế vẫn mở, chỉ đổi số
lượng/giá) publish đầy đủ.

`OrderFeed.positionChanged` (`presentation/ui/common/order_feed.py`) chỉ re-emit đúng những gì
event bus phát ra — không có cơ chế nào khác dọn một vị thế đã đóng khỏi bảng UI. Hệ quả trực
tiếp: `TradingPresenter._on_position_changed()` (`EPIC-021I`) không bao giờ được gọi cho trường
hợp đóng vị thế, nên `self._positions` giữ nguyên entry cũ — bảng "Vị thế đang mở" tiếp tục hiển
thị một vị thế đã thực sự đóng trên sàn, với PnL/giá đứng yên tại lần cập nhật cuối, cho tới lần
`EnableTradingCommand` (đối soát lại toàn bộ) kế tiếp.

## 3. Vì sao chưa nổ

`EPIC-021H` (User Data Stream) tự nó không có UI nào hiển thị vị thế — hậu quả chỉ nhìn thấy được
khi có một bảng UI thực sự vẽ `LivePosition` liên tục, đúng lúc `EPIC-021I` mới tạo ra bảng đó.
Trước đó gap này tồn tại nhưng vô hình.

## 4. Suggested next steps

1. `_handle_account_update()`'s "position closed" nhánh phải publish một `PositionChangedEvent`
   mang tín hiệu "đã đóng" — cách rẻ nhất không đổi shape `LivePosition` (không có trường
   `is_closed`): publish với `position_amt=0` và để consumer (đúng một nơi, `TradingPresenter`)
   coi `position_amt == 0` là "gỡ khỏi bảng", hoặc thêm hẳn một event riêng
   (`PositionClosedEvent`) nếu muốn tường minh hơn — quyết định thuộc về người sửa, tuỳ đọc thêm
   `LivePosition`'s invariant "position_amt never appears as 0" (docstring của chính class đó).
2. **Regression test viết trước, đỏ trước khi sửa**: giả một `_handle_account_update()` cho vị
   thế đóng (danh sách `get_positions()` rỗng) → phải thấy đúng một sự kiện bắn ra, event bus
   thật (không mock `IEventBus`), unit, không cần mạng.
3. Cho tới khi sửa: `TradingPresenter` không tự vá bằng polling — đúng chủ ý thiết kế `EPIC-021I`
   §2.4 (không tự gọi `ITradingClient` khi giao dịch tắt/đang chạy). Cách giảm nhẹ duy nhất hiện
   có là bật lại giao dịch (tắt rồi bật `EnableTradingCommand` đối soát lại toàn bộ tài khoản) —
   không phải một fix, chỉ là lối thoát thủ công cho tới khi bug này đóng.

## 5. Đóng thế nào (2026-09-02)

Đi đúng nhánh 2 của §4.1: `PositionClosedEvent` riêng (`domain/events/position_closed_event.py`),
không tái dùng `PositionChangedEvent` với `position_amt=0` — `LivePosition`'s docstring nói thẳng
"Zero never appears here", nên fabricate một VO vi phạm invariant đã ghi rõ của chính nó là sai
hướng hơn thêm một event.

- `_handle_account_update()`'s nhánh "position closed" giờ `emit(PositionClosedEvent(symbol=symbol))`
  cạnh dòng log đã có sẵn.
- `OrderFeed` thêm signal `positionClosed` thứ ba — cùng khuôn `orderFilled`/`positionChanged`, vẫn
  đúng phạm vi "sự thật lệnh/vị thế" đã ghi trong docstring của chính nó (không phải hình dạng Feed
  thứ năm).
- `TradingPresenter._on_position_closed()` (mới) — `self._positions.pop(symbol, None)` rồi
  `_render_positions()`. `pop(..., None)` chứ không index thẳng: event này bắn cho **mọi** symbol
  về flat, kể cả symbol bảng chưa từng có (không có `PositionChangedEvent` nào trước đó trong
  phiên).

**Regression test đúng như §4.2 yêu cầu** — `test_account_update_going_flat_publishes_position_closed`
(`test_futures_user_data_stream.py`): giả `get_positions()` trả về rỗng → đúng một
`PositionClosedEvent` bắn ra, qua `MemoryEventBus` thật, không mock `IEventBus`, không cần mạng.
Cộng `test_position_closed_removes_it_from_the_positions_table`
(`test_trading_presenter_toggle.py`) chứng minh bảng UI thật sự gỡ đúng dòng.

Triệu chứng gốc — bảng "Vị thế đang mở" sống sót sau khi vị thế đã đóng thật trên sàn — không còn
đúng. Đóng.
