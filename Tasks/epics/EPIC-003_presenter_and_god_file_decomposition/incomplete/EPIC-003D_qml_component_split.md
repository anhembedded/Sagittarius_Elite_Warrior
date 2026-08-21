# EPIC-003D — Dọn vị trí sai chỗ trong `components/` rồi tách 3 file QML lớn

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không có — độc lập hoàn toàn với `A`/`B`/`E`/`F`.

---

## 0. Gộp 2 việc, làm theo đúng thứ tự — vì sao

User chỉ ra `src/presentation/ui/components/` "lộn xộn, không biết cái gì
thật sự dùng chung". Kiểm tra thật bằng grep cross-screen (không suy đoán)
xác nhận: **đây không phải cảm tính**, mà là vi phạm đúng rule đã có sẵn từ
trước trong `qml-rule.md` §"Component File Structure": *"Reusable components
reside in `components/`; screen-specific subcomponents reside directly in
their screen folder."*

**8/17 file `.qml` đang nằm ở `components/` chỉ được dùng bởi đúng 1 màn
hình (Backtest)** — không phải component dùng chung:

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

---

## 1. Phase 1 — Di chuyển 8 file sang `screens/backtest/components/`

`screens/backtest/` hiện đã có 6 file `.qml` phẳng ở top level
(`BackTestModals.qml`, `BackTestTopPanel.qml`, `BackTestTradeLogs.qml`,
`ExtendedMetricsModal.qml`, `LimitationsModal.qml`, `NativeBacktestChart.qml`)
— đổ thêm 8 file misplaced vào phẳng luôn sẽ chỉ dời vấn đề "lộn xộn" từ chỗ
này sang chỗ khác. Tạo `screens/backtest/components/` mới, đúng tinh thần
"tách subfolder khi kích thước đòi hỏi" mà `logic/`/`coordinators/` (Python,
`code-rule.md` §3) đã áp dụng — lần đầu áp dụng tinh thần đó cho QML.

```text
src/presentation/ui/screens/backtest/
├── components/                    # MỚI
│   ├── CapitalDialog.qml
│   ├── IndicatorPickerModal.qml
│   ├── OrderExecutionModal.qml
│   ├── StrategyPropertiesModal.qml
│   ├── TimeRangePickerModal.qml
│   ├── TimezonePickerModal.qml
│   ├── DynamicTabBar.qml
│   └── MetricCard.qml
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

## 3. Kiểm Thử / Nghiệm Thu

- **Phase 1 (di chuyển):** mọi test QML hiện có tham chiếu 8 file này (dựng
  `qapp`/`qml_item`) phải pass không đổi assertion, chỉ đổi đường dẫn
  import. `grep` xác nhận không còn file nào trong 8 file đó nằm trong
  `src/presentation/ui/components/` sau Phase 1.
- **Phase 2 (tách):** test QML dựng/click thật phải pass không đổi — component
  tách ra vẫn phải render đúng và route sự kiện đúng như trước. Ảnh chụp UI
  trước/sau tách phải giống hệt (không đổi layout nhìn thấy được, chỉ đổi
  cấu trúc file).
- Sau cả 2 phase: `ci-local.ps1 -Full` xanh, bao gồm `mypy` gate (`EPIC-002`)
  không phát sinh lỗi mới do đường dẫn import đổi.
