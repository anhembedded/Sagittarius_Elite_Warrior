# 🔬 Phân tích Lớp Lỗi & Đề xuất Cơ chế cho Sagittarius Engine

> [!NOTE]
> **Báo cáo phân tích chuyên sâu — nguồn gốc của `BOT-066`…`BOT-071`.**
> Không phân tích từng bug riêng lẻ, mà nhóm toàn bộ lịch sử bug thành **lớp lỗi
> (defect class)** rồi hỏi: *cơ chế nào ở tầng engine sẽ khiến cả lớp đó không
> xảy ra được nữa?* — thay vì vá từng ca một như hiện tại.
>
> Xuất phát từ ghi chú của user ở cuối [`BUG-001`](../bug_report/completed/BUG-001.md):
> *"tôi nghĩ engine nên có cơ chế lo điều này"*.

---

## 1. 📊 Phạm vi & Phương pháp

Nguồn dữ liệu (toàn bộ đã verify tại thời điểm viết, không suy đoán):

- Toàn bộ commit `fix(...)`/`Fix ...` trong lịch sử `Sagittarius_Elite_Warrior`
  (`git log --oneline --all | grep -iE "fix|bug"` → 50+ commit).
- 2 bug report do user viết tay: [`BUG-001`](../bug_report/completed/BUG-001.md) (app treo),
  [`BUG-002`](../bug_report/completed/BUG-002.md) (chart lỗi khi zoom + log đầy warning).
- Các task đã đóng có bản chất bug: `BOT-027`, `BOT-061`, `BOT-062`, `BOT-065`.
- Code hiện trạng của `sagittarius_engine/` (các điểm mở rộng đã có sẵn).

Tiêu chí chọn lọc: chỉ giữ bug **lặp lại ≥ 2 lần** hoặc **1 lần nhưng hậu quả
nặng/âm thầm**. Bug 1 lần, dễ thấy, sửa xong là hết (vd. sai màu, sai chiều cao
layout) **không** tính là lớp lỗi — vá tại chỗ là đúng, thêm cơ chế chỉ tốn thêm.

---

## 2. 🔍 Sáu Lớp Lỗi Xác định được

| Lớp | Ca thực tế | Hình dạng gốc chung |
| :--- | :--- | :--- |
| **C. Tài nguyên nhân bản khi chạy lại** | `a84f58a` (legend), `4ba1eae` (subplot row), `dd565a0` (nến live), `5a063b5` (legend EMA), `f07d490` (overlay EMA) | Một object sống lâu, dùng lại nhiều lần (`ChartCard`) tích luỹ tài nguyên qua từng lần chạy. Teardown làm tay, **nhạy thứ tự** và **nhạy thread** |
| **B. Lỗi bị nuốt âm thầm** | `BOT-061` (thông số user gõ bị vứt, không báo gì) | `safe_ui_action` `print()` rồi `return None` — đang dùng ở **45 chỗ** |
| **A. Chạm UI từ luồng nền** | [`BUG-001`](../bug_report/completed/BUG-001.md) (app treo, `QBasicTimer`) | Luồng nền chạm object Qt; **chỉ phát bệnh** khi Qt cần Timer nội bộ |
| **D. Re-entrancy khi user bấm chồng** | `BOT-027` / `22166fa` | Không có guard single-flight; fix phải viết tay 2 lần cho 2 entry point |
| **E. Marshaling ranh giới QML↔Python** | `BOT-061` (`QJSValue`), 7× `Unable to assign [undefined]` trong log `BUG-002` | Ranh giới không có kiểu, không có tầng chuyển đổi |
| **F. Asset thiếu nhưng fallback im lặng** | `IconLoader` thiếu 7 icon (`BOT-048` khôi phục) | Warn-and-continue; ship lỗi qua nhiều phiên tới khi user tự đọc log |

### 2.1. Ba dữ kiện đáng chú ý về hiện trạng engine

Ba con số dưới đây là lý do các đề xuất ở §3 nằm ở **tầng engine** chứ không phải
tầng app:

1. **`grep -rn "currentThread\|QueuedConnection" sagittarius_engine/` → 0 kết quả.**
   Engine hoàn toàn không có bất kỳ guard thread-affinity nào. Toàn bộ tính đúng
   đắn của lớp A đang dựa vào kỷ luật thủ công của người viết Presenter.
