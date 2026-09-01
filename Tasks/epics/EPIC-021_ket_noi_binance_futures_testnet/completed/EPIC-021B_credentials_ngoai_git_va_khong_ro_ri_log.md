# EPIC-021B — Credentials: env-var trước, secret rời khỏi file git-tracked

- **Trạng thái:** ✅ Xong
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021A`
- **Đóng 1/2 bug:** [`BUG-080`](../../../bug_report/incomplete/BUG-080_settings_api_credentials_never_reach_the_exchange_client.md) — nửa còn lại đóng ở `021D`/`021F`, xem §2.4

---

## 1. Bối cảnh & vấn đề thật

Màn Settings có ô nhập API Key/Secret, có che ký tự (`setEchoMode(Password)`,
[`settings_view.py:345`](../../../../src/presentation/ui/screens/settings/settings_view.py)), và
lưu chúng khi bấm Lưu ([`settings_presenter.py:139-140`](../../../../src/presentation/ui/screens/settings/settings_presenter.py)).
**Không nơi nào đọc chúng ra để dựng client.** Giao diện đang hứa một khả năng mà hệ thống không
có — đó là `BUG-080`, và nó phải được đóng *trước* khi có bất kỳ đường đặt lệnh nào, vì task sau
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

### 2.4 Sửa phạm vi, phát hiện lúc code thật (2026-09-01): `ExchangeSessionFactory` KHÔNG đổi

Bản thiết kế gốc ở §3 (bảng dưới, bản cũ) định cho `exchange_session_factory.py` "nhận credentials
provider" để dựng một client có key. Khi bắt tay vào code, phát hiện: credentials là chuyện của
**`TradingVenue`**, không phải `MarketDataVenue` — trong tổ hợp ADR §2.2 khuyến khích (data =
`MAINNET_PUBLIC`, trading = `FUTURES_TESTNET`), client có key phải là **một instance hoàn toàn
tách biệt**, độc lập với `MarketDataVenue` đang chọn gì. Dựng instance đó đúng là
`create_trading_client()` mà `EPIC-021A` đã cố tình cắt khỏi phạm vi của chính nó (xem note ở
`EPIC-021A` §2.2) — vì chưa có `TradingVenue` resolution, chưa có config key
`EXCHANGE_TRADING_VENUE`, và quan trọng nhất: **chưa có gì tiêu thụ một client như vậy**.

Dựng nó bây giờ, không ai gọi, sẽ là chính lớp lỗi `BUG-081` vừa đóng — cấu hình/plumbing có mặt
nhưng không có consumer thật. `021B` vì vậy dừng đúng ở phần tự đứng được và đã có consumer thật
ngay hôm nay: `SettingsPresenter` tiêu thụ `IExchangeCredentialsProvider.resolve()` để hiện đúng
trạng thái/khoá ô. Việc dựng client có key dời sang `EPIC-021D` ("lần chạm sàn thật đầu tiên" —
đúng nơi cần nó đầu tiên) hoặc `021F`. Hệ quả: `BUG-080` chỉ đóng **một nửa** ở task này — xem
hồ sơ bug §6.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/exchange_credentials.py` | **Mới** — VO frozen, `__repr__`/`__str__` che secret |
| `src/application/ports/i_exchange_credentials_provider.py` | **Mới** — port (`CredentialsSource`, `ResolvedCredentials`, `IExchangeCredentialsProvider`) |
| `src/infrastructure/credentials/env_first_credentials_provider.py` | **Mới** — env → file → rỗng |
| `src/infrastructure/credentials/secrets_file_source.py` | **Mới** — đọc/ghi `secrets.local.json`, chịu được file thiếu/hỏng (khuôn `JsonSource` sẵn có) |
| `src/infrastructure/binance/exchange_session_factory.py` | **Không đổi** — xem §2.4 |
| `settings_presenter.py` / `settings_view.py` / `settings_view_model.py` | Trạng thái nguồn key (`credentialsSourceLabel`/`credentialsLocked`), khoá ô khi env thắng, bỏ ghi vào `user_config.json` |
| `src/config/user_config.json` | Xoá 2 key `API_KEY`/`API_SECRET` |
| `src/binance_bot_module.py` | Đăng ký `IExchangeCredentialsProvider` (DI) |
| `.gitignore` | Thêm `src/config/secrets.local.json` |

## 4. Kiểm thử

- **Unit:** thứ tự ưu tiên env > file > rỗng; file hỏng/thiếu → rỗng, không ném; cặp env chỉ có
  1 nửa (thiếu secret) → rơi xuống file, không "nửa resolve".
- **Unit (khoá rò rỉ):** `repr()`, `str()`, và `f"{creds}"` đều **không** chứa chuỗi secret; một
  exception chứa object này trong traceback cũng không. Mutation-verify: một `@dataclass` KHÔNG
  override `__repr__` (song song, không sửa class thật) chứng minh secret **có** lộ nếu thiếu
  override — test không vô nghĩa (vacuously passing).
