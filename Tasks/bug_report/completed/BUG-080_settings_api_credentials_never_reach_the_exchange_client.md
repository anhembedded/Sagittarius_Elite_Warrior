# BUG-080 — API Key/Secret nhập ở màn Settings không bao giờ tới exchange client

- **Trạng thái:** ✅ Đã sửa
- **Mức độ:** 🟡 P3 (hạ từ P2 khi `EPIC-021B` sửa nửa nguy hiểm nhất; đóng hẳn ở `EPIC-021D`)
- **Ngày báo:** 2026-09-01
- **Ngày sửa hẳn:** 2026-09-01
- **Phát hiện khi:** khảo sát code để lập [`EPIC-021`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/README.md)
- **Sửa 1/2 bởi:** [`EPIC-021B`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021B_credentials_ngoai_git_va_khong_ro_ri_log.md) (§6) — **đóng hẳn bởi:** [`EPIC-021D`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/completed/EPIC-021D_kiem_tra_ket_noi_read_only.md) (§7)

---

## 1. Symptom

Màn Settings có ô **API Key** và **API Secret**, ô secret được che ký tự
(`setEchoMode(QLineEdit.EchoMode.Password)`,
[`settings_view.py:345`](../../../src/presentation/ui/screens/settings/settings_view.py)), và
bấm Lưu thì giá trị được ghi xuống config
([`settings_presenter.py:139-140`](../../../src/presentation/ui/screens/settings/settings_presenter.py)):

```python
self.config.set("API_KEY", view_model.apiKey)
self.config.set("API_SECRET", view_model.apiSecret)
```

Giao diện vì vậy hứa với người dùng rằng bot sẽ dùng key đó để nói chuyện với Binance.
**Nó không dùng.** Không có request nào của app từng được ký.

Đây là bug thuộc loại *code/UI phát biểu sai sự thật* — cùng loại với `sentinel.prompt.md` trỏ
vào một file rule chưa bao giờ tồn tại (`EPIC-011`): mọi thứ chạy, không có gì đỏ, và người đọc
tin vào một điều không đúng.

## 2. Root cause

`PythonBinanceClient` được đăng ký vào DI container **bằng chính lớp, không phải bằng một
factory** ([`binance_bot_module.py:231`](../../../src/binance_bot_module.py)):

```python
app.container.singleton(IExchangeClient, PythonBinanceClient)
```

Container dựng nó **không tham số**, nên ctor rơi vào toàn bộ giá trị mặc định
([`client.py:62-83`](../../../src/infrastructure/binance/client.py)):

```python
def __init__(self, api_key: str = "", api_secret: str = "", client: Client | None = None):
    self.client = client if client is not None else Client(api_key, api_secret, ...)
```

→ `Client("", "")`: một client ẩn danh. Đường websocket giống hệt —
`await AsyncClient.create()` không tham số
([`binance_websocket_service.py:110`](../../../src/infrastructure/binance/binance_websocket_service.py)).

Xác nhận không có nơi nào đọc key ra:

```bash
grep -rn "API_KEY\|API_SECRET" --include=*.py src/ | grep -v presentation
# → chỉ còn 1 dòng docstring trong config_manager_state_store.py, không có lời gọi nào
```

**Vì sao chưa ai nhận ra:** cả 3 endpoint mà app dùng hôm nay (`ping`, `exchangeInfo`, `klines`)
đều **public** — không cần key. Client ẩn danh chạy hoàn hảo cho mọi tính năng hiện có, nên
không có triệu chứng nào để mà điều tra. Bug chỉ lộ ra tại đúng thời điểm ai đó cần xác thực,
tức là bây giờ.

## 3. Vấn đề thứ hai đi kèm: nơi lưu là file git-tracked

`user_config.json` **có trong git** (`git ls-files src/config/` xác nhận). Hiện hai key rỗng nên
chưa secret nào bị commit — nhưng đây là code path sẽ giữ key thật. Chính docstring của
[`config_manager_state_store.py`](../../../src/presentation/ui/state/adapters/config_manager_state_store.py)
đã gọi tên nó: *"It is git-tracked and holds `API_KEY`/`API_SECRET`"* — biết mà chưa xử lý.

## 4. Fix (thuộc `EPIC-021B`)

`IExchangeCredentialsProvider` + `EnvFirstCredentialsProvider`: biến môi trường trước, file
`secrets.local.json` (**gitignored**) sau. Client được dựng qua
`IExchangeSessionFactory` (`EPIC-021A`) có nhận credentials. `API_KEY`/`API_SECRET` bị xoá khỏi
`user_config.json`. `ExchangeCredentials` che secret trong `__repr__`/`__str__` để không rò qua
traceback.

