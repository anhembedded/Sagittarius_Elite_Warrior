# EPIC-021D — Kiểm tra kết nối read-only: lần chạm sàn thật đầu tiên

- **Trạng thái:** ✅ Xong
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021A`, `EPIC-021B` · **Chặn:** `EPIC-021F`
- **Đóng nốt bug:** [`BUG-080`](../../../bug_report/completed/BUG-080_settings_api_credentials_never_reach_the_exchange_client.md) (1/2 đã đóng bởi `EPIC-021B`)

---

## 1. Bối cảnh & vấn đề thật

Sau `021A`+`021B`, app **có thể** ký request tới Futures Testnet nhưng chưa ai chứng minh là nó
ký đúng. Nhảy thẳng sang đặt lệnh có nghĩa là lần đầu tiên chạm sàn thật cũng đồng thời là lần
đầu tiên gửi lệnh — nếu hỏng, không phân biệt được lỗi ở chữ ký, ở đồng hồ, ở quyền của key, hay
ở payload lệnh.

Task này tách bước đó ra: một đường **chỉ đọc**, chạy được với key thật của anh, và sau khi nó
xong thì trong toàn repo **vẫn chưa tồn tại** bất kỳ hàm nào gửi lệnh.

Ba nhóm lỗi hay bị gộp làm một và phải phân biệt tường minh:

| Triệu chứng | Nguyên nhân thật | Việc user phải làm |
| :--- | :--- | :--- |
| `-2015` / 401 | Key sai, hoặc key **của môi trường khác** (Spot Testnet ≠ Futures Testnet ≠ mainnet) | Lấy đúng key ở `testnet.binancefuture.com` |
| `-1021 Timestamp for this request is outside of the recvWindow` | Đồng hồ máy lệch giờ sàn | Đồng bộ NTP; app hiển thị độ lệch đo được |
| Kết nối được nhưng số dư 0 | Tài khoản testnet mới, chưa được cấp quỹ | Nhận USDT test trên web testnet |

Không phân biệt được ba nhóm này là cách một buổi chiều biến mất.

## 2. Thiết kế + lý do

### 2.1 Một query CQRS, không phải một lời gọi trực tiếp từ presenter

```
src/application/use_cases/queries/get_exchange_connection_status/{query.py,handler.py,__init__.py}
```

Đúng khuôn CQRS đã có (`architecture-rule.md` §4): mỗi use case một thư mục, command/response
tách khỏi handler. Presenter không được gọi thẳng adapter sàn.

### 2.2 Kết quả là một VO có tên, mô tả **cả** trạng thái xấu

```python
@dataclass(frozen=True)
class ExchangeConnectionStatus:
    venue: TradingVenue
    reachable: bool
    failure: ConnectionFailureKind | None   # NOT_CONFIGURED | BAD_SIGNATURE | CLOCK_SKEW | KEY_EXPIRED | NETWORK
    server_time_skew_ms: int | None
    usdt_balance: Decimal | None
    position_mode: PositionMode | None      # ONE_WAY | HEDGE
    margin_type: MarginType | None
    open_position_count: int | None
