# EPIC-008E — Engine: `HealthCheckRequested`, xoá đường vòng ở 2 màn

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** 🔵 Chưa làm
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
