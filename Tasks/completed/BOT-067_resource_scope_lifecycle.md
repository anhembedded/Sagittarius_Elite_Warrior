# Nhiệm vụ: `ResourceScope` — dọn tài nguyên tự động theo vòng đời lần chạy

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi C,
> lớp tái phát nhiều nhất: 5 bug riêng biệt, 5 lần sửa khác nhau.**
>
> Nên làm **sau** [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) (fail-loud), để lỗi
> trong lúc dọn tài nguyên không tiếp tục bị nuốt.

## 1. Mục tiêu

Năm bug cùng một hình dạng: một object **sống lâu và được dùng lại** (`ChartCard`) tích
luỹ tài nguyên qua từng lần chạy, vì teardown làm tay và dễ quên:

| Commit | Tài nguyên bị nhân bản |
| :--- | :--- |
| `a84f58a` | Legend entry của indicator |
| `4ba1eae` | Subplot row + đăng ký crosshair |
| `dd565a0` | Nến trong history (list bị alias, append 2 lần) |
| `5a063b5` | Legend EMA (10 đường thay vì 4 sau 3 lần bấm) |
| `f07d490` | Overlay EMA khi đổi chế độ chart |

Đáng chú ý nhất là commit message của `5a063b5`:

> *"clear_from_chart(card) must run BEFORE rebuild() replaces .active, and since it
> touches Qt widgets it must run on the main thread"*

Đây là **một bất biến của cơ chế đang nằm trong commit message** — không có gì trong code
bắt buộc nó. Ai thêm loại tài nguyên mới lên `ChartCard` lần sau (marker, region,
subplot...) phải tự nhớ lại đúng 2 điều kiện này. Đó là định nghĩa của lớp lỗi sẽ tái phát.

Mục tiêu: biến bất biến đó thành **thuộc tính của một kiểu dữ liệu**, không phải ghi chú.

## 2. Thiết kế đề xuất

Một `ResourceScope` ở engine (`sagittarius_engine/`, thuần Python — **không phụ thuộc Qt**,
để test được không cần QApplication và để dùng được ngoài phạm vi UI):

```python
scope = ResourceScope()
scope.add(
    handle, dispose=card.remove_indicator
)  # hàm có tên, KHÔNG lambda (theo code-rule)
...
previous_scope.dispose_all()  # LIFO, idempotent, gọi 2 lần không sao
```

Yêu cầu bắt buộc của cơ chế:
- **Idempotent**: `dispose_all()` gọi nhiều lần không lỗi, không dọn nhầm 2 lần.
- **LIFO**: dọn ngược thứ tự đăng ký (subplot row phải dọn sau curve nằm trong nó).
- **Không bỏ dở giữa chừng**: một `dispose` ném exception không được chặn các dispose còn
  lại — thu lại rồi báo cáo cuối (qua cơ chế của `BOT-066`).
- **Không dùng `lambda`** ở bất kỳ call-site nào (theo [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)):
  mỗi `dispose` là một hàm/method có tên, để hiện đúng trong stack trace khi teardown lỗi.

### 2.1. Chưa chốt — quyết lúc code
- **Có nên là context manager (`with`) không?** Nghe hợp lý, nhưng vòng đời thật ở đây
  **trải dài qua nhiều lượt event loop** (mở scope lúc bấm nút, đóng ở lần bấm kế tiếp),
  không nằm gọn trong một khối `with`. Nhiều khả năng API rõ ràng (`dispose_all()`) đúng
  hơn `with`. Đọc call-site thật rồi quyết.
- **Ai giữ scope?** Nếu làm cả [`BOT-069`](BOT-069_exclusive_action_single_flight.md) thì
  `ExclusiveAction` là nơi hợp lý nhất để mở/đóng scope (xem §3.2 của báo cáo). Nếu làm
  `BOT-067` trước, tạm để Presenter giữ, nhưng **thiết kế API sao cho chuyển giao được**.

## 3. Các bước thực hiện

- [x] `ResourceScope` + test đơn vị thuần Python (idempotent, LIFO, dispose lỗi không
      chặn phần còn lại) — chưa đụng UI.
- [x] Áp cho **đúng 1 chỗ trước**: `IndicatorScriptRunner` (`clear_from_chart`/`rebuild`,
      chính là nơi `5a063b5` đã sửa tay). Verify test hiện có của nó vẫn xanh.
- [x] Viết test tái hiện lại đúng kịch bản `5a063b5`: bấm chạy 3 lần → assert đúng 4
      đường, không phải 10. Test này phải **vỡ nếu ai đó gỡ scope ra**.
- [ ] Chỉ khi 1 chỗ trên đã ổn: cân nhắc áp tiếp cho `ChartCard`'s indicator/marker/region.
      **Không làm cả 5 chỗ trong một lượt** — xem §4. *(Cố ý để lại — đúng quyết định gốc
      của task, xem mục 6.)*
- [x] Ghi rõ trong docstring: dispose chạm widget Qt **phải** ở main thread (liên quan
      [`BOT-068`](BOT-068_ui_thread_affinity_guard.md)).

