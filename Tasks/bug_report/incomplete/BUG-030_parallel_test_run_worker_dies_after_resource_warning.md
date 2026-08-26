# BUG-030 — Full parallel test run (`-n 6`) dies mid-suite after `ResourceWarning: unclosed database`, no summary

**Reported:** 2026-08-21 — found running the real `.\scripts\ci-local.ps1
-Full` gate (previously this session only ran sequential `pytest` on
`tests/unit/`, which never exercises this).
**Severity:** 🟡 P2 — does not affect the shipped app (test-infrastructure
only), but silently breaks the mandatory local CI gate's "Tests" step under
its own default parallel settings, with no useful summary to diagnose from.
**Status:** 🔴 **Open — cơ chế rò rỉ đã được xác định và chứng minh bằng thực
nghiệm (2026-08-25, xem §"Điều tra 2026-08-25"); chưa pin được test cụ thể vì
cần chạy trên Windows. Đã có công cụ sẵn sàng chỉ đích danh file:line khi ai đó
chạy được trên Windows: `scripts/bug030_connection_leak_probe.py`.**

## Symptom

`.\scripts\ci-local.ps1 -Full` (6 xdist workers, `Sagittarius_Elite_Warrior/tests`
minus `sanity`/flaky-UI) — the "Tests" step fails with **no pytest summary
line at all** (no "`X passed, Y failed`"), `$LASTEXITCODE` non-zero. The
captured log's last lines before the script moves on to "Waiting for sanity
job to complete..." are:

```
Sagittarius_Elite_Warrior\tests\unit\application\services\test_strategy_factory.py::test_build_engine_wires_a_fresh_strategy_with_its_own_indicators
C:\Users\hoang\...\.venv\Lib\site-packages\_pytest\unraisableexception.py:33: ResourceWarning: unclosed database in <sqlite3.Connection object at 0x...>
```

No `PASSED`/`FAILED` line ever prints for that test — worker `gw0` simply
stops producing output. **Reproduced twice, independently, landing at the
exact same test on the exact same worker both times** (different SQLite
`Connection` object addresses each run, confirming genuinely separate runs,
not a duplicated log) — this is not flaky/random; it is a real, deterministic
condition given the same test collection and 6-worker split.

## What is confirmed, to narrow the search

- **Not caused by the test where it appears.** `test_strategy_factory.py::test_build_engine_wires_a_fresh_strategy_with_its_own_indicators`
  is pure domain code — `StrategyRegistry`, `Mock()`, no I/O, no SQLite
  anywhere in it or its imports. `pytest`'s `unraisableexception` plugin
  attaches an unraisable exception/warning (fired during GC finalization,
  which has no normal call stack to raise into) to whatever test happens to
  be running on that worker at the moment the finalizer runs — so this test
  is an innocent bystander, not the leak source.
- **Not caused by `test_shutdown_database_sync_process.py`** (runs
  immediately before, on the same worker, and is the most obvious suspect —
  real subprocess + real SQLite files). Read the file: it only does
  `subprocess.run([sys.executable, "-m", "...shutdown_database_sync_probe", mode], ...)`.
  Any SQLite connection opened *inside* that child process is reclaimed by
  the OS when the subprocess exits — it cannot leak a Python-level object
  back into the `gw0` worker process.
