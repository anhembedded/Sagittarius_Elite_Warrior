# EPIC-003D — Tách 3 file QML lớn thành component

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không có — độc lập hoàn toàn.

---

## 1. Phạm Vi (theo `PRO-002` §2.3)

| File gốc | Tách thành |
| :--- | :--- |
| `DatabaseScreen.qml` (993 dòng) | `DatabaseStorageTable.qml`, `DatabaseStatsCard.qml`, `DatabaseSyncControls.qml` |
| `BackTestTopPanel.qml` (823 dòng) | `BacktestStrategySelector.qml`, `BacktestDateRangeControls.qml`, `BacktestExecutionControls.qml` |
| `StrategyPropertiesModal.qml` (766 dòng) | `StrategyParamsTab.qml`, `StrategyRiskTab.qml`, `StrategyLeverageTab.qml` |

## 2. Nguyên Tắc Bắt Buộc (đối chiếu `qml-rule.md`, không phải chỉ đạt số dòng)

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

- Test QML hiện có (dựng `qapp`/`qml_item`, click thật) phải pass không đổi
  — component tách ra vẫn phải render đúng và route sự kiện đúng như trước.
- Ảnh chụp UI trước/sau tách phải giống hệt (không đổi layout nhìn thấy
  được, chỉ đổi cấu trúc file).