## 6. Kết quả triển khai thực tế

**`ResourceScope`** (`sagittarius_engine/runtime/tasks/resource_scope.py`, mới, thuần
Python — không import Qt, xuất qua `runtime/tasks/__init__.py` cạnh `CancellationToken`):
`add(handle, dispose)` (append, khoá `threading.Lock` cho an toàn đa luồng) +
`dispose_all()` (LIFO qua `pop()` từ cuối danh sách — tự nhiên idempotent vì danh sách
rỗng thì vòng lặp không chạy, không cần cờ `_disposed` riêng). Lỗi teardown: mỗi
`dispose` chạy trong `try/except`, lỗi được **gom lại**, KHÔNG chặn các dispose còn lại;
nếu có lỗi, `dispose_all()` `raise ExceptionGroup(...)` **sau khi** đã chạy hết — khớp
đúng "thu lại rồi báo cáo cuối qua cơ chế BOT-066": `ExceptionGroup` là subclass của
`Exception` nên `safe_ui_action`'s `except Exception` bắt được, log+emit tự động không
cần `ResourceScope` biết gì về logger/event bus. 7 test mới (LIFO, idempotent, lỗi không
chặn phần còn lại, nhiều lỗi gom vào 1 group, retry sau lỗi không lặp lại lỗi cũ).

**Áp dụng cho `IndicatorScriptRunner`** (đúng 1 chỗ, đúng quyết định gốc): `ActiveScript`
thêm field `scope: ResourceScope`. `draw()` — khi đăng ký 1 đường mới — gọi thêm
`active.scope.add(qualified, dispose=functools.partial(card.remove_indicator, qualified))`
cạnh `registered_lines.add()` cũ (giữ nguyên `registered_lines` cho việc check "đã vẽ
chưa", tách bạch khỏi việc "dọn thế nào" mà `scope` lo). `clear_from_chart()` đổi từ vòng
lặp tay `for line_name in registered_lines: card.remove_indicator(...)` sang
`active.scope.dispose_all()` — **hệ quả đúng ý**: dispose giờ luôn gọi qua đúng `card`
đối tượng lúc `draw()` (chụp qua `functools.partial`), không phải `card` truyền vào lúc
gọi `clear_from_chart()`, nên không còn phụ thuộc 2 lời gọi phải cùng nhận đúng 1 `card`.
`region`/`info`/`marker` clearing **giữ nguyên không đụng** (gọi thẳng, không qua scope) —
đúng phạm vi hẹp của task, chỉ đường vẽ (line) là nơi bug `5a063b5` xảy ra.

**Verify**: test cũ `test_clear_removes_every_registered_curve_from_the_chart` từng set
tay `registered_lines` (bỏ qua `draw()` thật) — sửa lại đi qua `feed()`+`draw()` thật, vì
set tay không còn kích hoạt `scope`. Thêm 1 test mới
`test_repeated_rebuild_clear_cycles_never_leave_stale_curves_registered` — chạy 3 vòng
`clear→rebuild→draw` (đúng thứ tự `_rebuild_scripts()` thật) rồi 1 lần clear thứ 4, assert
đúng 4 đường bị xoá (không phải 0, không phải >4). **Xác nhận bằng tay**: code hiện tại
(trước `BOT-067`) đã tự sửa đúng từ `5a063b5` nên 2 test này **không phân biệt được**
code cũ/mới nếu chỉ revert file — verify thật bằng cách xoá tay dòng
`active.scope.add(...)` khỏi `draw()` (mô phỏng ai đó gỡ scope sau này) → cả 2 test fail
đúng như kỳ vọng (`0 == 4`), rồi khôi phục lại. Đây là bằng chứng thật cho "test phải vỡ
nếu ai đó gỡ scope ra" — không phải suy đoán.

**Không mở rộng sang `ChartCard`'s indicator/marker/region** (đúng cảnh báo §4 của task —
"cám dỗ lớn nhất là refactor cả 5 chỗ cùng lúc, đừng"). 776 test app (1 fail không liên
quan, có sẵn từ trước) + 397 test engine pass, `ruff` sạch cả 2 repo.

## 4. Rủi ro / Lưu ý

- **Cám dỗ lớn nhất của task này là refactor cả 5 chỗ cùng lúc.** Đừng. Cả 5 chỗ đều
  đang **chạy đúng** (đã sửa xong rồi); giá trị của task là chống tái phát ở chỗ *thứ 6*.
  Áp 1 chỗ, chứng minh cơ chế đúng, rồi dừng lại đánh giá.
- `dd565a0` (list bị alias) **không** phải lớp lỗi này giải quyết được — đó là bug
  aliasing của mutable state, ghi vào bảng ở §1 để đủ bối cảnh chứ `ResourceScope` không
  chặn nó. Đừng cố kéo nó vào phạm vi.
- Engine là framework dùng chung — `ResourceScope` không được import Qt.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp C (§2.2).
- [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) — nên làm trước (lỗi teardown cần kêu to).
- [`BOT-069`](BOT-069_exclusive_action_single_flight.md) — cặp đôi tự nhiên, xem §2.1.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.
