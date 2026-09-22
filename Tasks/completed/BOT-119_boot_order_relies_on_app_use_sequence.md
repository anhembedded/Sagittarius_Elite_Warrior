# BOT-119: Thứ tự boot phụ thuộc hoàn toàn vào thứ tự gọi `app.use()`

**Status:** ✅ Done (2026-09-22)

> Original text below is preserved as the historical record (2026-08-23). The
> task's own instruction to re-measure before coding (§3.1) found its subject
> had moved and grown since then — see **Re-measurement** and
> **Implementation notes** at the end for what was actually true and actually
> done.

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-23, cùng đợt audit chéo với
[BOT-118](../completed/BOT-118_broken_state_tokens_import_in_test.md).

`src/main.py` đăng ký 6 extension/module, và thứ tự đúng đang được giữ **chỉ
bằng thứ tự dòng code**, có chỗ ghi hẳn thành comment:

```python
app.use(DependencyValidatorExtension([...]))
app.use(AssetValidatorExtension())
app.use(LoggerExtension())
app.use(ThreadManagerExtension())

# Load Domain Module (Registers Repositories & UseCases)
app.use(BinanceBotModule())

# Load Health Check Diagnostic Extension after domain modules
app.use(HealthExtension())
```

Dòng comment `# ... after domain modules` chính là vấn đề: **một ràng buộc
thứ tự thật đang được mã hoá bằng tiếng Anh trong comment, chứ không phải
bằng code.** Đổi chỗ hai dòng `app.use()` là hỏng, và không có gì báo.

Quét cả repo: **không có extension nào của app này khai báo `dependencies`.**

## 2. Engine hỗ trợ khai báo — chỉ là chưa dùng

`ExtensionManager._build_and_sort()` của engine làm **topological sort thật**
trên thuộc tính `dependencies`, khớp theo `descriptor.name`. Khai báo rồi thì
thứ tự `app.use()` không còn quan trọng.

Engine đã xác minh điều này bằng thực nghiệm và ghi lại trong
`examples/student_management/docs/module_registration.md`: đảo ngược thứ tự
hai lời gọi `app.use()` mà vẫn boot sạch, miễn là có khai báo. App mẫu
(`StudentManagementExtension`) hiện dùng đúng cách này:

```python
dependencies: ClassVar[list[str]] = ["DatabaseExtension"]
```

Đây đúng là loại "practice đã chốt ở app mẫu" mà quy trình cross-check này
sinh ra để phát hiện.

## 3. Yêu cầu

1. Xác định ràng buộc thứ tự **thật** giữa 6 thành phần trong `src/main.py` —
   dựa trên cái gì bind vào container và cái gì resolve ra, không dựa vào thứ
   tự hiện tại. Thứ tự hiện tại chạy được không có nghĩa nó phản ánh đúng
   ràng buộc; nó chỉ là một thứ tự thoả mãn.
2. Khai báo `dependencies: ClassVar[list[str]]` trên các extension của app,
   dùng tên class như engine yêu cầu (khớp `descriptor.name`).
3. **Viết test đảo thứ tự `app.use()` rồi assert vẫn boot được.** Đó mới là
   thứ chứng minh ràng buộc đã thành khai báo chứ không còn ngầm định — không
   có nó thì khai báo `dependencies` cũng chỉ là comment loại khác.
4. Xoá các comment mô tả thứ tự (`# ... after domain modules`) sau khi ràng
   buộc đã nằm trong code.
5. `BinanceBotModule` đang kế thừa `BaseModule` (đường `IModule` legacy —
   engine gọi thẳng trong code của nó là *"a legacy IModule"*). Cân nhắc
   chuyển sang `IExtension` luôn trong lúc làm, vì `dependencies` là cơ chế
   của `IExtension`. Nếu quyết định giữ legacy thì ghi lý do lại.

## 4. Ưu tiên

P3 — hiện đang chạy đúng, không có bug. Đây là giảm nợ về độ giòn: sửa trước
khi có người đổi thứ tự và mất nửa ngày dò.

## 5. Phân loại

Bootstrap / Engine integration

---

## Re-measurement (2026-09-22, before writing any code)

The task's own §3.1 instruction — determine the *real* constraint from what
binds and what resolves, not from the current order — required re-reading the
subject first, and it had moved since 2026-08-23:

- `src/main.py` no longer registers any extension or module at all; wiring
  moved to `src/shell/composition_root.py::create_app()` (that move predates
  this task and is unrelated to it).
- `BinanceBotModule` (the legacy `IModule` named in §3 item 5) **no longer
  exists**. The strangler migration it belonged to finished: bounded contexts
  now register through `BoundedContextModule(IExtension)` instances listed in
  `src/shell/modules.py::MODULES` and wired by
  `src/shell/module_registration.py::register_modules()`.
