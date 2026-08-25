# 🔬 Đánh giá Tầng Sanity & Phương án Khắc phục

> [!NOTE]
> **Báo cáo SA — trả lời câu hỏi: "sanity không bắt được user case cơ bản".**
>
> Kết luận ngắn: **đúng, nhưng không phải vì sanity yếu.** Có 3 nguyên nhân
> tách bạch, và chỉ 1 trong 3 là lỗi của tầng sanity. Hai cái còn lại quan
> trọng hơn nhiều, và một trong số đó là thứ đang khiến **49% tầng
> integration bị tắt khỏi mọi lần chạy CI mặc định**.
>
> Kế thừa [`qa_testing_strategy_report.md`](qa_testing_strategy_report.md)
> (BOT-015, thời điểm 477 test) — báo cáo này đo lại trên hiện trạng
> 2026-08-25 (~1.700 test) và đi vào đúng tầng Sanity.

---

## 1. 📐 Phương pháp & giới hạn

**Nguồn dữ liệu** (đã verify từng cái, không suy đoán):

- Toàn bộ 9 file `tests/sanity/` — đọc hết, không sampling.
- `scripts/ci-local.ps1` — cách tier được gọi thật, không theo mô tả trong docs.
- `.agents/rules/ci-rule.md` §6 (four-level test contract), `code-rule.md` §4.
- 43 hồ sơ bug trong `Tasks/bug_report/` — nguồn escape analysis ở §5.
- `src/main.py`, `src/presentation/ui/app_bootstrapper.py`, `main_window.py` —
  đối chiếu "cái sanity boot" với "cái production boot".

**Giới hạn phải nói rõ:** báo cáo này là **phân tích tĩnh + đối chiếu hồ sơ
bug**, không phải kết quả chạy suite. Môi trường viết báo cáo không có
`PySide6` lẫn `sagittarius_engine`, và CI của dự án là PowerShell/Windows-only
(`ci-local.ps1`). Mọi con số test đều đếm từ source; mọi khẳng định hành vi
đều dẫn `file:line`. Các đề xuất ở §6 **chưa được chạy CI** — cần verify theo
đúng `ci-rule.md` trước khi merge.

---

## 2. 📊 Hiện trạng tầng Sanity — số liệu

| Tier | Test function | File | Chạy trong `-Full` mặc định? |
| :--- | ---: | ---: | :---: |
| `tests/unit/` | 1.334 | 153 | ✅ (song song, 6 worker) |
| `tests/integration/` (không tính UI) | 37 | 15 | ✅ |
| `tests/integration/presentation/ui/` | **36** | 8 | ❌ **`--ignore` (BOT-038)** |
| `tests/sanity/` | 19 (→ **38 case** sau parametrize) | 9 | ✅ (tuần tự, job nền) |

Con số 38 khớp đúng với ghi nhận trong `BUG-041`/`BUG-042` (2026-08-24: *"38
sanity"*), nên đây là hiện trạng thật, không phải đếm nhầm.

**38 case đó thực sự assert cái gì:**

| Loại assertion | Số case | Tỷ lệ |
| :--- | ---: | ---: |
| `container.resolve(X)` → `isinstance` / tra nội dung registry | ≈24 | **63%** |
| Introspection class-level (thread-affinity `unprotected_mutators`) | 5 | 13% |
| Dựng View + Presenter thật | 4 | 11% |
| Boot chạy sạch / log health / AST circular-import | 5 | 13% |

**Chi phí:** fixture `booted_app` là **function-scoped** ở 5/6 file → tier boot
lại toàn bộ app thật khoảng **24 lần** để lấy 38 assertion. Đây là lý do nó
phải chạy tuần tự trong job riêng.

---

## 3. 🎯 Ba chẩn đoán (TL;DR)

### 🔴 Chẩn đoán 1 — Hợp đồng tầng Sanity đang viết cho một kiến trúc app **không còn tồn tại**

`code-rule.md` §4 quy định sanity phải: *"boot the real app, construct real
View + Presenter, assert real DI resolves and **`quick_widget.errors() == []`**"*.

Nhưng **EPIC-006 đã migrate toàn bộ UI khỏi QML sang QtWidgets.** Xác nhận:

- `grep -rn "QQuickWidget\|QmlHostView" src --include=*.py` → **chỉ còn trong
  comment**, không còn một chỗ dùng thật nào.
- `app_bootstrapper.py:105` ghi thẳng: *"EPIC-006F: no QML left in this app at
  all (the last consumer, the native chart, was deleted outright)"*.
- 22 file `.qml` vẫn nằm trong `src/` nhưng ở trạng thái *"kept on disk,
  unloaded"* (`sidebar.py:141`, `data_management_view.py:238`,
  `settings_view.py:43`).

