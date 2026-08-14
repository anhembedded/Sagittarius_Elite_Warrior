# Nhiệm vụ: `OverlayHost` — hạ tầng overlay full-window cho QML modal

> Thuộc Epic [`BOT-086`](BOT-086_ui_layout_and_overlay_architecture_epic.md), **Track A**,
> task 1/2. Nguồn: 📄 [`BUG-004`](../bug_report/BUG-004.md).
>
> ⚠️ **Sửa `sagittarius_engine/` (repo cha)** → commit ở **cả hai repo** + bump submodule
> pointer, giống `BOT-066`…`BOT-071`.

## 1. Vấn đề

`Overlay.overlay` trong QML **không** trỏ tới cửa sổ, mà tới `QQuickWidget` chứa nó. Đo
thật (xem `BOT-086` §2.1): màn Backtest có `QQuickWidget` cao cố định 190px → mọi
`Popup` khai báo trong đó bị kẹp trong 190px. `extendedMetricsPopup` cần **606px → chỉ
hiện 31%**.

Đây là hạ tầng dùng chung, không phải lỗi của màn nào: **bất kỳ màn nào chia QML thành
nhiều `QQuickWidget` con đều dính** — hôm nay là Backtest (3 widget), mai là màn khác.

## 2. Đã verify khả thi trước khi lập task

Probe thật với `QT_QPA_PLATFORM=offscreen`, dùng chính `create_quick_widget()` của engine:

```
overlay QQuickWidget : 1400x900   ← phủ toàn cửa sổ
Overlay.overlay      : 1400x900   ← không còn 190
606px modal fits?    : YES
click-through idle   : YES        ← WA_TransparentForMouseEvents khi không có modal
after resize         : 1000x600   ← geometry bám theo cửa sổ
```

Cấu hình đã chạy được trong probe:

```python
overlay = create_quick_widget()
overlay.setParent(window)                    # con của central widget, KHÔNG nằm trong layout
overlay.setAttribute(Qt.WA_AlwaysStackOnTop, True)
overlay.setClearColor(Qt.transparent)
overlay.setGeometry(window.rect())
overlay.raise_()
overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)   # khi rảnh
```

→ Task này là **triển khai + làm cho dùng lại được**, không phải nghiên cứu khả thi.

## 3. Các bước thực hiện

### 3.1. `OverlayHost` trong `sagittarius_engine/extensions/pyside_mvc/`

- [ ] Class mới (file riêng, cạnh `qml_host_view.py`): bọc 1 `QQuickWidget` trong suốt,
      là **con của central widget** chứ không nằm trong `QLayout` nào (layout sẽ chiếm chỗ
      thật, không phủ lên được).
- [ ] Tự đồng bộ geometry theo widget cha: bám `resizeEvent` của cha (event filter hoặc
      `QObject.installEventFilter`), **không** hardcode kích thước.
- [ ] `raise_()` để luôn nằm trên `QStackedWidget`. ⚠️ Xác nhận thật với `ChartCard`
      (pyqtgraph/QtWidgets) — z-order giữa QQuickWidget và widget OpenGL/raster là chỗ dễ
      sai nhất, **phải chạy tay xem modal có thật sự phủ lên chart không**, không tin lý
      thuyết.
- [ ] Bàn giao input: `WA_TransparentForMouseEvents = True` khi không có modal nào mở,
      `False` khi có. Nguồn sự thật là **trạng thái modal thật trong QML**, không phải cờ
      Python đếm tay (đếm tay sẽ lệch ngay khi 1 popup tự đóng bằng `closePolicy`).

### 3.2. API cho màn hình dùng

- [ ] Chốt cách 1 màn đăng ký modal của nó vào overlay host. Đề xuất (chốt lúc code):
      màn cung cấp URL QML + context properties, host `Loader` nó vào; hoặc host expose
      1 `Item` để màn `reparent` popup sẵn có vào. **Ưu tiên cách ít phải viết lại QML
      hiện có nhất** — `BOT-088` phải chuyển 6 popup, mỗi popup viết lại là 6 lần rủi ro.
- [ ] Không ép mọi màn phải có overlay host. Màn dùng `QmlHostView` (Settings/Database)
      hiện **chạy đúng** vì overlay của chúng đã là full màn — không được làm hỏng chúng.

### 3.3. Đóng gap test — **bắt buộc, không phải nice-to-have**

- [ ] Test từ Python đọc được `Overlay.overlay.width/height` (probe đã chứng minh làm
      được qua property trên QML root) → mọi test popup sau này verify được **"modal có
      vừa không"**, không chỉ "bấm không crash".
- [ ] Ghi lại cách làm vào chỗ dev đọc được, vì giới hạn *"Popup content không test được
      qua `find_qml_item`"* ghi từ [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md)
      chính là lý do `BOT-081` để lọt 1 popup tràn mà suite vẫn xanh.

## 4. Rủi ro / Lưu ý

- **Rủi ro cao nhất: z-order với `ChartCard`.** pyqtgraph vẽ bằng QtWidgets; QQuickWidget
  trong suốt phủ lên widget như vậy là ca kinh điển hay hỏng (native window handle). Nếu
  chạy tay thấy modal bị chart che → **dừng, báo user**, đừng tự chuyển sang hướng A/C.
- **Rủi ro thứ hai: input rơi vào khoảng trống.** Nếu `WA_TransparentForMouseEvents` bàn
  giao sai nhịp, user sẽ gặp "bấm không ăn" ở toàn app — tệ hơn nhiều so với bug gốc.
  Test cả 2 chiều (mở modal → chart không nhận click; đóng modal → chart nhận lại).
- **Không dùng `Qt.Popup`/`Qt.Tool` window riêng** làm overlay: nó là cửa sổ top-level
  khác, sẽ có viền/bóng của WM và không di chuyển cùng cửa sổ chính trên mọi nền tảng.
- Chỉ 1 app đang dùng, nhưng đặt ở `pyside_mvc` là đúng chỗ vì đây là hạ tầng thuần Qt,
  không biết gì về trading — cùng lý lẽ với `ResourceScope`/`from_qml`.

## 5. Phụ thuộc

- Không phụ thuộc task nào. Là task nền cho [`BOT-088`](BOT-088_migrate_backtest_popups_to_overlay_host.md).
- Liên quan: [`BOT-030`](../completed/BOT-030_full_qml_migration.md) (quyết định hybrid
  QML + `ChartCard` QtWidgets — gốc rễ khiến màn Backtest phải tách nhiều `QQuickWidget`),
  [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) (gap test Popup).
