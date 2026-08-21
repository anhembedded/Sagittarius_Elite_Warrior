# Nhiệm vụ: Gom 7 module cầu nối native chart đang nằm phẳng ở `src/presentation/ui/` vào 1 thư mục riêng

**Trạng thái:** 🔴 Backlog
**Không thuộc epic nào** — dọn tổ chức thư mục, không phải decomposition file
quá tải (khác `EPIC-003`), không phải bug.
**Nguồn:** User phát hiện trực tiếp khi mở `native_chart_marker_snapshot.py`.

---

## 1. Vấn đề thật

`src/presentation/ui/` hiện có 3 file top-level đúng nghĩa app-wide
orchestration (`app_bootstrapper.py`, `main_window.py`, `constants.py`) —
nhưng nằm **cùng cấp, lẫn lộn** với **7 file khác hoàn toàn không cùng tầng
ý nghĩa**, đều thuộc đúng 1 mối: cầu nối native chart (ABI serializer,
discovery, toán viewport/timezone). Xác nhận qua đọc docstring từng file,
không phải đoán theo tên:

```
src/presentation/ui/
├── native_chart_indicator_snapshot.py   # Serializer ABI v1 indicator
├── native_chart_interaction.py          # Contract marker LOD + crosshair snapping
├── native_chart_lod.py                  # Contract volume/indicator render bucket
├── native_chart_marker_snapshot.py      # Serializer ABI v1 marker
├── native_chart_runtime.py              # Discovery boundary QML module native
├── native_chart_snapshot.py             # Serializer ABI chart snapshot
├── native_chart_timezone_bridge.py      # Cầu nối timezone-formatting cho QML
└── native_chart_viewport_gestures.py    # Toán viewport drag/wheel thuần
```

Đúng rule đã có sẵn trong `code-rule.md` §3 (MVP Trio Screen Directory
Layout): *"Group only helper modules into `<name>/logic/` or
`<name>/helpers/` when size warrants it."* — 7 file rõ ràng đã đủ "warrant"
1 thư mục riêng, chỉ là rule đó viết cho `screens/<name>/`, chưa có tiền lệ
áp dụng ngược lên chính `ui/` top-level — task này là lần đầu áp dụng.

## 2. Cấu trúc đề xuất

```
src/presentation/ui/
├── app_bootstrapper.py     # giữ nguyên — app-wide, đúng chỗ
├── main_window.py          # giữ nguyên
├── constants.py            # giữ nguyên
└── native_chart/           # MỚI
    ├── __init__.py
    ├── indicator_snapshot.py      # đổi tên bỏ tiền tố "native_chart_" (đã ở trong package tên đó rồi)
    ├── interaction.py
    ├── lod.py
    ├── marker_snapshot.py
    ├── runtime.py
    ├── snapshot.py
    ├── timezone_bridge.py
    └── viewport_gestures.py
```

**Quyết định cần chốt trước khi code (không tự quyết):** có bỏ tiền tố
`native_chart_` khỏi tên file bên trong package mới không (vì đã nằm trong
thư mục `native_chart/` rồi, tiền tố lặp lại là dư — ví dụ
`native_chart.snapshot` thay vì `native_chart.native_chart_snapshot`), hay
giữ nguyên tên file y hệt, chỉ đổi đường dẫn thư mục (an toàn hơn, diff nhỏ
hơn, nhưng tên vẫn dư thừa)? Ảnh hưởng tới toàn bộ 17 file cần sửa import ở
bước 3 — chọn trước rồi mới code toàn bộ, không đổi giữa chừng.

## 3. Phạm vi ảnh hưởng — 17 file thật cần sửa import (đã đo, không phải 34 như ước tính ban đầu — số đó tính nhầm cả `.pyc` cache)

