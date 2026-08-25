# EPIC-008 — Chuẩn hoá luồng sự kiện từ nền lên màn hình

**Trạng thái:** 🟡 Đang làm (7/8 task con xong) — còn `008H` (Elite)
**Loại:** Kiến trúc / Presentation + Application
**Ưu tiên:** **P1** — cao hơn `EPIC-007`: hiện có lỗi runtime thật đang bị nuốt không dấu vết
**Nhánh đề xuất:** `epic/EPIC-008-chuan-hoa-event`
**ADR:** [`DECISION_2026-08-24_event_architecture.md`](DECISION_2026-08-24_event_architecture.md)
— **đọc trước README này.** Mọi quyết định nằm ở đó; README chỉ là thứ tự thi công.
**Epic song sinh:** [`EPIC-007`](../EPIC-007_chuan_hoa_card_dung_chung/) (card) — độc lập.

---

## 1. Vì sao P1

Ba thứ đang hỏng ở mức runtime, không phải mức "code chưa đẹp":

1. **Mọi exception trong mọi event handler bị nuốt tuyệt đối.** `MemoryEventBus.emit()` bọc
   handler trong `try/except` và chỉ log nếu có logger; `src/main.py:40` dựng bus **không
   truyền logger**.
2. **Hai luồng báo lỗi có cấu trúc chảy vào hư không.** `UiActionFailedEvent` (mọi lỗi slot UI,
   kèm traceback đầy đủ) và `runtime.tasks.failed` (mọi background task chết) — **0 subscriber**.
3. **Hai đăng ký `HealthUpdatedEvent` là mã chết**, chưa từng chạy một lần nào: sự kiện phát
   đúng 1 lần lúc `app.boot()`, còn presenter thì lazy nên luôn sinh ra sau đó.

Cộng lại: **một lỗi ở tầng nền có thể xảy ra mà không để lại dấu vết ở bất kỳ đâu người dùng
nhìn thấy được.**

## 2. Nguyên tắc nền — câu trả lời cho "event phải được sub bởi nhiều màn hình"

**Một sự kiện có đúng MỘT nơi xử lý, nhiều nơi *hiển thị*.**

"Nhiều màn cần biết về event X" **không** có nghĩa mỗi màn tự `event_bus.on(X, ...)` — làm thế
thì logic xử lý bị nhân bản đúng bằng số màn. Đó chính xác là thứ đang xảy ra:
`HealthUpdatedEvent` có **3** bản định dạng cùng một dict, `SingleSyncProgressEvent` có **2**
handler độc lập.

```text
EventBus ──1 subscriber──► XxxFeed (chuẩn hoá 1 lần) ──► Dashboard hiển thị
                                                     ├─► Backtest hiển thị
                                                     └─► DataMgmt hiển thị
```

## 3. Quyết định đã chốt

Nhật ký đầy đủ ở ADR §7. Tóm tắt:

| Quyết định | Nội dung |
| :--- | :--- |
| **Shared Kernel** | `IDomainEvent` + `BaseEvent` của engine là vùng dùng chung có tên, ghi vào `code-rule.md`. Mọi thứ khác của engine **phải qua port** của Elite. Guard giữ danh sách trắng đúng 2 ký hiệu này. |
| **`abc.ABC`, không `Protocol`** | User chốt: cần **type safe + ràng buộc thật**. Kiểm chứng: `Protocol` không chặn gì khi thiếu method; `ABC` ném `TypeError` ngay lúc dựng. |
| **Event kế thừa `BaseEvent`** | Phục vụ tool audit tương lai của engine (event nào, callback gì, chạy bao lâu). Phải **sửa `BaseEvent` cho chạy được** trước — hiện cả 3 thành viên kế thừa đều ném `AttributeError`. |
| **`HealthCheckRequested`** | Cặp request/response thay cơ chế sticky. Sticky bị **loại bỏ hoàn toàn** khỏi thiết kế. |
| **Registry, không enum, không tài liệu viết tay** | `BaseEvent.__init_subclass__` tự đăng ký; `EVENT_CATALOG.md` **sinh ra** từ registry; test so khớp doc với code. |
| **Định tuyến** | Epic này là **dọn dẹp, không thêm tính năng**. Không thêm subscriber mới ngoài 3 Feed. `MarketTickEvent` **không** sang Backtest — Backtest không có tính năng live. |

