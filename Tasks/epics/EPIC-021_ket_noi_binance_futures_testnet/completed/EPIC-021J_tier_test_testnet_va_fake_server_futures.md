# EPIC-021J — Tier `tests/testnet/` opt-in + fake server phục vụ endpoint futures

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021F` (chạy song song được với `G`–`I`)

---

## 1. Bối cảnh & vấn đề thật

Epic này tạo ra một loại bằng chứng mà repo chưa từng có: **chạy thật với sàn thật**. Nó không
vừa vào bất kỳ tầng nào trong 4 tầng hiện có, và nhét bừa vào một tầng sẵn có sẽ phá đúng thứ
tầng đó tồn tại để bảo vệ:

- `testing-rule.md` §1 quy định Integration **không bao giờ** phụ thuộc sàn công khai hay tài
  khoản sống.
- `EPIC-009`'s ADR quy định thay thế chỉ được đặt ở **ranh giới mạng, tại cấu hình** — chính là
  lý do `binance_fake_server.py` tồn tại thay vì một `IExchangeClient` viết tay (hình dạng đã sinh
  ra `BUG-026`/`BUG-027`).

Nếu để test testnet lọt vào `ci-local.ps1 -Full`, cổng CI sẽ đỏ mỗi lần key hết hạn hoặc mạng
chập — và đỏ vì lý do không liên quan tới thay đổi của người chạy là cách nhanh nhất khiến người
ta học cách bỏ qua cổng.

Vấn đề thứ hai: `binance_fake_server.py` hiện chỉ phục vụ **3 endpoint spot**
(`/api/v3/ping`, `/api/v3/exchangeInfo`, `/api/v3/klines`) — có ghi rõ trong docstring rằng mọi
path khác trả 404 **cố ý**. Không mở rộng nó thì mọi test integration của `EPIC-021D`–`I` không có
gì để chạy.

## 2. Thiết kế + lý do

### 2.1 Mở rộng fake server: futures, không phải mock

Thêm đúng những endpoint mà epic này thật sự gọi — verify bằng cách đọc adapter, không đoán:

```
GET  /fapi/v1/ping
GET  /fapi/v1/time
GET  /fapi/v1/exchangeInfo
GET  /fapi/v1/klines
POST /fapi/v1/order/test
POST /fapi/v1/order
DELETE /fapi/v1/order  ·  DELETE /fapi/v1/allOpenOrders
GET  /fapi/v1/openOrders
GET  /fapi/v2/account  ·  GET  /fapi/v2/positionRisk
POST /fapi/v1/listenKey  ·  PUT /fapi/v1/listenKey
```

Giữ nguyên hai nguyên tắc của bản gốc: **path lạ trả 404**, không phải một success rỗng trông có
vẻ hợp lý; và **response tất định**, không sinh dữ liệu phụ thuộc thời gian hay ngẫu nhiên.

Điểm mới so với bản spot: server này phải giữ **state tối thiểu** (lệnh đã đặt → xuất hiện trong
`openOrders`; huỷ → biến mất), vì vòng đời lệnh là chính thứ cần kiểm. Giữ state ở mức nhỏ nhất
đủ dùng — một fake mô phỏng cả matching engine sẽ trở thành thứ thứ hai phải bảo trì và tự nó sẽ
có bug.

### 2.2 File tách theo abstraction, không phình file cũ

`binance_fake_server.py` hiện là một handler phẳng. Thêm 12 endpoint có state vào đó sẽ vượt
ngưỡng 400 dòng (`architecture-rule.md` §5.4). Tách:

```
tests/sanity/fake_exchange/spot_routes.py
tests/sanity/fake_exchange/futures_routes.py
tests/sanity/fake_exchange/order_book_state.py
tests/sanity/fake_exchange/server.py           # dựng + chạy, giữ contextmanager API cũ
```

API `run_binance_fake_server()` **giữ nguyên chữ ký** để `tests/sanity/conftest.py` không phải
đổi cùng lúc với `EPIC-021A`.

### 2.3 Tier `tests/testnet/`: opt-in, hai lớp cổng

```
tests/testnet/{conftest.py,test_connection.py,test_order_lifecycle.py}
```

Chỉ chạy khi **cả hai** điều kiện đúng: biến `SEW_TESTNET_TESTS=1` **và** credentials tồn tại.
Thiếu một trong hai → `pytest.skip` với lý do đọc được, không phải đỏ.

Lớp cổng thứ hai nằm ở `ci-local.ps1`: thư mục này bị loại khỏi mọi mode, kể cả `-Full`. Thêm một
switch `-TestnetOnly` riêng để chạy có chủ đích.

**Hai lớp vì một lớp đã từng không đủ:** một thư mục chỉ dựa vào skip điều kiện sẽ chạy thật ngay
khi ai đó tình cờ có biến môi trường đó trong shell.

### 2.4 Kỷ luật của test chạm sàn thật

- Khối lượng **tối thiểu** cho phép, và luôn dọn dẹp trong `finally` (huỷ lệnh, đóng vị thế) —
  một test bỏ lại vị thế mở làm hỏng mọi lần chạy sau.
- Chờ bằng **điều kiện có tên** (trạng thái lệnh từ User Data Stream), không bằng `sleep`
  (`testing-rule.md` §2).
- Không assert giá/số dư cụ thể — testnet là môi trường chung, số liệu trôi. Assert **bất biến**:
  lệnh đạt `FILLED`, vị thế đóng lại về 0, số lệnh khớp đúng bằng số lệnh gửi.
- Ghi log ra file rồi grep, không `| tail` (`ONBOARDING.md` §5).

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `tests/sanity/fake_exchange/` | **Mới** — tách 4 file từ `binance_fake_server.py`, thêm route futures |
| `tests/sanity/binance_fake_server.py` | Thu về một shim tái xuất `run_binance_fake_server` (giữ import cũ chạy) |
| `tests/testnet/` | **Mới** — conftest với 2 lớp cổng + 2 file test |
| `scripts/ci-local.ps1` | Loại `tests/testnet/` khỏi mọi mode; thêm `-TestnetOnly` |
| `.agents/rules/ci-rule.md` | Ghi tier mới vào bảng §2, nói rõ nó **không** thay thế được `-Full` |
| `.agents/rules/testing-rule.md` | Bổ sung mục "tier testnet là bằng chứng vận hành, không phải tầng test thứ năm" |

## 4. Kiểm thử

- **Verify hai chiều cho fake server:** mọi endpoint mới trả đúng shape (test dùng chính adapter
  thật), **và** path lạ vẫn 404 — nếu 404 mất, một lời gọi sai sẽ im lặng thành công.
- **Unit:** state lệnh của fake server đúng vòng đời (đặt → openOrders có → huỷ → không còn).
- **Sanity:** tier hiện tại vẫn xanh và vẫn im lặng sau khi tách file — bằng chứng việc tách
  không đổi hành vi.
- **Cổng:** `ci-local.ps1 -Full` **không** chạy file nào trong `tests/testnet/` (khẳng định bằng
  đếm test collect, không bằng đọc script).
- **Skip đúng lý do:** thiếu biến môi trường → skip; có biến nhưng thiếu key → skip với thông báo
  khác. Hai lý do khác nhau phải phân biệt được, nếu không người chạy sẽ không biết mình thiếu gì.

## 5. Mốc chạy được

```bash
# Cổng thường — PHẢI không chạy file nào trong tests/testnet/
pwsh -NoProfile -File scripts/ci-local.ps1 -Full   > /tmp/full.log 2>&1
grep -E "^[0-9]+ (passed|failed)|failed,|testnet" /tmp/full.log

