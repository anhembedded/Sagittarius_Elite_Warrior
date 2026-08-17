# Native Chart — Build & Deploy Guide

Native chart là module C++/QML `Sagittarius.NativeChart`, không phải Python
thuần. Vì vậy cần phân biệt rõ:

- **Build:** biên dịch source C++ thành QML plugin/DLL để chạy và test tại máy
  phát triển.
- **Deploy/stage:** chép bộ module đã build vào thư mục của bản đóng gói. Bước
  này chỉ cần khi tạo portable/frozen desktop release hoặc kiểm tra package.

## Khi nào cần làm gì?

| Trường hợp | Build native | Deploy/stage |
| --- | :---: | :---: |
| Chạy CLI/headless, không mở desktop chart | Không | Không |
| Chạy UI hiện tại không có `-Dev` | Không bắt buộc | Không |
| Chạy `run-ui.ps1 -Dev` hoặc native visual test | Có | Không |
| Sửa `native/chart_renderer/`, CMake hoặc snapshot ABI | Có | Không |
| Chạy `ci-local.ps1 -Full` | Tự build | Không |
| Tạo portable/frozen desktop release có native chart | Có | Có |

Hiện tại runtime native được bật bắt buộc trong dev mode. Chart production vẫn
đang trong quá trình migration, nên build native chưa đồng nghĩa chart cũ trên
màn Backtest đã được thay hoàn toàn.

## 1. Prerequisites trên Windows

- Virtual environment `.venv` đã cài `PySide6`.
- CMake có trong `PATH`.
- Visual Studio 2022 Build Tools với workload C++/MSVC x64.
- Qt MSVC 2022 SDK có **đúng cùng version** với `PySide6.__version__`.

Vị trí Qt SDK mặc định:

```text
%LOCALAPPDATA%\SagittariusToolchains\Qt\<PySide6-version>\msvc2022_64
```

Nếu SDK nằm chỗ khác:

```powershell
$env:SAGITTARIUS_QT_ROOT = "D:\Qt\6.11.1\msvc2022_64"
```

Không build bằng Qt version khác rồi copy DLL vào app. Script sẽ chủ động từ
chối ABI mismatch.

## 2. Build cho development

Chạy từ root `Sagittarius_Elite_Warrior`:

```powershell
.\scripts\build-native-chart.ps1
```

Clean configure/build khi đổi toolchain, Qt SDK hoặc nghi ngờ cache CMake cũ:

```powershell
.\scripts\build-native-chart.ps1 -Clean
```

Output development:

```text
build/native-chart/qml/
├── native-chart-runtime.json
└── Sagittarius/NativeChart/
    ├── qmldir
    ├── sagittarius_native_chart.dll
    ├── sagittarius_native_chartplugin.dll
    └── sagittarius_native_chart.qmltypes
```

Sau đó chạy UI dev:

```powershell
.\scripts\run-ui.ps1 -Dev
```

`run-ui.ps1` hiện **không tự build**. Nếu plugin chưa tồn tại hoặc ABI không
khớp, dev mode phải fail rõ ràng thay vì âm thầm quay về DLL cũ.

## 3. Khi nào phải rebuild?

Rebuild sau khi thay đổi một trong các phần sau:

- `native/chart_renderer/*.cpp`, `*.h` hoặc `CMakeLists.txt`;
- `snapshot_abi.h` hoặc Python serializer tương ứng;
- version PySide6/Qt SDK;
- cấu hình compiler hoặc build configuration;
- checkout sang commit có native source khác với DLL đang có.

Thay đổi Python/QML không đụng native có thể không cần build trong vòng lặp
nhanh, nhưng gate cuối vẫn luôn là:

```powershell
.\scripts\ci-local.ps1 -Full
```

`-SkipNativeBuild` chỉ dùng chẩn đoán Python; không phải bằng chứng đủ để commit,
merge hay release.

## 4. Deploy/stage cho desktop package

Build Release trước:

```powershell
.\scripts\build-native-chart.ps1 -Configuration Release
```

Stage bằng install contract của CMake. Ví dụ stage vào thư mục disposable dưới
`build/`:

```powershell
$stageRoot = Join-Path $PWD "build\native-chart-stage"
cmake --install .\build\native-chart `
    --config Release `
    --prefix $stageRoot
```

Kết quả phải nằm tại:

```text
<stageRoot>/qml/native-chart-runtime.json
<stageRoot>/qml/Sagittarius/NativeChart/qmldir
<stageRoot>/qml/Sagittarius/NativeChart/sagittarius_native_chart.dll
<stageRoot>/qml/Sagittarius/NativeChart/sagittarius_native_chartplugin.dll
<stageRoot>/qml/Sagittarius/NativeChart/sagittarius_native_chart.qmltypes
```

Với frozen/portable app, `<app-root>/qml` phải ở cạnh executable vì runtime
loader tìm `<exe-directory>/qml`. Có thể install trực tiếp vào package root:

```powershell
cmake --install .\build\native-chart `
    --config Release `
    --prefix "C:\path\to\packaged-app"
```

Để kiểm tra một stage mà không copy vào app:

```powershell
$env:SAGITTARIUS_NATIVE_QML_IMPORT_PATH = `
    (Resolve-Path ".\build\native-chart-stage\qml").Path
$env:PYTHONPATH = (Resolve-Path "..").Path

& .\.venv\Scripts\python.exe -c `
    "from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import resolve_native_chart_runtime; print(resolve_native_chart_runtime(required=True))"
```

Lưu ý: `cmake --install` chỉ stage native QML module. Nó không đóng gói Python
application, PySide6 Qt runtime DLLs, config, icons hoặc database. Công cụ đóng
gói desktop vẫn phải bundle các phần đó.

## 5. Runtime lookup order

Runtime loader tìm QML import root theo thứ tự:

1. `SAGITTARIUS_NATIVE_QML_IMPORT_PATH`;
2. `src/presentation/ui/native_qml` nếu package source có bundle tại đây;
3. `<exe-directory>/qml` với frozen app;
4. `build/native-chart/qml` trong development checkout.

Mỗi candidate phải có `native-chart-runtime.json` đúng module URI, Qt version
và snapshot ABI. Không copy riêng một DLL: QML module chỉ hợp lệ khi đủ toàn bộ
bộ artifact ở trên.

## 6. Troubleshooting nhanh

### `Qt SDK ... was not found`

Cài đúng Qt MSVC SDK hoặc đặt `SAGITTARIUS_QT_ROOT`.

### `Qt SDK X does not match PySide6 Y`

Đồng bộ version. Không bypass check và không đổi manifest bằng tay.

### `Sagittarius.NativeChart is required but unavailable`

Chạy lại:

```powershell
.\scripts\build-native-chart.ps1 -Clean
```

### App vẫn dùng code native cũ

Đóng toàn bộ process UI trước khi rebuild vì Windows có thể đang giữ DLL.
Sau đó clean build và kiểm tra import root được in ra bởi script.

## 7. Quy tắc artifact

- Không commit `build/`, stage directory, DLL, CMake cache hoặc generated
  `.qmltypes`.
- Source of truth là `native/chart_renderer/`, CMake và snapshot serializer.
- Trước handoff/commit/merge: luôn chạy `ci-local.ps1 -Full`.

