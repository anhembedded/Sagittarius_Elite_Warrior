# EPIC-003D — Dọn `components/`: đúng chỗ, đúng kích thước, đúng danh mục

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm — **xung đột với `EPIC-005` đã kiểm tra và gỡ (2026-08-23)**
**Phụ thuộc:** Không có — độc lập hoàn toàn với `A`/`B`/`E`/`F`.

---

## ⚠️ Note gỡ xung đột (2026-08-23, `EPIC-005C`)

Từng bị đánh dấu có thể đá nhau với
[`EPIC-005`](../../EPIC-005_qml_to_qtwidgets_migration/README.md) (dời file QML trong khi
epic kia định xoá chúng). Sau khi `EPIC-005A`'s ADR thu hẹp phạm vi `EPIC-005` (chỉ
Settings/DatabaseScreen, **`backtest` hoãn vô thời hạn**), đã kiểm tra lại bằng grep thật:
cả 9 file mục 0 dưới đây định dời **đều chỉ thuộc `backtest/`**, không file nào được
`SettingsScreen`/`DatabaseScreen` tham chiếu. Task này **an toàn để làm bình thường**, không
còn lý do hoãn.

## 0. Gộp 3 việc, làm theo đúng thứ tự — vì sao

User chỉ ra `src/presentation/ui/components/` "lộn xộn, không biết cái gì
thật sự dùng chung". Kiểm tra thật bằng grep cross-screen (không suy đoán)
xác nhận: **đây không phải cảm tính**, mà là vi phạm đúng rule đã có sẵn từ
trước trong `qml-rule.md` §"Component File Structure": *"Reusable components
reside in `components/`; screen-specific subcomponents reside directly in
their screen folder."*

**9/18 file đang nằm ở `components/` chỉ được dùng bởi đúng 1 màn hình
(Backtest)** — không phải component dùng chung (`native_chart_card.py` phát
hiện thêm ở lần rà soát thứ 2, lọt lưới lần đầu vì chỉ grep `.qml`, không
grep file Python top-level):

| File | Dùng ở đâu (grep thật) |
| :--- | :--- |
| `CapitalDialog.qml` | Chỉ `BackTestModals.qml` |
| `IndicatorPickerModal.qml` | Chỉ `BackTestModals.qml` |
| `OrderExecutionModal.qml` | Chỉ `BackTestModals.qml` |
| `StrategyPropertiesModal.qml` (766 dòng) | Chỉ `BackTestModals.qml` |
| `TimeRangePickerModal.qml` | Chỉ `BackTestModals.qml` |
| `TimezonePickerModal.qml` | Chỉ `BackTestModals.qml` |
| `DynamicTabBar.qml` | Chỉ `BackTestTradeLogs.qml` |
| `MetricCard.qml` | Chỉ 2 file trong Backtest (`ExtendedMetricsModal.qml`, `BackTestTopPanel.qml`) |
| `native_chart_card.py` | Chỉ `screens/backtest/logic/native_backtest_chart_host_adapter.py` |

Trong khi đó phần **thật sự** dùng chung lại ít và bị chìm nghỉm giữa đống
trên: `ModalDialogCard.qml` (nền tảng thật — **15 nơi** dùng),
`SymbolPickerModal.qml` + `AppProgressBar.qml` (dùng cả ở Backtest lẫn Data
Management), `base_card.py`, `critical_error_dialog.py` (dùng toàn app, xác
nhận qua `app_bootstrapper.py`).

`chart_card/` (22 file, ~4000 dòng) và `sidebar/` (7 file) là 2 hệ thống
con trọn vẹn, đã đúng dạng "có thư mục riêng" — **không thuộc phạm vi dọn
dẹp này**, chỉ là chúng nằm phẳng ngang hàng các file 1-trang khiến thư mục
càng rối mắt hơn, ghi nhận cho biết chứ không phải việc cần sửa.

**Vì sao dọn vị trí phải làm TRƯỚC tách file (Phase 1 → Phase 2), không phải
ngược lại:** `StrategyPropertiesModal.qml` vừa sai vị trí vừa quá khổ (766
dòng, mục tiêu tách ở §2 dưới). Tách file trước rồi mới chuyển thư mục sẽ
phải sửa lại đường dẫn `import`/`property` 2 lần cho cùng 1 nhóm file, và
git history của việc tách sẽ lẫn với việc di chuyển — khó review, khó revert
nếu 1 trong 2 việc sai.

