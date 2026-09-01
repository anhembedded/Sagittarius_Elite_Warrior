# EPIC-003F1 — Lát cắt đầu tiên: `TradeLogViewModel` + facade chuyển tiếp

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu — phạm vi đã chốt 2026-09-01
**Phụ thuộc:** hướng C đã duyệt ở [`EPIC-003F`](EPIC-003F_backtest_viewmodel_composite_design_review.md) §4.
Không phụ thuộc kỹ thuật task nào. **Liên quan:** [`EPIC-021L`](../../EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021L_dao_chieu_phu_thuoc_qml_screens.md) — làm trước sẽ gọn hơn (xem §2.4), nhưng không chặn.

---

## 1. Bối cảnh & vấn đề thật

`EPIC-003F` đã đo, đã chốt hướng (facade chuyển tiếp — hướng C), và dừng ở đúng một dòng: *"Mở task
con `EPIC-003F1` — facade + sub-ViewModel đầu tiên, theo §4.1. **Chưa làm; cần user duyệt phạm vi
trước.**"* Task này là lát cắt đó.

Đo lại 2026-09-01 (số ở `003F` là của 27/08, đã trôi):

| | 27/08 (`003F` §2) | 01/09 |
| :--- | ---: | ---: |
| `backtest_view_model.py` | 1.368 dòng | **1.435** |
| `@Property` | 64 | **55 đếm được bằng regex khai báo** |
| `Signal` | 68 | 68 |

Ngưỡng cứng của repo: >400 dòng/file, >15 method công khai/lớp
(`architecture-rule.md` §5.4). File này vượt ~3,6× và ~3,7×.

## 2. Lát cắt đầu tiên: **trade log** — và vì sao là nó

Sáu nhóm thuộc tính tự nhiên trong ViewModel, đo bằng số **điểm đọc** trong `src` + `tests`:

| Nhóm | Prop | Điểm đọc | Ghi chú |
| :--- | ---: | ---: | :--- |
| Cấu hình chiến lược | 12 | 165 | Lớn nhất, đụng mọi modal |
| Tham số broker/execution | 15 | 179 | Lớn nhất |
| Khoảng thời gian | 6 | 63 | |
| Tiến trình & kết quả chạy | 15 | 91 | |
| **Trade log** | **6** | **56** | ← lát cắt này |
| Trạng thái UI lặt vặt | 4 | 38 | Nhỏ nhất **nhưng không cohesive** |

**Chọn trade log, không chọn nhóm nhỏ nhất.** Nhóm "UI lặt vặt" (38 điểm đọc) tuy nhỏ hơn nhưng gồm
ba mối quan tâm không liên quan nhau — tab nào đang mở, config có bẩn không, lần chạy cuối ra sao.
Tách theo nó là dựng đúng cái sọt mà `architecture-rule.md` §5.2 cấm, và lát cắt đầu tiên là lát cắt
**định hình khuôn cho 5 lát sau** — sai khuôn ở đây thì sai cả năm lần.

Trade log thắng vì đường nối đã tồn tại sẵn ở **ba** tầng khác, không phải do tôi vẽ ra:

1. **Coordinator:** `coordinators/trade_log_coordinator.py` (`EPIC-003E`) đã tách logic ra rồi.
2. **Widget ViewModel:** `qml/TradeLogTable/trade_log_vm.py` (`EPIC-015`) đã có ViewModel riêng cho
   đúng dữ liệu này.
3. **Module logic thuần:** `trade_log_row.py`, `trade_log_filter.py`, `trade_log_pagination.py`.

Nói cách khác: mọi tầng khác **đã** coi trade log là một đơn vị riêng. Chỉ ViewModel là chưa.

### 2.1 Sáu thuộc tính và sáu signal của lát cắt

```
tradeLogRows        tradeLogTotalCount   tradeLogTotalPages
tradeLogFilter      tradeLogSearchText   tradeLogCurrentPage

tradeLogRowsChanged  tradeLogFilterChanged  tradeLogSearchTextChanged
tradeLogCurrentPageChanged  tradeLogQueryChanged  tradeLogExportRequested
```

