# BOT-122: `correlation_id` thay cho lọc theo symbol/interval cho progress event chéo màn

**Trạng thái:** ✅ Hoàn thành (2026-08-31)

## 1. Bối cảnh & vấn đề thật

User: *"progress bar đang không follow đúng progress mà nó nên tracking, nếu có nhiều chỗ
publish event. cần 1 cơ chế phân biệt event nào của obj màn hình nào"* — hỏi tiếp thì xác nhận
đây là yêu cầu thiết kế chung (chưa có bug cụ thể mới), tiếp nối trực tiếp `BOT-121`.

`BOT-121` đã fix cross-talk giữa Backtest và Data Management (2 màn cùng nghe
`SingleSyncProgressEvent` trên 1 bus, `SyncProgressFeed` phát cho cả hai) bằng cách mỗi
coordinator tự lọc report có `(symbol, interval)` khớp với action nó đang chờ. Cách đó **là
một hack dựa trên trùng hợp dữ liệu nghiệp vụ, không phải định danh thật**: hai action khác
nhau (VD Backtest tự sync coverage-gap cho BTCUSDT/1m, đồng thời Data Management bấm resync
tay đúng BTCUSDT/1m) hoàn toàn có thể nhắm cùng 1 khoá `(symbol, interval)` — khi đó lọc theo
khoá đó không phân biệt được, y hệt bug gốc mà `BOT-121` sửa.

## 2. Thiết kế

Thêm `correlation_id: str` — sinh **tại nơi phát sinh request** (mỗi coordinator, khi nó quyết
định dispatch), xuyên suốt tới tận UI, thay hẳn việc lọc theo khoá nghiệp vụ:

```
Coordinator sinh correlation_id (uuid4)
  → SyncMarketDataCommand.correlation_id / BulkSyncMarketDataCommand.correlation_id
    → SyncMarketDataCommandHandler._progress_cb đọc command.correlation_id
      → SingleSyncProgressEvent.correlation_id
        → SyncProgressFeed chuẩn hoá, giữ nguyên, KHÔNG đụng vào
          → SyncProgressReport.correlation_id
            → Coordinator so sánh với correlation_id nó đang giữ
```

- `SyncMarketDataCommand`/`BulkSyncMarketDataCommand`: field mới, `default_factory=uuid4` — caller
  không cần biết tới nó vẫn hoạt động (CLI, test); coordinator cần theo dõi thì set tường minh và
  giữ lại để so sánh sau.
- Bulk sync: **1 batch = 1 correlation_id**, chia sẻ cho MỌI target trong batch (khác `BOT-121`
  vốn phải giữ 1 `set[(symbol,interval)]` vì không có định danh chung) —
  `BulkSyncMarketDataCommandHandler._sync_single_target` truyền `command.correlation_id` (của
  batch) vào từng `SyncMarketDataCommand` nó tự dựng cho từng target.
- `SyncProgressFeed`: chỉ đi qua, không "chuẩn hoá" `correlation_id` thành gì khác — đây là
  identity, không phải business data. Đã ghi rõ vào docstring của `base_feed.py`'s "công thức
  thăng cấp" và `sync_progress_feed.py` để Feed tương lai theo đúng khuôn.
- Kết quả: `DataSyncCoordinator._active_sync: tuple[str,str]|None` →
  `_active_correlation_id: str|None`; `SyncCoordinator._active_targets: set[tuple[str,str]]` →
  `_active_correlation_id: str|None` (đơn giản hơn hẳn — không cần set nữa vì bulk sync giờ chỉ
  có 1 id, không phải N cặp khoá).

## 3. Ngoài phạm vi

- Không đưa `correlation_id` lên `BaseEvent` (engine) — hiện chỉ 1 loại event
  (`SingleSyncProgressEvent`) thật sự cần, chưa đủ 2 consumer thật để thăng cấp lên engine theo
  đúng triết lý "thăng cấp khi có nhu cầu thật thứ 2" (`base_feed.py`). Nếu 1 event type khác sau
  này cũng cần — lúc đó mới cân nhắc đưa lên `BaseEvent`.
- Không đụng `BulkSyncProgressEvent` — chỉ Data Management nghe, không cross-talk.

## 4. Kiểm thử

- `test_sync_market_data_handler.py`: `SingleSyncProgressEvent` mang đúng `correlation_id` của
  command (test đỏ xác nhận: đổi handler in cứng `"WRONG"` → test fail đúng lý do, phục hồi →
  xanh).
- `test_bulk_sync_market_data.py`: mọi target trong 1 batch dispatch dưới cùng 1
  `correlation_id` của batch.
- `test_data_sync_coordinator.py`/`test_sync_coordinator.py`: report có `correlation_id` khác
  (kể cả khi symbol/interval TRÙNG với action đang chạy — đúng ca `BOT-121` không xử lý được)
  bị bỏ qua; report đúng `correlation_id` vẫn đi qua.

**Xác minh:** Linux thật (PySide6 6.11.1 + `sagittarius_engine`), 46 test liên quan trực tiếp +
310 test rộng hơn (`application/`, `screens/backtest/`, `screens/data_management/`) đều pass.
`tests/sanity/test_composition_root.py` (DI thật): 8 passed. `ruff`/`mypy`: sạch.