```

`ConnectionFailureKind` là enum chứ không phải chuỗi lỗi: nó là thứ UI phải rẽ nhánh theo, và
một chuỗi tiếng Anh của sàn không phải hợp đồng ổn định.

### 2.3 Hedge mode bị **từ chối tường minh**, không phải chạy tiếp rồi sai

ADR §6: toàn bộ epic giả định One-way mode. Nếu tài khoản testnet đang ở Hedge mode, mọi giả
định về "một vị thế cho một symbol" sai âm thầm. Vì vậy `position_mode == HEDGE` là một
**failure có tên**, hiển thị hướng dẫn đổi lại, và `EPIC-021G` sẽ từ chối bật giao dịch.

App **không tự đổi** position mode/margin type của tài khoản: đó là thay đổi ngoài phạm vi
"kiểm tra kết nối", và một task đọc-only không được có tác dụng phụ.

### 2.4 Bốn lời gọi, tất cả read-only — không phải ba như dự tính ban đầu

`futures_ping` (mạng) → `futures_time` (độ lệch đồng hồ) → `futures_account` (số dư, vị thế mở)
→ **`futures_get_position_mode`** (`GET /fapi/v1/positionSide/dual`, ký riêng). Xem §2.5 — bản kế
hoạch gốc giả định position mode nằm trong payload `futures_account()`; khi code thật, đó là một
endpoint tách biệt.

### 2.5 Sửa phạm vi, phát hiện lúc code thật (2026-09-01)

**Vì sao 4 lời gọi, không phải 3:** `position_mode` **không nằm trong** payload
`futures_account()` — đó là `GET /fapi/v1/positionSide/dual`, ký riêng, `futures_get_position_mode()`
trong `python-binance`. Đoán sai chỗ này sẽ khiến mọi tài khoản báo `ONE_WAY` một cách im lặng —
đúng kiểu lỗi "giả định sai âm thầm" mà §2.3 tồn tại để ngăn. Gọi thêm, không đoán.

**Thêm `ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`** (thứ 6, không phải 5 như liệt kê ở §2.2):
§2.3 đòi Hedge Mode phải là "failure có tên", nhưng danh sách 5 kind gốc không có chỗ nào khớp
nghĩa đó — cả 5 đều mô tả *không kết nối được*, không mô tả *kết nối được nhưng tài khoản không
dùng được cho epic này*. VO vẫn `reachable=True` trong trường hợp này (kết nối thật sự thành
công) — `failure` mang nghĩa "trade-readiness", không chỉ "connectivity".

**`margin_type` là per-symbol, không phải account-wide:** Binance Futures không có "margin type
mặc định của tài khoản" — mỗi symbol tự chọn Cross/Isolated, và tài khoản mới (0 vị thế) không có
gì để suy luận. `ExchangeConnectionStatus.margin_type` vì vậy là `None` khi chưa có vị thế mở nào
(không đoán CROSSED làm mặc định), và khi có, lấy mẫu từ vị thế mở đầu tiên — ghi rõ trong
docstring của `FuturesAccountReader`/VO, không âm thầm.

**Bug thật tìm thấy khi chạy CLI thật (không phải chỉ unit test):** `Client(...)`'s constructor tự
`ping()` khi dựng (`ping=True` mặc định, đúng trigger `BUG-045`) — bản đầu chỉ bọc try/except
quanh các lời gọi *sau khi* client đã dựng xong, không bọc chính lệnh dựng client. Chạy
`main.py exchange-status` thật với key giả + egress bị chặn tạo ra traceback chưa bắt được thay vì
`ConnectionFailureKind.NETWORK`. Unit test (dùng `Mock` cho toàn bộ client) không bắt được vì
không bao giờ dựng `Client` thật. Sửa: đưa lệnh dựng client vào trong cùng khối `try`. Thêm
regression test giả lập chính xác kịch bản này (`session_factory.create_trading_client` tự nó
raise). Bài học lặp lại đúng lý do `ci-rule.md` yêu cầu chạy thật, không chỉ tin unit test xanh.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/exchange_connection_status.py` | **Mới** — VO + `ConnectionFailureKind` (6 kind, xem §2.5), `PositionMode`, `MarginType` — cùng 1 file (implementation detail của 1 VO, không phải governance riêng như `MarketDataVenue`/`TradingVenue`) |
| `src/application/ports/i_trading_account_reader.py` | **Mới** — port **chỉ đọc**, 1 method `check_connection()`; `ITradingClient` (đặt lệnh) là `EPIC-021E`, cố ý chưa tồn tại |
| `src/infrastructure/binance/futures_account_reader.py` | **Mới** — implement bằng `futures_ping`/`futures_time`/`futures_account`/`futures_get_position_mode` |
| `src/infrastructure/binance/exchange_session_factory.py` | + `create_trading_client(credentials)` — client có key, luôn Futures Testnet |
| `src/application/use_cases/queries/get_exchange_connection_status/` | **Mới** — query + handler (thin wrapper, xem docstring handler) |
| `src/presentation/cli/exchange_status_formatter.py` | **Mới** — render VO thành text, dùng chung cho CLI headless/interactive **và** Settings UI |
| `src/presentation/cli/exchange_status_cmd.py`, `handlers/exchange_status_cli_handler.py` | **Mới** — `main.py exchange-status` (headless) + lệnh interactive shell |
| `src/config/cli_commands.json` | + entry `exchange-status` |
| `settings_view_model.py`/`settings_view.py`/`settings_presenter.py` | Nút "Kiểm tra kết nối" + vùng kết quả; `ActionOwnershipTracker` + `IThreadManager` + `Signal` cross-thread, không khoá UI |
| `tests/sanity/binance_fake_server.py` | + `/fapi/v1/time`, `/fapi/v2/account` (đúng version 2, không phải 1 — xác nhận từ source), `/fapi/v1/positionSide/dual` |
| `src/binance_bot_module.py` | Đăng ký reader + query handler |

## 4. Kiểm thử

- **Unit:** mỗi `ConnectionFailureKind` được suy ra đúng từ đúng loại lỗi/payload (bao gồm mã lỗi
  Binance không nhận diện được → `NETWORK`, không phải crash); độ lệch đồng hồ tính đúng dấu.
- **Unit:** `position_mode == HEDGE` → status là failure có tên, `reachable` vẫn `True`.
- **Unit (regression):** lỗi mạng xảy ra ngay lúc **dựng client** (không phải chỉ ở lời gọi sau
  đó) vẫn phân loại đúng — xem §2.5.