- **Not caused by `test_sqlalchemy_repository.py`'s standard fixture.**
  Every one of its 15 tests uses the same `repo` fixture, which already
  explicitly calls `db_manager.dispose_all()` in teardown with a comment
  acknowledging this exact class of bug ("Without this Python's GC fires
  ResourceWarning: unclosed database") — this file's own author already
  fixed it for every test that goes through `repo`.
- **Leading suspect, not confirmed:** `test_stream_klines_never_holds_more_than_a_bounded_number_of_rows_live`
  (BUG-025's backtest-side memory regression test, in the same
  `test_sqlalchemy_repository.py`) calls `gc.collect()` **repeatedly and
  explicitly** to sample live object counts. An explicit `gc.collect()`
  force-finalizes *every* currently-unreachable object process-wide, not
  just this test's own — so it is a very plausible place for a **pre-existing,
  unrelated leak from some earlier test/fixture** (anywhere in `gw0`'s test
  history, not necessarily in this file) to finally get collected and warned
  about, at a point that reads as "random" relative to the real leak's true
  origin. This is a hypothesis with strong circumstantial support (the
  `gc.collect()` calls are a uniquely aggressive pattern in this test suite,
  new from the same BUG-025 backtest-streaming work), not yet proven by
  bisection.

## Additional finding (2026-08-23, Linux dev machine)

Ran the identical `ci-local.ps1 -Full` gate (same scope — `unit` +
`integration` excl. `sanity`/flaky-UI, same default 6 xdist workers) on a
Linux machine: **1764 tests passed, zero `ResourceWarning`, no crash.** Same
command, same test collection, no repro — strong evidence this is
Windows-specific (most likely how Windows locks/handles open SQLite file
descriptors vs. POSIX, interacting with GC finalization timing under xdist).

Also audited every other test file that constructs a `DatabaseManager`/raw
`sqlite3`/SQLAlchemy engine directly, beyond what this report already ruled
out: `test_sqlalchemy_repository_gaps.py`, `test_security.py`,
`test_database_manager_shards.py`,
`test_bug010_sync_range_coverage_regression.py` (all in
`tests/unit/infrastructure/persistence/` or
`tests/integration/infrastructure/persistence/`). **All four already call
`dispose_all()` in a `finally`/fixture teardown** — same well-behaved pattern
as `test_sqlalchemy_repository.py`'s `repo` fixture. Ruled out, same as the
candidates already eliminated above.

**Consequence:** the "Suggested next steps" bisection plan below requires a
Windows machine to produce any signal — re-running on Linux only yields clean
passes regardless of which tests are deselected, since the condition never
triggers here at all.

## Suggested next steps (not yet attempted)

1. **Bisect by disabling tests, not by reading code further.** Run the same
   `Sagittarius_Elite_Warrior/tests` scope with `-n 6` repeatedly, each time
   deselecting (`--deselect`) a candidate block (start with everything in
   `tests/integration/infrastructure/persistence/` and `tests/integration/presentation/`),
   until the crash stops reproducing — narrows to the actual leaking
   fixture/test, not just a plausible one.
2. **Add a session-scoped autouse fixture** that runs `gc.collect()` +
   `warnings.catch_warnings(record=True)` after every test and reports which
   test's teardown first makes an unclosed-`sqlite3.Connection` object
   collectible — turns "some earlier test leaked it" into a specific file:line.
3. Once the real source is found, apply the same fix pattern already proven
   in this file's own `repo` fixture (`dispose_all()` in teardown) or in
   `BUG-023`'s completed report (which fixed the equivalent production-code
   class of this bug — `DatabaseManager`/`SqliteMarketDataRepository` engines
   not being disposed on shutdown).
4. Confirm the fix by re-running `ci-local.ps1 -Full` at least 3 times in a
   row with no `-SkipNativeBuild`/`-UnitOnly` shortcuts — this bug only
   manifests under the real full parallel scope, never under
   `pytest tests/unit/ -n 6` alone (verified: that narrower command passed
   cleanly, 1678/1678, in the same investigation that found this bug).

## Data point khác từ 2026-08-23 (`BUG-036`) — có thể liên quan, chưa xác nhận

Trong lúc xác minh [`BUG-036`](../completed/BUG-036_benchmark_crosshair_contract_synthetic_hover_race.md),
một lần chạy `-Full` (`logs/ci-local-20260823-203040.log`) hỏng ở
`tests/integration/presentation/test_database_user_flow.py::test_database_cancel_button_cancels_active_sync_flow`,
kèm `ListAvailableSymbolsQuery failed: object of type 'Mock' has no len()`.

**Cập nhật 2026-08-26:** data point này đã có **lần gặp thứ hai** — cùng đúng
test đó, cùng lớp lỗi (một `Mock` thô tới được code thật), cách nhau 3 ngày. Nay
mang mã [`BUG-062`](BUG-062_database_cancel_flow_test_is_flaky.md), nơi fixture
đã được đổi từ `Mock(spec=...)` sang một fake viết tay để bịt cả lớp. **Vẫn chưa
kết luận là cùng nguyên nhân với hồ sơ này** — triệu chứng khác nhau như đoạn
dưới đã ghi.

Cùng vùng (`-n 6` song song, tầng integration, đường Database Sync) nhưng
**triệu chứng khác hồ sơ này**: ở đây worker chết giữa chừng không có summary,
còn lần đó test fail bình thường và gate vẫn in đủ summary. Không tái hiện:
test đó chạy riêng pass 3/3, và 3 lần `-Full` tiếp theo đều PASS. Ghi lại để
lần điều tra sau có thêm một mẫu — **không kết luận là cùng nguyên nhân.**