# Tier mới, chạy có chủ đích, cần key thật
SEW_TESTNET_TESTS=1 pwsh -NoProfile -File scripts/ci-local.ps1 -TestnetOnly > /tmp/tnet.log 2>&1
```

```text
tests/testnet/test_connection.py::test_account_is_reachable            PASSED
tests/testnet/test_order_lifecycle.py::test_dry_run_is_accepted        PASSED
tests/testnet/test_order_lifecycle.py::test_market_order_fills_and_closes PASSED
3 passed in 11.42s
```

Và khi thiếu điều kiện, phải **skip với lý do đọc được**, không phải đỏ:

```text
SKIPPED [1] thiếu SEW_TESTNET_TESTS=1 — tier này không chạy trong CI thường
SKIPPED [2] có SEW_TESTNET_TESTS=1 nhưng không tìm thấy credentials Futures Testnet
```

Hai lý do skip khác nhau là cố ý: gộp làm một thì người chạy không biết mình đang thiếu **cái gì**.

Ghi log ra file rồi `grep`, không `| tail` — `ONBOARDING.md` §5.

## 6. Ghi chú triển khai

### 6.1 `/fapi/v3/positionRisk`, không phải `/fapi/v2` — đọc adapter, không đoán

Task's §2.1 liệt `GET /fapi/v2/positionRisk`. Đọc thẳng `python-binance`'s `client.py`
(`futures_position_information()` → `self._request_futures_api("get", "positionRisk", True, 3,
...)`) cho thấy adapter thật của app đang gọi **version 3**, không phải 2 — `FuturesTradingClient.
get_positions()` (`EPIC-021G`) đi qua đúng hàm này. Route được viết đúng theo adapter thật
(`/fapi/v3/positionRisk`), không theo bản nháp của task file. Ghi rõ trong docstring
`futures_routes.py` để không ai đọc lại nghĩ đây là lỗi gõ nhầm.

### 6.2 State: chỉ vòng đời lệnh, cố ý không mô phỏng khớp lệnh/vị thế

Đúng §2.1's chủ đích: `OrderBookState` chỉ theo dõi *đặt → mở → huỷ*. `GET /fapi/v3/positionRisk`
luôn trả `[]` cố định — đặt lệnh **không** tạo ra vị thế trong fake server này. Test riêng
(`test_positions_are_always_flat_no_matching_engine`) khẳng định tường minh đây là chủ ý, không
phải thiếu sót: một fake mô phỏng cả matching engine sẽ tự nó có bug cần bảo trì.

### 6.3 Tách file: 5 module thay vì 4 — thêm `__init__.py`

Bảng §3 liệt 4 file trong `fake_exchange/`. Vì `tests/sanity/` **không** có `__init__.py` (không
phải package thật, mọi nơi import nó qua `sys.path.insert` + import phẳng), gói con `fake_exchange/`
cần `__init__.py` riêng để `import fake_exchange.server` resolve được — nếu không mỗi lần import sẽ
`ModuleNotFoundError`. `binance_fake_server.py` giờ chỉ còn 33 dòng, một shim tái xuất, giữ nguyên
chữ ký cho 4 call site sẵn có (`tests/sanity/conftest.py` + 3 test integration + 1 probe script) —
không call site nào phải sửa.

### 6.4 Guard hai chiều thật, không chỉ đọc code

`tests/unit/fake_exchange/test_futures_routes_http.py` gọi thẳng HTTP (`requests`, bỏ qua
`python-binance`) để chứng minh: mọi route mới trả đúng shape, path lạ vẫn 404 (`test_unknown_path_
404s_on_every_verb`), và huỷ một lệnh không tồn tại trả đúng shape lỗi thật của Binance
(`{"code": -2011, "msg": "Unknown order sent."}`, status 400). `tests/unit/fake_exchange/
test_order_book_state.py` kiểm state thuần, không HTTP. Thêm một test integration mới
(`test_futures_trading_client_order_lifecycle_against_fake_server.py`) đóng một lỗ hổng coverage có
sẵn từ trước task này: `FuturesTradingClient.place_order()`'s nhánh `OrderSubmissionMode.LIVE`
(`else: client.futures_create_order(**params)`) **chưa từng** được test ở đâu trong repo — guard AST
`OrderSubmissionMode.LIVE` chỉ quét `src/`+`scripts/`, không quét `tests/`, nên test này hợp lệ và
an toàn (không chạm mạng thật, chỉ chạm fake server).

### 6.5 `tests/testnet/` viết được, verify được cơ chế gate — không verify được bằng chạy thật

Sandbox này chặn toàn bộ egress `*.binance.*`, nên `test_account_is_reachable`/`test_dry_run_is_
accepted`/`test_market_order_fills_and_closes` **không thể** chạy thật ở đây — như mọi lần chạm
mạng thật trước đó trong epic này (`BUG-080`, `EPIC-021D`). Đã verify được phần cơ chế: cả hai
lý do skip (thiếu biến môi trường / có biến nhưng thiếu credentials) tạo đúng thông báo phân biệt
được, khớp chữ y hệt mốc §5 của task; `--collect-only` xác nhận `ci-local.ps1 -Full`'s args
(`--ignore=.../tests/sanity --ignore=.../tests/testnet`) loại `tests/testnet/` hoàn toàn (0 test
collect được), trong khi target trực tiếp `tests/testnet` vẫn thấy đúng 3 test — đúng yêu cầu §4
"khẳng định bằng đếm test collect, không bằng đọc script". `test_market_order_fills_and_closes`
chờ bằng poll `get_positions()` (điều kiện có tên, bounded, không `sleep` mù) thay vì tự dựng
`FuturesUserDataStream` async bên trong một test đồng bộ — một thu hẹp phạm vi có chủ đích so với
câu chữ "trạng thái lệnh từ User Data Stream" của §4: `get_positions()` REST vẫn là cùng nguồn sự
thật (`ADR §4`) mà stream cuối cùng cũng đọc lại, và dựng đúng vòng đời async/thread bên trong
pytest chỉ để chờ cùng một sự thật đó là rủi ro không cần thiết cho lợi ích tương đương.

### 6.6 `ci-local.ps1` không tự chạy được ở đây — sửa mù chữ, verify bằng `--collect-only`

Sandbox này không có `pwsh`. Không thể tự chạy `ci-local.ps1 -TestnetOnly` hay `-Full` để xác nhận
trực tiếp; đã đọc kỹ toàn bộ script trước khi sửa (không đoán cấu trúc), thêm `-TestnetOnly` theo
đúng khuôn `-SanityOnly` đã có, và verify logic bằng cách tái tạo chính xác lệnh `pytest` mà mỗi
nhánh của script gọi (cùng `--ignore` list, cùng target) rồi chạy trực tiếp — kết quả khớp §6.5.

### 6.7 Kết quả kiểm thử

- Fake server tách file: 31/31 test sẵn có (sanity + integration đang dùng fake server) vẫn xanh
  sau khi tách — bằng chứng tách không đổi hành vi.
- Test mới: `test_order_book_state.py` 8/8, `test_futures_routes_http.py` 7/7,
  `test_futures_trading_client_order_lifecycle_against_fake_server.py` 3/3 — 18/18.
- Ruff (`src tests scripts tools`): 0 lỗi ngoài 3 lỗi baseline đã biết (không đụng — một lần vô ý
  chạy `ruff --fix` quét cả `scripts/` đã tự sửa 2 file baseline, phát hiện qua `git status` và
  `git checkout --` khôi phục ngay trước khi verify tiếp).
- `ruff format --check`: sạch.
- Mypy (từ `/home/user`): 0 lỗi, 231 file — không đổi vì task này không chạm `src/`.
- `tests/sanity`: 24/24, không đổi.
- Full suite (`tests` trừ `sanity`+`testnet`, `-n 4`, offscreen): 3312 passed, 4 skipped, 1 failed —
  `test_pan_preview_moves_only_the_data_region_not_the_axes`, đã root-cause và sửa ở [`BUG-083`](../../../bug_report/completed/BUG-083_pan_preview_test_drags_past_its_own_reanchor_boundary.md);
  4 skip đã đối chiếu là pre-existing, không phát sinh từ task này (`tests/testnet` bị `--ignore`
  hoàn toàn, không góp phần vào số skip đó).
