# BOLT-001 — Số đo: `_bar_bounds()` trên mỗi tick

**Ngày:** 2026-08-26 · **Máy:** container Linux 4 nhân, Python 3.12.3

## Cách đo

200.000 tick cách nhau 1 giây, bar 300s (mỗi bar 300 tick) — đúng hình dạng
`BUG-058` mô tả. So hai vòng lặp trên **cùng một** danh sách tick:

```python
# hiện tại
for t in ticks:
    bs, be = _bar_bounds(t, INTERVAL)

# đề xuất
bs = be = None
for t in ticks:
    if bs is None or not (bs <= t < be):
        bs, be = _bar_bounds(t, INTERVAL)
```

## Kết quả

```
mẫu 200,000 tick, bar 300s (một bar = 300 tick)
  hiện tại :    212.8 ms   (  1064 ns/tick)
  đề xuất  :     13.8 ms   (    69 ns/tick)
  nhanh hơn: 15.46x   tiết kiệm 93.5%

quy về 2,592,000 tick của BUG-058:
  hiện tại :   2.76 s
  đề xuất  :   0.18 s
  tiết kiệm:   2.58 s
```

## Đọc con số này cho đúng

2.58s là của **riêng bước tính biên bar**, không phải toàn bộ backtest. `BUG-058`
báo freeze UI trong một vòng chạy dài hơn thế nhiều, nên đây **không phải** bản
sửa cho bug đó — chỉ là một phần chi phí trong hot loop của nó bị bỏ đi.

Chi phí nằm ở `datetime`: một `.timestamp()` (đổi múi giờ) cộng hai lần dựng
`datetime`/`timedelta` cho mỗi tick. Phép so sánh thay thế không cấp phát gì.

Tỉ lệ tiết kiệm phụ thuộc số tick trên mỗi bar: bar 5 phút với tick 1s bỏ được
299/300 lần gọi. Nếu `tick_resolution == interval` (một tick mỗi bar) thì tối ưu
này không tiết kiệm gì — và cũng không tốn gì thêm.
