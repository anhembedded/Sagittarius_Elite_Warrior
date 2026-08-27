# EPIC-012D — Tách `ChartPreviewCoordinator` khỏi `chart_render`

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** `B`, `C`

## Kết quả

| | Dòng | Tham số ctor | Method công khai |
| :--- | ---: | ---: | ---: |
| `chart_render_coordinator.py` **trước** | 271 → 265 (sau `012C`) | 20 → 16 | 9 |
| `chart_render_coordinator.py` **sau** | **153** | **8** | 6 |
| `chart_preview_coordinator.py` **mới** | **155** | **12** | 3 |

Tổng tham số của cả nhóm coordinator: 63 → **67**. Tăng 4 là **đúng và phải
trả**: `view`, `state`, `view_model`, `log_dev_trace` giờ đi vào cả hai lớp.
Đổi lại, lớp nào cũng chỉ còn nhận thứ nó thật sự dùng — đó mới là Interface
Segregation (§1 "I"), chứ không phải tổng số nhỏ nhất.

## Ranh giới vẽ theo vòng đời, không theo "nhóm dòng giống nhau"

Câu phân xử của `architecture-rule.md` §5.5: *"đổi cách chart vẽ có bắt buộc
phải đọc/sửa logic huỷ preview cũ không?"* — **không**.

- **Render** xảy ra bất cứ khi nào dữ liệu tới.
- **Preview** là một *yêu cầu* đua với các yêu cầu khác và **có thể bị vứt đi**.

10 trong 16 tham số của file cũ chỉ thuộc nửa preview. Một tập dependency độc
quyền lớn cỡ đó chính là định nghĩa "một coordinator khác đang trốn bên trong".

## `self._view` giữ nguyên — có lý do, không phải bỏ sót

`ChartRenderCoordinator` vẫn giữ tham chiếu View. Theo §2.1, View được chọn
**lúc bootstrap** và không bị tráo runtime, nên giữ tham chiếu là hợp lệ. Cái
bị cấm là cache **widget con**: `first_chart_card()` vẫn là **method**, đọc
`self._view.chart_cards[0]` mỗi lần — `BUG-013`.

## Test cũng tách, và doubles về một chỗ

`test_chart_preview_coordinator.py` nhận 4 test về vòng đời preview;
`test_chart_render_coordinator.py` giữ 5 test về vẽ.

`FakeChartCard`/`FakeChartControls`/`FakeBacktestView`/`FakeChartViewModel`
chuyển vào `conftest.py` dùng chung, cùng lý do với `InMemoryScreenState` ở
`012C`: double nhân bản theo từng file test sẽ **tụt lại phía sau** một thay
đổi hợp đồng mà không ai biết (§2).

## Verify — bơm lỗi

Vô hiệu hoá hàng rào generation id (`if preview_id != active: return` →
`if False:`) → **`test_a_stale_preview_is_dropped_rather_than_drawn` đỏ**,
3 test còn lại xanh (đúng: chúng không nói về hàng rào). Khôi phục → 4/4 xanh.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