## 5. Regression test

Viết **trước** khi sửa, và phải xác nhận đỏ đúng lý do (không phải đỏ vì thiếu import):

- Dựng app với credentials giả qua provider → khẳng định trading client thật sự mang đúng key đó.
  Trên code hiện tại test này **không thể xanh**: không tồn tại đường nào để key đi từ config tới
  client.
- Test thứ hai, khác lớp: `grep`-guard khẳng định không nơi nào ghi secret vào file git-tracked.
  Test đầu chặn *bug này*; test sau chặn *lớp lỗi*.

## 6. Đã sửa 1 phần thế nào (`EPIC-021B`, 2026-09-01) — và vì sao chỉ 1 phần

**Sửa xong, thật sự đóng:** §3 — nơi lưu không còn là file git-tracked. `API_KEY`/`API_SECRET`
xoá khỏi `user_config.json`; `IExchangeCredentialsProvider` + `EnvFirstCredentialsProvider` +
`SecretsFileSource` ghi vào `secrets.local.json` (gitignored). Thứ tự ưu tiên env > file > rỗng.
`ExchangeCredentials` che secret trong `__repr__`/`__str__`/`f-string`/traceback. Settings hiện
đúng nguồn credentials đang thắng (`credentialsSourceLabel`) và **khoá ô nhập** khi biến môi
trường đang thắng — không còn cho user gõ một giá trị sẽ bị lờ đi trong im lặng.

**Chưa sửa xong, và lý do là kiến trúc chứ không phải thiếu thời gian:** §5's bản kế hoạch gốc
giả định `021B` xong thì có "trading client thật sự mang key" để test round-trip. Khi code thật,
phát hiện: credentials **theo `TradingVenue`**, không theo `MarketDataVenue` — trong tổ hợp
được khuyến khích ở ADR §2.2 (data = `MAINNET_PUBLIC`, trading = `FUTURES_TESTNET`), client có
key phải là một instance **hoàn toàn tách biệt** khỏi market-data client, độc lập với
`MarketDataVenue` đang chọn gì. Dựng instance đó là chính xác việc `EPIC-021A` đã cố tình cắt
ra khỏi phạm vi của mình (`create_trading_client()`, xem note tại `EPIC-021A` §2.2) — không có
`TradingVenue` resolution, không có config key `EXCHANGE_TRADING_VENUE`, và (đúng nhất) không có
gì thật sự tiêu thụ một client như vậy tồn tại trước `021D`. Dựng nó bây giờ, không ai gọi, sẽ
là chính lớp lỗi `BUG-081` vừa sửa — cấu hình/plumbing có mặt nhưng không ai đọc.

**Kết luận (tại thời điểm `021B`):** bug này còn đúng theo đúng nghĩa hẹp nhất của triệu chứng
gốc — "không có request nào của app từng được ký" **vẫn đúng** sau `021B`. Cái đã đổi là: (a) nửa
nguy hiểm hơn (secret git-tracked) đã hết, và (b) đường đi của key giờ thật, được test, chỉ còn
thiếu đầu nhận. Hạ mức độ P2→P3 vì phần còn lại không còn là "UI nói dối" — Settings giờ trung
thực về việc key đi đâu, chỉ là chưa có gì tiêu thụ nó.

## 7. Đóng hẳn thế nào (`EPIC-021D`, 2026-09-01)

`ExchangeSessionFactory.create_trading_client(credentials)` (mới) dựng `Client(api_key=...,
api_secret=..., testnet=True)` — client **có key**, luôn Futures Testnet. `FuturesAccountReader`
(mới, `ITradingAccountReader`) dùng client đó để gọi 4 endpoint đã ký:
`futures_ping`/`futures_time`/`futures_account`/`futures_get_position_mode`. Nút **Kiểm tra kết
nối** ở Settings và lệnh `main.py exchange-status` đều đi qua đúng đường này qua
`GetExchangeConnectionStatusQuery`.

**Bằng chứng key thật sự đi tới sàn** (không chỉ "đường tồn tại"): chạy `exchange-status` thật
với key giả đặt qua biến môi trường trong phiên dev remote này — request thật sự được gửi (và bị
egress-block của tầng chính sách chặn ở tầng mạng, phân loại đúng thành `NETWORK`, không phải
"never attempted"). Round-trip HTTP thật (không qua mạng, qua
`tests/sanity/binance_fake_server.py`) trong `test_futures_account_reader_against_fake_server.py`
chứng minh toàn bộ chuỗi ký + gửi + parse chạy đúng.

Triệu chứng gốc — "UI hứa key sẽ được dùng, nhưng không request nào từng được ký" — không còn
đúng. Đóng.
