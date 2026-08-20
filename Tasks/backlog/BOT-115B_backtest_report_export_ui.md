# Nhiệm vụ: Xuất Báo cáo Backtest từ UI

**Mã Task:** `BOT-115B`  
**Thuộc Epic:** [`BOT-115`](BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟢 **S (Fast Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-115A`](BOT-115A_backtest_report_schema_and_serializer.md)

---

## 1. Triển Khai

Thêm nút **"Lưu báo cáo"** cạnh khu kết quả màn Backtest, chỉ bật khi đã có kết quả thật (`_last_result is not None`).

Đường đi đã có sẵn tiền lệ trong chính presenter này — `_on_trade_log_export_requested()` (xuất Trade Logs ra CSV) dùng `QFileDialog.getSaveFileName` với hằng số tiêu đề/tên file/bộ lọc riêng. Task này lặp lại đúng khuôn đó, đổi bộ lọc thành `Sagittarius Report (*.sagi-report.json *.sagi-report.json.gz)` và tên gợi ý sinh động theo nội dung, ví dụ `ETHUSDT_5m_ema_crossover_20260820_1432.sagi-report.json`.

Thư mục mặc định: `reports/` cạnh `database/` (cùng cách suy ra qua `ConfigKeys`, có fallback `os.getcwd()` giống `_DEFAULT_DB_DIR_NAME` trong `binance_bot_module.py`), tự tạo nếu chưa có. User vẫn đổi được sang chỗ khác qua dialog.

---

## 2. Chi Tiết Cần Đúng

- **Xuất kết quả thật đang hiển thị, không phải toolbar hiện tại.** Nếu `isConfigDirty` đang bật (user đã chỉnh toolbar nhưng chưa chạy lại), file phải ghi **config của lần chạy đã sinh ra kết quả đó**, không phải config đang gõ dở. Ghi nhầm chỗ này là làm hỏng đúng thứ epic sinh ra để bảo vệ. Presenter đã có sẵn snapshot đó cho dirty-tracking (`BOT-095B`) nên chỉ cần dùng đúng biến.
- Khác với CSV export (xuất đúng phần **đang lọc/đang nhìn** — quyết định có chủ đích ghi trong `trade_log_export.py`), report **luôn xuất toàn bộ trades**: đây là ảnh chụp một lần chạy, không phải ảnh chụp màn hình.
- Xuất xong log một dòng nêu đường dẫn + số lệnh + dung lượng file.

---

## 3. Kiểm Thử

- Chưa có kết quả → nút tắt, bấm không làm gì.
- Dialog trả về chuỗi rỗng (user bấm Cancel) → không ghi file.
- `isConfigDirty=True` → file ghi config của lần chạy cũ, **không** phải giá trị toolbar mới.
- File sinh ra nạp lại được bằng đúng `from_json` của `BOT-115A`.
