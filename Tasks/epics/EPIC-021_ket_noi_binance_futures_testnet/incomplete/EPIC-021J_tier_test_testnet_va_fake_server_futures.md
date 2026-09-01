# EPIC-021J — Tier `tests/testnet/` opt-in + fake server phục vụ endpoint futures

- **Trạng thái:** 🔴 Chưa bắt đầu
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
