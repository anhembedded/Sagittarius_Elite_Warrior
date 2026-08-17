# Binance Trading Bot 🤖

Dự án này là một Trading Bot chuyên nghiệp được xây dựng dựa trên **Sagittarius Engine** và tuân thủ tuyệt đối **Clean Architecture**.

Hiện tại, dự án đã hoàn thành **Phase 1: Data Synchronizer** và **Phase 2: Live Market Stream**.

- Nó có khả năng đồng bộ dữ liệu nến (OHLCV) tĩnh từ sàn Binance về lưu trữ cục bộ tại SQLite (sử dụng WAL mode).
- Nó có khả năng kết nối Websocket Async để hứng sự kiện thị trường biến động theo thời gian thực (Real-time).

> Desktop dev mode sử dụng native C++/QML chart plugin. Xem
> [Native Chart — Build & Deploy Guide](Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md)
> trước khi chạy `\.\scripts\run-ui.ps1 -Dev` hoặc đóng gói desktop release.

---

## 📂 Cấu trúc Thư mục

Dự án được phân rã thành các lớp độc lập:

```text
Sagittarius_Elite_Warrior/
├── src/                        # 🟢 Chứa toàn bộ mã nguồn bot
│   ├── domain/                 # Các thực thể cốt lõi (MarketData, TimeFrame, MarketTickEvent)
│   ├── application/            # Logic nghiệp vụ (Use cases) và cấu hình DI (extensions)
│   ├── infrastructure/         # Các Adapter kết nối (python-binance, SQLAlchemy, WebSocket)
│   ├── presentation/           # (Tương lai) Các API FastAPI / Streamlit
│   └── main.py                 # File thực thi chính để khởi chạy CLI
├── tests/                      # 🔵 Chứa toàn bộ test
│   ├── unit/                   # Unit Tests soi gương cấu trúc src/
│   └── integration/            # Integration Tests chia theo Adapter
├── Tasks/                      # 🟡 Quản lý tiến độ (Kanban)
└── database/                   # 🔴 Nơi lưu trữ data (trading.db)
```

---

## 🚀 Hướng dẫn Chạy thử (Dual-Mode CLI)

Dự án hỗ trợ 2 chế độ khởi chạy linh hoạt: **Interactive Menu** (cho người dùng cá nhân) và **Headless Mode** (cho môi trường Server/Docker).

### Chế độ 1: Interactive Terminal Menu

Khi khởi chạy không có tham số, Bot sẽ tự động mở Menu tương tác trực quan:

```powershell
$env:PYTHONPATH="."
python Sagittarius_Elite_Warrior/src/main.py
```

*Kết quả:* Bạn sẽ được đưa vào vòng lặp Menu:

```text
========================================
 🤖 BINANCE TRADING BOT - INTERACTIVE 
========================================
1. Sync Market Data (Historical)
2. Start Live Stream (Websocket)
3. Stop Live Stream
4. Exit
```

### Chế độ 2: Headless CLI (Tự động hóa)

Nếu bạn truyền tham số, Bot sẽ bỏ qua Menu và chạy thẳng lệnh tương ứng, rất phù hợp cho Crontab hoặc Background Tasks.

**1. Đồng bộ dữ liệu (Sync):**

```powershell
$env:PYTHONPATH="."
python Sagittarius_Elite_Warrior/src/main.py sync --symbols BTCUSDT,ETHUSDT --interval 1m --days 1
```

**2. Khởi chạy nền Live Stream:**

```powershell
$env:PYTHONPATH="."
python Sagittarius_Elite_Warrior/src/main.py stream
```

---

## 🚫 Lầm tưởng Kiến trúc (Anti-patterns đã được né tránh)

Khi triển khai các hệ thống vòng lặp (CLI menu, Background loops) cho Trading Bot, người mới rất dễ mắc các sai lầm kiến trúc sau đây. Dự án này đã xử lý triệt để:

1. **God Object ở Presentation Layer:**
   - *Sai lầm:* Nhồi nhét logic hỏi/đáp của toàn bộ 10 tính năng vào một file `menu.py` khổng lồ, vi phạm Single Responsibility Principle (SRP).
   - *Cách giải quyết:* Áp dụng Command/Handler pattern, chia Menu thành `SyncMenuHandler` và `StartStreamMenuHandler`. `TerminalMenuService` chỉ đóng vai trò Router điều hướng giao diện.
2. **Loại bỏ CLI Parser khi làm UI:**
   - *Sai lầm:* Khi nâng cấp lên UI hoặc Interactive Menu, lập trình viên thường xóa luôn `argparse` dẫn tới việc mất khả năng chạy Headless Mode (cực kỳ quan trọng để deploy bot lên Cloud VPS).
   - *Cách giải quyết:* Kiến trúc **Dual-Mode**, hỗ trợ cả tương tác trực tiếp lẫn truyền tham số từ script automation.
3. **Blocking I/O gây chết luồng:**
   - *Sai lầm:* Chạy hàm `input()` (Synchronous Blocking) trên luồng chính của ứng dụng, khiến ứng dụng không thể nhận tín hiệu Graceful Shutdown (Ctrl+C).
   - *Cách giải quyết:* Tách Terminal Menu ra một `IHostedService` chạy trên `ThreadPool`. Xử lý exception `KeyboardInterrupt` triệt để nhằm đảm bảo mọi Data Base connection và Websocket connection được dọn dẹp (clean up) trước khi thoát.

---

## 🕵️ Hướng dẫn Khám phá Database

Toàn bộ dữ liệu bạn tải về được lưu tại `Sagittarius_Elite_Warrior/database/trading.db`.

Để xem dữ liệu, bạn có thể:

1. Cài đặt Extension **SQLite Viewer** trong VS Code.
2. Bấm chuột phải vào file `trading.db` -> Chọn **Open to the Side** (hoặc mở bằng SQLite Viewer).
3. Xem bảng `klines` để thấy danh sách hàng ngàn cây nến đã được lưu cực kỳ ngăn nắp với định dạng UTC Timezone.

---

## 🧪 Hướng dẫn Chạy Kiểm thử (Tests)

Dự án có bộ Test rất nghiêm ngặt (gần 100% Coverage). Để chạy lại toàn bộ Unit Test và Integration Test:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
pytest Sagittarius_Elite_Warrior/tests -v
```

Hoặc để xem độ phủ mã (Coverage):

```powershell
pytest Sagittarius_Elite_Warrior/tests -v --cov=Sagittarius_Elite_Warrior.src
```

---

## 📈 Lộ trình Tiếp theo

- **Phase 3:** Strategy Engine (Xử lý tín hiệu mua bán với Sliding Window).
- **Phase 4:** Backtesting Engine (vectorbt).
- **Phase 5:** UI Dashboard (FastAPI + Streamlit).
