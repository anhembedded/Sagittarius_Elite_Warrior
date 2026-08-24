# BUG-040 — Gate không tin cậy 100%: 2 dạng flaky lộ ra khi chạy `-Full`

**Trạng thái:** ✅ Một cái đã sửa và verify (crosshair phantom hover); một cái còn quan sát,
chưa tái hiện được nên chưa sửa (không đoán mò)
**Phát hiện:** 2026-08-24, trong lúc dọn `.venv_alias` và merge `EPIC-005`

---

## 1. Bối cảnh phát hiện

Sau khi merge `EPIC-005` vào `master-warrior`, chạy `ci-local.ps1 -Full` liên tục nhiều lần để
xác nhận không hồi quy. Gate đỏ 2 lần **không cùng nguyên nhân với nhau**, cả hai đều chỉ xuất
hiện dưới `-Full` (6 worker song song + sanity job nền), không tái hiện khi chạy đơn lẻ.

## 2. Dạng #1 — `test_database_cancel_button_cancels_active_sync_flow` (chưa sửa, chưa tái hiện lại)

```
FAILED tests/integration/presentation/test_database_user_flow.py::test_database_cancel_button_cancels_active_sync_flow
ERROR - ListAvailableSymbolsQuery failed: object of type 'Mock' has no len()
ERROR - SyncMarketDataCommand failed: 'Mock' object is not iterable
```

Chạy riêng 3/3 lần đều pass. Nghi vấn: `pytest-xdist` dùng `--dist=load` (mặc định), phân phối
test động theo tiến độ, không theo file — nên hai test **không liên quan nhau** có thể rơi vào
cùng một worker process, chạy tuần tự trong cùng process Python. Nếu có state global/container
singleton không được dọn sạch giữa các test trong cùng worker (không phải giữa các worker, vì đó
là process riêng), một test khác để lại `Mock` ở đâu đó có thể rò rỉ sang test này.

**Chưa sửa** — sau khi sửa dạng #2 bên dưới, chạy lại `-Full` **5/5 lần liên tiếp đều xanh**,
dạng #1 không xuất hiện lại lần nào. Không đủ bằng chứng để xác định nguyên nhân thật, sửa mù sẽ
chỉ che giấu triệu chứng. **Để theo dõi tiếp** — nếu tái xuất hiện, việc đầu tiên cần làm là bật
`pytest -p no:cacheprovider --dist=loadscope` hoặc log `gw#` id của mỗi test để xác định coi hai
test có thật sự rơi cùng worker không, trước khi sửa bất cứ gì.

## 3. Dạng #2 — `test_crosshair_sweep_is_stable_without_any_phantom_hover` (đã sửa, đã verify)

```
tests/sanity/test_bug036_benchmark_crosshair_hover_race.py:258: AssertionError
WARNING - [bench-crosshair] synthetic hover overwrote the crosshair after the
final move: authored=150 flushed=101 (BUG-036; contract uses authored)
```

### Nguyên nhân gốc

Test này **cố tình không** gọi `_deliver_phantom_hover()` — mục đích là chứng minh "không có
nhiễu thì cả hai chỉ số đọc đều khớp, chẩn đoán không kêu oan". Nhưng dưới tải máy cao (6 worker
+ sanity job cùng chạy), chính bản thân `view.show()` → `QTest.qWaitForWindowExposed()` →
`grabWindow()` trong fixture `native_chart` cũng có thể tự phát sinh một hover ảo tại con trỏ ảo
của offscreen platform — và **một lần `qapp.processEvents()`** sau `grabWindow()` không đảm bảo
sự kiện đó đã thực sự được dispatch. Dưới tải cao, nó có thể tới trễ, rơi đúng vào lúc
`drive_programmatic_crosshair_sweep()` của **test tiếp theo** đang tự gọi `processEvents()` —
đúng race mà `BUG-036` được sinh ra để phát hiện, chỉ khác là lần này nguồn nhiễu là chính setup
của fixture, không phải nhiễu do test cố ý tạo.

### Sửa

`tests/sanity/test_bug036_benchmark_crosshair_hover_race.py` — fixture `native_chart`: thêm vòng
lặp "settle" có giới hạn (20 lần `processEvents()` + `QTest.qWait(5)`) ngay sau
`grabWindow()`/`processEvents()` đầu tiên, trước khi `yield`. Cùng pattern đã có sẵn trong
`test_native_chart_qml_plugin_sanity.py::_wait_for_property()` (poll bounded thay vì sleep cố
định). Không đụng code C++/QML, không đổi hành vi benchmark thật — chỉ đảm bảo sự kiện phát sinh
từ setup được xử lý hết trước khi test body bắt đầu.

### Xác minh — trước/sau, không suy đoán

| | Trước sửa | Sau sửa |
| :--- | :--- | :--- |
| Chạy `-Full` lặp lại | 2/2 lần **FAIL** đúng test này | **5/5 lần PASS liên tiếp** |
| Chạy riêng lẻ (không tải) | 4/4 lần pass (không tái hiện được ở đây — đúng vì đây là bug do tải) | không đổi |

Log mỗi lần verify: `grep FAILED|ERROR|Traceback|ResourceWarning` sạch, `1800 passed / 54
sanity` cả 5 lần.

## 4. Việc không nằm trong phạm vi bug này

Trong lúc điều tra, xoá `.venv_alias/` (cơ chế PYTHONPATH cũ, dư thừa từ khi repo từng được
clone với tên có gạch ngang — user đã đổi tên thư mục checkout đúng, xác nhận bằng import test
thực tế) và sửa 3 script phụ thuộc nó (`ci-local.ps1`, `preview-qml.ps1`,
`benchmark_test_speed.ps1`). Việc này **không liên quan tới flaky** (test dạng #2 vẫn dùng tên
file/đường dẫn đúng dù `.venv_alias` còn hay mất — đã verify bằng traceback path), nhưng đi
chung commit vì cùng một phiên dọn dẹp gate.
