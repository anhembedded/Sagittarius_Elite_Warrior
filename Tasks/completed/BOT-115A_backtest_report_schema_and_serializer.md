# Nhiệm vụ: Schema `BacktestReport` & Serializer JSON

**Mã Task:** `BOT-115A`  
**Thuộc Epic:** [`BOT-115`](BOT-115_backtest_report_persistence_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ Done (2026-09-22)  
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

## Implementation notes (2026-09-22)

- **File**: `src/modules/backtesting/contracts/backtest_report.py` (thuần Python, không đụng UI/presenter, đúng §1).
  `BacktestReport` (`schema_version`, `provenance`, `config`, `result`) + `serialize_backtest_report`/`load_backtest_report`
  (không raise — luôn trả `BacktestReportLoadResult` có cấu trúc, đúng §3 mục 5) + `dump_backtest_report` (gzip tuỳ chọn,
  `load_backtest_report` tự nhận diện gzip qua magic byte, không cần biết trước).
- **`config` là dataclass riêng (`BacktestReportConfig`), không tái dùng `BacktestRunConfig`.** `BacktestRunConfig` nằm ở
  `ui/logic/backtest_fsm_matrix.py` — tầng UI. `contracts/` import ngược lên UI vi phạm `architecture-rule.md` §3
  (dependency phải hướng vào trong). Cùng lý do, `execution_mode` lưu dạng chuỗi thuần (giá trị thật của
  `BacktestExecutionMode`) thay vì import chính enum đó — enum này cũng đang ở tầng UI, dời nó sang `contracts/` là cải
  tiến thật nhưng là việc khác, ngoài phạm vi task này (nhiều call site khác đang dùng). `_KNOWN_EXECUTION_MODES` bắt lỗi
  giá trị lạ tường minh thay vì âm thầm chấp nhận.
- **An toàn khi nạp (§3), làm đủ cả 4 mục**: JSON thuần (`json.loads`, không `pickle`/`eval`/yaml) + dựng dataclass thủ
  công theo tên field đã biết; mọi enum là `str, Enum` nên `EnumClass(value)` tự whitelist, giá trị lạ raise `ValueError`
  → bắt thành lỗi nạp tường minh; `strategy_key` nhận whitelist qua tham số `valid_strategy_keys: Collection[str]` (gọi
  từ ngoài lấy từ `StrategyRegistry.available()` thật đang chạy — **không import `StrategyRegistry` trực tiếp vào
  `contracts/`**, cùng lý do inward-only ở trên) — key lạ vẫn nạp được `result` để xem, chỉ bật cờ
  `strategy_key_unknown`; `BacktestMetrics.compute()` được tính lại và so với `metrics` đã lưu bằng `math.isclose` (dung
  sai nổi để chịu được nhiễu làm tròn round-trip, đủ chặt để bắt số bị sửa tay) → cờ `metrics_mismatch`.
- **Klines không nhúng (Epic §3.1)**: `committed_bars` bị bỏ qua khi serialize, luôn dựng lại `None` khi deserialize —
  đúng giá trị `BacktestResult` đã dùng cho "đọc nến từ storage".
- **14 test mới** (`tests/unit/modules/backtesting/contracts/test_backtest_report.py`), gồm test xương sống round-trip
  đầy đủ trường (short, đòn bẩy 5x, metadata, `out_of_sample` lồng nhau), gzip/không-gzip cho cùng kết quả, equity curve
  0/1/2000 điểm, 7 test cho các đường an toàn khi nạp (JSON hỏng, mảng JSON ở gốc, `schema_version` tương lai, thiếu
  field, enum lạ, cột equity lệch độ dài, key lạ vẫn xem được, số liệu sửa tay bị bắt) + 1 fuzz nhẹ 7 chuỗi byte rác xác
  nhận không bao giờ raise. Mutation-verify: tắt `metrics_mismatch` (gán cứng `False`) → đúng 1 test đỏ đúng lý do, phục
  hồi lại xanh. `ruff`/`mypy` sạch trên toàn `src/` (639 file, gate thật).
- **Không làm trong task này** (đúng §1, chuyển cho các task con sau của Epic `BOT-115`): ghi/đọc file thật trên đĩa với
  đuôi `.sagi-report.json[.gz]` và ngưỡng tự động gzip theo dung lượng (`BOT-115B`), map `BacktestRunConfig` thật của
  UI sang `BacktestReportConfig`, và state FSM riêng cho chế độ xem báo cáo đã nhập (`BOT-115C`).
