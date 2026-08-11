# Nhiệm vụ: Segfault ngẫu nhiên khi chạy toàn bộ tests/integration/presentation/ui/

## 1. Mục tiêu

Root-cause và fix một segfault không ổn định (intermittent) chỉ xuất hiện khi
chạy **toàn bộ** `tests/integration/presentation/ui/` (~50-470+ test tuỳ
scope) trong **1 process** pytest duy nhất. Không phải bug logic — không
test nào tự fail vì assertion sai; đây là crash ở tầng native (Qt/PySide6),
rất có thể cùng loại bug object-lifetime đã từng gặp và fix một phần ở
BOT-034 (xem `Tasks/completed/BOT-034_dev_board_autostart_and_data_lifecycle.md`
§5 "Cạm bẫy đã dính khi verify").

## 2. Bối cảnh phát hiện

Phát hiện trong lúc verify task chuẩn hoá UI-state (migrate DevBoardPanel/
Sidebar/DatabaseScreen sang `StatefulButton`/`FieldBackground`/`BaseCard` từ
`sagittarius_engine`, xem commit `refactor(ui): migrate DevBoardPanel/Sidebar/
DatabaseScreen onto shared state components`). Mỗi test file/thư mục nhỏ chạy
riêng lẻ đều **pass 100%**, kể cả `tests/unit/` (466 tests). Chỉ khi chạy
`tests/integration/` (hoặc `tests/integration/presentation/ui/`) như một khối
lớn trong 1 process mới thấy crash.

## 3. Bằng chứng đã thu thập

- **Không deterministic theo test cụ thể**: lặp lại nhiều lần với **cùng một
  code state**, crash xảy ra ở test khác nhau mỗi lần — 1 lần tại
  `test_dev_board_load_more.py::test_a_second_edge_signal_before_the_first_settles_does_not_double_fetch`
  (dòng dot thứ 39), 1 lần khác tại
  `test_dev_board_known_gaps.py::test_strategy_dropdown_has_no_presenter_effect`
  (dòng dot thứ 21 trong 1 scope nhỏ hơn). Đặc điểm "crash ở vị trí khác nhau
  dù code giống hệt" là dấu hiệu kinh điển của memory corruption/dangling
  pointer, không phải lỗi logic trong 1 test cụ thể.
- **Không deterministic theo outcome**: bisect kỹ bằng `git stash` — cùng một
  code state (revert `Sidebar.qml`+`DevBoardPanel.qml`, giữ nguyên
  `Palette.py`/`dashboard_view_model.py`/`DatabaseScreen.qml`) chạy 2 lần cho
  2 kết quả khác nhau (1 lần CRASH, 1 lần PASS sạch). Tức là không có 1 file
  cụ thể nào "chắc chắn gây crash" hay "chắc chắn an toàn" — xác suất crash
  thay đổi theo state tích luỹ trong quá trình chạy, không theo code diff.
- **Tăng xác suất rõ rệt sau khi thêm UI-state migration**: với toàn bộ commit
  UI-state migration active, crash xảy ra 4/4 hoặc 5/6 lần thử (tuỳ scope) —
  cao hơn hẳn baseline (pristine code: 1/1 lần thử PASS sạch, nhưng sample
  size nhỏ nên chưa kết luận chắc baseline có bao giờ crash hay không).
- **Không cần đến toàn bộ suite để dựng lại** — có thể lặp lại (concentrate)
  bằng cách chạy lặp 1 test navigate-tới-Dev-Board nhiều lần trong 1 process
  (`pytest ... --count=N` từ `pytest-repeat`), vì `main_window`/`app_engine`
  fixture là function-scoped nên mỗi lần lặp tạo mới toàn bộ
  `MainWindow`→`Sidebar`→`DevBoardPanel` (và nhiều `QQuickWidget`/`QQmlEngine`
  riêng, xem `qml_host_view.py::create_quick_widget()` — mỗi lần gọi tạo
  `QQuickWidget()` MỚI, không share engine). Test cụ thể mỗi lần lặp tốn
  ~9-10s (đợi auto-start Live stream settle) — 150 lần lặp cần budget lớn,
  chưa kịp hoàn thành trong phiên làm việc này (dừng giữa chừng ở lần lặp thứ
  ~30-40, theo yêu cầu dừng lại của user).
