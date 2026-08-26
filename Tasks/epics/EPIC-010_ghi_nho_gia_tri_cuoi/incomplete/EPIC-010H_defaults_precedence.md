# EPIC-010H — Thứ tự ưu tiên 3 tầng, và hệ quả bắt buộc của nó

**Status:** ✅ Done 2026-08-26 (cả hai phần) — Elite
**Repo:** **Elite**
**Depends on:** `EPIC-010F`

## Thứ tự đã chốt

```text
ui_state  >  user_config DEFAULT_*  >  module constants
```

Đây là thứ tự **đúng**: thứ người dùng vừa làm trên màn hình phải thắng thứ họ
khai một lần trong Settings. Nhưng nó kèm **một hệ quả bắt buộc**, và bỏ qua hệ
quả đó thì thứ tự này biến thành bug:

> Đổi `DEFAULT_*` trong Settings **phải xoá** giá trị đã nhớ mà nó vừa thua.

Không có bước đó, user sửa Settings, bấm Lưu, và **không thấy gì xảy ra** — giá
trị cũ (ưu tiên cao hơn) vẫn thắng.

## Vì sao cần verb mới `discard_keys()`

`discard()` xoá **cả slice**. Dùng nó để vô hiệu một symbol sẽ kéo theo
leverage, commission, timezone, checklist script — **tệ hơn hẳn** vấn đề nó
định sửa. Đó chính là lý do `EPIC-010F` phải giữ lại 2 field cuối.

`IStateStore.discard_keys(scope, keys)` xoá đúng những key được nêu. Cài ở cả 3
store; test chạy **parametrized trên 2 store thật** để verb không thể được cài
cho một cái rồi quên cái kia.

## Phạm vi: Settings chỉ sở hữu 2 key

`_STATE_KEYS_OWNED_BY_SETTINGS` chỉ liệt kê `backtest → (symbol, timeframe)`.

Dev Board và Database **vắng mặt có chủ đích**: hai màn đó không đọc
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` nào cả, nên Settings **không** ưu tiên cao
hơn thứ gì của chúng — không có gì để vô hiệu.

Xoá là **vô điều kiện**, không so với giá trị cũ: Lưu là hành động tường minh,
và "đảm bảo cái này không còn được nhớ" là idempotent, nên lưu lại một field
không đổi tốn đúng một lần ghi vô hại và **không cần** sổ sách trước/sau để
đúng.

## Mở khoá 2 field cuối của `010F`

`symbol` và `timeframe` giờ đã được lưu. Nhưng **validate bằng hình dạng, không
phải membership** — khác với `strategy` ngay cạnh: `symbolOptions` được
`_fetch_symbol_options()` nạp trên thread pool, nên lúc restore nó **còn rỗng**
và membership sẽ loại sạch mọi symbol, mọi lần khởi động. Cùng kết luận `010D`
đã đi tới, bằng con đường khác.

## Nửa hai: tầng giữa giờ mới thật sự tồn tại

**Đã làm.** Trước đó chỉ `BackTestPresenter` đọc
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`; Dev Board và Database **bỏ qua hoàn
toàn**. Nghĩa là sửa Settings đổi **1 trong 3 màn**, im lặng, không có gì báo
cho user biết 2 màn kia không nghe.

Thêm tầng "giá trị đã nhớ" lên trên nền đó mới ép phải xử: tầng giữa **không
thể có ý nghĩa** trên một màn không bao giờ hỏi tới nó.

`presentation/ui/common/app_defaults.py` giữ phần **đọc config**, không giữ
sàn. Mỗi hàm nhận `fallback` của chính người gọi.

### ⚠️ Tôi từng vi phạm chính luật mình đặt ra, và test bắt được

Bản đầu của module đó có **một sàn dùng chung** cho mọi màn. Nó lặng lẽ đổi
symbol khởi đầu của màn Database từ `BTCUSDT` sang `ETHUSDT`, và interval từ
`1s` sang `1m` — trong khi docstring của chính module ghi *"đổi **nơi** default
đến từ đâu, không đổi **giá trị** của nó trên máy chưa cấu hình"*.

Test của màn Database bắt được. Đã sửa thành sàn theo từng màn, và ghim bất
biến đó bằng test riêng để nó không quay lại.

### Thay đổi hành vi người dùng nhìn thấy

Với `user_config.json` thật (`DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]`), Dev
Board giờ mở ở **BTCUSDT** thay vì ETHUSDT. Đó là **đúng ý đồ** — Settings cuối
cùng cũng có tác dụng. Ảnh hưởng chỉ ở **lần mở đầu tiên sau khi nâng cấp**: từ
lần sau giá trị đã nhớ (`EPIC-010D`) thắng.

3 test integration hardcode `"ETHUSDT"` đã được sửa để **lấy symbol từ card
thật** — như vậy chúng kiểm đúng điều muốn kiểm ("tick của symbol đang nạp cập
nhật chart") thay vì "symbol tình cờ là ETHUSDT".

## Acceptance

- Lưu Settings → `symbol`/`timeframe` đã nhớ bị xoá
- Lưu Settings → mọi giá trị khác của slice backtest **còn nguyên**
- Lưu bị từ chối (symbol rỗng) → không xoá gì
- Không có coordinator → Settings vẫn chạy như cũ
