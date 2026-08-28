# Spike — năm phép đo cho `EPIC-015`

Chạy 2026-08-28. Giữ lại **nguyên trạng** để chạy lại được, không phải để dùng lại làm code.

> Chúng nằm ngoài cổng lint (`ruff check src tests tools` — `Tasks/` không có trong đó) và
> **cố ý không được dọn**: giá trị của chúng là ở chỗ chạy lại ra đúng con số đã báo cáo. Sửa
> chúng cho đẹp là làm hỏng đúng thứ chúng dùng để chứng minh. Cùng khuôn với
> `scripts/benchmarking/` — probe được đóng băng, không phải code sản phẩm.

```bash
cd Tasks/epics/EPIC-015_qml_tung_widget_khong_chuyen_chart/spike
PYTHONPATH=<engine>:<repo-parent> QT_QPA_PLATFORM=offscreen python probe.py     # D — findChild, property, click
PYTHONPATH=... QT_QPA_PLATFORM=offscreen python probe2.py                        # D — QTest.keyClicks xuyên QML
PYTHONPATH=... QT_QPA_PLATFORM=offscreen python coexist.py                       # A, B, C — lồng nhau
QT_QPA_PLATFORM=minimal python vm_alone.py                                       # E — VM không cần GUI
```

| File | Trả lời câu hỏi |
| :--- | :--- |
| `probe.py` | Python có `findChild` được item QML theo `objectName`, đọc property, bắn signal không? |
| `probe2.py` | Gõ phím thật (`QTest.keyClicks`) có chạy xuyên QML vào ViewModel không? |
| `coexist.py` | QML ngồi cạnh chart pyqtgraph / làm cả route trong `QStackedWidget` / làm modal được không? |
| `vm_alone.py` | Widget ViewModel test được **không cần `QApplication`** không? |

Kết quả tóm tắt ở [`../README.md` §2](../README.md). Bẫy đáng nhớ nhất: `TextField.textEdited`
của QtQuick Controls **không có tham số**, khác `QLineEdit.textEdited(str)` bên widget — giả lập
signal bằng tay sẽ fail im lặng, dùng `QTest` thay vì.