### 2.2 Một nguồn độc lập xác nhận đúng lát cắt này

`qml/TradeLogTable/NOTES.md` — viết trước task này, bởi một đợt làm khác — nêu đúng điều kiện còn
thiếu để nối widget QML vào màn thật:

> *"wiring this to a real screen later means `BackTestViewModel` needs an unpaginated 'all filtered
> rows' source, not today's per-page one — a real, small change on the host side when that wiring
> happens, not a silent assumption."*

Đó chính xác là một thay đổi **bên trong** `TradeLogViewModel` mà task này tạo ra. Khi hai đợt làm
độc lập cùng chỉ vào một đường cắt, đường cắt đó nhiều khả năng là đường cắt thật.

**Nhưng task này KHÔNG nối widget và KHÔNG bỏ pagination.** Xem §3.2 — đó là bước sau, task khác.

### 2.3 Ràng buộc của `003F` §4, áp nguyên văn

1. **Facade trước, dời sau.** Bước một chỉ tạo `TradeLogViewModel` và cho `BackTestViewModel`
   forward sang — **không sửa call site nào**. Phải giữ toàn bộ test pass **không sửa một dòng
   test nào**; phải sửa test nghĩa là facade sai, dừng lại.
2. **Không big-bang.** Task này dời **một** nhóm (6 thuộc tính), không phải cả 55.
3. **Gỡ facade là task riêng, cuối cùng.** Dừng giữa chừng thì facade ở lại — nó vẫn đúng.
4. Bật `mypy` cho `presentation/` là việc tốt độc lập (`EPIC-002D`), **không** được chặn task này.

### 2.4 Quan hệ với `EPIC-021L`

`021L` dời `trade_log_row.py`/`trade_log_filter.py` sang `qml/TradeLogTable/`. Hai task đụng cùng
vùng nhưng **khác trục**: `021L` đổi *chỗ ở của module*, `003F1` đổi *chủ sở hữu của thuộc tính*.

Làm `021L` trước thì `003F1` gọn hơn (import trong `TradeLogViewModel` trỏ thẳng chỗ mới, không
phải sửa hai lần). Nhưng **không chặn**: làm ngược lại chỉ tốn một lần đổi import. Tránh làm **song
song** — cả hai đều chạm `coordinators/trade_log_coordinator.py`.

## 3. Thiết kế

### 3.1 Facade là `@Property` forward, không phải `__getattr__`

```python
# backtest_view_model.py — sau bước 1
class BackTestViewModel(QObject):
    def __init__(self, ...):
        self._trade_log = TradeLogViewModel(parent=self)
        self._trade_log.rowsChanged.connect(self.tradeLogRowsChanged)
        ...

    def _get_trade_log_rows(self) -> list: return self._trade_log.rows
    tradeLogRows = Property(list, _get_trade_log_rows, notify=tradeLogRowsChanged)
```

**Không dùng `__getattr__` để forward hàng loạt**, dù ngắn hơn nhiều. Lý do cụ thể của repo này:
`presentation/` bị loại khỏi cổng `mypy` (`003F` §2.2), nên `__getattr__` sẽ khiến **mọi** tên viết
sai đều trở thành hợp lệ về mặt tĩnh **và** im lặng lúc chạy cho tới đúng lúc UI cần giá trị đó. Một
`@Property` viết tay thì `AttributeError` nổ ngay tại chỗ, và `grep` ra được.

Đây là 6 property forward. Với 55 property thì lập luận có thể khác — nhưng ràng buộc §2.3.2 nói
không bao giờ có lần nào 55.

### 3.2 Signal: kết nối lại, không phát hai lần

Mỗi signal của sub-ViewModel `connect` thẳng tới signal cùng tên trên facade. Không có `emit()` thủ
công ở facade — nhân đôi đường phát là cách tạo ra một `beginInsertRows` thừa, đúng lớp lỗi
`BUG-042` đã trả giá.

