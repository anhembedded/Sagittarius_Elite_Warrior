# Epic: Lưu trữ & Nạp lại Báo cáo Backtest (Backtest Report Persistence & Portability)

**Mã Epic:** `BOT-115`  
**Độ phức tạp:** 🔴 **L (Thinking)**  
**Trạng thái:** 🔴 **Backlog**  
**Ưu tiên:** 📈 **P2 — Phân tích Hiệu suất & Đo lường Rủi ro**  
**Liên quan:** [`BOT-095G`](BOT-095G_backtest_session_run_history_cache.md) (cache trong phiên), [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md) (độ tin cậy kết quả), [`BOT-112D`](BOT-112D_market_data_import_export_csv_parquet.md) (import/export dữ liệu nến — **khác** epic này)

---

## 1. Vấn Đề Hiện Tại

App **không có bất kỳ cơ chế lưu kết quả backtest nào**. Chạy xong, đổi tham số chạy lại là kết quả cũ bị ghi đè và mất vĩnh viễn. Muốn xem lại kết quả hôm qua, trader phải nhớ lại toàn bộ cấu hình, chỉnh lại từng ô trên toolbar và chờ engine tính lại từ đầu — với điều kiện dữ liệu nến trong vault vẫn còn nguyên như lúc đó.

[`BOT-095G`](BOT-095G_backtest_session_run_history_cache.md) chỉ giải quyết được một nửa: cache 5 lần chạy gần nhất **trong RAM, trong một phiên làm việc**. Tắt app là sạch. Không gửi được cho người khác, không commit vào repo làm mốc so sánh, không dùng làm bằng chứng hồi quy ("bản engine mới chạy lại chiến lược cũ có ra đúng số cũ không?").

---

## 2. Mục Tiêu Epic

Xuất một lần chạy backtest ra **file độc lập**, nạp lại được sau nhiều ngày trên máy khác, hiển thị lại đầy đủ 4 panel của màn Backtest mà **không cần chạy lại engine**.

Ba nguyên tắc chốt trước khi code:

1. **Một định dạng duy nhất, không hai.** File report chứa cả *kết quả* (trades, equity curve, metrics) lẫn *công thức* (config đầy đủ). Import cho chọn 2 chế độ: "Xem lại kết quả" hoặc "Chỉ nạp cấu hình để chạy lại". Tách thành 2 định dạng file riêng là tự tạo ra 2 schema phải đồng bộ tay mãi mãi.
2. **Provenance là bắt buộc, không phải tuỳ chọn.** Đúng tinh thần Epic [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md): số liệu cũ **không bao giờ** được hiển thị như thể vừa mới tính xong. File ghi kèm engine version, strategy key + version, execution mode, phí/slippage/đòn bẩy/sizing, cửa sổ dữ liệu, thời điểm chạy — import lệch thì cảnh báo rõ ràng trên UI.
3. **JSON, tuyệt đối không `pickle`.** File report là input từ bên ngoài (user tải về, đồng nghiệp gửi). `pickle.load()` trên file không tin cậy là arbitrary code execution ngay lúc mở. JSON + validate schema nghiêm ngặt + whitelist `strategy_key` theo `StrategyRegistry` là con đường duy nhất.

---

## 3. Hai Cạm Bẫy Đã Nhận Diện Trước

### 3.1. Chart lấy nến ở đâu?

`trades` và `equity_curve` nằm trong file, **nến thì không** (nhúng klines vào report sẽ đẩy file lên hàng chục MB). Import trên máy chưa sync `ETHUSDT 5m` đúng khoảng thời gian đó thì panel nến vẽ bằng gì?

**Quyết định:** không nhúng klines. Import xong thì thử nạp từ vault theo đúng `symbol`/`timeframe`/`range`; có thì vẽ đầy đủ (nến + marker + trend zone), thiếu thì vẫn hiện Performance Summary + Trade Logs + Equity Curve bình thường, riêng panel nến hiện thông báo *"Cần sync dữ liệu ETHUSDT 5m để xem chart"* kèm nút sync (tái dùng cơ chế [`BOT-059`](../completed/BOT-059_backtest_inline_data_sync_affordance.md)). Thà thiếu một panel **có giải thích** còn hơn vẽ chart rỗng không rõ lý do.

### 3.2. FSM Dirty Tracking sẽ đánh nhau với import

[`BOT-095B`](BOT-095B_backtest_fsm_and_stale_data_lifecycle.md) so sánh toolbar hiện tại với config lần chạy cuối để phát hiện kết quả cũ. Import một report = màn hình đang hiện kết quả **không đến từ toolbar** → FSM sẽ lập tức bắn banner "Cấu hình đã thay đổi" một cách vô nghĩa.

**Quyết định:** cần một state riêng cho chế độ xem báo cáo đã nhập, có banner nêu rõ nguồn gốc file, bấm Run thì thoát chế độ đó. Không xử lý chỗ này thì tính năng vẫn "chạy" nhưng UX rối.

---

## 4. Danh sách Task thành phần

| Task ID | Tên Nhiệm vụ | Độ phức tạp | Mô tả tóm tắt |
| :--- | :--- | :---: | :--- |
| **[`BOT-115A`](BOT-115A_backtest_report_schema_and_serializer.md)** | **Schema `BacktestReport` & Serializer JSON** | 🟡 `M` | Dataclass + `to_json`/`from_json` + `schema_version` + provenance + validate nghiêm ngặt. Thuần domain, zero UI. |
| **[`BOT-115B`](BOT-115B_backtest_report_export_ui.md)** | **Xuất báo cáo từ màn Backtest** | 🟢 `S` | Nút "Lưu báo cáo" trên toolbar + file dialog + thư mục `reports/` mặc định. |
| **[`BOT-115C`](BOT-115C_backtest_report_import_and_readonly_state.md)** | **Nạp báo cáo & Chế độ xem chỉ đọc** | 🔴 `L` | Import, state FSM riêng, banner nguồn gốc, cảnh báo provenance lệch, fallback thiếu nến. |
| **[`BOT-115D`](BOT-115D_backtest_report_side_by_side_comparison.md)** | **So sánh 2 báo cáo cạnh nhau** | 🟡 `M` | Bảng diff config + metrics side-by-side. Đây là chỗ giá trị thật sự của epic đọng lại. |

---

## 5. Thứ Tự Thực Hiện & Quan Hệ Với `BOT-095G`

`BOT-115A` nên làm **trước** [`BOT-095G`](BOT-095G_backtest_session_run_history_cache.md), rồi cho `SessionRunHistoryCache` dùng chung đúng cấu trúc snapshot của `BacktestReport` — cache trong phiên khi đó chỉ là "report chưa ghi ra đĩa". Làm ngược lại sẽ đẻ ra 2 model snapshot song song mô tả cùng một thứ, phải đồng bộ tay mỗi lần `BacktestResult` đổi field (mà nó đổi thường xuyên: `out_of_sample` ở `BOT-080`, 6 field mới ở `BOT-106A`, `mae_percent`/`mfe_percent` sắp tới ở `BOT-106B`).

`BOT-115D` phụ thuộc `BOT-115C` và nên để cuối — 3 task đầu đã đủ dùng được độc lập.
