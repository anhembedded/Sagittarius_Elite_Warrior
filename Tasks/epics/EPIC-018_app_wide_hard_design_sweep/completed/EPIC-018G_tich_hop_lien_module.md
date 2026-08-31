# EPIC-018G — Rà soát tích hợp liên module

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** User yêu cầu 2026-08-30 ("có task check integration giữa các
module"), thêm vào sau 4 audit module-scoped `018C`-`018F`. Ratify ở
[`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục "Tích hợp liên module".

---

## Phạm vi

Khác với `018C`-`018F` (mỗi task đúng 1 module), task này soi đúng **ranh
giới giữa** các module: `domain → application → infrastructure →
presentation`, và 2 composition root (`src/binance_bot_module.py`/
`src/main.py` cho CLI, `src/presentation/ui/app_bootstrapper.py` cho UI).

## Kết quả rà soát

1. **Layer-dependency violations** (domain/application import ngược ra
   ngoài layer): **không tìm thấy** — grep import statement trong
   `src/domain/`, `src/application/` không ra kết quả nào trỏ vào
   `infrastructure`/`presentation` ngoài 2 symbol Shared Kernel đã biết
   (`BaseEvent`, `IDomainEvent`).
2. **Port/Adapter completeness**: spot-check 6 cặp Port↔Adapter chính
   (`IExchangeClient`↔`PythonBinanceClient`, `IMarketDataRepository`↔
   `SQLAlchemyMarketDataRepository`, v.v.) — đều implement đủ, không có
   `# type: ignore` che lỗ hổng.
3. **Composition-root drift**: `main.py`/`app_bootstrapper.py` đều gọi
   chung 1 đường `create_app()`/`BinanceBotModule().register()` — không
   có danh sách wiring độc lập thứ 2 nên drift không thể xảy ra về mặt cấu
   trúc.
4. **Command/Query↔Handler pairing**: 17 use case, `binance_bot_module.py`
   đăng ký đúng 10 command + 7 query = 17, không orphan.
5. **`TimeFrame` qua ranh giới Port** — **I1**: `ILiveStreamService.start_stream(interval_str: str)`
   khai `str` ở chữ ký Port, nhưng cả `StartLiveStreamCommand.interval`
   (đã là `TimeFrame`) lẫn `BinanceWebsocketService` (tự `TimeFrame(interval_str)`
   lại bên trong) đều thực chất làm việc với `TimeFrame` — Handler bị ép
   `.value` xuống rồi Adapter phải dựng lại, đúng lớp bug đã sửa nhiều lần
   (`EPIC-017B`, `EPIC-018A`, `018D`'s D-app-2).

## Việc cần làm

1. `src/application/ports/i_live_stream_service.py`: đổi
   `start_stream(self, symbols: list[str], interval_str: str) -> bool`
   thành `start_stream(self, symbols: list[str], interval: TimeFrame) -> bool`.
2. `src/application/use_cases/stream/start_live_stream/handler.py`: bỏ
   `.value` khi gọi `self._stream_service.start_stream(request.symbols, request.interval)`.
3. `src/infrastructure/binance/binance_websocket_service.py`: đổi
   `start_stream(self, symbols: list[str], interval_str: str) -> bool`
   thành nhận `interval: TimeFrame` thẳng, bỏ dòng `TimeFrame(interval_str)`
   dựng lại — dùng `interval.value` tại đúng biên gọi SDK Binance nếu SDK
   cần chuỗi thô (giữ đúng chỗ, không phải giữ nguyên cả field).

## Tiêu chí xong

- `grep -n "interval_str" src/application/ports/i_live_stream_service.py src/infrastructure/binance/binance_websocket_service.py src/application/use_cases/stream/start_live_stream/handler.py`
  không còn kết quả nào.
- Test `tests/.../start_live_stream*`, `tests/.../binance_websocket_service*`
  xanh không đổi assertion hành vi (chỉ đổi kiểu tham số).
- Không có finding mới nào khác cần xử lý ở mục 1-4 (đã xác nhận sạch).

## Kết quả

- `i_live_stream_service.py`: `start_stream(symbols, interval_str: str)` →
  `start_stream(symbols, interval: TimeFrame)`.
- `start_live_stream/handler.py`: bỏ `.value` khi gọi
  `self._stream_service.start_stream(request.symbols, request.interval)`.
- `binance_websocket_service.py`: `start_stream()` nhận `interval: TimeFrame`
  thẳng, xoá dòng `TimeFrame(interval_str)` dựng lại bên trong — bỏ đúng
  round-trip VO→str→VO đã nêu trong finding.
- Test cập nhật: `test_binance_websocket_service.py` — 2 lời gọi
  `start_stream(["BTCUSDT"], "1m")` đổi sang
  `start_stream(["BTCUSDT"], TimeFrame.ONE_MINUTE)`.
- `105 test xanh` (`test_binance_websocket_service.py` +
  `tests/unit/application/use_cases/`), thêm 9 test integration
  (`test_dashboard_live_stream.py`, `test_dashboard_integration.py`,
  `test_autostart_controller.py`) xanh không đổi assertion, 0 fail. `mypy`
  sạch trên cả 3 file sửa.