**Vì sao danh mục (Phase 3) làm SAU CÙNG, không phải đầu tiên:** viết danh
mục cho `components/` ở trạng thái hiện tại sẽ phải liệt kê cả 9 file sắp bị
chuyển đi — chỉ để xoá dòng đó ngay sau Phase 1. Đợi `components/` ổn định
(chỉ còn thứ thật sự dùng chung) rồi mới viết danh mục, tránh viết ra rồi
sửa lại ngay.

---

## 1. Phase 1 — Di chuyển 9 file sang đúng chỗ trong `screens/backtest/`

`screens/backtest/` hiện đã có 6 file `.qml` phẳng ở top level
(`BackTestModals.qml`, `BackTestTopPanel.qml`, `BackTestTradeLogs.qml`,
`ExtendedMetricsModal.qml`, `LimitationsModal.qml`, `NativeBacktestChart.qml`)
— đổ thêm 8 file QML misplaced vào phẳng luôn sẽ chỉ dời vấn đề "lộn xộn" từ
chỗ này sang chỗ khác. Tạo `screens/backtest/components/` mới, đúng tinh
thần "tách subfolder khi kích thước đòi hỏi" mà `logic/`/`coordinators/`
(Python, `code-rule.md` §3) đã áp dụng — lần đầu áp dụng tinh thần đó cho
QML. `native_chart_card.py` (Python, không phải QML) không vào
`components/` mới này — chuyển thẳng vào `screens/backtest/logic/`, cạnh
đúng file duy nhất dùng nó (`native_backtest_chart_host_adapter.py`).

```text
src/presentation/ui/screens/backtest/
├── components/                    # MỚI (QML)
│   ├── CapitalDialog.qml
│   ├── IndicatorPickerModal.qml
│   ├── OrderExecutionModal.qml
│   ├── StrategyPropertiesModal.qml
│   ├── TimeRangePickerModal.qml
│   ├── TimezonePickerModal.qml
│   ├── DynamicTabBar.qml
│   └── MetricCard.qml
├── logic/
│   ├── native_chart_card.py       # MỚI — Python, không phải QML
│   ├── native_backtest_chart_host_adapter.py   # đã có sẵn, chỉ sửa import
│   └── ...
├── BackTestModals.qml             # sửa import trỏ vào components/
├── BackTestTopPanel.qml           # sửa import (dùng MetricCard)
├── BackTestTradeLogs.qml          # sửa import (dùng DynamicTabBar)
├── ExtendedMetricsModal.qml       # sửa import (dùng MetricCard)
└── ...
```

`src/presentation/ui/components/` sau Phase 1 chỉ còn giữ thứ thật sự dùng
≥ 2 màn hình: `ModalDialogCard.qml`, `SymbolPickerModal.qml`,
`AppProgressBar.qml`, `base_card.py`, `critical_error_dialog.py`, cộng
`chart_card/`/`sidebar/` (2 hệ thống con, không đụng).

## 2. Phase 2 — Tách 3 file QML lớn (theo `PRO-002` §2.3, cập nhật đường dẫn sau Phase 1)

| File gốc | Tách thành |
| :--- | :--- |
| `screens/data_management/DatabaseScreen.qml` (993 dòng) | `DatabaseStorageTable.qml`, `DatabaseStatsCard.qml`, `DatabaseSyncControls.qml` |
| `screens/backtest/BackTestTopPanel.qml` (823 dòng) | `BacktestStrategySelector.qml`, `BacktestDateRangeControls.qml`, `BacktestExecutionControls.qml` |
| `screens/backtest/components/StrategyPropertiesModal.qml` (766 dòng, đã chuyển ở Phase 1) | `StrategyParamsTab.qml`, `StrategyRiskTab.qml`, `StrategyLeverageTab.qml` — tách ngay trong `screens/backtest/components/`, không tạo thêm cấp thư mục nữa |

### Nguyên Tắc Bắt Buộc Khi Tách (đối chiếu `qml-rule.md`, không phải chỉ đạt số dòng)

`qml-rule.md` §"Break Down God Components": *"300 lines as a mandatory
**review** threshold, not a blind line-count failure... do not split
cohesive layout markup merely to satisfy a number."* Mỗi lần tách phải nêu
rõ **N trách nhiệm bị trộn trong 1 file** (ví dụ `StrategyPropertiesModal.qml`
trộn form Schema chiến lược + form SL/TP + form Đòn bẩy — 3 mối quan tâm
khác nhau, đúng lý do đáng tách), không viện lý do "vượt 300 dòng" một mình.