## 4. Thứ tự thực hiện

| ID | Việc | Repo | Trạng thái |
| :--- | :--- | :--- | :---: |
| **[008A](completed/EPIC-008A_sua_base_event.md)** | Engine: `BaseEvent` thành dataclass `kw_only` + `event_name` tự đặt (`BUG-005`) | Engine | ✅ |
| **[008B](completed/EPIC-008B_event_registry_va_catalog.md)** | Engine: `EventRegistry` + sinh `EVENT_CATALOG.md` + test so khớp | Engine | ✅ |
| **[008C](completed/EPIC-008C_bus_khong_nuot_loi.md)** | Engine: bus không nuốt lỗi — `handler_reporting` dùng chung cho cả 5 bus, `FallbackLogger`, TRACE thay INFO | Engine | ✅ |
| **[008D](completed/EPIC-008D_qt_event_bridge_va_base_presenter.md)** | Engine: `QtEventBridge` + `BasePresenter.dispose()` tự gỡ đăng ký + bỏ `NotImplementedError` (LSP) | Engine | ✅ |
| **[008E](completed/EPIC-008E_health_check_requested.md)** | Engine: `HealthCheckRequested` + `HealthExtension` nghe request | Engine | ✅ |
| **[008F](completed/EPIC-008F_shared_kernel_va_ports.md)** | Elite: Shared Kernel vào `code-rule.md`; `IEventPublisher(ABC)`; đổi 3 port `Protocol`→`ABC`; bỏ `import App` | Elite | ✅ |
| **[008G](completed/EPIC-008G_ba_feed_va_xoa_signal_cau_noi.md)** | Elite: 3 Feed + xoá 48 signal cầu nối + payload dataclass | Elite | ✅ |
| **[008H](incomplete/EPIC-008H_guard_va_doi_ten.md)** | Elite: 5 guard + đổi tên `RunRealtimeBacktest*` → `RunHistoricalTick*` | Elite | 🔵 |

`008A` phải xong trước tất cả: registry, catalog và mọi quyết định định danh đều đứng trên nó.
`008C` nên làm sớm ngay sau — nó là thứ làm mọi lỗi trong các bước sau **nhìn thấy được**.

**Hai repo, hai commit, không có bước đồng bộ** (`Sagittarius_Engine/.agents/ONBOARDING.md` §8).

## 5. Điều kiện dừng (kill criteria)

- Sub-task vượt 3 lần ước lượng → dừng, đánh giá lại.
- `008A` làm vỡ bất kỳ consumer nào của `BaseEvent` trong Engine (`audit/events.py`,
  `health_module.py`) mà không sửa được trong buổi đó → rollback; `BaseEvent` là API công khai
  của một thư viện có người dùng ngoài Elite.
- Sau `008C`, nếu log lỗi mới làm ngập log (`BUG-042` tái diễn) → dừng, sửa ngưỡng log trước
  khi đi tiếp.
- Guard nào phải nới lỏng để CI xanh → **không nới**; dừng và xử lý nguyên nhân
  (`design-discipline.md`).

## 6. Ngoài phạm vi

- Card / widget — thuộc [`EPIC-007`](../EPIC-007_chuan_hoa_card_dung_chung/).
- Xây **tool audit** của Engine: epic này chỉ dựng registry làm nền.
- Đổi sang `ThreadPoolEventBus`/`AsyncioEventBus`; IPC bus.
- Nạp `AuditExtension`; thêm subscriber mới cho `BulkSyncProgressEvent` /
  `BacktestCompletedEvent` — ghi lại thành ứng viên task tính năng.
- Đăng ký 10 sự kiện vòng đời của engine (`app.booted`, `extension.*`, …) — chỉ đưa vào
  registry để nhìn thấy, không nghe.
