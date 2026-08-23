# BUG-038 — Fallback sang Python vứt luôn nội dung mà nó fallback vì nó (nền trend zone không bao giờ được vẽ)

**Reported:** 2026-08-23 — **user phát hiện bằng mắt**, không phải bằng test:
*"khong co background"* kèm ảnh chụp màn Backtest chạy
`long_term_trend_zone` — nến, volume, 4 đường EMA đều có, **nền xanh/đỏ hoàn
toàn không có**.
**Severity:** 🔴 **P1** — mất hẳn một tính năng (`BOT-113` trend zone,
`BOT-032` `shade()`), và mất *im lặng*: log báo fallback "thành công", test
xanh, không có cảnh báo nào.
**Status:** ✅ **Fixed 2026-08-23** — user tự xác nhận trên app thật
(*"oki ngon, co rui"*). Bằng chứng log từ chính lần chạy đó
(`logs/debug-20260823-151802.log`):

```
22:18:17,729 - App.BackTestPresenter - INFO -
[chart-region] strategy trend zones: replayed 1504 item(s) onto
PythonBacktestChartHost after fallback
```

1504 vùng nền thật sự được vẽ, thay vì bị bỏ im lặng. `ci-local.ps1 -Full`
PASS 3/3 (`logs/ci-local-20260823-221949.log`, `-2211*`, `-222228.log`),
1789 unit + 54 sanity, sạch.

---

## Symptom

Ảnh chụp của user: chart đầy đủ nến + volume + `ema_20/50/100/200`, **không có
một vùng nền nào**. Strategy đang chạy là `long_term_trend_zone` — strategy
**duy nhất** trong repo có override `classify_trend_zone()`, tức là lần chạy
này chắc chắn sinh ra span thật.

Log (`logs/debug-20260823-150343.log`) khớp chính xác, và **dừng lại đúng ở
đó**:

```
4600  22:04:14,740  BACKTEST_TRACE action=chart_data_ready klines=43239 volume=43239 trades=749
4603  22:04:15,311  BACKTEST_TRACE action=native_chart_unsupported_feature_fallback feature='strategy trend zones'
4604  22:04:15,311  WARNING  Native Backtest chart does not support strategy trend zones; rebuilding with the Python host.
4605  22:04:15,311  INFO     Backtest chart host initialized ... with backend 'python' (requested: 'python').
```

Sau dòng 4605 **không còn bất kỳ lời gọi vẽ region nào**. Fallback đã trả đủ
giá (vứt native chart) nhưng không nhận được gì.

---

## Root cause

`_on_chart_strategy_region` (và 3 handler cùng khuôn) có hình dạng:

```python
try:
    card.set_script_regions(_STRATEGY_TREND_ZONE_KEY, spans)
except NativeUnsupportedFeatureError:
    self._fallback_to_python_after_unsupported_native_feature("strategy trend zones")
    # ...rồi return. spans không bao giờ được áp lại.
```

`_fallback_to_python_after_unsupported_native_feature()` dựng host Python mới
rồi gọi `view.refresh_chart()`. Nhưng `refresh_chart()` chỉ vẽ lại từ
`_last_result` / `_last_klines` / `_last_volume` mà View cache sẵn — **region
không được cache ở đâu cả** (`grep` `backtest_view.py`: không có
`_last_regions`/`_last_spans` nào). Nên OHLC/volume sống sót qua rebuild, còn
region thì bốc hơi.

Nghịch lý: fallback tồn tại **chính là để** nội dung ngoài phạm vi native vẫn
được vẽ (`BOT-098F6`, "no silent visual omission"). Ở đây nó làm ngược lại — bỏ
native *và* bỏ luôn nội dung. Kết quả tệ hơn cả hai lựa chọn trung thực (giữ
native + báo không vẽ được, hoặc chuyển Python + vẽ).

### Vì sao không ai bắt được

Hai lỗ hổng cộng lại — và **user chỉ ra cả hai**:

1. **Test khẳng định sai thứ.** Test `BOT-113` sẵn có, và cả 2 test
   `BUG-037` tôi vừa viết, chỉ khẳng định **kiểu của host**
   (`isinstance(chart_cards[0], PythonBacktestChartHost)`). Cả 3 đều xanh
   trong khi chart không vẽ được gì. Đúng như user nói: *"khi test, bạn phải
   đặt log, để check xem cái background có được vẽ không"* — phải khẳng định
   **nội dung đã được vẽ**, không phải **host nào đã được chọn**.