Hệ quả dây chuyền:

1. **0/38 sanity test có `errors()`** (`grep -rn "errors()" tests/sanity/` →
   rỗng). Điều khoản bắt buộc của rule chưa từng được thực thi ở tầng nó quy
   định — và bây giờ thì **không thể thực thi được nữa**, vì không còn
   `QQuickWidget` nào để hỏi.
2. `tests/unit/.../test_preview_fixtures_exist.py::test_all_discovered_previews_build_cleanly`
   vẫn assert `widget.errors() == []` và duyệt `findChildren(QQuickWidget)` —
   sau EPIC-006 cả hai đều **vacuous**: luôn rỗng, luôn xanh, không còn canh gì.
3. `tests/conftest.py` có fixture session-autouse `_configure_app_qml` cấu hình
   nguyên một stack QML mà production **không còn gọi nữa**
   (`app_bootstrapper.py:105` nói rõ *"which no longer needs calling here"*).
   Test harness đang dựng một môi trường khác production.
4. Hai file `test_qml_imports_match_engine_qmldir.py` và
   `test_qml_shared_foundation.py` đang canh 22 file QML chết. Trớ trêu: file
   thứ nhất được thêm vào chính là để chặn tái diễn `BUG-035`.

**Đây là gốc rễ của cảm giác "sanity không làm tốt việc của nó":** tầng này
đang canh một thứ không còn tồn tại, và chưa ai viết lại hợp đồng cho thứ
đang tồn tại (QtWidgets).

### 🔴 Chẩn đoán 2 — Tầng chứng minh user journey **đang bị tắt**, không phải đang thiếu

Test hành trình người dùng **có tồn tại**: `tests/integration/presentation/ui/`
— 36 test function, gồm navigation, click "Sync Current" thật, walkthrough
toàn bộ Dev Board, Save trên màn hình Settings.

Chúng bị `--ignore` khỏi mọi lần chạy `-Full` mặc định
(`ci-local.ps1:359-361`), vì `BOT-038` — segfault native Qt/PySide6 không ổn
định. `-IncludeFlakyUi` là opt-in, và theo `ci-rule.md` §3 thì chỉ chạy *"when
a change touches that directory"*.

Kết quả: **tầng integration chạy mặc định chỉ còn 37 test function, so với
1.334 unit test — 2,7%.** Kim tự tháp không phải hình tháp, nó là một cây
kim: rất nhiều unit, gần như không có gì chứng minh các mảnh ghép lại thành
một app dùng được.

> **Không có phương án nào ở tầng sanity bù được việc này.** Sanity bị chính
> hợp đồng của nó cấm click, cấm dispatch, cấm mạng (`ci-rule.md` §6 mục 3).
> Nó *không được phép* bắt user case.

Điểm đáng chú ý: `BOT-038` §3 chỉ nghi phạm là *"mỗi lần lặp tạo `QQuickWidget`/
`QQmlEngine` MỚI, không share engine"*. **Sau EPIC-006, `QQuickWidget` đã bị xoá
sạch khỏi app.** Rất có khả năng BOT-038 đã tự khỏi và không ai kiểm tra lại.
Xem P2.0 ở §6 — đây là hành động có tỷ lệ lợi ích/chi phí cao nhất trong cả
báo cáo này.

### 🟡 Chẩn đoán 3 — Trong phạm vi việc của chính nó, sanity cũng có lỗ hổng thật

