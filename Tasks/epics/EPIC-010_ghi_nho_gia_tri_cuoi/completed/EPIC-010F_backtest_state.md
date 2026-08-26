# EPIC-010F — Backtest: toàn bộ form cấu hình

**Status:** ✅ Done 2026-08-26 — Elite
**Repo:** **Elite**
**Depends on:** `EPIC-010B`, và kinh nghiệm từ `010D`/`010E`

## Vì sao task này được hoãn tới lượt cuối

README của epic: *"Deliberately gated on evaluating `010A`–`010E` in real use.
Every value needs its own validation, so the cost of getting the mechanism wrong
is highest here."* Màn này có **58 `Property`** — nhiều gấp bội hai màn trước
cộng lại.

## Phân loại: lưu **ý định**, không lưu **hoạt động**

Nguyên tắc từ design doc đầu tiên. 58 Property không phải 58 giá trị cần lưu.

### Lưu (19) — thứ người dùng tự đặt

| Key | Property | Kiểu | Validate |
| :--- | :--- | :--- | :--- |
| `strategy` | `selectedStrategyKey` | str | có trong `strategyOptions` |
| `capital` | `initialCapitalText` | str | chuỗi ngắn |
| `currency` | `selectedCurrency` | str | `Currency` |
| `execution_mode` | `executionMode` | str | `BacktestExecutionMode` |
| `order_size_type` | `orderSizeType` | str | `PositionSizingType` |
| `order_size` | `orderSizeText` | str | chuỗi ngắn |
| `pyramiding` | `pyramiding` | int | 1..1000 |
| `commission_type` | `commissionType` | str | `CommissionType` |
| `commission` | `commissionText` | str | chuỗi ngắn |
| `slippage_ticks` | `slippageTicks` | int | 0..10000 |
| `long_leverage` | `longLeverage` | float | 0..1000 |
| `short_leverage` | `shortLeverage` | float | 0..1000 |
| `take_profit_enabled` | `takeProfitPctEnabled` | bool | bool |
| `take_profit_pct` | `takeProfitPctText` | str | chuỗi ngắn |
| `time_range_preset` | `timeRangePreset` | str | `TimeRangePreset` |
| `custom_start` | `customStartText` | str | chuỗi ngắn |
| `custom_end` | `customEndText` | str | chuỗi ngắn |
| `timezone` | `displayTimezone` | str | có trong `displayTimezoneOptions` |
| `extended_metrics` | `showExtendedMetrics` | bool | bool |

Lưu bản `*Text` chứ không phải `*Value` với order size/commission: setter của
`orderSizeText` cập nhật luôn `_order_size_value` (dòng 581-587), nên khôi phục
một cái là đủ cho cả hai. Lưu cả hai sẽ tạo hai nguồn sự thật có thể lệch nhau.

### Không lưu — output / trạng thái phái sinh

`resultText`, `resultIsError`, `resultWarningText`, `lastRunSummary`,
`configDiffSummary`, `capitalValidationMessage`, `botParamsError`,
`botParamsSchema`, `botParamsRows`, `marketRuleVerificationStatus`,
`marketRuleExplanation`, `dataCoverageMessage`, `isDataFullyCovered`,
`needsDataSync`, `isChartPreview`, mọi `*Progress*`, `strategyOptions`,
`symbolOptions`, `selectedStrategyName`, `selectedTimeRangePresetLabel`,
`displayTimezoneLabel`, `logModel`, `scriptModel`.

### Không lưu — thuộc phiên làm việc, không phải cấu hình

`tradeLogCurrentPage`, `tradeLogFilter`, `tradeLogSearchText`,
`tradeLogTotalCount`, `tradeLogTotalPages`, `activeBottomTab`. Đây là cách người
dùng **xem một kết quả cụ thể**; kết quả đó không sống qua restart, nên vị trí
xem nó cũng không nên.

## 🚧 Cố ý **không** lưu `selectedSymbol` và `selectedTimeframe`

Đây là quyết định thu hẹp phạm vi, ghi lại để không ai tưởng là bỏ sót.

`BackTestPresenter` là **màn duy nhất** đọc `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`
từ config (dòng 327-329) — Dev Board và Database bỏ qua hoàn toàn. Nên đúng hai
giá trị này là chỗ **duy nhất** trong app mà thứ tự ưu tiên ba tầng thật sự phát
sinh:

```text
ui_state  >  user_config DEFAULT_*  >  module constants
```

Design §7 có đề xuất thứ tự đó, kèm **hệ quả bắt buộc**: đổi giá trị trong
Settings thì **phải xoá key tương ứng khỏi `ui_state`**, nếu không người dùng
đổi Settings mà không thấy gì xảy ra.

Hệ quả đó chưa làm được sạch ở đây: `IStateStore.discard()` xoá **cả slice**,
không xoá được một key. Đổi `DEFAULT_SYMBOLS` mà xoá luôn cả slice backtest sẽ
mất luôn leverage, commission, timezone… — tệ hơn hẳn vấn đề nó định sửa.

Vậy nên: 17/19 giá trị Settings **không** sở hữu thì lưu ngay; hai giá trị
Settings sở hữu giữ nguyên Settings làm nguồn sự thật cho tới khi `010H` định
nghĩa xong thứ tự ưu tiên **và** cấp cho store một cách xoá theo key.

## Restore không được gây hiệu ứng phụ (mode #12)

Như `010D`/`010E`: ghi **ViewModel**, không ghi widget. Mở màn hình phải chỉ
điền sẵn form — **không** chạy backtest, không sync, không fetch.

## Acceptance

- Đặt 19 giá trị, thoát, mở lại → tất cả trở lại
- Restore **không** gọi `dispatch` nào
- Giá trị hỏng/lạ ở bất kỳ trường nào → riêng trường đó fallback, các trường
  khác vẫn khôi phục
- `selectedSymbol`/`selectedTimeframe` **vẫn theo Settings**, không bị ghi đè

## Ghi nhận khi làm

Test round-trip (`test_every_declared_field_round_trips`) — kiểm rằng mọi giá
trị `capture_state()` ghi ra đều qua nổi validator của chính nó — **bắt được 2
lỗi thật** trong bảng khai báo trước khi kịp commit:

1. `strategyOptions` là list các **dict** `{"key": ..., "name": ...}`
   (`backtest_presenter.py:471`), không phải list chuỗi. So sánh chuỗi với list
   dict luôn sai → strategy sẽ **không bao giờ** khôi phục được.
2. `displayTimezoneOptions` khoá id bằng `"id"`, trong khi
   `timeRangePresetOptions` dùng `"value"` — **hai hình dạng khác nhau cho cùng
   một loại danh sách**. Đó là lý do mỗi dòng trong bảng tự khai khoá của nó
   thay vì bảng giả định một quy ước chung.

Cả hai đều là loại lỗi "im lặng": không exception, không log, chỉ là giá trị
lặng lẽ không bao giờ khôi phục. Không có test này thì sẽ lọt.
