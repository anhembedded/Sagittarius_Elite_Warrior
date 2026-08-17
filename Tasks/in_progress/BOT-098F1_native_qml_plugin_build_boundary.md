# BOT-098F1 — Native C++ QML chart plugin build boundary

**Parent:** `BOT-098F`
**Depends on:** `BOT-098E`
**Ưu tiên:** P1
**Độ phức tạp:** L / Build-specialized
**Trạng thái:** In Progress

## Lý do tách task

Repo hiện là Python/PySide6 thuần, chưa có `CMakeLists.txt`, C++ source hay native
QML plugin pipeline. Viết `QSGGeometryNode` trực tiếp bằng Python là phản mục
tiêu: render thread vẫn phải gọi Python/GIL. Vì vậy build boundary native là
dependency thật, phải hoàn thành trước renderer `BOT-098F`.

## Scope

- Thêm CMake + Qt 6 Quick QML module tối thiểu, build được trên Windows với Qt
  đi cùng PySide6 hiện tại; không cài một Qt runtime thứ hai lệch ABI.
- Plugin đăng ký một `NativeChartItem : QQuickItem` placeholder và được QML
  engine hiện tại import/load từ output deterministic.
- Python bootstrap tìm plugin theo đường dẫn dev/package, báo lỗi actionable nếu
  binary thiếu hoặc ABI sai; không silent fallback trong dev.
- Thiết lập contiguous snapshot ABI version 1 (header revision/count + packed
  OHLC arrays). UI thread nhận/copy pending snapshot; render thread chỉ atomic
  swap native buffers.
- CI build cache và script local rõ ràng; production package chứa đúng DLL/QML
  metadata cần thiết.

## Acceptance criteria

- Clean checkout chạy một lệnh build native và một lệnh full CI.
- QML sanity tạo được `NativeChartItem`, resize/show/close không warning hay
  crash; plugin dùng đúng Qt runtime của `.venv`.
- Thread ownership được test: Python worker không chạm `QSGNode`; snapshot
  revision cũ không ghi đè revision mới.
- Chưa vẽ chart thật trong task này; geometry renderer thuộc `BOT-098F`.