Chi tiết ở §4. Tóm tắt: tier chỉ dựng **2/4 màn hình**, có 1 test rỗng luôn
xanh, 1 docstring nói dối assertion, không bắt được Qt message, fixture nhân
bản 6 lần và đã drift thật, và có thể **skip im lặng toàn bộ** khi thiếu Qt.

---

## 4. 🔍 Mười phát hiện cụ thể

### F1 — `tests/integration/test_ui_sanity.py` là một test **rỗng**, luôn xanh

```python
def test_sanity_ui_boot_and_navigation():
    print("Sanity Check GUI Setup...")
```

8 dòng, không một assertion. Tên hứa "boot and navigation". Đây là fake-green
thuần túy — nó chỉ làm số đếm test đẹp lên.

### F2 — Điều khoản bắt buộc của `code-rule.md` §4 chưa từng được thực thi

`quick_widget.errors() == []`: **0/38** sanity case. Xem Chẩn đoán 1.

### F3 — Docstring nói một đằng, assertion làm một nẻo

`tests/sanity/test_health_boot_and_ui_sanity.py:106-112`:

```python
def test_real_mainwindow_construction_initializes_health_cleanly(...):
    """Assert constructing the full MainWindow renders cleanly with zero QML errors."""
    window = MainWindow(app)
    assert window is not None
```

`MainWindow.__init__` không bao giờ trả `None`. Test này **về mặt logic không
thể fail** trừ khi có exception. Nó không kiểm tra "zero QML errors" như
docstring khẳng định. Ai đọc tên test và tin nó sẽ tin nhầm.

### F4 — Sanity chỉ dựng **2/4 màn hình**, và **0 modal**

`PresenterManager` là lazy-loading (`main_window.py:130`), và
`MainWindow.__init__` chỉ gọi `switch_screen("dashboard")` (`main_window.py:119`).

| Màn hình | Được dựng ở sanity? |
| :--- | :---: |
| Dev Board (dashboard) | ✅ (`test_health_boot_and_ui_sanity.py` + qua MainWindow) |
| Backtest | ✅ (`test_backtest_screen_ui_sanity.py`) |
| **Database (data_management)** | ❌ **chưa bao giờ** |
| **Settings** | ❌ **chưa bao giờ** |

Với Database, sanity chỉ resolve 9 handler trong container
(`test_database_screen_di_sanity.py`) rồi dừng — **không dựng View lấy một
lần**. `BUG-019` (`GapInspectorModal` không dựng được vì `import
Sagittarius.Theme` không tồn tại — P1) rơi đúng vào khe này. Chính hồ sơ
BUG-019 đã đề nghị *"cân nhắc bổ sung sanity/preview check cho mọi modal
mới"* — chưa làm.

### F5 — 63% tier chứng minh "đã đăng ký", không chứng minh "gọi được"

`container.resolve(X)` trả về instance ≠ handler đó chạy được. Hai lớp lỗi
sống sót qua nó:

- `BUG-020` — vá lỗ hổng thành công vẫn báo lỗi vì gọi `_run_check_status()`
  **không tồn tại**. Handler resolve sạch.
- `BUG-026`/`BUG-027` — test double thiếu 7/12 method của `IMarketDataRepository`.
  Bắt được nhờ **mypy**, không phải nhờ test.

### F6 — Allowlist viết tay, không có drift guard (dù pattern đúng đã có sẵn trong cùng tier)

`_BACKTEST_COMMANDS` (`test_backtest_screen_di_sanity.py:54`) và
`_DATABASE_COMMANDS` (`test_database_screen_di_sanity.py:54`) là danh sách gõ
tay. Chúng bắt được thứ bị **xoá** khỏi `binance_bot_module.py`, nhưng **mù
hoàn toàn** với use case **mới thêm mà quên đăng ký** — mà đó mới là ca hay
xảy ra.

Đối lập ngay trong cùng thư mục: `test_view_model_thread_affinity_sanity.py:60`
có hẳn `test_every_view_model_subclass_in_this_app_is_covered_by_this_list()`
— quét `__subclasses__()` thật và so với danh sách tay. **Pattern đúng đã tồn
tại, chỉ chưa được nhân bản sang 2 file DI.** Đây là fix rẻ nhất trong báo cáo.