- Component con nhận dữ liệu qua `property`, phát sự kiện qua `signal` —
  không truy cập `viewModel`/`Presenter` trực tiếp xuyên qua component cha
  nếu tránh được (giữ đúng "Reactive Property Bindings" đã có trong
  `code-rule.md` §3).
- Tái dùng đúng tiền lệ `ModalDialogCard.qml` đã có (kích thước responsive,
  không hardcode `width`/`height` cứng).

## 3. Phase 3 — Danh mục `components/README.md`, có test enforce

**Vấn đề Phase 1+2 không giải quyết được:** dọn đúng chỗ và tách file nhỏ
lại xong thì `components/` vẫn chỉ là 1 danh sách filename phẳng — user chỉ
ra đúng: *"AppProgressBar dùng ở 2 màn hình, nhưng nhìn vào dir không thấy
được — sau này tạo màn hình thứ 3 thì sao biết có cái để dùng lại?"* Dọn vị
trí không trả lời được câu hỏi *"có gì tồn tại"*.

**Giải pháp — đúng khuôn mẫu đã có sẵn cho `preview.py` (`qml-rule.md`
§"Mandatory preview.py per UI Package"), không phải cơ chế mới:** một file
`src/presentation/ui/components/README.md` liệt kê từng component còn lại
sau Phase 1 (bảng `Component | Mô tả 1 câu | Đang dùng ở`), cộng 1 dòng tóm
tắt cho mỗi hệ thống con (`chart_card/`, `sidebar/` — không liệt kê từng
file bên trong, đó không phải việc của danh mục này).

**Bắt buộc có test guard** (cùng phong cách
`tests/unit/presentation/ui/test_preview_fixtures_exist.py` đã có) — quét
mọi file `.qml`/`.py` ở top-level `components/` (không đệ quy vào
`chart_card/`/`sidebar/`), fail nếu file nào chưa có dòng trong
`README.md`. Không có test này thì danh mục sẽ trôi y hệt cách `AGENTS.md`
đã trôi khỏi `code-rule.md` — viết ra 1 lần rồi không ai cập nhật khi thêm
component mới.

Nội dung dự kiến (sau Phase 1, dựa trên số liệu đã grep ở mục 0):

| Component | Mô tả | Đang dùng ở |
| :--- | :--- | :--- |
| `ModalDialogCard.qml` | Khung modal chuẩn, responsive — mọi modal khác build trên nền này | 15 nơi |
| `SymbolPickerModal.qml` | Modal chọn symbol Binance, tìm kiếm qua REST API | Backtest, Data Management |
| `AppProgressBar.qml` | Thanh tiến trình cho tác vụ nền dài | Backtest, Data Management |
| `base_card.py` | Base class Python cho các card | (điền khi làm — xem call site thật) |
| `critical_error_dialog.py` | Hộp thoại lỗi nghiêm trọng, resizable (`BUG-005`) | Toàn app (`app_bootstrapper.py`) |
| `chart_card/` (hệ thống con) | Engine vẽ chart Python đầy đủ (candlestick, viewport, indicator, marker...) | Backtest, Dashboard |
| `sidebar/` (hệ thống con) | Sidebar điều hướng, MVP trio riêng | Toàn app |

## 4. Kiểm Thử / Nghiệm Thu

- **Phase 1 (di chuyển):** mọi test QML hiện có tham chiếu 9 file này (dựng
  `qapp`/`qml_item`) phải pass không đổi assertion, chỉ đổi đường dẫn
  import. `grep` xác nhận không còn file nào trong 9 file đó nằm trong
  `src/presentation/ui/components/` sau Phase 1.
- **Phase 2 (tách):** test QML dựng/click thật phải pass không đổi — component
  tách ra vẫn phải render đúng và route sự kiện đúng như trước. Ảnh chụp UI
  trước/sau tách phải giống hệt (không đổi layout nhìn thấy được, chỉ đổi
  cấu trúc file).
- **Phase 3 (danh mục):** test guard mới (`test_component_catalog_exists.py`
  hoặc tên tương đương) fail trước khi có `README.md`, pass sau khi có đủ
  dòng cho mọi file top-level còn lại trong `components/`. Test **cố tình
  thêm 1 file giả** vào `components/` lúc viết test (rồi xoá) để xác nhận
  guard thật sự phát hiện được file thiếu trong danh mục — không phải test
  luôn pass bất kể gì (đúng tinh thần mutation-verify đã dùng cho
  `BUG-025`).
- Sau cả 3 phase: `ci-local.ps1 -Full` xanh, bao gồm `mypy` gate (`EPIC-002`)
  không phát sinh lỗi mới do đường dẫn import đổi.