2. **Log chỉ ghi quyết định, không ghi kết quả.** Log nói "rebuilding with the
   Python host" rồi im. Không dòng nào cho biết có bao nhiêu vùng đã thật sự
   được vẽ, lên host nào. Người đọc log **không thể phân biệt** một lần chạy
   hỏng với một lần chạy tốt — đúng thứ `logging-rule.md` §2/§5 cấm.

Test `BOT-113` còn dùng `Mock()` với `side_effect` — nó chỉ khẳng định lại
niềm tin của người viết về *khi nào adapter raise*, và không hề chạm tới việc
nội dung có tới đích không. Cùng họ bẫy `Mock` mà `bug-fix-rule.md` §3 và
`BUG-013` đã cảnh báo.

---

## Fix

Gom 4 handler về một helper `_apply_after_native_fallback(feature, draw, *, drawn_count)`:

```python
try:
    draw(card)
except NativeUnsupportedFeatureError:
    self._fallback_to_python_after_unsupported_native_feature(feature_name)
    rebuilt = self.view.chart_cards[0] if self.view.chart_cards else None
    ...
    draw(rebuilt)          # ← phát lại lên host mới. Đây là phần bị thiếu.
```

Áp cho cả 4 chỗ cùng khuôn, không chỉ trend zone:
`strategy trend zones`, `script regions`, `script info`, `script markers`.

**Phòng thủ thêm:** nếu chính lần phát lại cũng ném
`NativeUnsupportedFeatureError` thì log **ERROR** thay vì để exception lọt ra
ngoài — handler là `@safe_ui_action`, nó nuốt exception, nên nếu không bắt thì
lỗi sẽ lại trở nên vô hình (bẫy #8 `ONBOARDING.md`).

### Logging mới — trả lời đúng câu hỏi "nền có được vẽ không"

| Tag | Mức | Khi nào |
| :--- | :--- | :--- |
| `[chart-region]` | DEBUG | Vẽ thẳng thành công: `drew N item(s) on <Host>` |
| `[chart-region]` | INFO | Sau fallback: `replayed N item(s) onto <Host> after fallback` |
| `[chart-region]` | ERROR | Host mới vẫn từ chối: `content dropped` |
| `[chart-region]` | ERROR | Rebuild không để lại card nào |

Giờ một dòng `grep '\[chart-region\]'` đủ trả lời câu hỏi của user.

---

## Regression test

`test_trend_zones_are_actually_drawn_on_the_host_it_fell_back_to`
(`test_backtest_presenter.py`) — khẳng định **nội dung**, không phải kiểu host:

```python
layer = rebuilt.chart_card.indicators._region_layer
assert layer.stored_span_count("strategy_trend_zone") == len(spans)
```

Chạy với `NativeBacktestChartHostAdapter` **thật** (chỉ fake
`NativeBacktestChartHost` tầng dưới).

**Xác nhận đỏ đúng lý do:**

```
FAILED ...::test_trend_zones_are_actually_drawn_on_the_host_it_fell_back_to
1 failed
```

Trong khi test cùng file khẳng định *kiểu host* vẫn xanh — chứng minh chính xác
luận điểm của user: khẳng định kiểu host **không đủ**.

Đồng thời sửa test `BOT-113` cũ: stub `_fallback_...` giờ **thay card thật sự**
(đúng như production làm), và test khẳng định thêm
`rebuilt_card.set_script_regions.assert_called_once_with(...)`. Không nới lỏng
gì — bổ sung đúng phần trước đây bỏ trống.

---

## Ghi chú

- Bug này **không phải do `BUG-037` gây ra** — nó có sẵn từ `BOT-098F6D`.
  `BUG-037` chỉ làm nó lộ ra: sau khi native host không còn bị vứt bỏ oan ở
  mọi lần chạy, lần fallback còn lại (đúng lúc có zone thật) mới thành trường
  hợp đáng chú ý.
- **Lỗi quy trình của tôi, ghi lại để không lặp:** khi kiểm tra "đỏ trước khi
  sửa", tôi chạy `git checkout HEAD -- <presenter>` trong lúc fix **chưa được
  commit** → xoá mất toàn bộ fix, phải viết lại. Với `BUG-037` thì
  `git checkout HEAD~1 -- <file>` an toàn vì fix đã commit. Quy tắc: **commit
  fix trước, rồi mới revert để kiểm đỏ.**