2. **`QJSValue` được xử lý ở đúng 1 chỗ** trong cả repo
   ([`backtest_view_model.py:542`](../../src/presentation/ui/screens/backtest/backtest_view_model.py#L542)
   — chính là bản vá `BOT-061`). Mỗi `@Slot("QVariant")` viết mới sau này là một
   `BOT-061` mới.
3. **`safe_ui_action` đang bọc 45 điểm** nhưng cơ chế của nó là *nuốt lỗi*. Nó
   không phải lưới an toàn — nó là **cái giảm thanh** đặt trên 45 họng súng.

### 2.2. Vì sao lớp C là lớp tốn kém nhất

5 bug, 5 lần sửa, mỗi lần một cách khác nhau. Đáng chú ý nhất là commit message
của `5a063b5`:

> *"clear_from_chart(card) must run BEFORE rebuild() replaces .active, and since
> it touches Qt widgets it must run on the main thread"*

Đây là **một bất biến của cơ chế đang nằm trong commit message** — không có gì
trong code bắt buộc nó, không có gì nhắc người sửa tiếp theo. Lần sau ai đó thêm
một loại tài nguyên mới lên `ChartCard` (marker, region, subplot...), họ phải tự
nhớ lại đúng 2 điều kiện này. Đó là định nghĩa của một lớp lỗi sẽ tái phát.

### 2.3. Ca **không** đề xuất cơ chế

`BOT-062`/`5c20156` (`self._autostart` chỉ gán khi config gate bật, nhưng gọi vô
điều kiện → `AttributeError` ở tick đầu tiên) — về bản chất chỉ là thiếu null-guard.
Xây machinery (null-object pattern, `Maybe` type) cho ca này **tốn hơn phần tiết
kiệm được**. Ghi lại ở đây để lần sau không ai đề xuất lại rồi mất công phân tích.

---

## 3. 🛠️ Sáu Cơ chế Đề xuất

Xếp theo ROI = (số bug chặn được × mức nghiêm trọng) ÷ chi phí triển khai.

| # | Task | Cơ chế | Lớp lỗi chặn | Chi phí |
| :---: | :--- | :--- | :---: | :---: |
| 1 | [`BOT-066`](../completed/BOT-066_fail_loud_ui_action_errors.md) | `safe_ui_action` báo lỗi thật (log + event + re-raise ở dev mode) | B | Thấp |
| 2 | [`BOT-067`](../completed/BOT-067_resource_scope_lifecycle.md) | `ResourceScope` — teardown tự động theo vòng đời lần chạy | C | Trung bình |
| 3 | [`BOT-068`](../completed/BOT-068_ui_thread_affinity_guard.md) | Guard thread-affinity + sanity test quét ViewModel | A | Trung bình |
| 4 | [`BOT-069`](../completed/BOT-069_exclusive_action_single_flight.md) | `ExclusiveAction` — single-flight cho hành động user | D | Thấp |
| 5 | [`BOT-070`](../completed/BOT-070_qml_value_normalizer.md) | `from_qml()` — chuẩn hoá giá trị qua ranh giới QML | E | Rất thấp |
| 6 | [`BOT-071`](../backlog/BOT-071_boot_asset_preflight.md) | Pre-flight asset lúc boot (mở rộng cơ chế đã có) | F | Thấp |

### 3.1. Thứ tự khuyến nghị: `BOT-066` → `BOT-067` → `BOT-068`

`BOT-066` đi trước **không phải vì nó quan trọng nhất**, mà vì nó gần như miễn phí
và nó biến các lớp còn lại thành lỗi **kêu to**. Chừng nào 45 điểm `safe_ui_action`
còn nuốt lỗi, mọi cơ chế mới thêm vào vẫn có thể hỏng âm thầm đúng theo cách
`BOT-061` đã hỏng. Sửa cái giảm thanh trước, rồi mới đi sửa các họng súng.

`BOT-067` đứng thứ hai vì nó là lớp tái phát nhiều nhất (5 bug, §2.2).

`BOT-068` đứng thứ ba dù nó trả lời trực tiếp yêu cầu của user ở `BUG-001` — vì
triệu chứng của nó (treo app) tuy nặng nhất nhưng tần suất thấp nhất (1 ca), và
nó sẽ dễ triển khai đúng hơn nhiều **sau khi** `BOT-066` đã bật chế độ fail-loud.

### 3.2. Hai cặp cơ chế có quan hệ với nhau

- **`BOT-067` ↔ `BOT-069`**: vòng đời của một `ResourceScope` **chính là** vòng đời
  của một `ExclusiveAction`. Nếu làm cả hai, `ExclusiveAction` nên là nơi mở/đóng
  scope, để bất biến "dọn cái cũ trước khi dựng cái mới" (§2.2) được đảm bảo bởi
  đúng một chỗ. **Không** ghép chúng thành 1 task — 2 khái niệm khác nhau, mỗi cái
  dùng được độc lập.
- **`BOT-066` ↔ `BOT-068`**: cả hai đều rẽ nhánh theo `DEV_MODE_CONFIG_KEY`
  (`"dev.mode"`, đã có sẵn ở `sagittarius_engine/extensions/pyside_mvc/base_view.py:9`,
  `BasePresenter` đã đọc nó cho dev-click-logging). Không phát minh cờ mới.

### 3.3. Nguyên tắc chung cho cả 6 task

- **Không phá vỡ app đang chạy.** Mọi cơ chế phải có đường "chế độ cũ" — engine là
  framework dùng chung, không chỉ phục vụ mỗi `Sagittarius_Elite_Warrior`.
- **Enforcement bằng sanity test, không bằng code review.** Repo này đã có văn hoá
  `tests/sanity/` (boot app thật, assert wiring thật). Cơ chế nào cũng cần một
  test quét toàn bộ subclass/call-site để chống drift — vì chính drift là thứ đã
  tạo ra `set_stats()` thiếu `@Slot` trong khi 3 method anh em của nó đều có
  ([`data_management_view_model.py:212`](../../src/presentation/ui/screens/data_management/data_management_view_model.py#L212)).
- **Engine ở repo cha, task board ở submodule.** Cả 6 task đều sửa
  `sagittarius_engine/` (repo cha) — cần commit ở **cả hai** repo, giống mọi task
  đụng engine trước đây (`BOT-030`, `BOT-032`, `BOT-036`).

---

## 4. 📎 Phụ lục — Bằng chứng cho từng lớp lỗi

### Lớp A — Chạm UI từ luồng nền
Chẩn đoán của user trong [`BUG-001`](../bug_report/completed/BUG-001.md) là chính xác và đáng
giữ nguyên văn: progress update bắn thẳng từ luồng nền lên UI; các phiên bản trước
sống sót chỉ vì progress bar **không có animation** nên QML không tạo Timer nào —
*"về lý thuyết vẫn là một quả bom nổ chậm"*. Thêm `Behavior on width { NumberAnimation }`
là kích nổ. Fix đã áp: thêm `@Slot(int, int, bool)` — nhưng làm **thủ công, từng
method một**, và `set_stats()` ngay bên dưới vẫn chưa có.

### Lớp B — Lỗi bị nuốt
`safe_ui_action` ([`thread_bridge.py:27-36`](../../../sagittarius_engine/extensions/pyside_mvc/thread_bridge.py#L27)):
`except Exception` → `print(...)` → duck-typed `ui_log_signal` → `return None`.
Comment trong chính file đó thừa nhận: *"for now we just swallow to prevent crash"*.
Ở `BOT-061`, `TypeError` từ `dict(QJSValue)` đi thẳng vào đây và biến mất — app
không sập, nút "Lưu" trông như đã chạy, nhưng **mọi giá trị user gõ bị vứt bỏ**.

### Lớp C — Nhân bản khi chạy lại
Xem §2.2. Bốn kiểu tài nguyên khác nhau (legend entry, subplot row, curve, danh
sách nến) trên cùng một object dùng lại, sai theo cùng một cách.

### Lớp D — Re-entrancy
Fix của `BOT-027` là cờ `historyLoading` + check FSM viết tay, lặp ở cả
`_on_load_history()` lẫn `_on_start_stream()`
([`stream_lifecycle_controller.py:173-215`](../../src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py#L173)).
Đúng và đang chạy tốt, nhưng là **quy ước**, không phải cơ chế: entry point thứ 3
thêm vào sau này sẽ không tự có guard.

### Lớp E — Marshaling QML
Log trong [`BUG-002`](../bug_report/completed/BUG-002.md) còn 7 dòng
`Unable to assign [undefined] to QString/QColor` (`BotParamField.qml`,
`StrategyComboBox.qml`) — đã xác định ở `BOT-061` là **vô hại** (nhiễu lúc parse
QML lần đầu), nhưng chúng cùng một gốc: ranh giới QML↔Python không có kiểu, nên
cả lỗi thật lẫn nhiễu vô hại đều trông giống hệt nhau trong log. Đó chính là lý do
`BOT-061` mất một vòng điều tra sai hướng trước khi tìm ra bug thật.

### Lớp F — Asset thiếu im lặng
`IconLoader` log `WARNING ... using blank fallback` rồi chạy tiếp. 7 icon biến mất
trong một lần `git reset` giữa các lượt merge và **không ai phát hiện** cho tới khi
user tự đọc log dán vào chat. Engine đã có sẵn `DependencyValidatorExtension` làm
đúng việc "pre-flight, thiếu thì `sys.exit(1)`" cho Python package — chỉ là chưa
áp cho asset UI.
