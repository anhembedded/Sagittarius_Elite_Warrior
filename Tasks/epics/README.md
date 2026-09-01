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
| **[EPIC-003](EPIC-003_presenter_and_god_file_decomposition/README.md)** | Phân rã Presenter/File quá tải (Coordinator Pattern, Domain Policy, QML) | 🟡 Đang làm (5/7 xong, 1 huỷ — `003D` hết đối tượng sau `EPIC-006F`; còn `003F`) |
| **[EPIC-004](EPIC-004_static_security_and_quality_analysis/README.md)** | Static security & quality analysis gate (Bandit + magic-number + code-smell qua Ruff) | 🟡 Đang làm (3/4 task con xong) |
| **[EPIC-005](EPIC-005_qml_to_qtwidgets_migration/README.md)** | Rút khỏi QML về QtWidgets, **trừ chart** — theo từng màn hình, mỗi bước rollback được | ⏹️ **Bị thay thế bởi `EPIC-006`** — 6/6 task con xong (`005F` do `EPIC-006D/E` làm) |
| **[EPIC-006](EPIC-006_drop_qml/README.md)** | Bỏ hẳn QML, thuần QtWidgets | ✅ **Hoàn thành (6/6 task con)** — 2026-08-25; Elite hết sạch `.qml`. Kit QML của Engine ở lại (sample app cần) — tháo kit là task riêng repo Engine |
| **[EPIC-007](EPIC-007_chuan_hoa_card_dung_chung/README.md)** | **Chuẩn hoá card dùng chung, đưa hình dạng lên Engine** — gộp ~10 biến thể màu card về 1 token, 6 hình dạng surface lên `pyside_mvc.widgets`, cắt 3 import chéo màn hình | ✅ **Hoàn thành (8/8 task con, `007A`–`007H`)** — 2026-08-26; guard bare-base 17 → 2, trên `screens/` là 0 |
| **[EPIC-008](EPIC-008_chuan_hoa_luong_event/README.md)** | **Chuẩn hoá luồng sự kiện** — Shared Kernel + port, `BaseEvent` kế thừa được thật, `EventRegistry` + catalog sinh tự động, 3 Feed thay 48 signal cầu nối | ✅ **Hoàn thành (8/8 task con)** — 2026-08-25 |
| **[EPIC-009](EPIC-009_sanity_tier_redesign/README.md)** | **Thiết kế lại tầng Sanity** — mô hình composition-root (scan chứ không liệt kê), `diagnostic_guard`, tầng out-of-process `--self-check`, fake Binance REST server. 9 file/~24 lần boot → 2 file/1 lần boot | ✅ **Hoàn thành (5/6 task con, 1 hoãn)** — 2026-08-25; ADR *Approved*. Tìm và đóng `BUG-045`, `BUG-048`, `BUG-049` |
| **[EPIC-010](EPIC-010_ghi_nho_gia_tri_cuoi/README.md)** | **Ghi nhớ giá trị cuối** — ~45 giá trị user đặt đang mất sạch mỗi lần mở lại app; chỉ 5 key của màn Settings sống sót. Store riêng `ui_state.json` (không dùng `user_config.json`), slice theo màn, merge khi ghi | ✅ **Xong 2026-08-26 (8/8 task con)** — app nhớ geometry/route/sidebar, symbol+interval của Dev Board và Database, 21 giá trị form Backtest, và checklist indicator script. Cơ chế đã promote lên Engine (`ui_state` extension, Engine PR #216). Khôi phục **layout** đa-instance vẫn mở, đúng như design tự dán nhãn |
| **[EPIC-011](EPIC-011_dong_bo_skill_dinh_ky_jules/README.md)** | **Đồng bộ 7 skill chạy định kỳ (`.jules/`) với repo hiện tại** — 7 agent chạy không người trông, prompt của chúng đã trôi: cả 7 dùng sai cổng CI (`-UnitOnly` thay vì `-Full`), Sentinel trỏ vào một rule file chưa bao giờ tồn tại, 6/7 còn nhắm vào QML đã bị gỡ từ `EPIC-006`, Palette mất sạch bãi săn. Rút phần chung ra `.jules/README.md`, mỗi agent neo vào một nguồn việc tự làm mới, cộng một guard cơ học | ✅ **Hoàn thành (8/8 task con)** — 2026-08-26; guard sống trong `ci-local.ps1 -Full`, verify hai chiều |
| **[EPIC-012](EPIC-012_di_chuyen_skills_ve_agents_va_lich_2_ngay/README.md)** | **Dời `.jules/` sang `.agents/Skills/`, xoá `.jules/`, lịch chạy 2 ngày/agent** — hỏi rõ trước khi xoá vì `.jules/` từng được mô tả là quy ước của một dịch vụ ngoài; 9 file dời bằng `git mv`, mọi link tương đối tính lại theo cấp thư mục mới, guard đổi tên và vá luôn một lỗ chưa từng được kiểm (`.claude/` thiếu trong `CHECKED_ROOTS`), 7 Routine bền (`create_trigger`) chạy mỗi 2 ngày/agent | ✅ **Hoàn thành** — 2026-08-27 |
| **[EPIC-013](EPIC-013_hop_dong_tuong_minh_va_tach_coordinator/README.md)** | **Hợp đồng tường minh (cấm duck-typing ngầm) & tách nốt Coordinator** — Presenter + 6 Coordinator gọi 15 thành viên của `view` mà 0 khai báo; `IView` của Engine khai 1 method `bind()` không View nào implement; 74 tham số ctor trong đó 24 là accessor state. Luật §2.1 (ABC mặc định, `Protocol` chỉ khi Shiboken/multiple-inheritance chặn) + `IBacktestView` + `BacktestScreenState` + tách `chart_preview`/`chart_feed` | ✅ **Hoàn thành (7/7 task con)** — 2026-08-27 |
| **[EPIC-014](EPIC-014_widget_chon_symbol_va_timeframe_dung_chung/README.md)** | **Widget chọn Symbol & Timeframe dùng chung** — ba bản picker symbol khác nhau, picker timeframe chỉ cho chọn 5/16 khung. Thêm yêu thích/gần đây dùng chung mọi màn hình | ✅ **Hoàn thành** — 2026-08-28. *(Ghi nhận 2026-08-30: hàng này bị thiếu ở bản trước của file — epic đã xong từ lâu, chỉ chưa lên index này; xem `ROADMAP.md` để biết trạng thái luôn chính xác hơn file này.)* |
| **[EPIC-015](EPIC-015_qml_tung_widget_khong_chuyen_chart/README.md)** | **QML từng widget, chart ở lại QtWidgets** — chart pyqtgraph + shell ở lại QtWidgets vĩnh viễn, mọi widget khác chuyển dần sang QML theo 4 phase tăng dần rủi ro (modal độc lập → nhúng màn không chart → nhúng cạnh chart thật) | ✅ **Hoàn thành cả 4 phase** — 2026-08-30; user xác nhận bằng mắt chart không giật ở Phase 4 (widget QML đầu tiên chạy cạnh chart pyqtgraph thật trong production) |
| **[EPIC-016](EPIC-016_screen_registry_pattern/README.md)** | **Screen Registry Pattern** — `MainWindow` hard-code `_NAV_SECTIONS`/`_setup_router()`, sửa 1 màn mới đòi đụng 2 chỗ. `ISidebar` (Protocol, lý do (b) — `Sidebar` đã kế thừa `BaseView`; bỏ `select_section()`/`set_navigation()` — không caller nào cần), `AbstractScreenModule` (ABC), `IScreenRegistry`/`ScreenRegistry`, Section/Item Sequence hai tầng — không tạo type song song với `ITab`/`SidebarSection` có sẵn. `MainWindow` hết import bất kỳ màn cụ thể nào | ✅ **Hoàn thành (4/4 task con)** — 2026-08-30; sanity 8/8, integration 42/42, 757 test `screens/` |
| **[EPIC-017](EPIC-017_presentation_hard_design_round2/README.md)** | **Presentation Hard-Design Round 2** — verify độc lập report ngoài (6 điểm): 2 điểm mở task (Settings hard-code field 3 màn khác — đăng ký eager tại bootstrap, không phải trong `__init__` từng Presenter vì lazy-loading; dùng `TimeFrame` Enum **đã có sẵn** thay literal `"1m"`), 1 điểm route sang `EPIC-003` (`003G`, không trùng epic), 1 điểm scope-corrected (boilerplate chỉ đúng 3/4 presenter, lõi đã DRY), 2 điểm từ chối (auto-discovery strategy/indicator; bỏ Junction hack `run-ui.ps1`) | ✅ **Hoàn thành (2/2 task con)** — 2026-08-30 |
| **[EPIC-018](EPIC-018_app_wide_hard_design_sweep/README.md)** | **App-Wide Hard Design Sweep** — rà soát ngoài `presentation/ui` (application/domain/infrastructure/cli). 3 việc đã sửa trước khi có task/ADR (lỗi quy trình, user chỉ ra giữa chừng): `sync_cli_handler.py` dead-code failure branch, `app_bootstrapper.py` hasattr dead branch x4, `RunBacktestCommand` hasattr dead code. Từ epic này: mỗi task rà soát chỉ đúng 1 module (`018C`-`018F`), cộng lại phủ hết `src/` | ✅ **Hoàn thành (7/7 task con)** — 2026-08-30 |
| **[EPIC-019](EPIC-019_dashboard_backtest_shared_coordinators/README.md)** | **Dashboard/Backtest: gộp logic Presenter trùng lặp thành Coordinator** — báo cáo ngoài (Gemini) claim thiếu lớp cha chung, verify độc lập: 4/7 claim sai/bịa (`DashboardSymbolPickerSource` không tồn tại, nút Refresh không tồn tại, Timeframe đã dùng chung từ `EPIC-014`/`EPIC-015`), 2/7 đúng (`SymbolOptionsCoordinator`, `HealthCheckCoordinator` dùng chung Dashboard+Backtest) + 1 finding tự phát hiện (133 method Property boilerplate ở ViewModel, chưa có factory) | ✅ **Hoàn thành (3/3 task con)** — 2026-08-30 |
| **[EPIC-020](EPIC-020_page_shell_bo_cuc_4_dai/README.md)** | **`PageShell` — bố cục 4 dải dùng chung** — user đối chiếu mockup vs app thật, phát hiện 2 bug (nút "Mở rộng" Backtest ẩn vĩnh viễn do thiếu 1 signal connection; tiêu đề Dev Board bị cắt do fixed-width) + 3 màn lệch bố cục (Database rail bên trái, Backtest/Dev Board không có đầu trang riêng). `PageShell` (header/context-bar/workspace+rail-luôn-phải/console) áp cho cả 4 màn, kèm 1 bug thật thứ 3 tự bắt được khi viết abstraction (`QSplitter` tạo lại mỗi lần gọi làm cascade-delete widget con đang sống). *(Đổi số từ `EPIC-018` khi merge nhánh — trùng ID với `EPIC-018_app_wide_hard_design_sweep`.)* | ✅ **Hoàn thành** — 2026-08-30; verify bằng build app thật offscreen + chụp ảnh so sánh, không chỉ đọc code |
| **[EPIC-021](EPIC-021_ket_noi_binance_futures_testnet/README.md)** | **Kết nối Binance USD-M Futures Testnet & đường đi lệnh thật** — app hiện **không có khái niệm môi trường sàn**: DI dựng `PythonBinanceClient` không tham số (`binance_bot_module.py:231`) nên luôn mainnet ẩn danh, key user nhập ở Settings không bao giờ tới client (`BUG-078`), 2 key endpoint trong config là config chết (`BUG-079`), và parser metadata (step/tick/minNotional) chỉ được `tests/` gọi. Chọn **Futures** thay vì Spot vì mô hình khớp lệnh của repo đã là futures (SHORT + leverage trong `PaperExchange`); Settings có **2 lựa chọn độc lập** (nguồn dữ liệu vs nơi đặt lệnh); `TradingVenue` **không có member MAINNET** — rào an toàn bằng type, không bằng cấu hình | 🔴 Chưa bắt đầu (0/10 task con) |