- `BoundedContextModule` **already declares** a typed
  `dependencies: list[str]` class attribute, already checked in both
  directions against real imports by `test_module_declarations.py`. Item 2
  and item 5 of §3 are therefore already done for every bounded context — no
  action needed there. `shell/modules.py`'s own docstring records a
  *deliberate* decision to keep list order (not the engine's topological
  sort) as the mechanism for module registration, because `contribute()`
  order is user-observable UI panel order — reordering that on its own would
  contradict a decision already made and documented, so this task does not
  touch it.
- The comment-encoded ordering §1 actually complained about is **still
  live**, just relocated and grown from 6 to 7 registrations in
  `composition_root.py::create_app()`:
  `DependencyValidatorExtension` → `EngineCapabilityValidatorExtension` →
  `AssetValidatorExtension` → `LoggerExtension` → `ThreadManagerExtension` →
  the 4 `MODULES` → `HealthExtension`, with two comments doing exactly what
  §1 flagged: *"Presence first (above), then capability"* and *"Load Health
  Check Diagnostic Extension after domain modules"*. Neither extension
  declared `dependencies`. This is the real, current scope of the task.

## Implementation notes (2026-09-22)

**Root cause traced to two real constraints, not just comments:**

1. `EngineCapabilityValidatorExtension.boot()` must run after
   `DependencyValidatorExtension.boot()` — a missing engine install must
   report "not installed", not a confusing attribute error from probing an
   engine that was never checked to be there at all.
2. `HealthExtension.boot()` must run after every `BoundedContextModule`'s
   `register()` — the engine's own `HealthCheckQuery.execute()`
   (`sagittarius_engine/extensions/health/health_check_query.py`) sweeps the
   container's bound types by name substring (`DatabaseManager`,
   `MarketDataRepository`, …) to report component health, so it silently
   under-reports if run before those bindings exist.

**Fix, per file:**

| File | Change |
| :--- | :--- |
| `src/infrastructure/engine_adapters/engine_capability_validator_extension.py` | Added `dependencies: ClassVar[list[str]] = ["DependencyValidatorExtension"]` (this class is app-owned, so a typed class attribute is direct); updated the stale docstring (it named `main.py`, which no longer wires anything) to describe the new mechanism. |
| `src/infrastructure/engine_adapters/ordered_health_extension.py` (new) | `OrderedHealthExtension(HealthExtension)` — the engine's `HealthExtension` cannot take the class-attribute fix directly (it is not this app's class), and `IExtension.descriptor` reading `dependencies` via a bare `getattr` on an unset instance attribute is invisible to mypy (confirmed: `mypy` reports `"HealthExtension" has no attribute "dependencies"  [attr-defined]` for that shape). This one-method subclass gives the attribute a real type and changes no lifecycle behaviour — every method still runs the engine's own implementation. |
| `src/shell/composition_root.py` | `app.use(OrderedHealthExtension([module.module_id for module in modules]))` replaces `app.use(HealthExtension())`, built from the real `modules` list `register_modules()` already returns (not a hand-typed list, so a fifth bounded context is covered automatically); updated both order-only comments to state the constraint is now enforced by `dependencies`, keeping the rationale prose that explained *why* the order matters. |
| `tests/unit/shell/test_extension_boot_order_is_declared.py` (new) | Two unit tests, each registering the real production classes via a minimal `App(StdLibContainer(), MemoryEventBus(None))` in the **opposite** order `composition_root.py` uses, asserting the engine's topological sort still runs them correctly. This is §3's required test: proof the constraint is now enforced code, not proof it merely has a `dependencies` attribute. |
| `tests/sanity/test_composition_root.py` | Two added tests read `booted_app` (the real `create_app()` graph) and assert `HealthExtension.dependencies` equals the real registered module ids, and `EngineCapabilityValidatorExtension.dependencies` names the real registered `DependencyValidatorExtension` — closing the gap the unit tests above cannot: that `composition_root.py`'s own wiring lines (not just the mechanism in general) are correct. |

**Mutation-verified** (`testing-rule.md` §2): reverted each `dependencies`
declaration in turn and re-ran the four new tests — all four failed for the
expected reason (`AssertionError` naming the swapped order, or the sanity
test's set-equality mismatch), then restored and re-confirmed green.

**Verification:**
- `.venv/bin/ruff check src tests scripts tools` — all checks passed.
- `.venv/bin/ruff format --check src tests scripts tools` — all files already formatted.
- `mypy` (`--config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts`, run from the checkout's parent directory): 566 pre-existing errors, none newly introduced by this change (checked the two touched files individually — zero errors in both); confirms this does not regress the `EPIC-002A` mypy baseline.
- `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen pytest tests/unit/shell tests/unit/architecture tests/sanity/test_composition_root.py -q` — 556 passed.
- `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen pytest tests/unit -q` — full unit tier, run from a stable worktree checked out as `.../Sagittarius_Elite_Warrior` (the ruff-isort/import-resolution convention this repo's `BOT-143` measured): **4919 passed** in 289.3s, 0 failed.

**Delivery:** implemented, verified locally, and pushed on branch
`claude/bot-119-boot-order-dependencies`; PR opened per `ONBOARDING.md` §7
(author never self-merges a code change).
