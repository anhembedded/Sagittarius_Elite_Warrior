# BOT-095E1 — Backtest: Metadata thị trường và trạng thái xác minh order rule

**Thuộc:** `BOT-095E`  
**Ưu tiên:** P2 — truthful validation boundary  
**Phụ thuộc:** `BOT-001` ✅

## Vấn đề

`BOT-095E` cần validation market rule nhưng repo hiện không lưu/cache metadata
của symbol (`MIN_NOTIONAL`/`NOTIONAL`, `LOT_SIZE`, `PRICE_FILTER`). Không được
hard-code `5 USDT`, và không được coi vốn backtest là order notional thật.

## Mục tiêu

1. Có application port + immutable snapshot cache theo đúng symbol/market và
   timestamp refresh cho exchange filters.
2. Validation nhận một **order intent/quantity/price** có thể tính được, không
   nhận `initialCapital` rồi giả định đó là notional.
3. Khi metadata thiếu/cũ, UI hiển thị trạng thái `Chưa xác minh theo quy tắc
   sàn`; không block Backtest simulation và không nói là đã đạt yêu cầu Binance.
4. Khi metadata có mặt, validation hiển thị rõ filter cụ thể và thời điểm cache;
   không network-call trong lúc gõ input.

## Ngoài phạm vi

- Không đặt lệnh thật, không cần API key, không nối trực tiếp validation UI vào
  Binance mỗi keystroke.
- Không đổi sizing/PaperExchange long-only. Mapping simulation sizing → order
  intent phải được chốt minh bạch trước khi dùng metadata để chặn một run.

## Acceptance

- Unit test cache stale/missing/fresh và từng filter bằng fixture Binance mẫu.
- Integration test UI chứng minh missing metadata là **unverified**, không phải
  valid/invalid giả.
- Metadata network smoke là opt-in; fixture cached là proof bắt buộc.

