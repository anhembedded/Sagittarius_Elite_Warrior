# Nhiệm vụ: Nạp Báo cáo & Chế độ Xem Chỉ đọc

**Mã Task:** `BOT-115C`  
**Thuộc Epic:** [`BOT-115`](BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-115A`](BOT-115A_backtest_report_schema_and_serializer.md), [`BOT-095B`](BOT-095B_backtest_fsm_and_stale_data_lifecycle.md)

---

## 1. Đây Là Task Khó Nhất Của Epic

Không phải vì đọc file (`BOT-115A` lo xong rồi), mà vì **màn Backtest đang giả định mọi kết quả trên màn hình đều do toolbar hiện tại sinh ra**. Import phá vỡ giả định đó.

---

## 2. State Mới Trong FSM

`BOT-095B` liên tục so `BacktestRunConfig` hiện tại của toolbar với snapshot lần chạy cuối để bật cờ `isConfigDirty`. Nạp một report từ đĩa vào sẽ khiến FSM lập tức bắn banner *"Cấu hình đã thay đổi — kết quả đang hiển thị là của lần chạy trước"*, hoàn toàn vô nghĩa với người dùng vừa mở file.

**Thiết kế:** thêm state `VIEWING_IMPORTED_REPORT` vào `BacktestUiState`:

- Vào state: hydrate toolbar theo config trong file **nhưng suppress dirty tracking** trong lúc hydrate (đúng kỹ thuật "restore transaction" mà `BOT-095G` §2.2 đã mô tả cho cache trong phiên — dùng chung cơ chế, đừng viết cơ chế thứ hai).
- Trong state: banner riêng nêu nguồn gốc — *"Đang xem báo cáo đã nhập — `ETHUSDT_5m_...json`, chạy ngày 18/08/2026"* — kèm nút "Thoát chế độ xem".
- Thoát state: bấm Run, hoặc bấm nút thoát. Bấm Run thì chạy thật bằng config đang hiện trên toolbar và quay về vòng đời bình thường.

---

## 3. Cảnh Báo Provenance (không được bỏ qua)

So `provenance` trong file với môi trường hiện tại, hiện badge ở khu kết quả khi lệch:

| Trường hợp | Xử lý |
| :--- | :--- |
| `engine_version` khác bản đang chạy | Badge vàng: *"Báo cáo tạo bởi engine v1.3.0 — chạy lại trên bản hiện tại có thể ra số khác."* |
| `strategy_key` không còn trong `StrategyRegistry` | Vẫn hiện kết quả, **khoá nút Run**, nêu rõ chiến lược không còn tồn tại. |
| `metrics` trong file lệch với `metrics` tính lại từ `trades` | Badge đỏ: nghi ngờ file bị sửa tay. |
| Không có `out_of_sample` | Tái dùng đúng dòng cảnh báo `BOT-080` đã có, không viết cảnh báo mới. |

Nguyên tắc xuyên suốt: **số liệu quá khứ không bao giờ được trình bày như số liệu vừa tính**.

---

## 4. Thiếu Dữ liệu Nến — Hạ Cấp Có Giải Thích

Report không chứa klines (quyết định ở §3.1 Epic). Sau khi nạp, thử lấy nến từ vault theo `symbol`/`timeframe`/`range` trong file:

- **Có đủ** → vẽ đầy đủ: nến, marker vào/ra, indicator của chiến lược (`strategy_indicator_lines.py`), tô nền xu hướng (`BOT-113`).
- **Thiếu/không có** → 3 panel còn lại (Performance Summary, Trade Logs, Equity Curve) hiển thị bình thường; panel nến hiện thông báo *"Cần sync dữ liệu ETHUSDT 5m (18/07–18/08) để xem biểu đồ nến"* + nút sync, tái dùng affordance của [`BOT-059`](../completed/BOT-059_backtest_inline_data_sync_affordance.md). Sync xong thì vẽ được ngay, không cần nạp lại file.

Lưu ý đường native chart: mọi tính năng ngoài phạm vi `NativeBacktestChartHostAdapter` đều raise `NativeUnsupportedFeatureError` và presenter tự rebuild host Python — đường import phải đi qua đúng cơ chế fallback đã có, không bypass.

---

## 5. Kiểm Thử

- Nạp file hợp lệ → 4 panel khớp **chính xác** kết quả gốc (so trực tiếp với `BacktestResult` dùng để xuất).
- Nạp xong `isConfigDirty` **phải là `False`** (đây là bug dễ xảy ra nhất của task này).
- Bấm Run trong chế độ xem → thoát state, chạy thật, banner biến mất.
- Engine version lệch / strategy key lạ / metrics bị sửa → đúng badge tương ứng.
- Vault không có nến → 3 panel vẫn đúng, panel nến hiện thông báo sync (không crash, không chart rỗng im lặng).
- File hỏng → thông báo lỗi tiếng Việt rõ ràng, màn hình giữ nguyên trạng thái cũ, không mất kết quả đang xem.
