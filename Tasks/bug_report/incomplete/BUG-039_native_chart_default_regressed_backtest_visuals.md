# BUG-039 — Native chart làm mặc định khiến Backtest mất grid, nến vẽ sai, và tự phá chart mỗi khi có trend zone

**Trạng thái:** 🟡 Đã né bằng kill-switch (config), **chưa sửa gốc**
**Phát hiện:** 2026-08-24, người dùng báo qua ảnh chụp app đang chạy
**Nguồn gốc:** [`30ffa18`](../../..) — `feat(backtest): promote native chart to default backend with python kill-switch (BOT-098F6E)`, 2026-08-18

---

## 1. Triệu chứng người dùng thấy

Mở app, so 2 màn hình cạnh nhau:

| | Dev Board | Backtest Engine |
| :--- | :--- | :--- |
| Grid nền | Có | **Mất** |
| Thân nến | Vẽ đầy đủ, rõ thân + râu | **Chỉ còn que dọc mảnh**, gần như không thấy thân |
| Nền trend zone | — | Chỉ hiện sau khi chart bị dựng lại giữa chừng |

Người dùng mô tả: *"dev board thì đúng, còn backtest thì sai rồi"*, *"nó không có grid, nền phẳng"*,
*"cái chart hiện tại vẽ cây nến còn sai kia"*.

## 2. Nguyên nhân gốc — hai renderer khác nhau, cái kém hoàn thiện hơn được đặt làm mặc định

Backtest có **2 backend chart** thay thế nhau qua `BacktestChartHostFactory`
(`src/presentation/ui/screens/backtest/logic/backtest_chart_host.py`):

| Backend | Renderer | Grid | Thân nến | Background trend zone |
| :--- | :--- | :---: | :---: | :---: |
| `python` | `ChartCard` — **pyqtgraph / QtWidgets** (đúng cái Dev Board dùng) | ✅ `showGrid(x=True, y=True, alpha=0.2)` | ✅ | ✅ `RegionLayer` |
| `native` | `NativeChartItem` — **C++ / QtQuick scene graph** | ❌ không có node grid | ⚠️ geometry riêng, mảnh hơn | ❌ **raise `NativeUnsupportedFeatureError`** |

`30ffa18` (BOT-098F6E) đổi mặc định `backtest.chart.backend` từ `"python"` → `"auto"`
(ưu tiên native). **Trước commit đó, Backtest dùng đúng `ChartCard` pyqtgraph như Dev Board** —
đó chính là "bản cũ" mà người dùng nhớ.

Không liên quan `EPIC-005` (QML→QtWidgets): đã xác minh
`git diff origin/master-warrior...epic/EPIC-005-qml-to-qtwidgets` cho `native/`,
`screens/backtest/`, `components/` → **0 dòng thay đổi**.

## 3. Cái giá thật của native mặc định: nó tự phá chính mình mỗi lần có trend zone

Native **không hề có ABI vẽ background region** — presenter ghi thẳng: *"Native chart has no
background-region ABI at all"*. Nên mỗi khi strategy sinh trend zone:

1. `set_script_regions()` raise `NativeUnsupportedFeatureError`
   ([`native_backtest_chart_host_adapter.py:211`](../../../src/presentation/ui/screens/backtest/logic/native_backtest_chart_host_adapter.py)).
2. App **phá native host, dựng lại Python host giữa chừng** (`_apply_after_native_fallback`).
3. Replay lại spans lên host mới (đây chính là nội dung `BUG-038` vừa fix).

Nghĩa là **cái nền trend màu mà người dùng vẫn thấy xưa nay vốn đã luôn do pyqtgraph vẽ**, không
phải native. Native chỉ tồn tại được tới lúc gặp region đầu tiên. `BUG-037` và `BUG-038` đều là
hệ quả trực tiếp của kiến trúc này — vá quanh khoảng trống tính năng, không lấp nó.

Chuỗi bug sinh ra từ cùng một gốc: `BUG-013` → `BUG-037` → `BUG-038` → `BUG-039` (bug này).

## 4. Đã làm gì (2026-08-24)

Lật **kill-switch có sẵn** mà chính `BOT-098F6E` cố ý để lại (*"retain python backend as tested
emergency fallback and kill-switch"*) — thêm 1 dòng vào `src/config/app_config.json`:

```json
"backtest.chart.backend": "python",
```

**Không sửa code, không revert commit nào.** Native vẫn nguyên vẹn, bật lại chỉ cần xoá dòng này.

Xác minh bằng code thật, không suy đoán:

```
config backend resolved = 'python'
host type                = PythonBacktestChartHost
has pyqtgraph plot_layout = True
set_script_regions -> RegionLayer: _spans 0→1, _items 0→1, _active_slices 0→1
```

Gate: `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`,
`1800 passed / 54 sanity` — không test nào vỡ, tức **không có test nào từng khẳng định mặc định
phải là native**. Đây tự nó đã là một lỗ hổng: `BOT-098F6E` đổi mặc định mà không có test khoá lại.

## 5. Còn phải làm (chưa xong)

1. **Quyết định hướng đi cho native renderer.** Hai lựa chọn, không được để lửng:
   - Bù đủ khoảng cách: thêm grid, sửa geometry thân nến, **và** làm ABI background region cho
     `NativeChartItem` — chỉ khi đó `"auto"` mới đáng bật lại.
   - Hoặc thừa nhận native chưa đủ chín và giữ `"python"` làm mặc định lâu dài, hạ native xuống
     opt-in cho người cần throughput cao.
2. **Thêm test khoá mặc định**, để lần sau đổi backend mặc định là gate đỏ ngay, thay vì phải chờ
   người dùng chụp màn hình báo lỗi.
3. **Ảnh hưởng tới `EPIC-005`'s ADR.** ADR loại chart khỏi phạm vi migrate với lý do *"chart phải ở
   lại QtQuick vì hiệu năng GPU"*. Thực tế ngược lại: bản **QtWidgets/pyqtgraph mới là bản vẽ đúng
   và đủ tính năng**, bản QtQuick native mới là bản thiếu. Luận điểm của ADR yếu hơn nó tưởng —
   cần ghi nhận trước khi ai đó dùng ADR đó để biện minh cho quyết định tiếp theo (`EPIC-005F`).
4. **`FPS 3.0` + label giá đè lên nhau** ở góc trên-phải chart native (`devFpsOverlay` và
   `priceAxisTicks` cùng neo góc phải-trên, không tránh nhau) — bug hiển thị riêng, chỉ xuất hiện
   trên đường native, tạm thời không còn thấy vì đã chuyển sang python.
