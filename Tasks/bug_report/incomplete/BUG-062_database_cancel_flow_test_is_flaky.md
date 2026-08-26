# BUG-062 — `test_database_cancel_button_cancels_active_sync_flow` đỏ ngẫu nhiên

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | 🟡 **Đã bịt lớp lỗi, chưa tái hiện được cú đỏ** — xem §Đã làm và §Chưa chứng minh |
| **Mức độ** | 🟡 P2 — không ảnh hưởng app đã ship; làm CI đỏ ngẫu nhiên |
| **Phát hiện** | 2026-08-26, khi chạy tier integration lúc điều tra `BUG-060` |
| **Liên quan** | **`BUG-030` §"Data point khác từ 2026-08-23" — cùng test, cùng lớp lỗi, cách nhau 3 ngày** |

## Đây là lần gặp THỨ HAI, không phải bug mới

`BUG-030` đã ghi lại một lần gặp mà lúc đó chưa ai nối được với gì:

| Ngày | Test | Lỗi |
| :--- | :--- | :--- |
| 2026-08-23 | `test_database_cancel_button_cancels_active_sync_flow` | `ListAvailableSymbolsQuery failed: object of type 'Mock' has no len()` |
| 2026-08-26 | **cùng test** | `SyncMarketDataCommand failed: 'Mock' object is not iterable` |

Cùng test, cùng lớp lỗi (**một `Mock` thô nằm ở chỗ đáng lẽ là collection thật**),
cùng chạy `-n` song song, cùng không tái hiện khi chạy lại. Hai mẫu độc lập.

## Hiện tượng

```
>       qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
E       pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
```

kèm, ngay phía trên trong log của **đúng lần đỏ đó**:

```
ERROR    App:std_logger.py:87 SyncMarketDataCommand failed: 'Mock' object is not iterable
```

Chạy lại cùng lệnh, cùng cấu hình: `82 passed`, **0** lỗi Mock. Bốn lần chạy tier
này trước đó cũng 0.

Thứ tự test **không** phải biến số: `pytest-randomly` không hề được cài trong
repo — mọi cờ `-p no:randomly` rải rác trong tài liệu cũ đều là no-op.

## Đã làm — bịt cả lớp, không vá từng lần gặp

Fixture `database_app_context` dùng `Mock(spec=IExchangeClient)`. `spec=` chỉ
ràng buộc **tên** method, không ràng buộc kiểu trả về — nên bất kỳ đường nào
fixture chưa cấu hình sẽ trao một `Mock` thô cho code production thật, rồi nổ
khi handler gọi `len()` hoặc lặp lên nó.

Chính comment cũ trong fixture đã mô tả đúng lớp lỗi này. Nhưng cách xử lý mỗi
lần gặp là **cấu hình thêm một method nữa** — sửa được lần đó, để nguyên lớp.
`get_available_symbols` được thêm sau lần 2026-08-23; lần 2026-08-26 nổ ở
method tiếp theo trong dãy.

Thay bằng `_FakeExchangeClient` **viết tay**. Một class thật không thể sinh ra
`Mock` thô: method thiếu là `AttributeError` gọi đúng tên nó, tại call site,
**mọi lần chạy**.

Kèm hai test, đã fault-inject:

| Phá gì | Kết quả |
| :--- | :--- |
| bỏ một method khỏi fake | test drift đỏ, gọi đúng tên method thiếu |
| trả iterator dùng-một-lần | test iterator đỏ |
| khôi phục | 3 passed |

Cũng sửa một khiếm khuyết tiềm ẩn độc lập: Mock cũ dùng
`return_value = iter(())` — iterator **dùng một lần**, nên mọi lần gọi sau lần
đầu trả về **cùng một** object đã cạn. Ở đây đều rỗng nên vô hại, nhưng một test
sync hai lần sẽ im lặng nhận rỗng ở lần hai và đọc như đang pass.

