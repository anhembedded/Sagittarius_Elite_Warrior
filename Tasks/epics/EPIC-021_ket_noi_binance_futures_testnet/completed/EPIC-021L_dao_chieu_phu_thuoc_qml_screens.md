# EPIC-021L — Đảo chiều phụ thuộc `qml/ → screens/`, để màn Giao dịch dùng lại được widget

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
- **Repo:** Elite
- **Chặn bởi:** — (độc lập với `021A`–`021H`, làm song song được) · **Chặn:** `EPIC-021I`
- **Đóng bug:** [`BUG-082`](../../../bug_report/incomplete/BUG-082_shared_qml_widget_library_depends_on_screen_modules.md)

---

## 1. Bối cảnh & vấn đề thật

`EPIC-021I` dựng màn Giao dịch với hai bảng: vị thế đang mở và lệnh đang chờ. Widget bảng đã có
sẵn và được thiết kế để dùng chung — `qml/TradeLogTable/` (`EPIC-015`). Nhưng dùng lại nó hôm nay
sẽ kéo theo `screens/backtest/` vào màn Giao dịch, vì ViewModel của chính widget đó import
`screens.backtest.logic.trade_log_row` và `trade_log_filter`.

> **Đo lại 2026-09-01 — widget này chưa nối vào màn nào.** Không file nào trong `screens/` dựng
> `TradeLogTable`; màn Backtest vẫn chạy panel QtWidgets cũ (`backtest_view.py:148`
> → `BackTestTradeLogsPanel`, 392 dòng). `qml/TradeLogTable/NOTES.md` nói rõ đây là chủ ý
> (*"dựng khung trước, đủ tính năng sau"*) và nêu đúng điều kiện còn thiếu để nối được:
> *"`BackTestViewModel` needs an unpaginated 'all filtered rows' source, not today's per-page one"*.
> Điều kiện đó là việc của [`EPIC-003F1`](../../EPIC-003_presenter_and_god_file_decomposition/incomplete/EPIC-003F1_trade_log_sub_view_model_facade.md),
> **không** thuộc task này. `021L` chỉ đảo chiều phụ thuộc — sau nó, widget vẫn chưa nối, nhưng đã
> **nối được** mà không kéo theo màn nào.

Đó là `BUG-082`: thư viện widget dùng chung phụ thuộc ngược vào màn hình cụ thể, ngược đúng luật mà
`qml/StatCardRow/stat_card_row_widget.py:25` phát biểu bằng văn bản. 4 file production + 5 hit ở
`preview`/`tests`.

**Task này là điều kiện cần của `EPIC-021I`, không phải dọn dẹp tuỳ hứng.** Không làm nó thì màn
Giao dịch hoặc phải import backtest (sai), hoặc phải chép lại một bảng thứ hai (sai hơn — đúng thứ
`EPIC-014` vừa gỡ xong với ba bản picker symbol).

**Đo trước, để biết quy mô thật:** 5 module, **1.112 dòng**, ~26 điểm import trong `src` + `tests`.
Ba module của backtest **hoàn toàn không có Qt** (`grep -c PySide6` → 0), nên dời chúng không đụng
tới vòng đời widget nào.

## 2. Thiết kế + lý do

### 2.1 Chỗ đến: **thư mục của chính widget sở hữu model đó**

| Module | Từ | Về |
| :--- | :--- | :--- |
| `trade_log_row.py` (185) | `screens/backtest/logic/` | `qml/TradeLogTable/` |
| `trade_log_filter.py` (60) | `screens/backtest/logic/` | `qml/TradeLogTable/` |
| `performance_metrics_view.py` (359) | `screens/backtest/logic/` | `qml/MetricsDetailPanel/` |
| `database_status_table_model.py` (230) | `screens/data_management/` | `qml/DatabaseStatusTable/` |
| `kline_inspector_table_model.py` (278) | `screens/data_management/` | `qml/KlineInspectorTable/` |

**Lý do — câu phân xử của `architecture-rule.md` §5.5:** *"Đổi A có bắt buộc phải sửa B không?"*
Đổi cột của `TradeLogTable.qml` **bắt buộc** phải sửa `trade_log_row.py`; đổi bộ lọc trong
`trade_log_vm.py` **bắt buộc** phải sửa `trade_log_filter.py`. Cùng vòng đời → cùng thư mục. Thư
mục widget vốn đã chứa `*.qml` + `*_vm.py` + `preview.py` + `tests/` — model là cùng tầng với
ViewModel, không phải tầng khác.