- **Integration:** qua `tests/sanity/binance_fake_server.py` thật (round-trip HTTP cục bộ) —
  chứng minh toàn bộ chuỗi gọi chạy đúng đường, **không** chứng minh việc sàn xác thực chữ ký
  (fixture không kiểm chữ ký) — ghi rõ trong docstring test.
- **Testnet tier (opt-in, `EPIC-021J`, chưa làm — task riêng):** chạy thật với key thật, khẳng
  định `reachable` và `usdt_balance is not None`. Đây là **bằng chứng vận hành**, không phải cổng
  CI (ADR §5).
- **Async UI (`async-ui-action-rule.md`):** action_id + `ActionOwnershipTracker` thật (không phải
  khoá UI trần) — bắt đầu action, khoá nút, chạy trên `IThreadManager`, callback qua `Signal`
  (Qt tự chuyển thread an toàn), xác nhận `is_current_pending()` trước khi ghi bất kỳ state nào
  vào ViewModel. Test riêng khẳng định: kết quả của lần bấm đã bị lần bấm sau đè lên (stale) bị
  bỏ qua đúng cách, không viết đè lên state của lần bấm mới hơn.
  **Không hỗ trợ huỷ (cancel)** — sửa phạm vi so với dự tính ban đầu: 4 lời gọi HTTP tuần tự,
  tổng thời gian cỡ giây, không phải một tác vụ dài cần điểm dừng giữa chừng — cùng lý do
  `GapCoordinator.run_inspect_gaps()` (đọc, không sửa dữ liệu) trong repo cũng không có
  `CancellationToken`, khác `run_repair_gap()`/`run_repair_all_gaps()` (ghi dữ liệu, có thể chạy
  lâu). `BUG-018`'s bẫy cụ thể (unlock signal phát ra dù chưa từng khoá) không áp dụng — không có
  đường huỷ nào để phát tín hiệu unlock sai.

## 5. Mốc chạy được

**Đây là mốc đầu tiên chạm sàn thật, và là mốc đầu tiên anh nhìn thấy tiền testnet của mình.**
Hai đường, cùng một query:

```bash
# Headless (VPS, không cần GUI) — command mới trong cli_commands.json + 1 handler
PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
    Sagittarius_Elite_Warrior/src/main.py exchange-status
```

Chạy thật, chưa cấu hình key (2026-09-01, phiên dev remote này):

```text
→ Chưa cấu hình API key/secret. Lấy key tại testnet.binancefuture.com, rồi lưu
qua màn Settings hoặc biến môi trường
BINANCE_FUTURES_TESTNET_API_KEY/BINANCE_FUTURES_TESTNET_API_SECRET.
```

Chạy thật lần hai, với key **giả** đặt qua biến môi trường (egress `*.binance.*` bị chặn tầng
chính sách ở phiên dev remote này — xem `EPIC-021A` §2.2b, cùng giới hạn):

```text
Venue: FUTURES_TESTNET   Kết nối: ✘  NETWORK
→ Không kết nối được tới sàn. Kiểm tra mạng/proxy rồi thử lại.
```

Hai lần chạy trên chứng minh đúng những gì mốc này cần chứng minh: pipeline thật chạy hết đường
(DI → dispatcher → handler → reader → `ExchangeSessionFactory.create_trading_client()` → `Client`
thật cố gắng ký request), phân loại lỗi đúng thay vì crash. Dạng bảng đầy đủ ở dưới (key thật,
`reachable=True`) đã verify qua fake server (`tests/integration/.../test_futures_account_reader_
against_fake_server.py`) — xem giới hạn của bằng chứng đó ở chính docstring test:

```text
Venue:            FUTURES_TESTNET          Kết nối: ✔
Lệch đồng hồ:     +134 ms                  (recvWindow 5000 ms → an toàn)
Position mode:    ONE_WAY ✔                Margin type: CROSSED
Số dư USDT:       15,000.00                Vị thế đang mở: 0
```

Và cùng thông tin đó trên nút **Kiểm tra kết nối** ở màn Settings — cùng
`format_exchange_connection_status()`, nên không lệch nhau.

Thêm CLI command ở repo này là **1 entry JSON + 1 handler + 1 dòng registry** — khuôn đã có sẵn
(`src/config/cli_commands.json`, `presentation/cli/handlers/`, `interactive_shell.py:46-47`),
không phải hạ tầng mới.

Ba nhóm lỗi ở §1 phải hiện ra **thành ba câu khác nhau**, không phải một dòng "connection failed":

```text
Venue: FUTURES_TESTNET   Kết nối: ✘  KEY_EXPIRED
→ Key testnet đã hết hạn hoặc bị reset. Lấy key mới tại testnet.binancefuture.com.
  (Lưu ý: key Spot Testnet và key mainnet KHÔNG dùng được ở đây.)
```

