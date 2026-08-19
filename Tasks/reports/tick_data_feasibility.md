# BOT-075 — Spike: khả thi & chi phí dữ liệu tick

> Trạng thái: **✅ Spike hoàn thành (19/08)** — §3.1–§3.4 đều đo bằng số thật
> (sync thật 7 ngày `BTCUSDT` qua Binance public REST) và §3.1 (nguồn dữ liệu)
> đã được user xác nhận. Không còn chặn `BOT-076`. Còn thiếu: viết
> `RunRealtimeBacktestCommand` (đó là `BOT-076`, ngoài phạm vi spike này).

**Cửa sổ đo thật**: `BTCUSDT`, `2026-08-12T06:46:13Z` → `2026-08-19T06:46:13Z`
(7 ngày tròn, kết thúc tại thời điểm chạy script). Script:
[`scripts/tick_data_feasibility_probe.py`](../../scripts/tick_data_feasibility_probe.py)
— chạy 1 lần, kết quả giữ trong file này; **không sync lại** trừ khi cần đo lại
với cửa sổ khác. Dữ liệu sync được giữ lại làm fixture tại
`database/BTCUSDT_1S_SPIKE.db` (120,12 MiB) và `database/BTCUSDT_1M_SPIKE.db`
(2,11 MiB) — cả hai đều `.db` nên tự động gitignore, không commit.

## §3.1 — Nguồn dữ liệu: đề xuất `1s kline`, không dùng `aggTrades`

### Số liệu chính thức (Binance Spot REST API docs, developers.binance.com)

| | `GET /api/v3/klines` (`interval=1s`) | `GET /api/v3/aggTrades` |
| :--- | :---: | :---: |
| Max entries/request | 1000 | 1000 |
| Request weight (IP) | **2** | **4** |
| Nhịp dữ liệu | Đều, đúng 1 dòng/giây | Không đều — 1 dòng/lệnh khớp thật, có giây 0 lệnh, có giây hàng chục lệnh |
| Fidelity | OHLCV gộp trong giây đó — **không phải** từng lệnh riêng lẻ | Tick thật, từng lệnh khớp |

Nguồn: [Klines endpoint](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints), [Aggregate Trades endpoint](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints) — cả hai đọc trực tiếp từ trang docs chính thức, không suy đoán.

### Ước lượng chi phí request cho 7 ngày (604.800 giây)

- **`1s kline`**: 604.800 ÷ 1000 = **~605 request** × weight 2 = **~1.210 weight**.
  Rẻ, đều, dự đoán được trước khi chạy.
- **`aggTrades`**: số request phụ thuộc **số lệnh khớp thật** trong 7 ngày —
  chưa đo được bằng lý thuyết, chỉ biết chắc **cao hơn nhiều bậc** so với
  klines (nhiều lệnh khớp/giây ở giờ cao điểm). Muốn dùng cái này thì bản
  thân việc ước lượng chi phí **cũng phải sync thật một đợt riêng** — tốn
  gấp đôi effort của cả spike.

### Code hiện có — 1s kline gần như không cần sửa gì để thử

Đã verify trực tiếp, không suy đoán:

- [`TimeFrame.ONE_SECOND = "1s"`](../../src/domain/value_objects/timeframe.py) đã có sẵn ở domain.
- `python-binance==1.0.37` (đang cài trong `.venv`) có `Client.KLINE_INTERVAL_1SECOND == "1s"` — verify thật bằng `python -c` trong venv dự án, không phải đọc changelog.
- [`PythonBinanceClient._fetch_raw_klines()`](../../src/infrastructure/binance/client.py#L43) dùng `client.get_historical_klines_generator(symbol, interval, ...)` — **không interval nào bị hard-code**, generator tự phân trang bất kể `interval` là gì. Nghĩa là gọi với `interval="1s"` chạy qua đúng pipeline hiện có, không cần code path riêng.
- [`SqlAlchemyMarketDataRepository.save_klines()`](../../src/infrastructure/persistence/sqlalchemy_repository.py#L38) đã upsert theo chunk (`_UPSERT_CHUNK_SIZE`) qua Core connection, docstring tự ghi rõ mục đích *"prevent database locks on massive syncs"* — cũng không có gì đặc thù cho 1m/5m, `interval` chỉ là 1 cột string trong bảng.

`aggTrades` thì **chưa có method nào** trong `PythonBinanceClient`/`IExchangeClient` — phải viết thêm adapter mới, map sang `MarketData` hoặc entity khác (không khớp OHLCV 1-1), và quyết định cách gộp về nhịp "1 lần/giây" cho vòng lặp strategy — tức là **tự tay làm lại việc mà `1s kline` Binance đã làm sẵn**.

### Fidelity limit — phải ghi rõ (theo yêu cầu `BOT-073` §8)

`1s kline` **vẫn không phải** tick thật 100%: nếu có 5 lệnh khớp trong cùng
1 giây, kline `1s` chỉ cho biết open/high/low/close/volume gộp của giây đó,
không cho biết thứ tự/giá từng lệnh riêng lẻ. Với yêu cầu gốc của user
(*"every one sec, we must calculate the last candle and all last
indicator"*) — đơn vị "mỗi giây" đã khớp đúng nhịp `1s kline`, nên giới hạn
này **chấp nhận được cho mục tiêu hiện tại** (không phải giả lập khớp lệnh
intra-second), miễn là tài liệu nói rõ ràng để không ai hiểu nhầm thành tick
thật.

### Quyết định — ✅ đã chốt (19/08, user xác nhận)

**Dùng `1s kline`, không dùng `aggTrades`.** Rẻ hơn ~2x/request, đều nhịp
đúng model "mỗi giây" user mô tả, hạ tầng hiện có gần như dùng lại được
nguyên vẹn. `aggTrades` chỉ nên cân nhắc lại nếu sau này có yêu cầu mô phỏng
intra-second thật (nhiều lệnh trong 1 giây phải phân biệt) — hiện chưa ai
yêu cầu điều đó. `BOT-076` dùng `1s kline` làm nguồn dữ liệu, không cần đánh
giá lại.

---

## §3.2 — Lưu trữ: số đo thật

| | `1s` | `1m` | Tỷ lệ |
| :--- | :---: | :---: | :---: |
| Số dòng (7 ngày) | 604.801 | 10.080 | **60,0×** |
| Thời gian fetch (Binance REST thật) | 314,5s (~5,2 phút, ~1.923 dòng/s) | 5,2s | 60,4× |
| Thời gian save (`save_klines`, upsert theo chunk) | 5,12s | 0,07s | 73× |
| Dung lượng `.db` thật (sau `PRAGMA wal_checkpoint(FULL)`) | **120,12 MiB** | **2,11 MiB** | **56,9×** — khớp sát tỷ lệ số dòng |
| Query lại full range (`get_klines`, 604.801/10.080 dòng) | **6,32s** | 0,16s | 40× |

**Lưu ý vận hành thật gặp phải, đáng ghi lại cho `BOT-076`**: SQLite chạy
`journal_mode=WAL` ([`database_manager.py`](../../src/infrastructure/persistence/database_manager.py#L68))
— đo `os.path.getsize()` **ngay sau** `save_klines()` cho ra số sai (file `1m`
đo được 4096 byte, tức gần như rỗng) vì dữ liệu còn nằm trong WAL, chưa
checkpoint vào file chính. Phải `PRAGMA wal_checkpoint(FULL)` (hoặc đóng hết
connection) rồi mới đo được dung lượng thật. Bất kỳ ai đo lại sau này cần biết
điều này, nếu không sẽ tưởng nhầm dữ liệu "biến mất".

Tốc độ fetch (~1.923 dòng/s) bị giới hạn bởi **độ trễ network round-trip mỗi
request**, không phải rate-limit weight của Binance (605 request × weight 2 =
1.210 weight, quá nhẹ so với hạn 6000 weight/phút của Binance) — nghĩa là
muốn sync nhanh hơn thì phải song song hoá request, không phải "chờ rate
limit nới ra".

## §3.3 — Runtime: số đo thật

Chạy `RunStaticBacktestCommandHandler` thật (strategy `ema_crossover`, có
out-of-sample split bắt buộc theo `BOT-080`) trên đúng 604.801 nến `1s` vừa
sync — không phải ước lượng.

| | `1s` (đo thật, 604.801 nến) | `1m` (mốc `BUG-002`, 10.079 nến) | Tỷ lệ |
| :--- | :---: | :---: | :---: |
| Thời gian handler chạy | **10,98s** | ~1,5s | **~7,3×** — thấp hơn nhiều so với 60× số nến |
| Số lệnh khớp (`trades`) | 11.285 | 807 | 14× |

Handler scale **tốt hơn tuyến tính** theo số nến (7,3× thời gian cho 60× dữ
liệu) — không phải nỗi lo lớn nhất. Nỗi lo thật nằm ở **tổng độ trễ cảm nhận
được của người dùng**: query lại dữ liệu từ DB (§3.2, 6,32s) + chạy handler
(10,98s) ≈ **~17 giây** cho 1 lần bấm "Chạy Backtest" trên khung `1s`/7 ngày —
so với Static `1m` hiện tại gần như tức thời (~1,5s). 17 giây **không thể**
coi là "chạy trong UI" theo nghĩa đồng bộ — bắt buộc phải chạy nền + progress
+ nút Hủy, đúng cơ chế `CancellationToken` đã có sẵn từ `BOT-034`/`BOT-095C`,
không cần dựng cơ chế mới.

⚠️ Số đo này **chưa gồm** chi phí tính lại N indicator mỗi tick (`BOT-042`
provisional/commit) — `ema_crossover` ở đây tự nó nhẹ. Chiến lược nhiều
indicator hơn sẽ khiến con số 17 giây này là **cận dưới**, không phải cận
trên.

## §3.4 — Độ phân giải cố định hay cho chọn: kết luận sơ bộ

Với số đo thật ở §3.2/§3.3, **17 giây cho 1 cửa sổ 7 ngày ở `1s`** (đã có
progress+cancel để không đứng UI, nhưng vẫn là 17 giây chờ) ủng hộ rõ đề xuất
ở §3.4 gốc: **cho user chọn độ phân giải (`1s`/`5s`/`15s`)** thay vì cố định
`1s`. Ở `5s`: ~121 nghìn dòng thay vì 604 nghìn (12× thay vì 60× so với `1m`)
— theo tỷ lệ đo được, ước lượng còn khoảng **1/5** chi phí runtime hiện tại
(~2,2s runtime + phần query nhỏ hơn theo cùng tỷ lệ), dù cần đo lại thật khi
implement `BOT-076` chứ không suy ra tuyến tính hoàn toàn an toàn. Hình thức
field (`RunRealtimeBacktestCommand` field riêng hay `TimeFrame` riêng) để
`BOT-076` tự chốt lúc code — spike này chỉ xác nhận **có nên cho chọn** chứ
không chốt kiến trúc field.

## Tổng kết — trả lời 4 câu hỏi mục tiêu (§1 task gốc)

1. **Nguồn dữ liệu từ đâu, dạng gì?** → `1s kline` Binance (`GET /api/v3/klines`), không dùng `aggTrades`. Xem §3.1.
2. **Lưu trữ tốn bao nhiêu — hạ tầng chịu được không?** → 120 MiB/7 ngày/symbol ở `1s` (~6,3 GiB/năm/symbol theo cùng tỷ lệ) — SQLite sharding theo symbol hiện tại **chịu được** về mặt dung lượng, chunked upsert đã sẵn cho "massive syncs". Chưa cần shard thêm theo thời gian ở quy mô 1 symbol/7 ngày; **chưa đo** ở quy mô nhiều symbol × nhiều tháng (ngoài phạm vi 7 ngày × 1 symbol của spike này).
3. **Backtest chạy mất bao lâu — dùng được trong UI không?** → ~17s tổng (query + handler) cho 7 ngày `1s` — **không** dùng được kiểu đồng bộ, **bắt buộc** chạy nền + progress + cancel (hạ tầng đã có sẵn từ `BOT-034`/`BOT-095C`, không cần xây mới).
4. **Cố định `1s` hay cho chọn độ phân giải?** → **Cho chọn** (`1s`/`5s`/`15s`) — số đo thật ủng hộ rõ, xem §3.4.