## Note

Found only because the user pushed to actually run the real `-Full` gate
(with a real captured log) instead of trusting a narrower, faster command as
a stand-in — `tests/unit/ -n 6` alone is clean and would never have surfaced
this; it needs the broader `unit + integration` scope's real SQLite/subprocess
tests present to trigger.

---

## Điều tra 2026-08-25 (Linux) — tìm ra **cơ chế** rò rỉ, và một giả định trong hồ sơ này bị bác bỏ

### 1. Linux vẫn không tái hiện — nhưng lần này kiểm bằng bằng chứng dương tính

Lần kiểm 2026-08-23 kết luận "không có `ResourceWarning`". Đó là bằng chứng
**vắng mặt triệu chứng**, yếu: connection có thể vẫn đang mở mà GC chưa kịp
than phiền. Lần này đo thẳng **trạng thái đóng/mở của từng connection**, không
chờ GC:

| Cấu hình | Kết quả |
| :--- | :--- |
| Tuần tự, `unit + integration` (trừ `sanity`/flaky-UI) | 1700 passed, **31 connection mở, 0 chưa đóng** |
| `-n 6` (đúng cấu hình bug mô tả) | 1700 passed, 0 `ResourceWarning`, **0 rò rỉ trên cả 6 worker** |

Phân bố dưới `-n 6`: `gw0` mở 21 connection (nhiều nhất — đúng worker chết trên
Windows), `gw2` 5, `gw4` 3, còn lại 0. **Tất cả đều được đóng tường minh.**

Kết luận không đổi so với 23/08 nhưng nay chắc chắn hơn: ở HEAD hiện tại, trên
Linux, **không test nào để lại connection chưa đóng** — kể cả nghi phạm chính
`test_stream_klines_never_holds_more_than_a_bounded_number_of_rows_live`.

### 2. Cơ chế rò rỉ — đã chứng minh, và nó bác bỏ bước 3 của kế hoạch cũ

`SqliteShardManager.dispose_all()` gọi `engine.dispose()` cho mọi engine. Nhưng
`Engine.dispose()` **chỉ đóng connection đang nằm trong pool (checked-in)**.
Một `Session` còn đang giữ connection (checked-out) thì `dispose()` **không
đóng** — nó detach, và connection chỉ được đóng khi GC finalize. Đó **chính xác**
là điều kiện sinh ra `ResourceWarning` ở thời điểm ngẫu nhiên trên Windows.

Chứng minh (dùng `DatabaseManager` thật, không mock):

```
A. session KHÔNG close, rồi dispose_all()   -> connection VẪN MỞ   ← rò rỉ
B. session.close() rồi dispose_all()        -> connection ĐÃ ĐÓNG
```

**Hệ quả cho bước 3 của "Suggested next steps" ở trên:** kế hoạch đó nói cứ áp
lại "fix pattern" `dispose_all()` trong teardown là xong. **Không đủ.**
`dispose_all()` là điều kiện cần, không phải điều kiện đủ — bất kỳ đường code
nào lấy session mà không đóng đều sống sót qua `dispose_all()`. Khi truy trên
Windows, thứ cần tìm **không phải** "fixture nào quên `dispose_all()`" mà là
"**session/connection nào bị bỏ quên ở trạng thái checked-out**".

### 3. `test_sqlalchemy_repository.py` được minh oan — lần thứ hai, và lần này có bằng chứng

Một bản probe sai (xem §4) từng tố cáo 18 test của file này. Sau khi sửa probe,
file này cho **0 rò rỉ trên 17 connection**. Đánh giá ban đầu của hồ sơ về fixture
`repo` là **đúng**; `SQLAlchemyMarketDataRepository` cũng dùng
`with self.db_manager.get_session(symbol) as session:` ở toàn bộ 11 call site, tức
luôn `close()`.

### 4. Công cụ: `scripts/bug030_connection_leak_probe.py`

Đây là thứ mà bước 2 của kế hoạch cũ mô tả, nay đã tồn tại và đã được kiểm chứng.
Nó gán **đích danh test** để lại connection chưa đóng, kèm stack nơi connection
được mở. Cách chạy nằm trong docstring của chính file.

**Ba cái bẫy đã làm probe trả về "sạch" một cách sai lệch — ghi lại vì bất kỳ ai
tự viết lại probe này sẽ dẫm đúng vào:**

1. `sqlite3.Connection` **không weak-reference được** trong CPython —
   `weakref.ref()` ném `TypeError`. Nuốt lỗi đó = probe im lặng không theo dõi gì,
   báo "0 connection".
