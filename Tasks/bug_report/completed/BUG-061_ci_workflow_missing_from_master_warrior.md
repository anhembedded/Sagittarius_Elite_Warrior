# BUG-061 — CI không chạy: workflow biến mất khỏi `master-warrior`

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | ✅ Đã sửa — 2026-08-26 |
| **Mức độ** | Cao (mọi PR merge suốt 16 ngày không có gate nào) |
| **User báo** | 2026-08-26 — "cai ci cd bi block gi roi, hay fix giup" |

## Hiện tượng

GitHub Actions không chạy trên bất kỳ push hay PR nào vào `master-warrior`.
Run cuối cùng của workflow `Binance Bot CI` là **2026-08-10**, tức 16 ngày
trước. Trên trang Actions repo trông "sạch" đơn giản vì không có gì đang kiểm
tra cả.

Nặng hơn: **mọi run trong toàn bộ lịch sử repo đều `failure`.** Ruff và pytest
chưa từng chạy trên CI một lần nào.

## Nguyên nhân — ba lỗi chồng lên nhau

Phải gỡ cả ba mới có một run chạm được tới test.

### 1. File workflow không tồn tại trên `master-warrior`

```
$ git ls-tree -r --name-only origin/master-warrior -- .github
(rỗng)
```

Nhánh này **không có thư mục `.github/` nào cả**. File `ci.yml` chỉ tồn tại
trên nhánh `main` cũ, và `main` giờ cũng không còn là remote branch. Workflow
đã mất khi repo đổi nhánh mặc định sang `master-warrior`.

### 2. Trigger trỏ vào hai nhánh đã chết

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
```

Cả `main` lẫn `develop` đều không còn tồn tại. Kể cả khôi phục nguyên văn file
cũ thì cũng không có gì kích hoạt nó.

### 3. Bước cài engine chết vì một submodule private

Đây mới là lý do mọi run lịch sử đều đỏ. Log run #48 (`31414282515`):

```
Collecting git+https://github.com/anhembedded/Sagittarius-Engine.git
  Cloning ... to /tmp/pip-req-build-g7w5c0gf
  Resolved ... to commit a5ba7e6d
  Running command git submodule update --init --recursive -q
  fatal: could not read Username for 'https://github.com': No such device or address
  fatal: clone of 'https://github.com/anhembedded/Sagittarius_LogViewer.git'
         into submodule path '.../tools/Sagittarius_LogViewer' failed
ERROR: Failed to build 'git+https://github.com/anhembedded/Sagittarius-Engine.git'
```

Repo engine **public** (clone chính nó thành công, resolve ra commit thật).
Nhưng `pip install git+…` **luôn** chạy `git submodule update --init
--recursive` sau khi clone, và engine có submodule **private**
`tools/Sagittarius_LogViewer` mà runner không xác thực được. Không có flag pip
nào tắt bước đó.

## Bản sửa

`.github/workflows/ci.yml` trên `master-warrior`:

- **Trigger** đổi sang `master-warrior`.
- **Engine** clone thủ công **không kèm submodule**, rồi `pip install` từ thư
  mục local — pip không đụng tới git khi cài từ đường dẫn. `Sagittarius_LogViewer`
  là công cụ dev, không phải runtime dependency, nên bỏ qua nó không mất gì cho test.
- **Qt** thêm `QT_QPA_PLATFORM: offscreen` và các thư viện hệ thống PySide6
  `dlopen()` (`libegl1`, `libgl1`, `libxkbcommon-x11-0`, nhóm `libxcb-*`…).
  Chưa từng cần trước đây chỉ vì chưa run nào đi xa tới mức `import PySide6`.
- **`PYTHONPATH=..`** giữ nguyên và vẫn đúng: test import
  `Sagittarius_Elite_Warrior.src…` tức chính thư mục checkout như một package,
  và tên thư mục checkout khớp tên package.

## Cố ý KHÔNG đưa vào

**Mypy.** Gate local (`scripts/ci-local.ps1`) có chạy mypy, nhưng trên master
sạch nó đang đỏ sẵn 2 lỗi:

```
scripts/preview_qml.py:106: error: Argument 1 to "configure_app_qml" has
  incompatible type "dict[str, str | float]"; expected "dict[str, str]"
scripts/shutdown_database_sync_probe.py:116: error: Argument 1 to
  "get_theme_bridge" has incompatible type "dict[str, str | float]";
  expected "dict[str, str] | None"
```

Đã đối chiếu bằng `git stash` — có sẵn trên base, không phải do thay đổi nào
của lần này. Thêm mypy vào CI bây giờ sẽ làm CI đỏ ngay từ commit đầu, tức là
đổi một cổng-không-chạy lấy một cổng-luôn-đỏ. Cả hai đều nằm trong `scripts/`
(không phải `src/`) và đều là cùng một kiểu lỗi: `Palette.as_ui_dict()` trả
`dict[str, str | float]` trong khi hàm nhận nhận `dict[str, str]`. Sửa xong 2
lỗi đó rồi hãy thêm mypy step — nên là task riêng.

## Chưa kiểm chứng được ở đây

Workflow chỉ chạy thật khi đã push. Ba lỗi trên đều đã xác định từ bằng chứng
thật (cây git của nhánh, nội dung file, log job của run #48), và toàn bộ suite
đã chạy xanh tại chỗ bằng đúng lệnh pytest mà workflow gọi — nhưng **bản thân
GitHub Actions run thì chưa quan sát được**. Run đầu tiên sau khi merge là chỗ
xác nhận.