### 3.3 Task này KHÔNG làm ba việc sau

| Không làm | Vì |
| :--- | :--- |
| Bỏ pagination / thêm nguồn "all filtered rows" | Đó là **đổi hành vi**. Bước 1 phải chứng minh được "không đổi gì" bằng việc không sửa dòng test nào. Việc này thuộc task nối widget QML |
| Nối `qml/TradeLogTable/` vào màn Backtest | Cùng lý do; và nó cần `021L` xong trước |
| Dời 5 nhóm còn lại | Ràng buộc §2.3.2 |

## 4. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `screens/backtest/view_models/trade_log_view_model.py` | **Mới** — `TradeLogViewModel(QObject)`, 6 property + 6 signal, mang theo logic đang nằm trong `BackTestViewModel` |
| `screens/backtest/backtest_view_model.py` | Dựng sub-VM, forward 6 property, nối 6 signal; **xoá** state đã dời (không giữ hai bản) |
| — | **Không sửa file nào khác.** Đó là định nghĩa của bước facade |

Thư mục `view_models/` mới (số nhiều) là chỗ hạ cánh cho 5 lát sau — `architecture-rule.md` §7.1:
điểm mở rộng đã biết phải có chỗ có tên, để người làm lát thứ hai bắt chước được thay vì tự chế.

## 5. Kiểm thử

- **Điều kiện dừng, không phải mong muốn:** toàn bộ test hiện có pass **với diff của `tests/` rỗng
  tuyệt đối**. Không một dòng import, không một assert. Khác với `021L` (được sửa dòng `import`) —
  ở đây call site không đổi *chút nào*, nên test cũng không.
- **Unit mới cho `TradeLogViewModel`:** test thẳng sub-VM (lọc, tìm kiếm, đổi trang) không qua
  facade — đây là thứ lát cắt này mua được và phải chứng minh là đã mua được.
- **Unit (facade):** đọc `vm.tradeLogRows` trả đúng `vm._trade_log.rows`; `_trade_log.rowsChanged`
  phát ra làm `tradeLogRowsChanged` phát **đúng một lần** (mutation-verify: thêm `emit()` thủ công
  ở facade → test phải đỏ).
- **Cổng đầy đủ:** `ci-local.ps1 -Full` xanh, và `backtest_view_model.py` phải **giảm** dòng — nếu
  không giảm thì state đang tồn tại hai bản.

## 6. Mốc chạy được

```bash
# 1. Bằng chứng của bước facade: diff tests/ rỗng
git diff --stat tests/            # → không có gì
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/f1.log 2>&1
grep -E "^[0-9]+ (passed|failed)|failed," /tmp/f1.log | tail -3
```

```bash
# 2. Sub-VM chạy độc lập, không cần dựng BackTestViewModel 1.435 dòng
PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/unit/presentation/ui/screens/backtest/view_models/test_trade_log_view_model.py -q
```

```bash
# 3. Con số phải đi đúng chiều
wc -l src/presentation/ui/screens/backtest/backtest_view_model.py       # < 1.435
wc -l src/presentation/ui/screens/backtest/view_models/trade_log_view_model.py
```

Mốc 2 là thứ đáng nhìn nhất: hôm nay muốn test logic trade log phải dựng cả ViewModel 1.435 dòng.
Sau task này, nó là một `QObject` nhỏ dựng được một mình — và đó là toàn bộ lý do `EPIC-003` tồn tại.

## 7. Sau task này

Năm lát còn lại, **mỗi lát một task riêng**, theo thứ tự rủi ro tăng dần: khoảng thời gian (63) →
tiến trình & kết quả (91) → cấu hình chiến lược (165) → tham số broker (179). Nhóm "UI lặt vặt" (38)
xử lý cuối, và có thể kết luận là **không tách** — bốn thuộc tính không liên quan nhau thì ở lại
facade là đúng, không phải là việc còn dở.

Gỡ facade là task cuối cùng của `EPIC-003F`, chỉ mở khi cả 344 điểm đọc đã dời hết (`003F` §4.3).
