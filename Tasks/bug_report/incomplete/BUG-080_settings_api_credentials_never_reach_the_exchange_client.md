# BUG-080 — API Key/Secret nhập ở màn Settings không bao giờ tới exchange client

- **Trạng thái:** 🔴 Đang mở
- **Mức độ:** 🟠 P2 (chặn `EPIC-021`; chưa gây hại hôm nay vì app chưa cần xác thực)
- **Ngày báo:** 2026-09-01
- **Phát hiện khi:** khảo sát code để lập [`EPIC-021`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/README.md)
- **Sẽ đóng bởi:** [`EPIC-021B`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021B_credentials_ngoai_git_va_khong_ro_ri_log.md)

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
