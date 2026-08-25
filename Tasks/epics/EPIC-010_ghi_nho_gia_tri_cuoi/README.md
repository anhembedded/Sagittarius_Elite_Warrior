# EPIC-010 — Ghi nhớ giá trị cuối (UI State Persistence)

**Trạng thái:** 🔵 **Chưa bắt đầu — đang chờ duyệt thiết kế** (0/8 task con)
**Ngày tạo:** 2026-08-25

---

## Vấn đề

App hiện có **đúng một** đường lưu xuống đĩa: màn Settings ghi 5 key
(`API_KEY`, `API_SECRET`, `DEFAULT_SYMBOLS`, `DEFAULT_INTERVAL`,
`DEFAULT_SYNC_DAYS`) vào `src/config/user_config.json`.

**Mọi thứ khác người dùng chạm vào đều mất khi đóng app** — khoảng **45 giá trị**
trên 4 màn hình: symbol và interval của Dev Board, toàn bộ form Backtest
(strategy, vốn, timeframe, khoảng thời gian, commission, leverage…), lựa chọn
của màn Database, kích thước cửa sổ, màn hình đang mở, danh sách indicator script
đã bật.

Grep toàn repo xác nhận: **không có `QSettings`**, **không có
`saveGeometry`/`restoreGeometry`**, và **không có `config.set()`** nào trong
`src/presentation/` ngoài `settings_presenter.py`.

## Thiết kế

📄 **[`design/DESIGN_2026-08-25_ui_state_persistence.md`](design/DESIGN_2026-08-25_ui_state_persistence.md)**

Tài liệu đó chứa: mô hình cấu trúc + danh mục 12 failure mode suy ra từ vòng đời
của một giá trị được lưu, đánh giá 7 quyết định thiết kế (mỗi cái có bảng so
sánh phương án và lý do chọn), kiến trúc đề xuất, và 12 sơ đồ mermaid
(component, class, 2 sequence, state machine, ER, 2 flowchart, mindmap, gantt,
journey).

### Ba quyết định quan trọng nhất

| # | Quyết định | Lý do quyết định |
| :-: | :--- | :--- |
| **D1** | File **riêng** `state/ui_state.json`, **không** dùng lại `user_config.json` | `user_config.json` được git track **và** chứa `API_KEY`/`API_SECRET`; `ConfigManager.save()` không atomic và **âm thầm ghi đè file hỏng**; tầng Sanity đang nạp đúng file thật đó với `writable=True`. Sâu xa hơn: *preference* (user chủ động khai, phải tôn trọng nguyên văn) và *hint* (tác dụng phụ của việc dùng app, được phép vứt im lặng) có chính sách hỏng ngược nhau |
| **D2** | Tài liệu chia **slice theo màn**, ghi thì **merge từng slice**, không bao giờ thay cả tài liệu | `PresenterManager` là *TRUE LAZY* — presenter chỉ dựng khi user vào màn. Ghi cả tài liệu lúc shutdown sẽ **xoá sạch** slice của những màn phiên này không mở |
| **D6** | Lưu **ý định**, không bao giờ lưu **hoạt động** (FSM, stream đang chạy) | `BOT-062` đã chủ động tắt autostart vì *"opening the Dev Board must not silently start a live connection unless the user has opted in"*. Restore FSM về `LIVE` là lách đúng quyết định đó bằng cửa sau |

## Task con (chưa tạo file — chờ duyệt thiết kế)

| ID | Tên | Tầng | Trạng thái |
| :--- | :--- | :---: | :---: |
| `EPIC-010A` | `IUiStateStore` + `JsonFileUiStateStore` + unit test đủ 12 failure mode | Nền móng | 🔵 Chưa bắt đầu |
| `EPIC-010B` | `UiStateService` — debounce, flush trong `teardown()` | Nền móng | 🔵 Chưa bắt đầu |
| `EPIC-010C` | Shell: kích thước cửa sổ + route cuối + sidebar | T1 | 🔵 Chưa bắt đầu |
| `EPIC-010D` | Dev Board: symbol + interval | T1 | 🔵 Chưa bắt đầu |
| `EPIC-010E` | Database: symbol + interval | T1 | 🔵 Chưa bắt đầu |
| `EPIC-010F` | Backtest: slice đầy đủ | T2 | 🔵 Chưa bắt đầu |
| `EPIC-010G` | Indicator script + cờ `_user_touched` | T2 | 🔵 Chưa bắt đầu |
| `EPIC-010H` | Gộp default trùng lặp về một nguồn | Nợ kỹ thuật | 🔵 Chưa bắt đầu |

> File task con **cố ý chưa tạo**. Thiết kế còn 3 câu hỏi mở cần user quyết
> (xem §8 của design doc), và tạo 8 file task cho một thiết kế chưa duyệt là
> đúng kiểu "đoán sai hình dạng của thứ chưa tồn tại" mà
> `architecture-rule.md` §7.2 nêu đích danh là bài học từ 4 stub card của
> `EPIC-006`.

## `EPIC-010H` không phải việc phụ

Cùng một khái niệm đang có nhiều bản sao độc lập: `"ETHUSDT"` là literal ở **3
file**, `"1m"` ở **4+ file**. Và chỉ `BackTestPresenter` đọc
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` từ config — Dev Board và Database bỏ qua
hoàn toàn, nên **sửa Settings hôm nay đã tạo default không nhất quán giữa các
màn rồi**.

Chồng thêm một tầng "giá trị cuối" lên trên nền đó sẽ tạo ra thứ tự ưu tiên 3
tầng mà chưa ai định nghĩa. Design doc §7 đề xuất:

```text
ui_state (điều user vừa làm)  >  user_config DEFAULT_* (điều user khai ở Settings)  >  hằng số module
```

kèm hệ quả bắt buộc: **đổi giá trị ở Settings phải xoá key tương ứng trong
`ui_state`** — nếu không, user đổi Settings mà không thấy gì xảy ra.

## Liên quan

- [`BOT-115`](../../backlog/BOT-115_backtest_report_persistence_epic.md) — lưu
  **báo cáo backtest** ra file. Khác epic này (lưu *kết quả một lần chạy*, không
  phải *lựa chọn của user*), nhưng đã chốt sẵn 2 nguyên tắc mà epic này dùng
  lại: JSON có `schema_version`, và **không bao giờ `pickle`**.
- [`BOT-047`](../../completed/BOT-047_dynamic_params_form_ui.md) — có nút "Khôi
  phục Mặc định"; là tiền lệ UI cho R1 trong design doc.