### F7 — Không có `tests/sanity/conftest.py` → fixture nhân bản 6 lần và **đã drift thật**

| File | Config load | Patch WebSocket | Fixture scope |
| :--- | :--- | :---: | :--- |
| `test_bootstrapper_di_sanity.py` | app + user | ✅ | function |
| `test_backtest_screen_di_sanity.py` | app + user | ✅ | function |
| `test_backtest_screen_ui_sanity.py` | app + user | ✅ | function |
| `test_asset_preflight_sanity.py` | app + user | ✅ | (inline ×2) |
| `test_health_boot_and_ui_sanity.py` | app + user | ✅ | function |
| **`test_database_screen_di_sanity.py`** | app + user | ✅ | **module** |
| **`test_health_sanity.py`** | **chỉ app** | ❌ **không patch** | (inline) |

`test_health_sanity.py` là test sanity **duy nhất** boot mà không patch
`AsyncClient`/`BinanceSocketManager`. Một trong hai điều đang đúng, và cả hai
đều là lỗi:

- hoặc nó **thật sự chạm mạng** khi boot → tier sanity có một điểm
  non-deterministic không ai biết;
- hoặc thiếu `user_config.json` khiến nó boot một composition root **khác** 5
  test kia → nó đang xác thực một cấu hình production không dùng.

### F8 — Thiếu PySide6 = **skip im lặng**, tier vẫn báo xanh

`tests/conftest.py:53`:

```python
except ImportError:
    pytest.skip("PySide6 not installed — skipping UI tests")
```

