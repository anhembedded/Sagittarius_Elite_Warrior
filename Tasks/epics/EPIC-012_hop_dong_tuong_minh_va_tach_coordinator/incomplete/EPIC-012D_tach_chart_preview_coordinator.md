# EPIC-012D — Tách `ChartPreviewCoordinator` khỏi `chart_render`

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite
**Phụ thuộc:** `B`, `C` (tách khi chưa có kiểu đại diện là nhân bản tham số ngầm)

## Số đo

`chart_render_coordinator.py`: **271 dòng, 20 tham số ctor, 9 method công khai**.

Nhánh **preview** sở hữu **10 dependency mà không nhánh nào khác dùng**:
`is_busy`, `next_preview_id`, `get_active_preview_id`, `emit_preview_ready`,
`run_preview_worker`, `get_current_config`, `format_coverage_message`,
`set_current_raw_klines`, `refresh_market_rule_verification`,
`get_chart_klines_fetch_limit`.

Một tập dependency **độc quyền** to bằng nửa constructor chính là định nghĩa của
"đây là một Coordinator khác đang trốn bên trong" — và là dấu hiệu Interface
Segregation mà `architecture-rule.md` §1 (I) nói tới.

## Kết quả mong đợi

`chart_render_coordinator` còn ~10 tham số, chỉ lo **vẽ dữ liệu đã có**;
`chart_preview_coordinator` lo **vòng đời một lần preview** (xin id, chạy
worker, huỷ preview cũ, phát `preview_ready`).

Ranh giới phân xử theo §5.5 của `architecture-rule.md`: *"đổi cách vẽ chart có
bắt buộc phải đọc/sửa logic huỷ preview cũ không?"* — **không**. Khác vòng đời
→ tách.

## Bẫy đã biết

`chart_render_coordinator.py` đang giữ `self._view = view` (early binding). Theo
§3.2 của epic README, View **không** bị tráo lúc runtime nên bản thân việc giữ
tham chiếu View là hợp lệ — nhưng **không được** mở rộng nó sang widget con
(`chart_cards`, chart host). Task này là lúc kiểm lại đúng chỗ đó.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- **Bơm lỗi:** cho `next_preview_id` trả về hằng số → test "preview cũ bị huỷ
  khi preview mới bắt đầu" phải đỏ.