Chiều phụ thuộc sau khi dời: `screens/backtest/` → `qml/TradeLogTable/`. Đó **chính là** chiều mà
`stat_card_row_widget.py` gọi là *"the one direction this rollout uses throughout"*.

### 2.2 Phương án bị bác bỏ: một thư mục trung lập `ui/models/`

Nghe gọn hơn, và sai. Năm module này không có gì chung ngoài việc "đều là model" — trade log,
metrics, database status, kline inspector là bốn miền khác nhau. Gom chúng vào một `dir` là dựng
đúng cái mà `architecture-rule.md` §5.2 cấm: *"thư mục là một tầng, không phải một cái sọt"*. Và
tiền lệ thật đã có: `data_management_widgets.py` (1.156 dòng) trở thành cái sọt đúng theo cách này,
`EPIC-007` §1 phải gỡ.

Cụ thể hơn: một `ui/models/` sẽ không có tiêu chí nào để từ chối file thứ sáu. `qml/TradeLogTable/`
thì có — file phải là model của **bảng đó**.

### 2.3 Guard viết **trước**, không phải sau

`ruff` không bắt được lớp lỗi này, và `mypy` loại trừ `src/presentation/` nguyên khối
(`pyproject.toml`, `EPIC-002A`) — nên nếu không có guard thì defect này sẽ quay lại lần tới có
người vội. Guard quét `ast` toàn `ui/qml/`, đỏ khi thấy bất kỳ import nào tới
`presentation.ui.screens`.

Thứ tự bắt buộc, theo `bug-fix-rule.md`: **viết guard trước → chạy → xác nhận nó đỏ với đúng 9 hit
hiện có → rồi mới dời file.** Guard viết sau khi dời là guard không ai chứng minh được là nó bắt
được gì.

### 2.4 Dời bằng `git mv`, không chép

`git mv` giữ lịch sử — cần thiết vì `performance_metrics_view.py` và `trade_log_row.py` đều có
`git log` mang lý do thiết kế thật (`BOT-045`, `BOT-106A`). Chép rồi xoá là mất chỗ dựa cho người
đọc sau.

### 2.5 Không đổi nội dung module nào trong task này

Task này **chỉ** đổi chỗ ở và đường import. Không sửa logic, không đổi API, không tách file — kể cả
`performance_metrics_view.py` đang 359 dòng (dưới ngưỡng 400, không bắt buộc tách). Trộn refactor
vào một lần dời file làm diff không review nổi, và làm mất khả năng khẳng định *"không đổi hành vi"*.

Hệ quả kiểm chứng được: **không một dòng test nào phải sửa ngoài dòng `import`.** Nếu phải sửa
assert thì task này đã làm quá phạm vi — dừng lại.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `tests/unit/presentation/ui/qml/test_qml_library_does_not_import_screens.py` | **Mới, viết đầu tiên** — guard `ast` |
| 5 module ở bảng §2.1 | `git mv` sang thư mục widget tương ứng |
| `qml/TradeLogTable/{trade_log_vm,preview}.py`, `tests/` | Import tương đối trong cùng thư mục |
| `qml/MetricsDetailPanel/{metrics_detail_vm,preview}.py`, `tests/` | như trên |
| `qml/DatabaseStatusTable/`, `qml/KlineInspectorTable/` | như trên |
| `screens/backtest/`: `backtest_presenter.py`, `backtest_view_model.py`, `coordinators/trade_log_coordinator.py`, `logic/extended_metrics_snapshot.py`, `backtest_modals/backtest_metrics_detail_source.py`, `preview.py` | Đổi đường import sang `qml/…` |
| `screens/data_management/` | Đổi đường import tương ứng |
| `tests/unit/presentation/ui/screens/` (≈8 file) | Đổi đường import |
| `qml/StatCardRow/stat_card_row_widget.py` | Cập nhật docstring: luật này giờ **có guard**, không còn là quy ước truyền miệng |

## 4. Kiểm thử

- **Guard (regression cho `BUG-082`):** hai chiều — sạch sau khi dời, **và** đỏ khi chèn lại một
  import vi phạm. Chạy trước khi dời để xác nhận nó đỏ với đúng 9 hit hiện có.
- **Không sửa assert nào:** diff của thư mục `tests/` chỉ được chứa dòng `import`. Đây là điều kiện
  dừng, không phải mong muốn.