- **Đã có precedent y hệt trong chính codebase này**: `tests/integration/
  presentation/ui/conftest.py`'s `main_window` fixture có hẳn 1 đoạn docstring
  dài mô tả 1 crash *đã từng reproduce thật* ("Windows access violation")
  gây ra bởi `ChartCard.viewport`/`ViewportController.__init__` không có C++
  parent (raw pointer từ `installEventFilter()` không được Qt quản lý vòng
  đời) — đã fix bằng cách gọi `card.cleanup()` tường minh ở fixture teardown.
  Rất có thể segfault lần này là cùng 1 lớp bug (hoặc 1 biến thể chưa được
  patch hết) trong cùng khu vực code, bị "lộ" nhiều hơn vì
  `StatefulButton`/`FieldBackground`/`BaseCard` tăng số lượng
  `QQmlComponent` compile/instantiate/destroy mỗi lần navigate — nhiều
  QML object churn hơn mỗi test → xác suất trigger 1 race điều kiện đã tồn
  tại từ trước cao hơn, KHÔNG hẳn là 1 bug hoàn toàn mới do
  `StatefulButton`/`BaseCard` tự thân gây ra (2 component này là QML thuần —
  `Button`/`Rectangle`-based, không tạo custom `QObject` Python nào với
  `parent=None` thủ công).
- **Không lấy được native backtrace thật**: `ulimit -c` = 0 mặc định, hệ
  thống route crash qua `apport` (không dump core file dùng được cho process
  Python/Qt bị crash). Thử chạy dưới `gdb` với `debuginfod` (để tự tải debug
  symbols) nhưng sandbox này không có network ra ngoài — `debuginfod` timeout
  liên tục, tốn hết budget mà chưa chạy được `run`. Chạy dưới `gdb` không
  debuginfod thì cực chậm (ptrace overhead cho mỗi thread create/exit — app
  này spawn ~6 thread/test qua `ThreadManagerExtension`/`scheduler`/
  `async_runtime`/`tcp_log_viewer_handler`) — chỉ chạy được ~2-3 test trong
  280s, không đủ để chạm tới vùng test hay crash (~test #21-39).

## 4. Hướng điều tra tiếp theo (đề xuất, chưa làm)

1. **Dựng lại nhanh hơn bằng `pytest-repeat`** (`pip install pytest-repeat`,
   đã cài trong venv debug — xem có sẵn không, nếu không thì cài lại):
   ```
   pytest tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_strategy_dropdown_has_no_presenter_effect --count=150 -q
   ```
   Test riêng lẻ này ~9-10s/lần vì phải đợi auto-start settle — cân nhắc tìm
   1 test rẻ hơn (không có Dev Board auto-start wait) nhưng vẫn tạo
   `MainWindow`+`Sidebar` mới mỗi lần, để rút ngắn thời gian dựng lại.
2. Khi dựng lại được nhanh và ổn định hơn, chạy dưới `gdb` **không bật
   debuginfod** (`set debuginfod enabled off` — tránh treo vì sandbox không
   có mạng), chấp nhận backtrace thiếu symbol tên hàm nhưng vẫn thấy được
   library/offset nào đang thực thi lúc crash — đủ để khoanh vùng
   Qt/PySide6/shiboken hay code Python.
3. Nếu môi trường THẬT (máy dev Windows, theo `R9` trong các task file khác)
   có sẵn debug symbols/Visual Studio debugger, ưu tiên dựng lại ở đó thay vì
   Linux sandbox này — nhiều khả năng nhanh và có symbol đầy đủ hơn.
4. Nghi vấn hàng đầu để kiểm tra trước: liệu `main_window` fixture's
   teardown (`card.cleanup()` loop) có cần mở rộng để cover thêm object mới
   nào không — kiểm tra `StatefulButton`/`BaseCard`/`FieldBackground` instances
   có bị Qt tự động dọn đúng thứ tự khi `Sidebar`/`DevBoardPanel`'s
   `QQuickWidget` bị `deleteLater()`, hay có raw-pointer/event-filter nào
   tương tự `ViewportController` đang thiếu parent.
5. Thử tăng `qtbot.wait(...)` sau `window.deleteLater()` trong fixture
   teardown (hiện là 100ms) — nếu tăng lên rõ rệt giảm/loại bỏ được crash,
   xác nhận đây đúng là race điều kiện teardown chưa kịp drain hết, không
   phải bug logic thật.

## 5. Không thuộc phạm vi

- Không phải bug trong UI-state migration's *logic* — mọi test assertion đều
  đúng, kể cả khi crash không xảy ra thì kết quả pass 100%.
- Không block việc merge/dùng `StatefulButton`/`FieldBackground`/`BaseCard` —
  commit migration đã được duyệt và push; đây là task riêng để điều tra thêm.

## 6. Phụ thuộc

- Không phụ thuộc task nào khác trực tiếp, nhưng liên quan mật thiết tới
  BOT-034 §5 (cùng lớp bug, cùng file `conftest.py`'s `main_window` fixture).
