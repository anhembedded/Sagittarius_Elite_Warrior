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
scope.add(handle, dispose=card.remove_indicator)   # hàm có tên, KHÔNG lambda (theo code-rule)
...
previous_scope.dispose_all()   # LIFO, idempotent, gọi 2 lần không sao
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

- [ ] `ResourceScope` + test đơn vị thuần Python (idempotent, LIFO, dispose lỗi không
      chặn phần còn lại) — chưa đụng UI.
- [ ] Áp cho **đúng 1 chỗ trước**: `IndicatorScriptRunner` (`clear_from_chart`/`rebuild`,
      chính là nơi `5a063b5` đã sửa tay). Verify test hiện có của nó vẫn xanh.
- [ ] Viết test tái hiện lại đúng kịch bản `5a063b5`: bấm chạy 3 lần → assert đúng 4
      đường, không phải 10. Test này phải **vỡ nếu ai đó gỡ scope ra**.
- [ ] Chỉ khi 1 chỗ trên đã ổn: cân nhắc áp tiếp cho `ChartCard`'s indicator/marker/region.
      **Không làm cả 5 chỗ trong một lượt** — xem §4.
- [ ] Ghi rõ trong docstring: dispose chạm widget Qt **phải** ở main thread (liên quan
      [`BOT-068`](BOT-068_ui_thread_affinity_guard.md)).

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
