# 🏛️ Epics — Sagittarius Elite Warrior

Quy ước mới (2026-08-20): mọi Epic từ giờ có **thư mục riêng của chính nó**,
không còn 1 file `.md` nằm chung với task thường trong `Tasks/backlog/`.
Lý do giống hệt lý do tách `Tasks/bug_report/` khỏi `ROADMAP.md`: 1 epic có
nhiều task con, nhiều lần cập nhật trạng thái — nhét hết vào 1 file phẳng
hoặc vào bảng Kanban chính làm cả 2 nơi đều khó đọc.

## Bố cục

```text
Tasks/epics/
├── README.md                          # File này
└── EPIC-XXX_slug_ngan_gon/
    ├── README.md                      # Tổng quan epic: mục tiêu, bối cảnh, danh sách task con
    ├── incomplete/                    # Task con CHƯA xong — task mới luôn tạo ở đây
    │   └── EPIC-XXXA_ten_task.md
    ├── completed/                     # Task con ĐÃ xong, dời từ incomplete/ sang
    │   └── EPIC-XXXB_ten_task.md
    └── cancelled/                     # Task con bị HUỶ — chỉ tạo khi thật sự cần
        └── EPIC-XXXC_ten_task.md
```

- **ID Epic**: `EPIC-XXX` (số tăng dần riêng, không dùng chung pool với
  `BOT-XXX`/`BUG-XXX` — độc lập, giống cách `BUG-XXX` đã tách khỏi `BOT-XXX`
  từ trước). Epic tiếp theo lấy số lớn nhất đang có trong `Tasks/epics/` + 1.
- **ID task con**: `EPIC-XXX` + chữ cái (`EPIC-001A`, `EPIC-001B`, …) — tự
  chứa trong đúng thư mục epic của nó, không cần đăng ký ở pool nào khác.
- **Khi task con xong**: `git mv incomplete/EPIC-XXXA_*.md completed/`, cập
  nhật `Status` trong file, cập nhật dòng tương ứng ở bảng trong epic's
  `README.md`.
- **Khi task con bị huỷ**: `git mv` sang `cancelled/` (tạo thư mục nếu chưa
  có), **không xoá file**. Lý do phải là "việc này không còn tồn tại/không còn
  đúng", và **viết ra ở đầu file** — huỷ mà không ghi lý do thì lần sau sẽ có
  người mở lại đúng task đó. Bảng ở epic's `README.md` giữ dòng của nó với
  trạng thái ❌ để lịch sử không bị thủng.

  Thư mục là nguồn sự thật mà người ta *liệt kê*, README là thứ người ta *đọc*.
  Để một task đã huỷ nằm lại `incomplete/` thì `ls` vẫn báo nó là việc đang
  chờ, dù README nói ngược lại — đó chính là kiểu lệch đã khiến `EPIC-003D`
  bị đưa vào danh sách việc còn lại nhiều lần. Tiền lệ có sẵn ở cấp repo:
  [`Tasks/cancelled/`](../cancelled/).
- **`Tasks/ROADMAP.md` chỉ giữ 1 dòng liên kết** tới `README.md` của epic —
  không chép lại nội dung, không viết đoạn dài. Muốn biết chi tiết thì mở
  thẳng file epic. (Áp dụng từ epic mới tạo theo quy ước này trở đi — các
  epic cũ dạng file phẳng trong `Tasks/backlog/`/`Tasks/completed/`
  — ví dụ `BOT-109`, `BOT-112`, `BOT-115` — **không** bị di dời ngược lại,
  để tránh phá link đang trỏ tới chúng mà không ai yêu cầu.)

## Epic đang có

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-001](EPIC-001_ema_trend_pullback_tradingview_cross_reference/README.md)** | Đối chiếu `EmaTrendPullbackStrategy` với TradingView thật | 🟡 Đang làm (1/2 task con xong) |
| **[EPIC-002](EPIC-002_static_type_checking_in_local_ci/README.md)** | Kiểm tra kiểu tĩnh (`mypy`) trong CI cục bộ | 🟡 Đang làm (4/5 task con xong) |
| **[EPIC-003](EPIC-003_presenter_and_god_file_decomposition/README.md)** | Phân rã Presenter/File quá tải (Coordinator Pattern, Domain Policy, QML) | 🟡 Đang làm (3/6 xong, 1 huỷ — `003D` hết đối tượng sau `EPIC-006F`) |
| **[EPIC-004](EPIC-004_static_security_and_quality_analysis/README.md)** | Static security & quality analysis gate (Bandit + magic-number + code-smell qua Ruff) | 🟡 Đang làm (3/4 task con xong) |
| **[EPIC-005](EPIC-005_qml_to_qtwidgets_migration/README.md)** | Rút khỏi QML về QtWidgets, **trừ chart** — theo từng màn hình, mỗi bước rollback được | ⏹️ **Bị thay thế bởi `EPIC-006`** — 6/6 task con xong (`005F` do `EPIC-006D/E` làm) |
| **[EPIC-006](EPIC-006_drop_qml/README.md)** | Bỏ hẳn QML, thuần QtWidgets | ✅ **Hoàn thành (6/6 task con)** — 2026-08-25; Elite hết sạch `.qml`. Kit QML của Engine ở lại (sample app cần) — tháo kit là task riêng repo Engine |
| **[EPIC-007](EPIC-007_chuan_hoa_card_dung_chung/README.md)** | **Chuẩn hoá card dùng chung, đưa hình dạng lên Engine** — gộp ~10 biến thể màu card về 1 token, 6 hình dạng surface lên `pyside_mvc.widgets`, cắt 3 import chéo màn hình | 🟡 Đang làm (6/7 — `007A`–`007F` xong; còn `007G`) |
| **[EPIC-008](EPIC-008_chuan_hoa_luong_event/README.md)** | **Chuẩn hoá luồng sự kiện** — Shared Kernel + port, `BaseEvent` kế thừa được thật, `EventRegistry` + catalog sinh tự động, 3 Feed thay 48 signal cầu nối | ✅ **Hoàn thành (8/8 task con)** — 2026-08-25 |
| **[EPIC-009](EPIC-009_sanity_tier_redesign/README.md)** | **Thiết kế lại tầng Sanity** — mô hình composition-root (scan chứ không liệt kê), `diagnostic_guard`, tầng out-of-process `--self-check`, fake Binance REST server. 9 file/~24 lần boot → 2 file/1 lần boot | ✅ **Hoàn thành (5/6 task con, 1 hoãn)** — 2026-08-25; ADR *Approved*. Tìm và đóng `BUG-045`, `BUG-048`, `BUG-049` |
| **[EPIC-010](EPIC-010_ghi_nho_gia_tri_cuoi/README.md)** | **Ghi nhớ giá trị cuối** — ~45 giá trị user đặt đang mất sạch mỗi lần mở lại app; chỉ 5 key của màn Settings sống sót. Store riêng `ui_state.json` (không dùng `user_config.json`), slice theo màn, merge khi ghi | ✅ **Xong 2026-08-26 (8/8 task con)** — app nhớ geometry/route/sidebar, symbol+interval của Dev Board và Database, 21 giá trị form Backtest, và checklist indicator script. Cơ chế đã promote lên Engine (`ui_state` extension, Engine PR #216). Khôi phục **layout** đa-instance vẫn mở, đúng như design tự dán nhãn |
