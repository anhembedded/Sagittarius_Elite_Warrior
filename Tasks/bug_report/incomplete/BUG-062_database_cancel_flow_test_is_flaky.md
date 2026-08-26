# BUG-062 — `test_database_cancel_button_cancels_active_sync_flow` đỏ ngẫu nhiên

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | 🔴 Mở — **chỉ ghi hiện tượng**, chưa điều tra root cause |
| **Mức độ** | 🟡 P2 — không ảnh hưởng app đã ship; làm CI đỏ ngẫu nhiên, và một cổng đỏ ngẫu nhiên thì mất tin cậy rất nhanh |
| **Phát hiện** | 2026-08-26, khi chạy tier integration trong lúc điều tra `BUG-060` |
| **Liên quan** | `BUG-030` (worker chết trong lần chạy song song) — cùng họ "suite không ổn định khi chạy `-n`" |

## Hiện tượng

`tests/integration/presentation/test_database_user_flow.py::test_database_cancel_button_cancels_active_sync_flow`

```
>       qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
E       pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
```

Ngay phía trên trong log của **đúng lần chạy đỏ đó**:

```
ERROR    App:std_logger.py:87 SyncMarketDataCommand failed: 'Mock' object is not iterable
```

## Bằng chứng nó là flake, không phải hỏng thật

Chạy **cùng một lệnh, cùng cấu hình** ngay sau đó:

| Lần | Kết quả | Số lần lỗi `'Mock' object is not iterable` |
| :-- | :--- | :-: |
| 1 | `1 failed, 81 passed, 4 skipped` | 1 |
| 2 | `82 passed, 4 skipped` | 0 |

Và bốn lần chạy tier này trước đó (log còn giữ) đều **0 lần** xuất hiện lỗi Mock.

Thứ tự test **không** phải biến số: `pytest-randomly` không hề được cài trong
repo này — mọi cờ `-p no:randomly` rải rác trong tài liệu/bug cũ đều là no-op.

## Chưa điều tra

Chưa xác định vì sao `SyncMarketDataCommand` đôi khi nhận `Mock` không iterable
được từ `IExchangeClient` giả, trong khi phần lớn lần chạy thì không. Hai
hướng chưa loại trừ:

1. Fixture `database_app_context` cấu hình mock theo một đường phụ thuộc thời
   điểm (ví dụ `return_value` được set sau khi một task nền đã kịp gọi).
2. Một task nền của test **trước đó** trong cùng xdist worker còn sống và gọi
   vào mock của test này — đúng lớp hazard `BUG-030` mô tả.

Hướng (2) đáng thử trước, vì nó giải thích luôn tính ngẫu nhiên.