- **Regression `BUG-080` (nửa đóng được ở task này):** `user_config.json` không còn 2 key; không
  còn file nào trong `src/` gọi `IConfig.set("API_KEY"/"API_SECRET", ...)`. Nửa còn lại ("client
  thật sự ký request") đóng ở `021D`/`021F` — xem §2.4.
- **Sanity:** tier vẫn xanh sau khi đăng ký `IExchangeCredentialsProvider` vào DI thật.
- **Guard:** `grep`/scan toàn `src/` không còn nơi nào ghi secret vào file git-tracked.

## 5. Mốc chạy được

`scripts/epic021b_credentials_probe.py` — in ra **nguồn** credentials đang thắng và key đã che.
Chạy được cả khi chưa có key (đó cũng là một kết quả hợp lệ):

```bash
PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
    Sagittarius_Elite_Warrior/scripts/epic021b_credentials_probe.py
```

Chạy thật, chưa cấu hình gì (2026-09-01, phiên dev remote này):

```text
Nguồn: NONE
Key:    (chưa cấu hình) — lấy key ở testnet.binancefuture.com, rồi export BINANCE_FUTURES_TESTNET_API_KEY hoặc lưu qua màn Settings.
```

Thoát 0 — chưa có key không phải lỗi ở mốc này. Chạy thật lần hai, với `BINANCE_FUTURES_TESTNET_API_KEY`/
`_API_SECRET` đặt tạm qua biến môi trường:

```text
Nguồn: ENV (BINANCE_FUTURES_TESTNET_API_KEY)
repr(ExchangeCredentials) → ExchangeCredentials(api_key='Bx7f…9dQ2', api_secret='***')
Kiểm rò rỉ: repr ✔ str ✔ f-string ✔ traceback ✔
```

Dòng "Kiểm rò rỉ" là bản chạy tay của chính test khoá ở §4: nó cố tình đưa object vào 4 đường mà
secret hay rò ra, và in kết quả từng đường.

## 6. Ghi chú triển khai (2026-09-01)

**Sửa phạm vi so với bản thiết kế gốc:** §2.4 — `exchange_session_factory.py` không đổi;
`create_trading_client()` dời sang `021D`/`021F` cùng lý do `EPIC-021A` đã tự cắt scope của nó.

**Phát hiện thật khi code, ngoài phần đã biết trước:**

- `unprotected_mutators()` (guard `BOT-068`, chạy trong sanity tier) bắt được
  `SettingsViewModel.set_credentials_source` thiếu `@Slot` — cùng lớp lỗi `BUG-001`: một mutator
  `set_*` không được bảo vệ, gọi được trực tiếp từ thread nền. Sửa bằng `@Slot(str, bool)`, khớp
  `set_status` cùng file. Bắt được ngay ở lần chạy sanity đầu tiên sau khi thêm property mới —
  đúng lý do tier này tồn tại.
- `ruff` gắn `S105` (hardcoded-password) lên **assignment** `NAME = "chuỗi"` khi `NAME` khớp mẫu
  tên bí mật (`ENV_API_SECRET`, `_API_SECRET_FIELD`, dữ liệu test `_API_SECRET`) và lên **so
  sánh** `obj.api_secret == "chuỗi"` — false positive thật (tên biến môi trường, tên field JSON,
  dữ liệu test), không phải secret thật; xử lý bằng `# noqa: S105` kèm lý do tại chỗ, không tắt
  rule toàn cục.
- `ruff check --fix` chạy trên toàn `src tests scripts tools` tiện tay sửa luôn 2 lỗi
  import-order pre-existing ở `scripts/shutdown_*probe.py` (baseline biết trước, không thuộc
  phạm vi task này) — revert lại bằng `git checkout --` để giữ commit atomic, đúng
  `commit-rule.md` §4.

**Quyết định khó nhất — retarget `BUG-080` thay vì đóng nó:** bản kế hoạch gốc của task này
(§5's phiên bản trước) giả định xong `021B` là có "trading client mang key" để test. Khi hiểu ra
credentials theo `TradingVenue` (độc lập `MarketDataVenue`, xem §2.4), việc dựng client có key
đúng ra thuộc `021D`. Quyết định: không tự ép một thiết kế cho có để khớp task text cũ, không
dựng wiring chết — sửa hồ sơ `BUG-080` để phản ánh đúng những gì task này thật sự đóng được
(nửa lưu trữ an toàn) và những gì còn lại thật sự cần task nào (`021D`/`021F`). Chi tiết đầy đủ
ở hồ sơ bug §6.

**Bằng chứng verify cuối cùng** (đúng 4 cổng `ci-rule.md`, chạy sau khi hoàn tất toàn bộ):

```
ruff check src tests scripts tools    → 3 lỗi, cả 3 pre-existing (scripts/shutdown_*probe.py,
                                          chưa từng đụng tới)
ruff format --check src tests scripts tools → 855 files already formatted
mypy (src+scripts, một lệnh, đúng flag ci-local.ps1 dùng) → Success: no issues found in
                                          175 source files
pytest tests/sanity                    → 24 passed
pytest tests/unit + tests/integration  → 1 failed (pre-existing, không liên quan:
                                          test_pan_preview_moves_only_the_data_region_not_the_axes),
                                          2995 passed, 4 skipped, coverage 95%
```
