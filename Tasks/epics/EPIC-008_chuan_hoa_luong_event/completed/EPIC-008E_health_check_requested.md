# EPIC-008E — Engine: `HealthCheckRequested`, xoá đường vòng ở 2 màn

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong (2026-08-25)
**Phụ thuộc:** `008A`

---

## Vấn đề

`HealthExtension.boot()` phát `HealthUpdatedEvent` **đúng một lần**, ở bước 1 của
`app_bootstrapper` (`app_engine.boot()`). `MainWindow` dựng ở bước 3, và `PresenterManager`
**lazy** — presenter chỉ tồn tại khi user bấm vào màn đó lần đầu. Nên tại thời điểm phát,
**chưa có subscriber nào tồn tại**.

Hai dòng này là mã chết theo đúng nghĩa đen:

- `backtest_presenter.py:571`
- `dashboard_presenter.py:427`

Cả hai màn đã tự vá bằng cách **tự chế sự kiện giả**: `_trigger_initial_health_check()` resolve
`HealthCheckQuery` rồi gọi thẳng handler với một `HealthUpdatedEvent` do chính nó dựng ra.

## Quyết định: request/response, **không** dùng sticky

User chốt (ADR §4.3). Sticky (bus giữ lại giá trị cuối) bị loại bỏ hoàn toàn — cặp
request/response giải quyết trọn vẹn mà không phải thêm khả năng mới nào cho bus, và cho số
liệu **tươi tại thời điểm mở màn** thay vì ảnh chụp lúc boot.

```text
Presenter mở màn ──publish──► HealthCheckRequested
                                      │
                          HealthExtension nghe, đo lại
                                      │
                                      └──emit──► HealthUpdatedEvent ──► HealthFeed ──► mọi màn
```

## Yêu cầu

1. `HealthCheckRequested(BaseEvent)` — file riêng trong `extensions/health/`.
2. `HealthExtension` đăng ký nghe nó trong `boot()`, chạy `HealthCheckQuery`, phát
   `HealthUpdatedEvent`.
3. `HealthExtension.boot()` vẫn phát một lần lúc boot như cũ — **không bỏ**, có consumer khác
   ngoài Elite.
4. **Đây là tính năng mới nhỏ ở Engine**, không phải refactor thuần — ghi rõ trong
   `CHANGELOG.md` để không ai hiểu nhầm (`release.md`).

## Đổi hành vi — đã được user duyệt

Hôm nay 2 màn in 2 kiểu khác nhau vì mỗi màn tự chế:

```text
Backtest  : [Health] Trạng thái hệ thống: HEALTHY (Database: OK, EventBus: OK)
Dashboard : System Health: HEALTHY (DB: OK, Container: OK, EventBus: OK)
```

Sau task (cộng `HealthFeed` ở `008G`) cả hai đi qua **một** bộ định dạng, ra cùng một chuỗi.
Chữ đổi — user đã duyệt.

## Bằng chứng phải nộp

- Test: phát `HealthCheckRequested` → nhận đúng một `HealthUpdatedEvent` có số liệu tươi.
- Sau `008G`: chụp log của cả 2 màn, chứng minh cùng định dạng và **không** còn
  `_trigger_initial_health_check`.
- `pwsh ./scripts/ci-local.ps1` — block `===CI_LOCAL_RESULT===` + log.

## Xong 2026-08-25

**Trạng thái:** ✅ Xong. Sửa ở **repo Engine** (commit riêng), file này ghi tiến độ phía Elite.

- `HealthCheckRequested` ở file riêng `extensions/health/health_check_requested.py`,
  `event_name` ghim `"health.check_requested"`, không payload.
- `HealthExtension.boot()` **vẫn báo cáo 1 lần như cũ** (yêu cầu 3 — có consumer ngoài Elite),
  rồi đăng ký nghe request. Thân chung tách thành `_report_health(context, *, trigger=...)`.
- `EVENT_CATALOG.md` sinh lại: 16 → 17 event.
- 6 test mới (`tests/extensions/test_health_check_requested.py`). Gate Engine
  `RESULT: PASS`, **973 passed** (trước task: 965).

### Áp rule mới `code-rule.md` §7 (Abstraction-Level Separation)

`HealthUpdatedEvent` trước nằm chung `health_module.py` với `HealthExtension` — event và
extension phát ra nó là **hai abstraction level khác nhau**. Đã tách sang
`health_updated_event.py`; `health_module` re-export tên đó vì 3 call site bên Elite đang
import theo đường cũ (`from ...health_module import HealthUpdatedEvent`) — có test khoá lại
đường import cũ để không vỡ ngầm.

### Ba thứ gate bắt được, không phải tự khai

1. **Quên sinh lại `EVENT_CATALOG.md`** sau khi thêm event → `test_event_catalog_matches_registry`
   đỏ. Đúng như cơ chế `008B` thiết kế để bắt.
2. **`test_edge_cases::test_health_module__boot_raises__...`** (regression guard của `TASK-026`)
   đỏ vì tôi đổi thông điệp lỗi thành chung chung. **Không sửa test cho xanh** — thay vào đó cho
   thông điệp nêu đích danh đường nào hỏng (`trigger=`), vì giờ có 2 đường (boot vs request) và
   gộp một câu chung sẽ giấu mất cái nào thật sự lỗi (`logging-rule.md`).
3. **`mypy`**: `_CountingQuery.execute()` thu hẹp chữ ký của `HealthCheckQuery.execute()` — vi
   phạm LSP thật, không phải nhiễu type checker. Sửa cho khớp đúng chữ ký lớp cha.

### Lệch với yêu cầu #4 của task — có chủ đích

Yêu cầu #4 ghi "ghi rõ trong `CHANGELOG.md`". **Không làm**, vì chính `release.md` §1 mà yêu cầu
đó trích dẫn nói ngược lại: *"Finishing a task is not a reason to cut a version… no changelog
entry"*, và §4 bắt buộc changelog phải dựng **từ diff lúc release**, không viết từ trí nhớ.
Ý đúng của yêu cầu #4 là *khi nào release thì phải mô tả đây là tính năng mới, không phải
refactor* — điều đó đã ghi rõ trong commit message để lúc dựng changelog từ diff không ai hiểu
nhầm. Ghi lại ở đây để người sau không tưởng là bỏ sót.

**Lưu ý cho lúc release:** cả loạt `008A`–`008E` hiện **chưa có mục nào trong `CHANGELOG.md`**,
trong đó `008A` đổi `BaseEvent` thành dataclass — thay đổi consumer bắt buộc phải biết.