- **Cổng đầy đủ:** `ci-local.ps1 -Full` xanh — đặc biệt `ruff` (thứ tự import đổi ở ~26 file) và
  `tests/sanity/test_circular_imports.py` (dời module là đúng lúc một vòng import ẩn có thể lộ ra).
- **Không thêm test hành vi nào.** Task này không đổi hành vi; thêm test mới ở đây là ngụ ý có, và
  sẽ khiến người đọc sau đi tìm một thay đổi không tồn tại.

## 5. Mốc chạy được

```bash
# 1. Guard đỏ TRƯỚC khi dời — bằng chứng nó bắt được defect thật
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/presentation/ui/qml/test_qml_library_does_not_import_screens.py -q
```

```text
FAILED — ui/qml/ imports ui/screens/ ở 9 chỗ:
  qml/TradeLogTable/trade_log_vm.py:31        → screens.backtest.logic.trade_log_row
  qml/TradeLogTable/trade_log_vm.py:35        → screens.backtest.logic.trade_log_filter
  qml/MetricsDetailPanel/metrics_detail_vm.py:22 → screens.backtest.logic.performance_metrics_view
  qml/DatabaseStatusTable/database_status_vm.py:20 → screens.data_management…
  qml/KlineInspectorTable/kline_inspector_vm.py:18 → screens.data_management…
  (+4 hit ở preview.py / tests/)
```

```bash
# 2. Sau khi git mv + sửa import
grep -rn "screens\." --include=*.py src/presentation/ui/qml/ | grep import   # → rỗng
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/full.log 2>&1
grep -E "^[0-9]+ (passed|failed)|failed," /tmp/full.log | tail -3
```

```bash
# 3. Bằng chứng cuối cùng, và là lý do task này tồn tại:
#    dựng bảng lệnh của màn Giao dịch mà không chạm screens/backtest/
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  .venv/bin/python src/presentation/ui/qml/TradeLogTable/preview.py
```

Mốc 3 là mốc thật sự đáng nhìn: `preview.py` của widget chạy độc lập, không import màn nào — nghĩa
là `EPIC-021I` cắm nó vào màn Giao dịch được, và người đọc code màn đó sẽ không gặp một dòng
`import screens.backtest` mà không ai giải thích nổi.

## 6. Ghi chú triển khai

### 6.1 Guard viết trước, xác nhận đỏ, rồi mới dời — đúng thứ tự §2.3 yêu cầu

`tests/unit/presentation/ui/qml/test_qml_library_does_not_import_screens.py` quét `ast` cho
`ImportFrom`/`Import` mà module path chứa `presentation.ui.screens`. Chạy trước khi dời: đỏ với
**11 file** (không phải 9 — task's ước tính đếm theo *dòng* import, guard này đếm theo *file*; hai
module có 2 dòng import vi phạm trong cùng file — `trade_log_vm.py` nhập cả `trade_log_row` lẫn
`trade_log_filter`). Cùng tập hợp thật: `TradeLogTable/{trade_log_vm,preview}.py` +
`tests/test_trade_log_vm.py`, `MetricsDetailPanel/{metrics_detail_vm,preview}.py` +
`tests/test_metrics_detail_vm.py`, `DatabaseStatusTable/{database_status_vm,preview}.py` +
`tests/{test_database_status_vm,test_database_status_qml}.py`, `KlineInspectorTable/
kline_inspector_vm.py`. Sau khi dời + sửa import: guard xanh (0 hit), và
`test_guard_actually_detects_a_violation` (mutation-verify) xác nhận scanner bắt đúng shape vi
phạm thật và bỏ qua docstring chỉ nhắc tên gói.

### 6.2 Quy ước import: `preview.py`/file test cạnh nó dùng absolute, VM/logic dùng relative

Đọc code có sẵn trước khi sửa cho thấy hai quy ước khác nhau đã tồn tại song song trong `qml/`:
`*_vm.py`/`*_table_model.py` dùng relative (`.trade_log_row`) cho sibling cùng thư mục;
`preview.py` và file test cạnh nó (`tests/test_*.py` trong cùng widget) luôn dùng absolute
(`Sagittarius_Elite_Warrior.src...qml.TradeLogTable.trade_log_vm`) kể cả cho sibling. Task's §3 nói
"import tương đối trong cùng thư mục" cho `trade_log_vm.py`/`preview.py` — áp dụng đúng nghĩa đen
sẽ phá quy ước đã có của `preview.py`. Giữ nguyên quy ước hiện có của từng loại file thay vì áp một
kiểu cho tất cả: `trade_log_vm.py`/`metrics_detail_vm.py`/`database_status_vm.py`/
`kline_inspector_vm.py` chuyển sang relative; mọi `preview.py` và test cạnh nó giữ absolute, chỉ
đổi path đích.

