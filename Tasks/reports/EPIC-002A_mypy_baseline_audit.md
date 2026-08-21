# 🔎 EPIC-002A — Đo Baseline `mypy` Trên Codebase Hiện Tại

> [!NOTE]
> **Báo cáo đo lường — task con đầu tiên của [`EPIC-002`](../epics/EPIC-002_static_type_checking_in_local_ci/README.md).**
> Phạm vi chỉ là **đo và báo cáo**, không sửa bất kỳ lỗi nào tìm thấy (trừ 1
> phát hiện "sống" ghi rõ ở §5 — cân nhắc riêng, chưa fix). Mọi con số dưới
> đây chạy thật bằng `mypy 2.1.0`, không suy đoán.

---

## 1. Phạm vi & Phương pháp

```bash
pip install mypy==2.1.0   # đã thêm vào requirements.txt
mypy --namespace-packages --explicit-package-bases <path>
```

Chạy tách riêng theo 3 vùng để so sánh:

| Vùng | Số file kiểm tra | Số lỗi |
| :--- | ---: | ---: |
| `src/` | 241 | **183** |
| `scripts/` | 21 | **29** |
| `tests/` | 200 | **9** |

Không dùng `--strict` — cấu hình mặc định của `mypy`, đúng khuyến nghị của
epic (không bật nghiêm ngặt ngay từ đầu).

---

## 2. `src/` — Phân loại theo Layer & Mã lỗi

| Layer | Số lỗi | Mã lỗi (số lượng) |
| :--- | ---: | :--- |
| `presentation/` | 133 (73%) | `arg-type` 65, `assignment` 28, `attr-defined` 26, `dict-item` 4, `index` 3, `call-overload` 3, `var-annotated` 2, khác 2 |
| `domain/` | 33 (18%) | `operator` 20, `arg-type` 13 |
| `application/` | 10 (5%) | `arg-type` 7, `call-arg` 2, `str` 1 |
| `infrastructure/` | 7 (4%) | `arg-type` 5, `valid-type` 1, `misc` 1 |

**Phát hiện quan trọng nhất của mục này: 96/183 lỗi toàn `src/` (52%) — gần
như toàn bộ nằm trong `presentation/` — là 1 lớp lỗi hệ thống duy nhất**:
PySide6's `@Property` descriptor. `mypy` đọc kiểu của `view_model.someProp`
là chính object `Property` (bộ mô tả descriptor) thay vì kiểu dữ liệu thật nó
trả về lúc runtime — vì `PySide6` không có type stub đầy đủ cho cơ chế này.
Ví dụ điển hình:

```
backtest_presenter.py:2259: error: Argument "long_leverage" to
"BrokerSimulationConfig" has incompatible type "Property"; expected "float"
```

Đây **không phải bug logic thật** — là ma sát giữa `mypy` và PySide6, không
liên quan gì tới đúng/sai của code. Ý nghĩa cho `EPIC-002B`: nếu bật gate
ngay trên `presentation/` mà không xử lý riêng lớp này (stub riêng, hoặc
loại trừ tạm thời), phần lớn "lỗi" người review nhìn thấy sẽ là nhiễu, không
phải giá trị thật — càng củng cố khuyến nghị bắt đầu từ `domain/` trước
(xem `EPIC-002D`).

`domain/` sạch khỏi nhiễu Property (đúng nguyên tắc Clean Architecture đã
ghi trong `AGENTS.md` — Domain không phụ thuộc `sagittarius_engine`/PySide6).
20/33 lỗi domain là `[operator]`, mẫu điển hình đáng chú ý thật (không phải
nhiễu công cụ) ở `long_term_trend_zone_strategy.py:60,62` (chiến lược từ
`BOT-113`): so sánh `float > trend_ema` khi `trend_ema` được khai kiểu Union
gồm nhiều loại `IndicatorValue` (`MACDValue`, `SupportResistanceValue`, …).
Runtime có thể luôn đúng (logic biết `trend_ema` chỉ bao giờ là `float` ở
nhánh này), nhưng kiểu khai báo không thu hẹp được điều đó — đúng loại "type
gap thật" mà `mypy` sinh ra để lộ, đáng xem lại khi tới lượt `domain/` ở
`EPIC-002D`, không phải lỗi khẩn cấp.

---

## 3. Vì sao cần chạy `src/` + `scripts/` (+ `tests/`) TRONG CÙNG 1 lệnh

Phát hiện kỹ thuật quan trọng thứ hai, ảnh hưởng trực tiếp thiết kế của
`EPIC-002B`: đã thử tái hiện đúng lỗi `BUG-026`
(`_BlockingExchangeClient` thiếu `stream_historical_klines()`) bằng `mypy`
chạy **riêng lẻ trên 1 file** `scripts/shutdown_sync_probe.py` — kết quả
**"Success: no issues found"**, dù lỗi đó có thật và đã crash runtime. Chỉ
khi chạy `mypy` trên file đó **cùng lúc** với module định nghĩa
`IExchangeClient` (hoặc cùng lúc với toàn bộ `src/`), `mypy` mới báo đúng:

