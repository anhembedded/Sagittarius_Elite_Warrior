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

## Cập nhật 2026-08-26 (lần 2) — bản sửa fixture KHÔNG chặn được flake

Sau khi thay `Mock(spec=IExchangeClient)` bằng `_FakeExchangeClient` viết tay,
test **vẫn đỏ** trong một lần chạy `ci-local.ps1 -Full` ngay sau đó:

```
>       qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
E       pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
```

Điểm quyết định: fixture trong dòng header của lần đỏ này đúng là
`_FakeExchangeClient`, và **toàn bộ log có 0 lỗi `Mock`**.

**Kết luận rút ra:** lỗi `'Mock' object is not iterable` / `has no len()` là
**triệu chứng đi kèm, không phải nguyên nhân**. Bản sửa fixture đã đóng đúng
đường nó bịt — không còn `Mock` thô nào tới được code thật — nhưng cái làm test
đỏ là **FSM không kịp vào `UIMode.SYNCING` trong 2000ms**, và điều đó vẫn xảy ra.

Giả thuyết mới, chưa kiểm chứng: dưới tải song song (`-n`), tác vụ nền dispatch
`SyncMarketDataCommand` không được lập lịch kịp trong cửa sổ 2 giây, nên FSM
chưa chuyển trạng thái khi `waitUntil` hết giờ. Nếu đúng thì đây là **test quá
chặt về thời gian**, không phải lỗi sản phẩm — nhưng phải đo, không đoán.

Hướng điều tra tiếp:

1. Ghi lại `presenter.fsm.current_state` **thực tế** lúc timeout (hiện tại
   thông báo chỉ nói "không phải SYNCING", không nói nó đang ở đâu).
2. Nếu nó đang ở trạng thái trung gian hợp lệ → nới timeout hoặc chờ theo tín
   hiệu thay vì theo đồng hồ.
3. Nếu nó ở trạng thái lỗi → có lỗi thật, và cần biết lỗi gì.

**Không nới timeout trước khi biết câu 1** — nới mù là cách biến một bug thật
thành một test ngủ quên.

### Đo tỉ lệ — thêm từ phiên `EPIC-003E`

Kết luận trên trùng khớp với những gì phiên `EPIC-003E` đo được độc lập. Phần
bổ sung là **tỉ lệ**, và một quan sát thứ hai:

Trên **5 lượt `ci-local.ps1 -Full` liên tiếp**, cùng máy, từ một cây làm việc
**không đụng file `data_management/` nào**:

| Lượt | Test này |
| :-: | :--- |
| 1 | ❌ |
| 2 | ✅ (cây sạch, không có việc đang dở) |
| 3 | ❌ — **kèm** `test_ui_state_coordinator::test_marking_again_restarts_the_window` cũng đỏ |
| 4 | ✅ |
| 5 | ❌ |

**3/5 đỏ.** Chạy riêng: **10/10 xanh** (2 đợt × 5).

Quan sát ở lượt 3 củng cố giả thuyết "quá chặt về thời gian": test đỏ **kèm**
kia có docstring **tự ghi** rằng nó hỏng khi máy tải nặng —

> *"It passed alone and **failed inside the full unit run** ... because on a
> loaded machine `wait(75)` really can take longer than the 150ms window"*

**Mỗi lượt đỏ một tập test khác nhau** là chữ ký của flake theo tải, không phải
của regression (regression đỏ cùng một test mọi lượt).

**Cách kiểm rẻ nhất cho bước 1–3 ở trên:** chạy suite với `-n 2` thay vì mặc
định và so tỉ lệ đỏ. Nếu tỉ lệ tụt, biến số là tranh CPU giữa worker `xdist`,
và chỗ cần sửa là chỗ test chờ — chờ theo tín hiệu thay vì theo hạn giờ cứng —
chứ không phải production code.