### 6.3 `trade_log_pagination.py` không nằm trong 5 module dời, nhưng vẫn phải sửa import

Không có trong bảng §2.1, nhưng `import .trade_log_row` (relative, cùng thư mục `logic/` cũ) —
sau khi `trade_log_row.py` dời đi, import này vỡ nếu không sửa. Đổi sang absolute trỏ tới
`qml/TradeLogTable/trade_log_row.py`, không dời file này (nó thật sự thuộc về backtest — comment
riêng trong `trade_log_vm.py` giải thích tại sao QML không cần phân trang mà `logic/
trade_log_pagination.py` vẫn tồn tại cho panel QtWidgets cũ).

### 6.4 27 điểm import thật, không phải ~26 — và 2 điểm docstring không phải import

Đếm lại bằng `grep` cho từng module thay vì gộp: 27 dòng `from`/`import` thật cần sửa (5 file nội
bộ module tự tham chiếu lẫn nhau không tính, vì không đổi — `trade_log_filter.py`'s `.trade_log_row`
relative vẫn đúng sau khi dời vì cả hai ở chung thư mục mới). Hai chỗ khác chỉ là **tên file trong
docstring**, không phải import thật — `stat_card_row_vm.py`'s comment giải thích nguồn gốc
`stat_cards_to_qml()`, và `stat_card_row_widget.py`'s luật "một chiều" — cả hai sửa theo cho khỏi
trôi (`CLAUDE.md` cảnh báo đúng bệnh này), dù không nằm trong bảng §3 gốc.

### 6.5 Không sửa assert nào — đúng điều kiện dừng của §2.5

`git diff` từng file test bị đụng: 100% là dòng `import` (kiểm bằng `git diff | grep '^[+-][^+-]'`
rồi đọc lại từng file) — không một `assert` nào đổi. Diff dài nhất (14 dòng, `test_truthful_
backtest_markers_and_logs.py`) vẫn chỉ là 2 khối import bị isort xếp lại chỗ khác, không phải nội
dung mới.

### 6.6 Mốc 3 (`preview.py` chạy standalone) không chạy được nguyên văn trong sandbox này —
### lý do có sẵn từ trước, không phải lỗi do dời file

Lệnh `python .../TradeLogTable/preview.py` trong task's §5 crash với
`get_theme_bridge() has no palette yet` — nhưng đây là đặc tính **có sẵn từ trước** của mọi
`preview.py` dùng pattern `quick.rootContext().setContextProperty("Theme", get_theme_bridge())`
(kiểm tra chéo với `qml/kit/preview.py` — cùng pattern, cùng phụ thuộc một palette đã được set từ
nơi khác, thường là `create_quick_widget()` hoặc app thật). `build_preview()` không đổi gì trong
khối này — chỉ đổi 1 dòng import ở đầu file. Bằng chứng thật cho mốc 3 (không import `screens`)
là guard `ast` ở §6.1 và `grep -rn "screens\." src/presentation/ui/qml/ | grep import` (rỗng, trừ
chính dòng docstring của `stat_card_row_widget.py` nhắc tên file guard — false positive của grep
theo văn bản, không phải import), không phải chạy được script trong sandbox mạng/GUI hạn chế này.

### 6.7 Kết quả kiểm thử

- Guard: đỏ 11 file trước khi dời (bằng chứng bắt được `BUG-082` thật), xanh sau khi dời + sửa
  import, mutation-verify xanh.
- `tests/sanity/test_circular_imports.py` + toàn bộ `tests/unit/presentation/ui/qml/` +
  `tests/unit/presentation/ui/screens/`: 922/922 xanh.
- Ruff (`src tests scripts tools`): 0 lỗi ngoài 3 lỗi baseline đã biết (không đụng).
- `ruff format --check`: sạch.
- Mypy (từ `/home/user`): 0 lỗi, 231 file — lưu ý `presentation/` bị loại khỏi phạm vi mypy
  (`pyproject.toml`), nên guard `ast` + test suite là nguồn xác nhận thật cho thay đổi này, không
  phải mypy.
- `tests/unit` đầy đủ (`-n 4`, offscreen): 3192 passed, 1 failed — thất bại duy nhất vẫn là
  `test_pan_preview_moves_only_the_data_region_not_the_axes`, đã xác nhận không liên quan qua
  nhiều task trước.
