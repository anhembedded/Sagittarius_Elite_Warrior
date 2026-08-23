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
    └── completed/                     # Task con ĐÃ xong, dời từ incomplete/ sang
        └── EPIC-XXXB_ten_task.md
```

- **ID Epic**: `EPIC-XXX` (số tăng dần riêng, không dùng chung pool với
  `BOT-XXX`/`BUG-XXX` — độc lập, giống cách `BUG-XXX` đã tách khỏi `BOT-XXX`
  từ trước). Epic tiếp theo lấy số lớn nhất đang có trong `Tasks/epics/` + 1.
- **ID task con**: `EPIC-XXX` + chữ cái (`EPIC-001A`, `EPIC-001B`, …) — tự
  chứa trong đúng thư mục epic của nó, không cần đăng ký ở pool nào khác.
- **Khi task con xong**: `git mv incomplete/EPIC-XXXA_*.md completed/`, cập
  nhật `Status` trong file, cập nhật dòng tương ứng ở bảng trong epic's
  `README.md`.
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
| **[EPIC-003](EPIC-003_presenter_and_god_file_decomposition/README.md)** | Phân rã Presenter/File quá tải (Coordinator Pattern, Domain Policy, QML) | 🟡 Đang làm (3/6 task con xong) |
| **[EPIC-004](EPIC-004_static_security_and_quality_analysis/README.md)** | Static security & quality analysis gate (Bandit + magic-number + code-smell qua Ruff) | 🟡 Đang làm (1/4 task con xong) |
