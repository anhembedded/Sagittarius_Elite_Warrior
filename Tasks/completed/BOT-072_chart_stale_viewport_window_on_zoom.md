# Nhiệm vụ: Chart mất nến sau khi zoom out rồi zoom in — viewport window bị stale

> Nguồn: 📄 [`BUG-002`](../bug_report/BUG-002.md) do user báo kèm ảnh chụp
> ([`image.png`](../bug_report/image.png)): *"zoom out nhiều, sau đó zoom in lại thì bị vầy"*.
>
> **Đã điều tra, xác định được root cause, CHƯA sửa.** Toàn bộ §2 đã verify trực tiếp trên
> code (kể cả source của `pyqtgraph` đang cài) tại thời điểm viết task — không suy đoán.
> Nhưng **chưa tái hiện được bằng test tự động**, và theo
> [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md) thì đó là việc **đầu tiên**
> phải làm, trước khi sửa bất kỳ dòng nào.

## 1. Triệu chứng

Sau khi zoom out rất xa rồi zoom in trở lại, chart rơi vào trạng thái hỏng: **nến biến mất
ở phần lớn bề ngang**, trong khi marker Buy/Sell **vẫn hiện đầy đủ** trên đúng vùng không
có nến nào bên dưới.

Trong ảnh user gửi: trục X trải 02:00→12:00, nhưng nến chỉ tồn tại từ ~07:30 trở đi. Marker
Buy/Sell nằm rải khắp 02:00→07:00 — lơ lửng trên vùng trống.

**Chi tiết này chính là manh mối quyết định**, không phải nhiễu: tập phần tử *biến mất* trùng
khít với tập phần tử *có dùng viewport windowing*, còn `marker_layer.py` — thành phần duy nhất
**không** dùng windowing — là thành phần duy nhất vẽ đủ toàn dải.

## 2. Root cause (đã verify)

`viewport_windowing.py` (tối ưu hoá pan: chỉ vẽ phần đang nhìn thấy thay vì cả 5000 nến) có
**3 nơi dùng**, và cả 3 đều thiếu đúng một thứ: **không có gì kích hoạt lại chúng khi viewport
đổi.**

### 2.1. `grep "sigRangeChanged\b" src/` → **0 kết quả**
Không chỗ nào trong app lắng nghe sự kiện "viewport vừa đổi range". Ba chỗ đang connect là
`sigRangeChangedManually` — **signal khác**, chỉ phát khi user tự pan/zoom, dùng cho mục đích
khác hẳn ([`viewport_controller.py`](../../src/presentation/ui/components/chart_card/viewport_controller.py)
lo trạng thái auto-follow, `edge_scroll_detector.py`, `zoom_controls.py`) — không cái nào
re-window gì cả.

