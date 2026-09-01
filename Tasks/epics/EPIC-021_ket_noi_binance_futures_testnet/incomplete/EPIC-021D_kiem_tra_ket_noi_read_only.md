# EPIC-021D — Kiểm tra kết nối read-only: lần chạm sàn thật đầu tiên

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021A`, `EPIC-021B` · **Chặn:** `EPIC-021F`

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

### 2.4 Ba lời gọi, tất cả read-only

`futures_ping` (mạng) → `futures_time` (độ lệch đồng hồ) → `futures_account` (số dư, quyền,
position mode). Ba cái này đủ để phân loại cả 5 `ConnectionFailureKind`.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/exchange_connection_status.py` | **Mới** — VO + `ConnectionFailureKind`, `PositionMode`, `MarginType` (mỗi enum một file theo §5 nếu vượt ngưỡng) |
| `src/application/ports/i_trading_account_reader.py` | **Mới** — port **chỉ đọc**; `ITradingClient` (đặt lệnh) là `EPIC-021E`, cố ý chưa tồn tại |
| `src/infrastructure/binance/futures_account_reader.py` | **Mới** — implement bằng `futures_ping`/`futures_time`/`futures_account` |
| `src/application/use_cases/queries/get_exchange_connection_status/` | **Mới** — query + handler |
| `settings_view.py` / `settings_presenter.py` | Nút "Kiểm tra kết nối" + vùng kết quả; chạy trên worker, không khoá UI |
| `src/binance_bot_module.py` | Đăng ký reader + query handler |

## 4. Kiểm thử

- **Unit:** mỗi `ConnectionFailureKind` được suy ra đúng từ đúng loại lỗi/payload; độ lệch đồng hồ
  tính đúng dấu.
- **Unit:** `position_mode == HEDGE` → status là failure, không phải success kèm cảnh báo.
- **Integration:** qua fake server futures (`EPIC-021J`) — không chạm mạng, tất định.
- **Testnet tier (opt-in, `EPIC-021J`):** chạy thật với key thật, khẳng định `reachable` và
  `usdt_balance is not None`. Đây là **bằng chứng vận hành**, không phải cổng CI (ADR §5).
- **Async UI (`async-ui-action-rule.md`):** nút không khoá UI, huỷ được, và không phát tín hiệu
  unlock nếu chưa từng khoá (bẫy 7 ở `ONBOARDING.md` §8 — `BUG-018`).

## 5. Mốc chạy được

**Đây là mốc đầu tiên chạm sàn thật, và là mốc đầu tiên anh nhìn thấy tiền testnet của mình.**
Hai đường, cùng một query:

```bash
# Headless (VPS, không cần GUI) — command mới trong cli_commands.json + 1 handler
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py exchange-status
```

```text
Venue:            FUTURES_TESTNET          Kết nối: ✔
Lệch đồng hồ:     +134 ms                  (recvWindow 5000 ms → an toàn)
Position mode:    ONE_WAY ✔                Margin type: CROSSED
Số dư USDT:       15,000.00                Vị thế đang mở: 0
```

Và cùng thông tin đó trên nút **Kiểm tra kết nối** ở màn Settings.

Thêm CLI command ở repo này là **1 entry JSON + 1 handler + 1 dòng registry** — khuôn đã có sẵn
(`src/config/cli_commands.json`, `presentation/cli/handlers/`, `interactive_shell.py:46-47`),
không phải hạ tầng mới.

Ba nhóm lỗi ở §1 phải hiện ra **thành ba câu khác nhau**, không phải một dòng "connection failed":

```text
Venue: FUTURES_TESTNET   Kết nối: ✘  KEY_EXPIRED
→ Key testnet đã hết hạn hoặc bị reset. Lấy key mới tại testnet.binancefuture.com.
  (Lưu ý: key Spot Testnet và key mainnet KHÔNG dùng được ở đây.)
```
