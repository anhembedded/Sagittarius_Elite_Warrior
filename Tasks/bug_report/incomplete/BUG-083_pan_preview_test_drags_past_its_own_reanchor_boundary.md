# BUG-083 — Cổng CI bắt buộc đỏ vĩnh viễn: `test_pan_preview_moves_only_the_data_region_not_the_axes` kéo quá ngưỡng re-anchor của chính nó

**Reported date:** 2026-09-02
**Severity:** 🟠 **P2** — không phải lỗi sản phẩm, nhưng làm **cổng bắt buộc**
(`scripts/ci-local.ps1 -Full`) đỏ vĩnh viễn, và **10 file task đã bắt đầu coi nó là bình thường**.
**Status:** 🔴 Open — root cause **đã xác nhận bằng đo đạc** (§3), hướng sửa đã chốt (§5), chưa sửa.

---

## 1. Hiện tượng (Symptom)

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` luôn kết thúc **FAIL** với đúng **1** test đỏ:

```text
1 failed, 3312 passed, 4 skipped
FAILED tests/unit/presentation/ui/components/test_cached_frame_interaction.py
       ::test_pan_preview_moves_only_the_data_region_not_the_axes
```

Bước quét log bắt buộc (`FAILED|ERROR|Traceback|ResourceWarning` trong `LOG_FILE:`) **sạch** —
"no WARNING/ERROR/CRITICAL log records". Nghĩa là toàn bộ phần còn lại của cổng xanh; chỉ một
assertion này chặn.

Assertion đỏ là **assertion cuối cùng** của test:

```text
>       assert time_axis_during != time_axis_before
E       assert (4278190081, 4279173376, 4285085706, ...) != (4278190081, 4279173376, 4285085706, ...)
tests/unit/presentation/ui/components/test_cached_frame_interaction.py:324
```

## 2. Vì sao đáng mở hồ sơ dù "chỉ là test"

Test này **đỏ từ lúc sinh ra**: cả `cached_frame_interaction.py` (632 dòng) lẫn
`test_cached_frame_interaction.py` (487 dòng) được tạo **nguyên khối trong cùng một merge**,
`0c75a7a` (PR #140, 2026-08-27), và **không commit nào** chạm vào hai file đó kể từ đó
(`git log -- <file>` chỉ trả về đúng `0c75a7a`).

Hệ quả đã xảy ra thật: **10/13** file task của `EPIC-021` (`A`, `B`, `C`, `D`, `E`, `F`, `G`,
`H`, `J`, `L`) đều gọi tên đúng test này kèm biến thể của câu *"không liên quan"*. Đó chính là
cơ chế mà một cổng bắt buộc mất tác dụng: khi trạng thái mặc định là đỏ, không ai phân biệt được
đỏ-mới với đỏ-cũ nữa.

**Đã loại trừ liên quan tới EPIC-021 bằng lịch sử git**, không phải bằng phán đoán: không commit
nào trong `afbe1fb~1..HEAD` chạm `chart_card/` hay file test này (`git log --name-only`, 0 hit).

## 3. Root cause — **hai** lỗi test độc lập cộng dồn, sản phẩm không sai

Đo trực tiếp trên chính đối tượng test (script tái hiện đặt trong `tests/`, chạy thật, đã xoá sau
khi đo — không suy đoán tĩnh):

### 3.1 Test kéo **vượt ngưỡng re-anchor của chính nó**

`ChartCard` 1200×700 → `_view_width = 1121.5px`. Ngưỡng re-anchor:

```python
_PAN_REANCHOR_VIEWPORT_RATIO = 0.05
_PAN_REANCHOR_MAX_PIXELS = 96.0
threshold = min(1121.5 * 0.05, 96.0) = 56.075  # px
```

Test kéo `QPointF(100.0, 0.0)` — **gần gấp đôi ngưỡng**. Đo `_gesture_reanchors`:

| Quãng kéo | `_gesture_reanchors` sau `update_pan` | x-range trong lúc kéo |
| ---: | :---: | :--- |
| 40px | **0** | `3600.0 .. 9600.0` (không đổi — đúng nghĩa preview thuần) |
| 100px | **1** | `3065.0 .. 9065.0` (**đã re-render thật**) |

Docstring và comment của chính test nói ngược lại điều đang xảy ra:

> *"Deliberately shorter than `_PAN_REANCHOR_VIEWPORT_RATIO` of the plot width, so this stays a
> test of the pure cached-pixmap transform and never trips the mid-drag re-render."*

Nó **không** ngắn hơn. Và file này **đã có sẵn hằng số dành riêng cho đúng chuyện đó**, các test
anh em trong cùng file đều dùng:

```python
#: Short enough to stay inside the cached frame on every card size used here,
#: so a test of the pure preview transform never trips the mid-drag re-render.
_SHORT_PAN_PIXELS = 40.0
```

Hai chỗ trong test này (dòng 284 `update_pan`, dòng 326 `commit_pan`) ghi cứng `100.0` thay vì
dùng hằng số. Đây là dạng lỗi "hằng số được viết ra để tránh đúng cái bẫy này, rồi một test quên
dùng nó".

### 3.2 Cách lấy mẫu trục thời gian **không nhìn thấy** thay đổi sau re-anchor

Sau khi re-anchor, trục thời gian **có** được vẽ lại đúng (range mới 3065..9065). Đo toàn bộ dải
pixel của trục:

| Cách lấy mẫu | Kết quả |
| :--- | :--- |
| **Một hàng ngang** tại `time_axis_rect.center().y()` (cách test đang dùng) | **không đổi** → assertion đỏ |
| **Toàn bộ dải trục** (`top..bottom` × `left..right`) | **đổi thật — 3.774 / 124.850 pixel khác nhau** |

Hàng ngang duy nhất mà test lấy mẫu rơi vào khoảng trống giữa vạch chia và dòng chữ nhãn, nên nó
không chứa một pixel nào trong số 3.774 pixel đã đổi.

**Kết luận:** sản phẩm hành xử đúng ở cả hai nhánh (preview thuần khi kéo ngắn; re-render đúng
range khi kéo dài). Test sai ở hai chỗ độc lập: kéo quá ngưỡng nó tự khai là không vượt, và lấy
mẫu quá hẹp để thấy được thứ nó khẳng định phải thấy.

## 4. Bằng chứng quyết định

Bản sao **nguyên văn** của test, chỉ đổi `100.0 → 40.0`:

```text
1 passed in 0.71s      # 40px, reanchors=0
1 failed in 0.77s      # 100px, reanchors=1   ← bản gốc
```

## 5. Hướng sửa và tại sao nó **không** làm yếu test (`bug-fix-rule.md` §4)

Đổi hai literal `100.0` (dòng 284, 326) thành `_SHORT_PAN_PIXELS` — đúng hằng số mà file đã định
nghĩa và các test anh em đang dùng.

`bug-fix-rule.md` §4 cấm sửa test theo hướng làm nó dễ hơn. Sửa này không rơi vào đó, vì:

- Test này **tự khai** mục tiêu là "pure cached-pixmap transform, never trips the mid-drag
  re-render". Dùng 40px là **đưa nó về đúng phạm vi nó tuyên bố**, không phải nới lỏng.
- Hành vi re-anchor **đã được phủ riêng** bởi
  `test_reanchoring_mid_drag_lands_on_the_same_range_as_one_continuous_pan` (dòng 440) và
  `test_long_drag_does_not_expose_a_large_blank_band` — nên không có nhánh nào mất coverage.
- Không assertion nào bị xoá hay nới; chỉ đổi tham số đầu vào về đúng miền hợp lệ.

**Cân nhắc thêm (không bắt buộc, đề xuất để user quyết):** §3.2 cho thấy cách lấy mẫu một-hàng-
ngang là mong manh — nó sẽ tiếp tục cho âm tính giả nếu chiều cao trục hay font nhãn đổi. Có thể
đổi sang lấy mẫu toàn dải trục. Đây là **cải thiện chất lượng test**, không cần thiết để đóng bug
này, và làm nó chung một commit sẽ trộn hai thay đổi khác bản chất.

## 6. Việc phải làm khi sửa

1. Viết/chạy regression: xác nhận test đỏ **đúng vì lý do §3.1** trước khi sửa (đã làm, §4).
2. Đổi 2 literal → `_SHORT_PAN_PIXELS`.
3. Chạy **cổng thật** `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`, quét `LOG_FILE:` —
   phải xanh hoàn toàn, không còn "1 failed".
4. Cập nhật 10 file task `EPIC-021A/B/C/D/E/F/G/H/J/L`: thay câu *"không liên quan"* bằng con
   trỏ tới hồ sơ này. Để nguyên là giữ lại cái cớ cho lần sau.
