# EPIC-007F — Elite: migrate 4 màn hình sang widget dùng chung

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007D`, `007E`

---

## Phạm vi

Bốn màn, làm **theo thứ tự rủi ro tăng dần, mỗi màn một commit riêng, rollback được**:

| Thứ tự | Màn | Đổi gì | Hiện `setStyleSheet` |
| :-: | :--- | :--- | ---: |
| 1 | **Settings** | card inline (`settings_view.py:166`) → `Card` | 13 |
| 2 | **Dashboard (Dev Board)** | `DevBoardPanel` → `Panel`; `_SectionLabel` → `SectionLabel`; log → `LogPanel` | 22 |
| 3 | **Backtest** | `BackTestTopPanel` → `Panel`; `MetricCardWidget` → `StatCard`; 4 banner → `Banner`; `DynamicTabBarWidget` → `TabBar`; `_TradeLogRowWidget` → `DataRow`; bảng log → `TableCard` | 33 + 27 + 16 |
| 4 | **Data Management** | `_StatusRowWidget`/`_KLineRowWidget`/`_GapRowWidget` → `DataRow`; 4 `QDialog` → `ConfirmOverlay`/`PickerOverlay`; audit banner → `Banner`; 2 inspector → `TableCard` | 31 + 65 |

Settings đi đầu vì nhỏ nhất và lỗi lộ ra ngay; Data Management đi cuối vì nặng nhất và là nơi
`007E` vừa rút widget ra.

## Yêu cầu

1. **Sau task này, `find_bare_qt_base_widgets` (đã mở rộng sang `QWidget` ở `007A`) phải về 0**
   trên `src/presentation/ui/screens/`, trừ danh sách miễn trừ có ghi lý do.
2. **Giữ nguyên hành vi.** Đây **không** phải task đổi thị giác — phần đổi màu đã làm trọn ở
   `007D`. Mọi khác biệt thị giác phát sinh ở đây là **regression**, phải sửa hoặc rollback.
3. **Không widget nào tự viết `setStyleSheet` có hex.** Cần một biến thể chưa có → thêm
   `StyleRole` ở Engine (`007B`), không vá tại chỗ. Đây chính là sai lầm `EPIC-005` đã mắc.
4. **Test theo màn**: mỗi commit giữ nguyên số test pass so với baseline chụp trước khi bắt đầu
   màn đó. Số test đổi thì phải giải thích từng cái.
5. `_CoverageSegmentWidget` (`data_management_widgets.py:913`) **ở lại screens/** — nó vẽ dải
   phủ dữ liệu theo khoảng thời gian, là khái niệm nghiệp vụ của riêng DataMgmt, không phải
   hình dạng chung. Kế thừa `Panel`, không lên Engine.

## Bằng chứng phải nộp

- Ảnh chụp trước/sau **từng màn** — dùng để chứng minh **không** đổi gì, ngược với `007D`.
- Output guard trước/sau.
- `pwsh -NoProfile -File scripts/ci-local.ps1` sau **mỗi** màn, không phải chỉ ở cuối.

## Rủi ro

Backtest có 11 `Overlay` đã làm đúng từ `EPIC-006E3` — **không đụng vào**, trừ chỗ chúng dựng
`MetricCardWidget` (`ExtendedMetricsModal`). Sửa nhầm phạm vi ở đây là cách nhanh nhất để phá
một phần đang chạy tốt.