```
scripts/shutdown_sync_probe.py:83: error: Cannot instantiate abstract class
"_BlockingExchangeClient" with abstract attribute "stream_historical_klines"
[abstract]
```

**Kết luận cho `EPIC-002B`:** cổng CI **không được** chạy `mypy` riêng lẻ
theo từng thư mục tách biệt (`mypy src` rồi `mypy scripts` rồi `mypy tests`
ba lệnh độc lập) — phải chạy **1 lệnh duy nhất** bao trọn mọi vùng cần kiểm
tra (`mypy src scripts` tối thiểu), để `mypy` phân tích đủ toàn bộ đồ thị
import và xác nhận được tính đầy đủ của ABC xuyên file.

---

## 4. `scripts/` (29 lỗi) & `tests/` (9 lỗi)

`scripts/` bẩn hơn `tests/` đáng kể (29 vs 9), hợp lý vì đây là nơi chứa
nhiều test double/probe tự viết tay (`_BlockingExchangeClient`,
`_SeededMarketDataRepository`, …) — đúng loại code dễ trôi khỏi interface
thật nhất, và là nguồn gốc của cả `BUG-026` lẫn phát hiện mới ở §5.
`tests/` sạch hơn nhiều vì phần lớn dùng `Mock()` (không được `mypy` phân
tích sâu — bản chất duck-typing của `Mock` né được type checking, không
phải vì code test tốt hơn code script).

Không lỗi `[abstract]` nào trong `tests/` — `_InMemoryMarketDataRepository`
(`test_backtest_user_flow.py`) đã cập nhật đúng interface mới nhất khi sửa
`BUG-025`, còn nguyên vẹn.

---

## 5. ⚠️ Phát hiện "sống" — chưa fix, cần quyết định riêng

Quét `src/` + `scripts/` cùng lúc lộ ra **1 defect thật, đang tồn tại ngay
bây giờ, cùng lớp với `BUG-026`, chưa từng được báo cáo**:

```
scripts/backtest_timeframe_toolbar_e2e.py:198: error: Cannot instantiate
abstract class "_SeededMarketDataRepository" with abstract attributes
"clear_klines", "count_klines", ... and "vacuum" (4 methods suppressed)
[abstract]
```

`_SeededMarketDataRepository` implement `IMarketDataRepository` nhưng chỉ có
5/12 method: `save_klines`, `get_latest_kline_time`, `get_klines`,
`get_database_status`, `get_range_coverage`. Thiếu **7**: `count_klines`,
`stream_klines`, `clear_klines`, `purge_all`, `list_available_shards`,
`vacuum`, `get_gaps`.

**Tự nhận trách nhiệm một phần:** 2 trong 7 method thiếu (`count_klines`,
`stream_klines`) là do chính `BUG-025` (phiên này) thêm vào interface —
lúc đó tôi chỉ `grep -rl "IMarketDataRepository)" src/ tests/` để tìm hết
implementer cần cập nhật, **không có `scripts/` trong phạm vi grep đó**, nên
file này lọt qua. 5 method còn lại thiếu từ trước, không liên quan `BUG-025`.

Đây đúng là bằng chứng sống động nhất cho toàn bộ lý do `EPIC-002` tồn tại —
tìm thấy **trong lúc đo baseline**, đúng như cơ chế đang được đề xuất sẽ tự
động bắt trong tương lai.

**Chưa fix** (đúng phạm vi task này). Cần bạn quyết định: fix ngay bây giờ
(nhỏ, cô lập, giống `BUG-026`), hay để `EPIC-002B` khi cổng CI thật được bật
sẽ tự chặn commit tiếp theo chạm tới file này.

---

## 6. Khuyến nghị cho `EPIC-002B`

1. Lệnh gate: `mypy --namespace-packages --explicit-package-bases src scripts`
   (tối thiểu) — không tách lệnh theo thư mục (xem §3). Cân nhắc thêm `tests`
   sau khi `EPIC-002B` ổn định, không bắt buộc ngay đợt đầu (chỉ 9 lỗi,
   nhưng làm chậm lệnh gate và không phải nơi bug thật hay xuất hiện nhất —
   dữ liệu §4 cho thấy `scripts/` mới là nơi cần ưu tiên).
2. Vùng nhiễu 96 lỗi `Property` ở `presentation/` cần 1 quyết định tường
   minh trước khi bật gate — không thể để mặc định đỏ vì nhiễu công cụ:
   loại trừ tạm `presentation/` khỏi gate ban đầu (khuyến nghị, khớp
   `EPIC-002D`'s thứ tự Domain trước), hoặc chấp nhận baseline-suppression
   riêng cho đúng pattern `Property`.
3. `domain/`, `application/`, `infrastructure/` — 50 lỗi tổng cộng, không có
   nhiễu hệ thống nào tương tự Property, nhưng vẫn còn baseline thật (`50`
   lỗi) — không bật gate như "0 lỗi cho phép" ngay ở 3 layer này nếu chưa
   dọn hết; cần baseline-suppression tạm thời hoặc dọn trước khi bật.