Trên môi trường thiếu Qt, 4 case dựng UI (11% tier) biến mất **không tiếng
động** và `-SanityOnly` vẫn exit 0. Với một tier có nhiệm vụ *"chứng minh
composition health"*, môi trường thiếu Qt phải là **FAIL**, không phải SKIP.
(`BUG-043` — `run-ui.ps1` không import được engine local — đúng lớp "môi
trường hỏng nhưng test không kêu".)

### F9 — Log scan không nhìn thấy Qt message

`Invoke-RunLogScan` (`ci-local.ps1:103`) grep `- (WARNING|ERROR|CRITICAL) -`
— đúng format `logging` của Python. Nhưng Qt phát cảnh báo qua kênh riêng:

- `qt.qml: Unable to assign [undefined] to double` → **BUG-028**
- `QBasicTimer::start: Timers cannot be started from another thread` → **BUG-031 (P1)**

Không khớp pattern nào cả. Và **không một file test nào trong repo dùng
`qInstallMessageHandler`** (grep toàn repo → 0 hit). Toàn bộ kênh chẩn đoán
của Qt hiện **không được quan sát ở bất kỳ tầng nào**.

### F10 — Không có sanity cho **shutdown**

`app.stop()` chỉ nằm trong teardown fixture, không có assertion nào. Nếu nó
treo, test **hang** chứ không fail — tệ hơn.

Ba bug treo shutdown, hai trong đó P1, cả ba đều do user báo:
`BUG-007`, `BUG-023`, `BUG-041`. `MainWindow.shutdown()` /
`closeEvent()` (`main_window.py:121-127`) chưa từng được gọi ở tầng sanity.
Chính `BUG-007` §"Why sanity missed it" đã ghi nhận điều này và kết luận giữ
nguyên hiện trạng.

---

## 5. 📉 Phân tích thoát lỗi — 43 bug

Phân loại toàn bộ `Tasks/bug_report/` theo lớp lỗi, và tầng **đáng ra** phải bắt:

| Lớp lỗi | Bug | SL | Tầng đáng ra phải bắt | Sanity có quyền đụng? |
| :--- | :--- | ---: | :--- | :---: |
| Render/hiển thị sai | 002,003,004,005,006,009,012,014,021,032,034,037,038,039 | **14** | Desktop E2E / visual | ❌ cấm |
| Thread / lifecycle / shutdown treo | 001,007,011,013,023,031,033,041,042 | **9** | Sanity (mở rộng) + Integration | 🟡 một phần |
| Hạ tầng test flaky | 015,016,029,030,036,040,043 | 7 | — (meta) | ❌ |
| Hành động không có tác dụng | 008,010,017,018,020 | **5** | Integration (user journey) | ❌ cấm |
| **QML / module import vỡ** | **019,028,035** | **3** | **Sanity** | ✅ **đúng việc** |
| Drift interface/port | 026,027 | 2 | mypy (đã bắt) | ❌ |
| Hiệu năng / bộ nhớ | 024,025 | 2 | Benchmark tier | ❌ |
| Logic domain sai | 022 | 1 | Unit | ❌ |

**Đọc bảng này ra hai câu:**

1. **Chỉ 3/43 (7%) bug nằm trong đúng thẩm quyền của tầng sanity — và sanity
   trượt cả 3.** Đó là phần lỗi thật của tier, và F4 + F9 giải thích chính
   xác tại sao (không dựng màn hình Database → BUG-019; không nghe Qt message
   → BUG-028; không có "dựng mọi màn hình" → BUG-035).
2. **19/43 (44%) bug thuộc hai lớp mà sanity bị *cấm* đụng vào** (render sai +
   hành động không tác dụng). Đây chính là "user case cơ bản" mà anh thấy lọt.
   Việc chúng lọt **không phải lỗi của sanity** — đó là hệ quả trực tiếp của
   Chẩn đoán 2: tầng chứng minh chúng đang bị tắt.

Thêm một dữ kiện đáng lo: nhiều hồ sơ bug ghi rõ CI xanh sạch ngay tại thời
điểm bug đang sống. `BUG-038`: *"1789 unit + 54 sanity, sạch"* — user phát
hiện bằng mắt. `BUG-039`: *"1800 passed / 54 sanity — không test nào vỡ, tức
**không có test nào từng khẳng định mặc định** đó là đúng"*. Coverage 93% cùng
tồn tại với 43 bug. **Coverage và số lượng test đã bão hoà giá trị tín hiệu ở
dự án này.**

---

## 6. 🛠️ Phương án khắc phục

Xếp theo tỷ lệ lợi ích/chi phí, không theo thứ tự chẩn đoán.

### P2.0 — 🚩 Làm cái này TRƯỚC MỌI THỨ: kiểm chứng lại BOT-038 (chi phí: 1 lần chạy)

```powershell
.\scripts\ci-local.ps1 -Full -IncludeFlakyUi
```

Chạy 5 lần, ghi lại kết quả.

**Lý do:** `BOT-038` §3 kết luận nghi phạm là *"mỗi lần lặp tạo
`QQuickWidget`/`QQmlEngine` MỚI, không share engine"* — cùng lớp với crash
object-lifetime đã fix một phần ở BOT-034. **EPIC-006 đã xoá sạch
`QQuickWidget` khỏi app.** Nếu BOT-038 đã tự khỏi, một lệnh này mở khoá lại
**36 test hành trình người dùng = 49% tầng integration**, và giải quyết phần
lớn nhất của câu hỏi "tại sao user case cơ bản lọt".

Đây là hành động rẻ nhất và có đòn bẩy lớn nhất trong toàn bộ báo cáo.

- ✅ **Nếu xanh 5/5:** bỏ `--ignore` ở `ci-local.ps1:359-361`, đóng BOT-038,
  cập nhật `ci-rule.md` §3. Xong 44% escape.
- ❌ **Nếu vẫn crash:** BOT-038 lên P1 và trở thành task chặn của cả roadmap
  chất lượng. Hướng fix ưu tiên: chuyển `main_window`/`app_engine` fixture
  (`tests/integration/presentation/ui/conftest.py`) sang session-scope với
  teardown tường minh, thay vì function-scope dựng lại toàn bộ cây widget mỗi test.

### P0 — Chặn fake-green (≈0,5 ngày)

Làm trước khi thêm bất kỳ test mới nào — nếu không, drift và fake-green sẽ được
nhân bản theo.

| # | Việc | Fix |
| :--- | :--- | :--- |
| **P0.1** | F1 — test rỗng | Xoá `tests/integration/test_ui_sanity.py`. Nội dung nó hứa đã được `test_sanity_ui_e2e.py` làm thật. |
| **P0.2** | F7 — fixture nhân bản & drift | Tạo `tests/sanity/conftest.py`: **một** fixture `booted_app` **session-scope**, load đúng 2 file config như `app_bootstrapper.py:67-69` (kèm `writable=True`), patch WebSocket nhất quán. Xoá 6 bản sao. Phụ lợi: **24 lần boot → 1**, tier nhanh lên khoảng một bậc độ lớn. |
| **P0.3** | F8 — skip im lặng | Trong `tests/sanity/conftest.py`, override `qapp`: thiếu PySide6 → `pytest.fail`, không `skip`. Với tier "composition health", môi trường hỏng là kết quả hợp lệ và phải đỏ. |
| **P0.4** | F3 — docstring nói dối | Sửa `test_real_mainwindow_construction_initializes_health_cleanly` — sau P1.2 nó sẽ có assertion thật để mà giữ. |

### P1 — Viết lại hợp đồng Sanity cho kiến trúc QtWidgets (≈2–3 ngày)

| # | Việc | Fix |
| :--- | :--- | :--- |
| **P1.1** | Chẩn đoán 1 — rule lỗi thời | Sửa `code-rule.md` §4: bỏ `quick_widget.errors() == []` (vô nghĩa sau EPIC-006), thay bằng *"dựng View + Presenter thật cho **mọi** route đăng ký trong `MainWindow._setup_router()`, dưới `qt_message_guard`, và đóng sạch"*. **Rule phải sửa trước code** — nếu không, mọi feature mới lại ship theo một hợp đồng đã chết. |
| **P1.2** | F9 — Qt message mù | `qt_message_guard` — fixture autouse toàn tier sanity, dùng `qInstallMessageHandler`, fail khi có `QtWarningMsg`/`QtCriticalMsg`/`QtFatalMsg`. Allowlist phải hẹp và khai báo tường minh từng dòng. **Đây mới là thứ thay thế đúng nghĩa cho `errors()`** trong thế giới QtWidgets, và nó bắt được cả `BUG-028` lẫn `BUG-031` — hai thứ `Invoke-RunLogScan` cấu trúc không thể thấy. |
| **P1.3** | F4 — 2/4 màn hình | `test_every_registered_route_constructs.py`: tách registry trong `MainWindow._setup_router()` thành hằng số module-level, rồi parametrize sanity **từ chính nó** (không phải allowlist tay). 2/4 → **4/4**, và tự động phủ mọi màn hình thêm sau này. |
| **P1.4** | F6 — allowlist mù với cái mới | Thay `_BACKTEST_COMMANDS` / `_DATABASE_COMMANDS` bằng scan: quét mọi class `*Command`/`*Query` dưới `src/application/use_cases/`, assert container resolve được. Sao chép nguyên pattern drift-guard đã có ở `test_view_model_thread_affinity_sanity.py:60`. |
| **P1.5** | F10 — shutdown không được canh | Sanity shutdown: boot → dựng `MainWindow` → `window.shutdown()` + `app.stop()` **có timeout**, assert không còn thread non-daemon sống. Lớp `BUG-007`/`023`/`041` (2×P1) hiện không có tầng nào canh. |
| **P1.6** | Chẩn đoán 1 — tài sản chết | 22 file `.qml` + `test_qml_imports_match_engine_qmldir.py` + `test_qml_shared_foundation.py` + fixture `_configure_app_qml` trong `tests/conftest.py` + các assertion `errors()`/`QQuickWidget` đã vacuous trong `test_preview_fixtures_exist.py`. Xoá, hoặc chuyển hẳn vào `Docs/legacy/`. **Test canh code chết không phải trung tính — nó làm loãng tín hiệu và tạo cảm giác an toàn giả.** |

### P2 — Đóng khe user journey (≈1 tuần, sau P2.0)

| # | Việc |
| :--- | :--- |
| **P2.1** | Nếu P2.0 xanh: nâng `tests/integration/presentation/ui/` thành gate bắt buộc trong `-Full`, bỏ `-IncludeFlakyUi`. |
| **P2.2** | Lập danh mục user journey lõi từ [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](../../Docs/PROJECT_INTENT_AND_USER_STORIES.md) + [`dev_board_user_end_test_cases.md`](dev_board_user_end_test_cases.md). Mỗi journey đúng **1** test, chạy **mọi** lần CI. Ưu tiên theo §5: lớp "hành động không có tác dụng" (5 bug) trước — rẻ nhất, deterministic nhất, không cần màn hình thật. |
| **P2.3** | Sửa `ci-rule.md` §6: nói thẳng rằng tầng Sanity **cấu trúc không thể** chứng minh user case, và Integration mới là tầng chịu trách nhiệm — để không ai đọc "38 sanity passed" rồi tưởng app dùng được. |

---

## 7. 📏 Chỉ số theo dõi

Bỏ "số test" và "coverage %" làm chỉ số sức khỏe — §5 đã cho thấy cả hai bão
hoà. Thay bằng:

| Chỉ số | Hiện tại | Mục tiêu |
| :--- | :---: | :---: |
| Test hành trình chạy mặc định trong `-Full` | **0** | ≥ 36 (P2.0) |
| Màn hình được dựng ở tầng Sanity | **2 / 4** | 4 / 4 |
| Qt message lọt qua CI | **không đo được** | 0 (đo được sau P1.2) |
| Tỷ lệ Integration / Unit (chạy mặc định) | **2,7%** | ≥ 10% |
| Escape rate: bug do **user** phát hiện / tổng bug mới, theo tháng | ~ chưa đo | giảm dần |

Chỉ số cuối là chỉ số thật duy nhất. Mọi thứ khác chỉ là proxy.

---

## 8. 🚫 Việc KHÔNG nên làm

- **Đừng nhét user journey vào `tests/sanity/`.** Tier này boot app thật, chạy
  tuần tự, và (trước P0.2) boot lại 24 lần. Đó là chỗ đắt nhất trong toàn suite
  để thêm hành vi. Sanity phải **nhanh và hẹp**; user journey thuộc Integration.
- **Đừng nâng ngưỡng coverage.** Coverage 93% đang cùng tồn tại với 43 bug và
  hai bug P1 mà *"không test nào từng khẳng định"* (`BUG-039`). Nâng ngưỡng
  chỉ đẻ thêm test cho code dễ test.
- **Đừng thêm test mới trước khi xong P0.1 + P0.2.** Fake-green và fixture
  drift sẽ được sao chép vào mọi file mới — đúng cách 6 bản sao hiện tại ra đời.
- **Đừng xoá `tests/sanity/` để gộp vào integration.** Tier này có giá trị
  thật và duy nhất: `test_view_model_thread_affinity_sanity.py` là guard chặn
  cả một lớp lỗi (BUG-001), và `test_circular_imports.py` bắt thứ pytest
  không bao giờ chạm tới. Vấn đề là **phạm vi và hợp đồng**, không phải sự tồn tại.

---

## 9. ✅ Tóm tắt hành động

1. **Chạy `.\scripts\ci-local.ps1 -Full -IncludeFlakyUi` ×5, ngay.** (P2.0)
   Kết quả quyết định toàn bộ ưu tiên phía sau.
2. Song song: P0.1–P0.4 (nửa ngày, không phụ thuộc kết quả trên).
3. Sửa `code-rule.md` §4 (P1.1) **trước** khi viết bất kỳ sanity test mới nào.
4. P1.2 (`qt_message_guard`) và P1.3 (dựng 4/4 màn hình) — hai thứ duy nhất
   trong tầng sanity thật sự đóng được lớp lỗi đã từng thoát ra ngoài.

> Câu trả lời một dòng cho câu hỏi ban đầu: **sanity không bắt được user case
> vì nó bị cấm làm việc đó — cái đáng lẽ phải làm việc đó thì đang bị
> `--ignore` khỏi CI, và hợp đồng của sanity thì được viết cho một kiến trúc
> QML mà app đã bỏ từ EPIC-006.**

---

*Báo cáo lập 2026-08-25. Toàn bộ số liệu đếm từ source tại commit `f27649e`.
Phân tích tĩnh — chưa chạy suite (xem §1, Giới hạn). Mọi đề xuất cần verify
qua `ci-local.ps1 -Full` trước khi merge.*
