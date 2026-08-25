"""
Chụp ảnh từng màn hình, để so sánh trước/sau một thay đổi thị giác.

Không phải test — không assert gì về đúng/sai. Nó là **dụng cụ** dùng lại
đúng bộ fixture `main_window`/`navigate` mà các test e2e đã dựng công phu
(xem docstring của chúng trong `conftest.py`: cancellation token, drain
thread pool, huỷ QTimer treo). Tự dựng lại app cho việc chụp ảnh sẽ phải
chép lại toàn bộ những cái bẫy đó, rồi trôi khỏi bản gốc.

Bị bỏ qua trừ khi bật `SEW_CAPTURE_SCREENSHOTS`, nên nó không chạy trong
CI và không làm chậm suite:

    SEW_CAPTURE_SCREENSHOTS=out/before \
        pytest tests/integration/presentation/ui/test_capture_screenshots.py

`EPIC-007D` là task **cố ý đổi pixel** và bắt buộc nộp ảnh trước/sau; đây
là thứ tạo ra chúng. `007F` sẽ cần lại.

⚠️ **Ảnh không so sánh được từng pixel một cách ngây thơ.** Vài màn hiển thị
thời gian hiện tại (ô DATA RANGE của Dev Board, dấu thời gian trong log), nên
hai lần chụp cách nhau vài phút đã khác nhau ở hàng trăm pixel — không liên
quan gì tới thay đổi được đo. Ở `007D` việc này đẻ ra delta max 586/765 và
suýt bị đọc nhầm thành lỗi màu; hoá ra là `09:37` với `09:49`. Khi so sánh,
xem **delta trung bình** (đổi màu thật là một dịch chuyển nhỏ, đều khắp ảnh)
chứ đừng xem delta max, hoặc bỏ qua các vùng có đồng hồ.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

#: Bật bằng cách đặt biến môi trường thành thư mục đích.
_OUTPUT_ENV = "SEW_CAPTURE_SCREENSHOTS"

#: Bốn màn trong phạm vi `EPIC-007`, theo đúng tên route mà sidebar dùng.
_ROUTES = ("dashboard", "data_management", "backtest", "settings")

pytestmark = pytest.mark.skipif(
    not os.environ.get(_OUTPUT_ENV),
    reason=f"đặt {_OUTPUT_ENV}=<thư mục> để chụp ảnh",
)


@pytest.mark.parametrize("route", _ROUTES)
def test_capture(qtbot, qapp, main_window, navigate, route):
    out_dir = Path(os.environ[_OUTPUT_ENV])
    out_dir.mkdir(parents=True, exist_ok=True)

    main_window.resize(1600, 1000)
    main_window.show()
    navigate(route)
    # Hai vòng: vòng đầu xử lý xong việc chuyển route, vòng sau để layout
    # đã đổi kịp vẽ lại trước khi grab() đọc pixel.
    qapp.processEvents()
    qapp.processEvents()

    target = out_dir / f"{route}.png"
    assert main_window.grab().save(str(target)), f"không lưu được {target}"
    print(f"đã chụp: {target}")
