# EPIC-007B — Engine: 6 hình dạng surface dùng chung, mỗi lớp một file

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007A` (guard phải bắt đúng trước)

---

## Phạm vi

Sáu hình dạng đang bị Elite viết lại 2–5 lần. Mỗi cái đều thoả kỷ luật ADR `EPIC-006` §4:
**≥2 instance thật đang tồn tại**, không suy đoán.

| Lớp mới | File | Kế thừa | Instance thật hiện có |
| :--- | :--- | :--- | ---: |
| `LogPanel` | `widgets/surfaces/log_panel.py` | `Card` | 3 |
| `StatCard` | `widgets/surfaces/stat_card.py` | `Card` | 2 |
| `TableCard` | `widgets/surfaces/table_card.py` | `Card` | 3 |
| `DataRow` | `widgets/surfaces/data_row.py` | `Panel` | 4 |
| `Banner` | `widgets/surfaces/banner.py` | `Panel` | 5 |
| `TabBar` | `widgets/surfaces/tab_bar.py` | `Panel` | 2 |

Instance thật tương ứng, để người review đối chiếu:

- **LogPanel** — `data_management_widgets.LogPanelWidget`, dùng bởi DataMgmt + DevBoard +
  BackTestTradeLogsPanel.
- **StatCard** — `backtest_widgets.MetricCardWidget` + `data_management_view._build_stat_tile()`.
- **TableCard** — header cột + hàng + phân trang: `BackTestTradeLogsPanel`,
  `KLineInspectorDialog`, `GapInspectorDialog`.
- **DataRow** — `_TradeLogRowWidget`, `_StatusRowWidget`, `_KLineRowWidget`, `_GapRowWidget`.
- **Banner** — 4 banner của `backtest_top_panel` (`progress`/`preview`/`stale`/`coverage`) +
  `_build_audit_banner` của DataMgmt.
- **TabBar** — `DynamicTabBarWidget` + hàng `_FilterTabButton`.

## Yêu cầu

1. **1 file 1 lớp.** Không dồn vào `surface.py`. `surface.py` giữ nguyên `Surface`/`Panel`/
   `Card`/`SelectableCard` — chúng là gốc phân loại, đã ở đúng chỗ.
2. **`StyleRole` mới đặt trong `style.py`**, không tách file: `BADGE`, `BANNER_INFO`,
   `BANNER_WARN`, `BANNER_DANGER`, `SECTION_LABEL`, `TABLE_HEADER`, `PROGRESS`. Đây là ngoại lệ
   có chủ đích của luật "1 file 1 lớp" — `StyleRole` và `_build_qss()` là **cùng một vòng đời**,
   tách ra vi phạm Single-Scope Cohesion (`code-rule.md`).
3. **Không lớp nào biết Elite tồn tại.** Không có tên nghiệp vụ (`Trade`, `Kline`, `Symbol`,
   `Backtest`) trong bất kỳ file nào của `widgets/`.
4. **`TableCard` — trả lời trước câu hỏi chắc chắn bị hỏi:** tên này trùng 1 trong 4 stub QML
   đã bị xoá ở `EPIC-006`. Khác biệt phải ghi ngay trong docstring: 4 stub đó suy đoán từ một
   docstring và có **0 instance**; cái này có **3 instance thật** cùng contract. Nếu review
   thấy vẫn gợn, đổi tên thành `ListCard` — không đổi thiết kế.
5. **Không hex literal ngoài `style.py`** — guard `find_inline_stylesheets` phải xanh.
6. Test cho từng lớp, đặt gương với cấu trúc package (`tests/extensions/pyside_mvc/widgets/surfaces/`).

## Bằng chứng phải nộp

- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + đường dẫn log.
- Với mỗi lớp mới: dẫn ra **≥2 file:line** của instance thật nó thay thế. Không có đủ 2 thì
  **không tạo lớp đó** và ghi lý do vào file này.

## Rủi ro

`DataRow` là cái dễ vượt phạm vi nhất — 4 instance thật có số cột và kiểu ô khác nhau. Giữ nó
ở mức "hàng có ô + hàng nút hành động", đừng cố mô hình hoá cột. Nếu phải thêm tham số thứ 4
để chiều một instance thì dừng lại: đó là dấu hiệu cái này chưa phải một hình dạng chung.
