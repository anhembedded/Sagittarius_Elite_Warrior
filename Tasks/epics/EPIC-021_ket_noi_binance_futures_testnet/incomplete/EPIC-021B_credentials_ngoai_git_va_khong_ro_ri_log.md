# EPIC-021B — Credentials: env-var trước, secret rời khỏi file git-tracked

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021A`
- **Đóng bug:** [`BUG-078`](../../../bug_report/incomplete/BUG-078_settings_api_credentials_never_reach_the_exchange_client.md)

---

## 1. Bối cảnh & vấn đề thật

Màn Settings có ô nhập API Key/Secret, có che ký tự (`setEchoMode(Password)`,
[`settings_view.py:345`](../../../../src/presentation/ui/screens/settings/settings_view.py)), và
lưu chúng khi bấm Lưu ([`settings_presenter.py:139-140`](../../../../src/presentation/ui/screens/settings/settings_presenter.py)).
**Không nơi nào đọc chúng ra để dựng client.** Giao diện đang hứa một khả năng mà hệ thống không
có — đó là `BUG-078`, và nó phải được đóng *trước* khi có bất kỳ đường đặt lệnh nào, vì task sau
sẽ tin rằng "nhập key ở Settings là đủ".

Vấn đề thứ hai, độc lập và nặng hơn: chỗ lưu là `src/config/user_config.json`, **file
git-tracked** (`git ls-files src/config/` xác nhận). Hiện nó rỗng, nên chưa có secret nào bị
commit — nhưng đây chính là code path sẽ giữ key mainnet sau này. Chính docstring của
[`config_manager_state_store.py`](../../../../src/presentation/ui/state/adapters/config_manager_state_store.py)
đã gọi tên vấn đề: *"It is git-tracked and holds `API_KEY`/`API_SECRET`"*.

## 2. Thiết kế + lý do

### 2.1 Thứ tự nguồn: env-var → file secret ngoài git → không có

```
src/application/ports/i_exchange_credentials_provider.py   # ABC
src/infrastructure/credentials/env_first_credentials_provider.py
```

Thứ tự này không tuỳ tiện: biến môi trường là cách duy nhất chạy được trong CI/VPS headless mà
không đặt secret lên đĩa, và nó **thắng** file để một máy đã cấu hình đúng không bị một file cũ
ghi đè ngầm.

Tên biến gắn với venue, không phải chung chung — vì Futures Testnet có **bộ key riêng**, không
dùng chung với Spot Testnet hay mainnet (ADR §5). Một tên `BINANCE_API_KEY` chung sẽ mời gọi
đúng cái nhầm lẫn đắt nhất:

```
BINANCE_FUTURES_TESTNET_API_KEY
BINANCE_FUTURES_TESTNET_API_SECRET
```

File dự phòng: `secrets.local.json` cạnh `user_config.json` nhưng **có trong `.gitignore`**.

### 2.2 `ExchangeCredentials` là value object, không phải hai chuỗi

```python
@dataclass(frozen=True)
class ExchangeCredentials:
    api_key: str
    api_secret: str
    def __repr__(self) -> str: ...   # che secret
    def __str__(self) -> str: ...    # che secret
```

Lý do `__repr__`/`__str__` bị override chứ không chỉ "nhớ đừng log": exception traceback,
`logger.debug(f"{obj}")`, và `pytest` assertion diff đều gọi `repr()` **tự động**. Một secret rò
ra log không rò vì ai đó cố tình log nó — nó rò vì một dataclass mặc định in hết field ra trong
một traceback không ai lường trước.

### 2.3 Settings screen: hiện trạng thái, không phải là nơi giữ secret

Ô nhập vẫn còn (user cần đường nhập lần đầu), nhưng:

- Ghi vào `secrets.local.json`, **không** vào `user_config.json`.
- Nếu key đã đến từ biến môi trường: ô hiển thị trạng thái *"Đang dùng key từ biến môi trường"*
  và **khoá ô nhập** — nếu không, user sẽ gõ một key khác và không hiểu vì sao nó bị bỏ qua.
- `API_KEY`/`API_SECRET` bị **xoá** khỏi `user_config.json` và khỏi mọi đường ghi.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/exchange_credentials.py` | **Mới** — VO frozen, `__repr__`/`__str__` che secret |
| `src/application/ports/i_exchange_credentials_provider.py` | **Mới** — port |
| `src/infrastructure/credentials/env_first_credentials_provider.py` | **Mới** — env → file → rỗng |
| `src/infrastructure/credentials/secrets_file_source.py` | **Mới** — đọc `secrets.local.json`, chịu được file thiếu/hỏng (khuôn `JsonSource` sẵn có) |
| `src/infrastructure/binance/exchange_session_factory.py` | Nhận credentials provider; market-data client ở `MAINNET_PUBLIC` **không** nhận key (ADR §2.1) |
| `settings_presenter.py` / `settings_view.py` / `settings_view_model.py` | Trạng thái nguồn key, khoá ô khi env thắng, bỏ ghi vào `user_config.json` |
| `src/config/user_config.json` | Xoá 2 key `API_KEY`/`API_SECRET` |
| `.gitignore` | Thêm `secrets.local.json` |

## 4. Kiểm thử

- **Unit:** thứ tự ưu tiên env > file > rỗng; file hỏng/thiếu → rỗng, không ném.
- **Unit (khoá rò rỉ):** `repr()`, `str()`, và `f"{creds}"` đều **không** chứa chuỗi secret; một
  exception chứa object này trong traceback cũng không. Mutation-verify: bỏ override `__repr__`
  → test phải đỏ.
- **Unit:** market-data client ở `MAINNET_PUBLIC` được dựng **không** kèm key.
- **Regression `BUG-078`:** viết **trước** khi sửa — dựng app với credentials giả, xác nhận
  trading client thật sự nhận đúng key đó. Phải đỏ trên code hiện tại vì hôm nay không có đường
  nào để key đi qua.
- **Guard:** `grep` toàn repo không còn nơi nào ghi secret vào file git-tracked.