## Chưa chứng minh — đọc kỹ chỗ này

**Chưa tái hiện được cú đỏ**, nên **không tuyên bố** bản thay này sửa nó. Nó bịt
đường mà cả hai lần gặp đều đi qua (một `Mock` thô tới được code thật); nó không
giải thích *vì sao* đường đó chỉ thỉnh thoảng bị đi.

Hai giả thuyết đã **bị bác bỏ** trong lúc điều tra, ghi lại để lần sau khỏi đi lại:

1. **"Method chưa được cấu hình."** Sai: `IExchangeClient` có đúng ba method, và
   fixture cấu hình **cả ba**.
2. **"`unittest.mock` không thread-safe nên child mock đã cấu hình bị thay."**
   Không tái hiện được: stress test 8 thread × 4000 vòng reset/cấu hình lại,
   **0 lỗi**.

Vẫn để **Open**. Đóng khi tái hiện được, hoặc khi tier integration chạy đủ nhiều
lần sau thay đổi này mà không tái xuất.

---

## Đã tái hiện SAU bản vá `b94b7ff` — thêm 2026-08-26 (phiên `EPIC-003E`)

Mục trên nói *"chưa tái hiện được cú đỏ"*. **Tái hiện được rồi**, và là **sau**
khi `_FakeExchangeClient` đã thay `Mock`. Ghi lại vì đây đúng là dữ kiện mục trên
đang thiếu.

Đo trên 5 lượt `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` liên tiếp,
cùng một máy, trong lúc làm việc **không đụng gì tới `data_management/`**:

| Lượt | Kết quả test này |
| :-: | :--- |
| 1 | ❌ đỏ |
| 2 | ✅ (cây sạch, không có việc đang dở) |
| 3 | ❌ đỏ — **kèm** một test khác cũng đỏ (`test_ui_state_coordinator::test_marking_again_restarts_the_window`) |
| 4 | ✅ |
| 5 | ❌ đỏ |

**3/5 lượt đỏ.** Triệu chứng **y hệt** mô tả ở §Hiện tượng:

```
qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
E  pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
```

Hai điều bản vá **đã** làm được, đọc từ log lượt đỏ:

- Dòng `SyncMarketDataCommand failed: 'Mock' object is not iterable` — có ở mọi
  lần gặp **trước đây** — **không còn xuất hiện**. Fixture `_FakeExchangeClient`
  hiện diện trong output (`database_app_context = (..., <_FakeExchangeClient ...>)`).
- Nên: bản vá **đã bịt đúng lớp lỗi nó nhắm tới**. Cú đỏ còn lại là **nguyên
  nhân khác**, không phải cái cũ sót lại.

### Hai quan sát thu hẹp được phạm vi

1. **Chạy riêng luôn xanh.** 10/10 lượt chạy đơn lẻ test này đều pass (2 đợt × 5).
   Chỉ đỏ khi chạy trong suite song song (`-n`), khớp họ `BUG-030`.
2. **Lượt 3 đỏ kèm một test khác**, và test kia có docstring **tự ghi** rằng nó
   hỏng khi máy tải nặng:
   > *"It passed alone and **failed inside the full unit run** ... because on a
   > loaded machine `wait(75)` really can take longer than the 150ms window"*

   Hai test đỏ **khác nhau giữa các lượt** là chữ ký của **flake theo tải**, không
   phải của một regression (regression đỏ cùng một test mọi lượt).

**Giả thuyết đề xuất cho lần điều tra sau:** không phải `Mock`, mà là **timeout
2000ms quá sát** khi worker `xdist` tranh CPU. Cách kiểm rẻ nhất: chạy suite với
`-n 2` thay vì mặc định và xem tỉ lệ đỏ có tụt không. Nếu có, cái cần sửa là chỗ
test chờ (`waitUntil` theo điều kiện thay vì theo hạn giờ cứng), không phải
production code.