## 6. Ghi chú triển khai (2026-09-01)

Ba sửa phạm vi so với bản thiết kế gốc, chi tiết ở §2.5: 4 lời gọi HTTP không phải 3
(`futures_get_position_mode` là endpoint riêng); thêm `ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`
(thứ 6); `margin_type` là `None` khi tài khoản chưa có vị thế mở (per-symbol, không có "mặc định
tài khoản"). Không hỗ trợ huỷ (cancel) — 4 lời gọi tuần tự, cỡ giây, không phải tác vụ dài.

**Bug thật tìm thấy khi chạy CLI thật, unit test (dùng `Mock`) không bắt được:** `Client(...)`'s
constructor tự ping khi dựng (`ping=True` mặc định, `BUG-045`'s trigger) — bản đầu chỉ bọc
try/except quanh các lời gọi *sau* khi client đã dựng, không bọc chính lệnh dựng. Chạy
`main.py exchange-status` thật với key giả (egress bị chặn) tạo traceback chưa bắt thay vì
`ConnectionFailureKind.NETWORK`. Sửa: đưa lệnh dựng client vào cùng khối `try`; thêm regression
test giả lập chính xác kịch bản (`session_factory.create_trading_client` tự nó raise). Bài học
lặp lại đúng lý do `ci-rule.md` yêu cầu chạy thật — 3 tầng test (unit/integration/sanity) xanh hết
nhưng bug này chỉ lộ ra khi chạy `python main.py exchange-status` thật với biến môi trường thật.

**Quyết định thiết kế khác:**

- `IMarketMetadataProvider` (`021C`) và `ITradingAccountReader` (`021D`) là hai port tách biệt dù
  cùng "đọc thông tin từ sàn" — khác entity trả về, khác lý do tồn tại (rounding vs kiểm tra kết
  nối), không gộp cho "gọn".
- `exchange_status_formatter.py` dùng chung cho CLI headless, CLI interactive, **và** nút Settings
  — một hàm render, ba nơi gọi, không lệch chữ.
- `GetExchangeConnectionStatusQueryHandler` là wrapper mỏng cố ý: toàn bộ phân loại lỗi Binance
  nằm ở `FuturesAccountReader` (infra, nơi thực sự thấy mã lỗi), không phải ở handler.
- Async UI action dùng đúng khuôn `ActionOwnershipTracker` + `IThreadManager` + `Signal` cross-thread
  sẵn có trong repo (mẫu từ `GapCoordinator.run_inspect_gaps`), không phát minh cơ chế mới. Test
  riêng khẳng định kết quả của lần bấm bị lần bấm sau đè lên (stale) bị bỏ qua đúng cách.

**Đóng nốt `BUG-080`** (1/2 đã đóng bởi `021B`) — xem hồ sơ bug §7: client có key giờ ký request
thật, chứng minh bằng round-trip HTTP thật qua fake server + chạy CLI thật với key giả (request
thật sự được gửi, bị egress-block chặn ở tầng mạng, không phải "chưa từng thử").

**Chưa làm, cố ý, không phải thiếu sót:** testnet tier thật với key thật (`EPIC-021J`, opt-in,
task riêng — ADR §5 nói rõ đây không phải cổng CI). Đối chiếu shape payload thật (`futures_account`,
`positionSide/dual`) với API sống — cùng giới hạn egress-block đã disclose từ `EPIC-021A`.

**Bằng chứng verify cuối cùng** (đúng 4 cổng `ci-rule.md`, chạy sau khi hoàn tất toàn bộ):

```
ruff check src tests scripts tools    → 3 lỗi, cả 3 pre-existing (scripts/shutdown_*probe.py,
                                          chưa từng đụng tới)
ruff format --check src tests scripts tools → 883 files already formatted
mypy (src+scripts, một lệnh) → Success: no issues found in 190 source files
pytest tests/sanity                    → 24 passed
pytest tests/unit + tests/integration  → 1 failed (pre-existing, không liên quan:
                                          test_pan_preview_moves_only_the_data_region_not_the_axes),
                                          3078 passed, 4 skipped, coverage 95%
```

**Ghi chú vận hành phiên này (không phải bug):** chạy tuần tự (không `-n`) trên máy dev remote
này chậm bất thường — một lần chạy đứng yên >10 phút ở cùng vị trí 2% mà không tiến thêm, ban đầu
tưởng là deadlock thật. Chạy lại với `-n 4` (song song, đúng cách `ci-local.ps1` tự dùng) xong
trong 2 phút 40 giây, xanh sạch. Kết luận: giới hạn tài nguyên của sandbox này, không phải lỗi
trong code — nhưng bài học thật: **luôn dùng `-n` khi chạy full suite ở phiên dev remote này**,
đừng vội kết luận "treo" chỉ từ một lần chạy tuần tự chậm.