2. SQLAlchemy gọi `sqlite3.dbapi2.connect`, là **attribute module khác** với
   `sqlite3.connect` dù cùng trỏ tới một builtin. Patch mỗi cái sau = chặn hụt
   hoàn toàn.
3. `pytest_runtest_teardown` **phải là hookwrapper**. Bản impl thường đua với
   hook teardown của chính pytest và có thể chạy **trước** finalizer của fixture
   — đó là nguồn của 18 cáo buộc sai ở §3.

Cả ba đều cho ra kết quả trông rất thuyết phục mà hoàn toàn sai. Đây đúng loại
"test/probe pass mà không chứng minh được gì" mà `bug-fix-rule.md` §3 cảnh báo.

### 5. Bước tiếp theo (cần một máy Windows)

1. Chạy probe trên Windows đúng cấu hình `-n 6` của gate thật. Nó sẽ in ra test
   nào để lại connection mở, kèm stack — biến "một test nào đó rò rỉ" thành
   file:line cụ thể.
2. Với test đó, tìm session **checked-out** không được đóng (theo §2), không phải
   tìm `dispose_all()` thiếu.
3. Nếu probe trên Windows cũng báo 0 rò rỉ: giả thuyết "unclosed connection" sai
   hẳn, và hướng điều tra phải chuyển sang xdist/Windows file-handle thay vì
   SQLite — lúc đó §2 vẫn còn giá trị như một defect độc lập cần vá phòng ngừa.

### 6. Ghi chú môi trường

Repo Engine yêu cầu **Python ≥3.14** (dùng cú pháp PEP 758 `except A, B:` không
ngoặc, 3.13 không parse được). Máy Linux phải dựng venv 3.14 riêng mới chạy được
bộ test — `python3` mặc định của môi trường CI cloud là 3.11.

---

## Điều tra 2026-08-26 (Linux, môi trường agent không có Windows) — loại trừ thêm 1
giả thuyết mới, vẫn **chưa** tìm được file:line

Trong lúc sửa `BUG-051` (`RunHistoricalTickBacktestCommandHandler` đổi từ
`get_klines()` sang `count_klines()`+`stream_klines()`), nảy ra một giả thuyết mới
đáng kiểm: `stream_klines()` là generator giữ session trong khối `with ... as
session:`; nếu caller (`_simulate()`) bỏ dở generator giữa chừng — ví dụ nhánh
`return BacktestCancelled(...)` khi user bấm huỷ — session có bị bỏ lại
**checked-out** cho tới khi cyclic GC dọn không?

**Đã kiểm bằng thực nghiệm, kết quả: KHÔNG.** Dựng generator thật từ
`SQLAlchemyMarketDataRepository.stream_klines()`, tiêu thụ dở 3/5000 dòng rồi để
biến cục bộ ra khỏi phạm vi (mô phỏng đúng hình dạng `_simulate()` return sớm),
kiểm tra `engine.pool.checkedout()` và một `weakref` trỏ tới generator:

```
checked out BEFORE: 0
checked out RIGHT AFTER abandon (before any gc): 0
generator still alive (refcounting alone did NOT collect it): False   # nghĩa là: ĐÃ bị dọn
checked out AFTER explicit gc.collect(): 0
```

CPython's refcounting tự đóng generator (gửi `GeneratorExit` tại điểm `yield`,
chạy `with`-exit, `session.close()`) **ngay khi hết tham chiếu** — không cần đợi
cyclic GC — vì bản thân generator/`with`-block ở đây không tạo chu trình tham
chiếu. `pool.checkedout()` không bao giờ tăng. Giả thuyết "abandon generator giữa
chừng = rò rỉ" **sai**, loại trừ hẳn — không phải cơ chế của bug này (dù đáng lẽ
là một nghi phạm hợp lý xét theo §2's cơ chế "session checked-out không được
đóng").

**Ghi chú khác:** đã grep lại toàn bộ `src/` + `scripts/` cho `get_session(`/
`get_raw_session(` — **100% call site đã dùng `with ... as session:`** đúng
pattern, không còn chỗ nào thiếu. Củng cố thêm kết luận cũ của hồ sơ: nếu có rò
rỉ thật, nó nằm ở **test code** (fixture/test tự dựng session ngoài
`with`), không phải production code — đúng hướng §5 mục 1 đã vạch, vẫn cần máy
Windows để chỉ đích danh.
