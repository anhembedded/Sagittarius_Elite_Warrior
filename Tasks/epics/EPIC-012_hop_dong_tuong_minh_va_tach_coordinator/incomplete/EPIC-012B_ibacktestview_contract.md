# EPIC-012B — Khai `IBacktestView`: 15 thành viên, hết hợp đồng ngầm

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite (có thể chạm Engine ở bước annotate `BasePresenter.view`)
**Phụ thuộc:** `A` (luật §2.1 định nghĩa ABC-hay-Protocol)

## Việc

Khai một kiểu tường minh cho hợp đồng Presenter ↔ View của màn Backtest, gồm
đúng 15 thành viên đang được dùng thật:

| Nhóm | Thành viên |
| :--- | :--- |
| Thuộc tính | `chart_cards`, `chart_controls` |
| Vòng đời | `set_view_model`, `resize` |
| Cấu hình chart host | `set_chart_host_factory`, `set_chart_mode`, `set_chart_dev_mode`, `set_chart_opengl_enabled`, `set_chart_cached_interaction_enabled` |
| Hiển thị | `render_symbol_cards`, `set_display_timezone`, `set_volume_visible`, `set_trade_flags_visible` |
| Callback dữ liệu | `on_preview_data_ready`, `on_backtest_data_ready` |

Rồi annotate: `BackTestPresenter.view`, và mọi Coordinator nhận `view` (hiện chỉ
`chart_render_coordinator`).

## ABC hay Protocol?

**`Protocol`, theo §2.1 lý do (a) + (b)** — `BackTestView` là subclass
`QWidget`/`BaseView`; ABC sẽ xung đột metaclass với Shiboken **và** vi phạm §2
"NO Multiple Inheritance". **Docstring bắt buộc ghi rõ đang dùng lý do nào** —
đó là điều kiện §2.1 đặt ra, không phải tuỳ chọn.

## Quan hệ với `IView` của Engine

`IView` khai `bind()`, **không View nào implement**, Elite tham chiếu **0 lần**.
`IBacktestView` **không** kế thừa `IView` trong task này — làm vậy là buộc mọi
View phải có `bind()` chỉ để thoả một interface chưa ai dùng. Việc `IView` nên
được định nghĩa lại hay gỡ đi là **task của repo Engine**, ghi ở đây để lần sau
không ai coi là đã xử lý.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- Lệnh dưới in ra **đúng** tập thành viên đã khai trong `IBacktestView`, không
  thừa không thiếu:
  ```bash
  grep -rhoE "(self\.)?_?view\.[a-zA-Z_]+" src/presentation/ui/screens/backtest/ \
    | sed -E 's/.*view\.//' | sort -u
  ```
- Bơm lỗi: xoá một thành viên khỏi `IBacktestView` → `mypy` phải đỏ. Nếu **không
  đỏ** thì hợp đồng chưa thật sự được kiểm — Protocol không có cơ chế nào khác.
