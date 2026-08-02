# Binance Trading Bot 🤖

Dự án này là một Trading Bot chuyên nghiệp được xây dựng dựa trên **Sagittarius Engine** và tuân thủ tuyệt đối **Clean Architecture**.

Hiện tại, dự án đã hoàn thành **Phase 1: Data Synchronizer**. Nó có khả năng đồng bộ dữ liệu nến (OHLCV) từ sàn Binance về lưu trữ cục bộ tại SQLite (sử dụng WAL mode để đảm bảo an toàn đọc/ghi tốc độ cao).

---

## 📂 Cấu trúc Thư mục

Dự án được phân rã thành các lớp độc lập:

```text
Binace_Bot/
├── src/                        # 🟢 Chứa toàn bộ mã nguồn bot
│   ├── domain/                 # Các thực thể cốt lõi (MarketData, TimeFrame)
│   ├── application/            # Logic nghiệp vụ (SyncMarketDataCommand)
│   ├── infrastructure/         # Các Adapter kết nối (python-binance, SQLAlchemy)
│   ├── presentation/           # (Tương lai) Các API FastAPI / Streamlit
│   └── main.py                 # File thực thi chính để khởi chạy CLI
├── tests/                      # 🔵 Chứa toàn bộ test
│   ├── unit/                   # Unit Tests soi gương cấu trúc src/
│   └── integration/            # Integration Tests chia theo Adapter
├── Tasks/                      # 🟡 Quản lý tiến độ (Kanban)
└── database/                   # 🔴 Nơi lưu trữ data (trading.db)
```

---

## 🚀 Hướng dẫn Chạy thử (Phase 1)

Bạn có thể chạy thử công cụ đồng bộ dữ liệu từ Binance. Nó sẽ tải dữ liệu lịch sử và lưu vào `database/trading.db`.

1. **Kích hoạt môi trường ảo (từ thư mục gốc `Sagittarius_ForkBoy`):**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Chạy lệnh đồng bộ dữ liệu (Sync):**
   Cú pháp:
   ```powershell
   $env:PYTHONPATH="."
   python Binace_Bot/src/main.py sync --symbols BTCUSDT,ETHUSDT --interval 1m --days 1
   ```
   *Lệnh này sẽ lấy dữ liệu nến 1 phút (`1m`) của `BTCUSDT` và `ETHUSDT` trong vòng `1 ngày` vừa qua.*

   **Lưu ý:** Bot được thiết kế để **tải nối tiếp**. Nếu bạn chạy lại lệnh trên lần thứ 2, nó sẽ kiểm tra trong Database nến cuối cùng là giờ nào, và chỉ tải những nến mới nhất phát sinh sau thời điểm đó!

---

## 🕵️ Hướng dẫn Khám phá Database

Toàn bộ dữ liệu bạn tải về được lưu tại `Binace_Bot/database/trading.db`.

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
pytest Binace_Bot/tests -v
```

Hoặc để xem độ phủ mã (Coverage):
```powershell
pytest Binace_Bot/tests -v --cov=Binace_Bot.src
```

---

## 📈 Lộ trình Tiếp theo

- **Phase 2:** Live Market Stream (Kết nối Binance Websocket, bắn Event real-time).
- **Phase 3:** Strategy Engine (Xử lý tín hiệu mua bán với Sliding Window).
- **Phase 4:** Backtesting Engine (vectorbt).
- **Phase 5:** UI Dashboard (FastAPI + Streamlit).
