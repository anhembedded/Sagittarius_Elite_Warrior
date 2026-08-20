# Nhiệm vụ: Schema `BacktestReport` & Serializer JSON

**Mã Task:** `BOT-115A`  
**Thuộc Epic:** [`BOT-115`](BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅, [`BOT-104`](../completed/BOT-104_backtest_properties_and_broker_simulator_modal.md) ✅

---

## 1. Phạm Vi

Toàn bộ task này là **thuần Python, zero UI** — không đụng file `.qml` nào, không đụng presenter. Chỉ có: một dataclass, một hàm serialize, một hàm deserialize + validate, và test. Đây là móng của cả epic, làm chắc chỗ này thì 3 task còn lại đều nhẹ.

---

## 2. Cấu Trúc File

Đuôi `.sagi-report.json`, gzip khi vượt ngưỡng (`.sagi-report.json.gz`). 4 section:

```jsonc
{
  "schema_version": 1,
  "provenance": {
    "engine_version": "1.4.0",
    "app_version": "...",
    "strategy_key": "ema_trend_confirm_pullback",
    "created_at": "2026-08-20T14:32:05+00:00",
    "execution_mode": "BAR_CLOSE",
    "data_window": { "first_kline_open": "...", "last_kline_close": "...", "kline_count": 43200 }
  },
  "config": { /* BacktestRunConfig đầy đủ: symbol, timeframe, range, strategy_params, position_sizing, broker_config (phí/slippage/pyramiding/đòn bẩy), currency, initial_balance */ },
  "result": {
    "final_balance": 12843.51,
    "metrics": { /* toàn bộ field BacktestMetrics */ },
    "trades": [ /* toàn bộ field Trade, kể cả metadata + side + exit_reason */ ],
    "equity_curve": { "t": ["..."], "v": [10000.0] },
    "out_of_sample": { /* OutOfSampleValidation hoặc null */ }
  }
}
```

Ghi chú thiết kế:

- **`equity_curve` lưu dạng cột** (`{"t": [...], "v": [...]}`) chứ không phải list of objects. Backtest `1m` vài tháng là hàng trăm nghìn điểm — dạng cột tiết kiệm khoảng 3–4 lần dung lượng và parse nhanh hơn hẳn.
- **`schema_version` là số nguyên tăng dần**, kiểm tra ngay dòng đầu khi đọc. Version lạ (lớn hơn version app hiểu) → từ chối nạp kèm thông báo rõ, **không** cố đoán.
- **Không nhúng klines** — xem §3.1 của Epic.
- Mọi `datetime` ghi ISO-8601 **có timezone UTC tường minh**, giữ đúng invariant "engine/DB luôn UTC" đã chốt ở [`BOT-097`](../completed/BOT-097_backtest_display_timezone_selector.md).

---

## 3. An Toàn Khi Nạp (bắt buộc)

File report là **input không tin cậy**: user tải về từ đâu đó, đồng nghiệp gửi qua chat. Vì vậy:

1. **Tuyệt đối không `pickle`/`eval`/`yaml.load` không an toàn.** `json.loads` + dựng dataclass thủ công theo từng field đã biết tên.
2. **Whitelist `strategy_key`** theo `StrategyRegistry` thật đang chạy. Key lạ → vẫn cho xem `result` (số liệu là dữ liệu chết, vô hại) nhưng **khoá chế độ "nạp cấu hình để chạy lại"** vì không có class chiến lược nào để chạy.
3. **Whitelist enum** (`TimeFrame`, `PositionSizingType`, `ExitReason`, `PositionSide`, `BacktestExecutionMode`, `Currency`): giá trị lạ → lỗi nạp tường minh, không `getattr` động theo chuỗi trong file.
4. **Không tin số liệu trong file là nhất quán.** `metrics` được lưu sẵn để hiển thị nhanh, nhưng phải có cờ kiểm tra chéo: tính lại `BacktestMetrics.compute(trades, equity_curve, initial_balance)` và so với `metrics` đã lưu; lệch quá ngưỡng → cảnh báo *"báo cáo có dấu hiệu bị sửa tay hoặc tạo bởi phiên bản engine khác"*. Đây chính là chỗ Epic [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md) đòi hỏi: không hiển thị số không kiểm chứng được.
5. Lỗi nạp trả về **kết quả có cấu trúc** (loại lỗi + thông điệp tiếng Việt cho UI), không raise exception trần để UI phải đoán.

---

## 4. Kiểm Thử

- **Round-trip là test xương sống**: dựng một `BacktestResult` + `BacktestRunConfig` đầy đủ (có short, có metadata, có `out_of_sample`, có đòn bẩy ≠ 1.0x), export → import → khẳng định **mọi field bằng đúng bản gốc**, kể cả `metrics` tính lại khớp.
- File thiếu field / sai kiểu / `schema_version` tương lai / JSON hỏng → lỗi tường minh, không crash.
- `strategy_key` lạ → nạp được `result`, cờ "không nạp được config" bật đúng.
- `metrics` bị sửa tay lệch khỏi `trades` → cờ cảnh báo bật đúng.
- Equity curve rỗng / 1 điểm / 100k điểm (kiểm tra dung lượng dạng cột và thời gian parse).
- Gzip và không gzip đọc lại đều đúng.