```
scripts/benchmarking/chart_migration_benchmark.py
scripts/benchmarking/native_chart_camera_probe.py
scripts/benchmarking/native_chart_interaction_probe.py
src/presentation/ui/app_bootstrapper.py
src/presentation/ui/native_chart_interaction.py        # import chéo nội bộ giữa 2 trong 7 file
src/presentation/ui/screens/backtest/logic/backtest_chart_host.py
src/presentation/ui/screens/backtest/logic/native_backtest_chart_adapter.py
tests/sanity/test_native_chart_qml_plugin_sanity.py
tests/unit/presentation/ui/screens/test_backtest_chart_host.py
tests/unit/presentation/ui/screens/test_native_backtest_chart_adapter.py
tests/unit/presentation/ui/test_native_chart_indicator_snapshot.py
tests/unit/presentation/ui/test_native_chart_interaction.py
tests/unit/presentation/ui/test_native_chart_lod.py
tests/unit/presentation/ui/test_native_chart_marker_snapshot.py
tests/unit/presentation/ui/test_native_chart_runtime.py
tests/unit/presentation/ui/test_native_chart_snapshot.py
tests/unit/presentation/ui/test_native_chart_timezone_bridge.py
tests/unit/presentation/ui/test_native_chart_viewport_gestures.py
```

(Đo lại bằng `grep -rlE "ui\.native_chart_(indicator_snapshot|interaction|lod|marker_snapshot|runtime|snapshot|timezone_bridge|viewport_gestures)" src tests scripts | grep -v __pycache__` ngay trước khi bắt tay code — con số có thể trôi nếu có commit khác chen giữa.)

**Câu hỏi phụ cần chốt:** 8 file test hiện nằm phẳng ở
`tests/unit/presentation/ui/test_native_chart_*.py` — có dời theo cùng vào
`tests/unit/presentation/ui/native_chart/` để mirror đúng cấu trúc `src/`
(quy ước sẵn có của repo) hay giữ nguyên chỗ cũ? Khuyến nghị: dời theo, giữ
mirror 1-1 src↔tests như mọi nơi khác trong repo.

## 4. Việc cần làm

1. Chốt 2 câu hỏi thiết kế ở mục 2 và mục 3 với user trước khi code.
2. Tạo `src/presentation/ui/native_chart/__init__.py`, `git mv` 7 file vào
   đó (giữ lịch sử git qua `mv`, không xoá-tạo-lại).
3. Sửa import ở toàn bộ 17 (hoặc số đo lại) file — mỗi nhóm liên quan 1
   commit nhỏ nếu tách được (ví dụ: `scripts/` riêng, `src/` riêng,
   `tests/` riêng), không gộp hết thành 1 diff khổng lồ khó review.
4. Nếu chọn dời test theo (mục 3), `git mv` 8 file test tương ứng.
5. Chạy `ruff check --fix` cho import sort sau khi đổi đường dẫn (import
   path mới có thể lệch thứ tự alphabet so với trước).

## 5. Kiểm thử

Không có logic nghiệp vụ nào đổi — đây thuần là di chuyển file + sửa import.
**Test tái sử dụng nguyên vẹn, không sửa 1 assertion nào** là bằng chứng
đúng cho "hành vi giữ nguyên, chỉ đổi vị trí". Verify:

- `ruff check src tests scripts` sạch (không import lỗi/không dùng).
- `mypy` (`EPIC-002` gate) sạch — đặc biệt quan trọng vì đây chính xác lớp
  lỗi `mypy` mới bắt được mà `ruff` không thấy (`BUG-026`): nếu sót 1 import
  path, mypy sẽ báo `attr-defined`/`import-error` ngay, ruff có thể im lặng
  bỏ qua tuỳ tình huống.
- `.\scripts\ci-local.ps1 -Full` — đọc `logs/ci-local-latest.log` đầy đủ
  (không chỉ nhìn terminal — bài học `BUG-029`/`BUG-030`), xác nhận toàn bộ
  test cũ pass không đổi số lượng.
