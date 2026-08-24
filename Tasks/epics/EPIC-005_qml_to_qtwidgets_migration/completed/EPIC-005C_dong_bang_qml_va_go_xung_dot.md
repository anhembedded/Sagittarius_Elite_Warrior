# EPIC-005C — Đóng băng QML (phạm vi thu hẹp) + gỡ xung đột với EPIC-003D

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-23)
**Phụ thuộc:** [`EPIC-005A`](../incomplete/EPIC-005A_quyet_dinh_va_dieu_kien_dung.md) ✅

---

## 1. Yêu cầu 1&2 (sửa `qml-rule.md`, ghi ngày/lý do/ADR) — đã làm trong lúc áp dụng ADR

Commit `758afea` (áp dụng kết luận `EPIC-005A`) đã thêm scope note đầu
`.agents/rules/qml-rule.md`, trỏ tới ADR, ghi rõ ngày 2026-08-23. Nội dung **không phải**
"đóng băng hoàn toàn QML cho UI mới" như bản nháp gốc của task này định làm — ADR đã sửa lại:
QML vẫn là **mặc định** cho màn hình nhận mockup trực tiếp; chỉ `SettingsScreen`/
`DatabaseScreen` nằm trong phạm vi migrate. Không cần sửa thêm.

## 2. Yêu cầu 3 — chốt xung đột với `EPIC-003D`

**Không hoãn `EPIC-003D`.** Sau khi `EPIC-005A`'s ADR thu hẹp phạm vi `EPIC-005` (bỏ `F`
— `backtest`/`dashboard` — khỏi lộ trình chủ động), xung đột gốc tự biến mất: cả 9 file
`EPIC-003D` định dời đều chỉ thuộc `backtest/`, và `backtest/` không còn nằm trong phạm vi
`EPIC-005` migrate. Xác nhận bằng grep thật, không suy đoán — xem bảng §3.

`EPIC-003D`'s file đã cập nhật ghi chú, trỏ ngược về đây, để làm rõ tại sao trạng thái vẫn
🔴 (chưa làm, không phải chưa được duyệt) chứ không cần đánh dấu ⏸️.

## 3. Yêu cầu 4 — bảng phân loại `components/` (trích từ `EPIC-003D`, xác nhận lại)

| File | Dùng ở màn hình nào | Có nằm trong phạm vi `EPIC-005` không |
| :--- | :--- | :---: |
| `CapitalDialog.qml` | Chỉ Backtest | Không (thuộc `F`, hoãn) |
| `IndicatorPickerModal.qml` | Chỉ Backtest | Không |
| `OrderExecutionModal.qml` | Chỉ Backtest | Không |
| `StrategyPropertiesModal.qml` | Chỉ Backtest | Không |
| `TimeRangePickerModal.qml` | Chỉ Backtest | Không |
| `TimezonePickerModal.qml` | Chỉ Backtest | Không |
| `DynamicTabBar.qml` | Chỉ Backtest | Không |
| `MetricCard.qml` | Backtest (2 nơi) | Không |
| `native_chart_card.py` | Chỉ Backtest (chart) | Không — ranh giới cứng, ngoài phạm vi vĩnh viễn |
| `ModalDialogCard.qml` | 15 nơi, toàn app | Gián tiếp — Settings/Database có thể đang dùng nó qua QML hiện tại, nhưng migrate không xoá file, chỉ ngừng nạp ở 2 màn đó |
| `SymbolPickerModal.qml` | Backtest + Data Management | Gián tiếp, tương tự |
| `AppProgressBar.qml` | Backtest + Data Management | Gián tiếp, tương tự |
| `base_card.py` | Toàn app | Gián tiếp |
| `critical_error_dialog.py` | Toàn app (`app_bootstrapper.py`) | Gián tiếp |

**Kết luận cho `EPIC-005D`/`E`:** 3 component dùng chung (`ModalDialogCard`,
`SymbolPickerModal`, `AppProgressBar`) không cần viết lại thành widget dùng chung ngay —
`EPIC-005` chỉ ngừng nạp QML ở đúng 2 màn hình migrate, các màn khác (kể cả sau khi
`EPIC-003D` dời 9 file backtest-only) vẫn dùng bản QML hiện có bình thường. Việc "component
dùng chung cần bản QtWidgets" chỉ phát sinh nếu phạm vi migrate mở rộng sang màn hình khác
dùng chúng — không phải bây giờ.

## 4. Xác minh

Chỉ sửa tài liệu, không đụng code/`.qml`. `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`
— `RESULT: PASS`, verify qua log file.