### 2.2. Hai renderer dùng "push model" — nhưng không ai push
| Hàm | Docstring của chính nó | Thực tế |
| :--- | :--- | :--- |
| `IndicatorManager.refresh_window()` ([indicator_manager.py:91](../../src/presentation/ui/components/chart_card/indicator_manager.py#L91)) | *"Called by ChartCard whenever the chart's viewport changes (pan/zoom)"* | **ChartCard không hề gọi.** `grep` toàn `src/` → 0 call site |
| `VolumeRenderer.set_visible_range()` ([volume_renderer.py:86](../../src/presentation/ui/components/chart_card/volume_renderer.py#L86)) | tương tự | **Không ai gọi** |

Hệ quả: `self._visible_range` mãi là `None` → cả hai rơi vào nhánh fallback `lo, hi = 0, len(...)`
→ **vẽ toàn bộ**. Output **đúng**, nhưng tối ưu hoá coi như **code chết**. Đây cũng là lý do
đường EMA và volume trong ảnh không bị thủng lỗ giống nến.

### 2.3. `FastCandlestickItem` dùng "pull model" — và đây mới là chỗ sinh bug
Khác 2 renderer trên, nó không chờ ai push. `paint()` gọi `_visible_history_slice()`, hàm này
**tự đọc** `self.getViewBox().viewRange()` ngay tại thời điểm vẽ
([candlestick_item.py:113-130](../../src/presentation/ui/components/chart_card/candlestick_item.py#L113)).
Nên nó **thật sự có** windowing.

Vấn đề: output của `paint()` phụ thuộc `viewRange()`, **nhưng không có gì báo Qt phải vẽ lại
khi `viewRange()` đổi.**

pyqtgraph đã chừa sẵn đúng cái móc cho việc này, và nó là móc **rỗng** — cố ý để item tự override:

```
GraphicsItem.py:445   view.sigRangeChanged.connect(self.viewRangeChanged)
GraphicsItem.py:474   def viewRangeChanged(self):
                          """Called whenever the view coordinates ... have changed."""
                          # (không có thân hàm — chỉ docstring + comment)
```

`FastCandlestickItem` **không override** `viewRangeChanged()`, cũng không tự connect
`sigRangeChanged` để gọi `self.update()`.

Bình thường vẫn chạy đúng vì pan/zoom thường khiến Qt expose lại toàn khung và `paint()` chạy
lại với `viewRange()` mới. Nhưng khi Qt quyết định vùng đó không cần vẽ lại (BSP tree/exposed
region sau một cú zoom out cực rộng rồi zoom in), slice của **lần paint trước** ở nguyên đó
trong khi transform đã đổi → nến vẽ theo cửa sổ cũ, trống trơn ở chỗ cửa sổ cũ không có dữ liệu.

### 2.4. Vì sao bug này *xuất hiện muộn*
Trước khi có windowing, `paint()` vẽ mọi nến bất kể `viewRange()` → không phụ thuộc viewport →
không cần invalidate. Chính lần tối ưu hoá pan đã biến `paint()` thành **viewport-dependent**
mà không kèm theo cơ chế invalidate tương ứng. Đây là regression do tối ưu hoá, không phải lỗi
có từ đầu.

## 3. Hai việc tách bạch — đừng gộp

### 3.1. Sửa bug (bắt buộc)
Làm cho candlestick item vẽ lại khi viewport đổi. Hai cách, **chọn một, không làm cả hai**:
- **Native pyqtgraph**: override `viewRangeChanged()` trong `FastCandlestickItem` → `self.update()`.
  Gọn nhất, đúng contract của thư viện, không cần ChartCard biết gì.
- **Tập trung ở ChartCard**: một chỗ connect `sigRangeChanged` rồi tự điều phối cả 3 renderer.
  Lợi thế: giải quyết luôn §3.2 bằng cùng một mối nối.

Khuyến nghị: làm **cách 1 trước** vì nó vá đúng bug với bề mặt thay đổi nhỏ nhất, rồi mới bàn §3.2.

### 3.2. Quyết định số phận của tối ưu hoá đã chết (tách riêng)
`refresh_window()`/`set_visible_range()` là code chết có docstring **nói sai sự thật** (khẳng
định ChartCard gọi mình). Hai lựa chọn đều chấp nhận được, **để nguyên thì không**:
- **Nối dây thật**: connect `sigRangeChanged` → gọi cả 2. Được đúng phần perf mà module
  `viewport_windowing.py` sinh ra để giải quyết (docstring của nó ghi: *"QPicture.play() alone
  cost ~4.2s across 200 simulated pan frames"*). **Rủi ro**: `sigRangeChanged` phát rất dày khi
  pan; re-slice + `setData()` mỗi lần phát có thể tự nó thành nút thắt — **phải đo trước/sau**,
  không nối rồi tin là nhanh hơn.
- **Xoá đi**: nếu đo ra không đáng, xoá 2 hàm + phần fallback, giữ windowing chỉ cho candlestick.

**Không tự quyết — hỏi user**, vì đây là đánh đổi perf chứ không phải đúng/sai.

## 4. Các bước thực hiện

- [x] **Tái hiện bằng test trước** (bắt buộc, [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)).
      Seam gợi ý — test `paint()` trực tiếp rất khó, đừng cố:
      dựng `FastCandlestickItem` gắn vào ViewBox thật với N nến, đặt X range rộng, ép vẽ, rồi
      đổi sang X range hẹp và **assert item được invalidate** (spy `update()`), và
      `_visible_history_slice()` trả đúng cửa sổ mới. Test phải **fail trước khi sửa**.
- [x] Sửa theo §3.1 (chọn 1 cách).
- [x] Chạy lại toàn bộ test `chart_card` hiện có — không được sửa test nào để cho xanh.
- [x] Kiểm bằng tay đúng kịch bản user mô tả: zoom out thật xa → zoom in → nến phải còn đủ.
- [x] Ghi lại kết quả đo perf nếu có đụng §3.2.

## 8. Kết quả triển khai thực tế

Làm đúng cách 1 của §3.1 (native pyqtgraph, bề mặt thay đổi nhỏ nhất, đúng khuyến nghị của
task): thêm `FastCandlestickItem.viewRangeChanged()` (`candlestick_item.py`), override hook
rỗng của `pyqtgraph.GraphicsItem` — chỉ gọi `self.update()`. Hook này tự động được nối dây bởi
pyqtgraph khi item được `addItem()` vào một `ViewBox` thật (`GraphicsItem._updateView()` connect
`view.sigRangeChanged` → `self.viewRangeChanged`), nên không cần sửa gì ở `ChartCard`.

**Test tái hiện trước khi sửa** (`tests/unit/presentation/ui/components/test_candlestick_item.py`,
file mới): dựng `pg.PlotItem()` thật, `addItem()` 1 `_SpyCandlestickItem` (subclass đếm số lần
`update()` được gọi) với 200 nến, set X range rộng rồi hẹp qua `plot_item.vb.setRange(xRange=...)`
— trước fix `update_call_count == 0` (bug tái hiện đúng như §2.3 mô tả), sau fix `> 0`. Test thứ 2
(`test_visible_history_slice_reflects_the_current_viewport_after_a_range_change`) xác nhận
`_visible_history_slice()` luôn tính đúng ngay cả **trước** fix — đúng như §2.3 chỉ ra, bug nằm ở
chỗ **không ai gọi lại `paint()`**, không phải ở phép tính slice.

**Kiểm tay** (script offscreen, không phải phiên GUI thật có chuột — môi trường dev không có
display): dựng `ChartCard` thật với 1000 nến, `vb.setRange(xRange=(-500000, 500000))` (mô phỏng
zoom out rất xa) rồi `vb.setRange(xRange=...)` hẹp lại trong vùng có dữ liệu — `_visible_history_slice()`
trả về đúng 21 nến trong cửa sổ hẹp, không rỗng. Đây **không phải bằng chứng hình ảnh thật** (không
grab pixel so sánh trước/sau fix) — mức độ tin cậy thật sự tới từ test đầu tiên (spy `update()`),
vốn trực tiếp verify đúng cơ chế root cause đã xác định ở §2.3, không phải suy đoán.

**Không đụng §3.2** (số phận `refresh_window()`/`set_visible_range()` code chết) — đúng quyết
định "không tự quyết" của task gốc, để lại nguyên trạng chờ user chốt hướng nếu muốn làm tiếp.

775 test unit+sanity pass (1 fail không liên quan, `test_interactive_shell_wait_for_exit_exception`
— `ModuleNotFoundError: No module named 'src'`, xác nhận lỗi có sẵn từ trước bằng `git stash`,
không phải do thay đổi của task này), `ruff` sạch.

## 5. Rủi ro / Lưu ý

- **Không phải mất dữ liệu.** `history_data` vẫn đủ; chỉ là không được vẽ. Không có nguy cơ
  sai số liệu backtest/indicator — thuần lỗi hiển thị. Đừng đi tìm bug ở tầng domain.
- Ảnh của user còn 2 dị thường nhỏ chưa giải thích được (nhãn giá `166.4613` dính ở góc trên
  trái, subplot dưới hiện thang 110/120/130 kèm nhãn `8:10:46`). **Nhiều khả năng cùng một
  gốc** (trục tự scale theo slice rỗng), nhưng **chưa verify** — nếu sửa §3.1 xong mà 2 dị
  thường này còn, tách task riêng, đừng mở rộng task này.
- Đừng nhầm `sigRangeChanged` với `sigRangeChangedManually`. Ba chỗ đang dùng cái thứ hai đều
  **đúng** với mục đích của chúng — không được đổi chúng sang cái thứ nhất.
- `marker_layer.py` cố ý không windowing. Đừng "cho nhất quán" bằng cách thêm windowing vào nó
  trong task này.

## 6. Liên hệ với nhóm Engine Hardening

Không thuộc 6 lớp lỗi ở 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md),
nhưng cùng họ với **lớp F (fallback im lặng)**: `if self._visible_range is None: vẽ tất cả` là
một fallback hợp lý-về-mặt-kết-quả, và chính nó đã **che giấu việc dây chưa được nối** — code
chạy đúng nên không ai phát hiện tối ưu hoá không hề chạy. Nếu
[`BOT-071`](BOT-071_boot_asset_preflight.md) mở rộng thành nguyên tắc chung "fallback phải kêu",
ca này là ví dụ tốt để nhắc tới.

## 7. Phụ thuộc

- 📄 [`BUG-002`](../bug_report/BUG-002.md) + [ảnh chụp](../bug_report/image.png) — báo cáo gốc của user.
- Không phụ thuộc task nào khác. Sửa **chỉ trong `Sagittarius_Elite_Warrior/src/`** (không đụng
  `sagittarius_engine/`) → chỉ cần commit ở submodule + bump pointer.
