# Epic EPIC-018 — App-Wide Hard Design Sweep

**Trạng thái:** 🟡 Đang làm — 2/6 task xong (`018A`, `018B`; còn 4 task rà
soát `018C`-`018F`); 3 việc khác đã sửa **trước khi** có task/ADR (xem
bảng riêng bên dưới, ghi nhận lỗi quy trình). Cập nhật 2026-08-30.
**Nguồn:** User yêu cầu rà soát tiếp toàn bộ `src/` sau khi `EPIC-016`/
`EPIC-017`/`EPIC-003G` dọn xong `presentation/ui`. Ratify ở
[`DECISION_2026-08-30_app_wide_hard_design_sweep.md`](DECISION_2026-08-30_app_wide_hard_design_sweep.md).

---

## 1. Bối cảnh

Một đợt khảo sát rộng (1 agent, quét cả `application`/`domain`/`infrastructure`
và phần còn lại của `presentation`) tìm ra 7 finding, verify độc lập từng
cái. 3 finding rủi ro thấp/độ tin cậy cao đã được sửa **trước khi** epic
này được tạo — sai quy trình (lẽ ra phải có task/ADR trước), user đã chỉ ra
lỗi này giữa chừng. ADR ghi lại đúng sự thật: cái nào đã sửa trước, cái nào
sửa sau khi có task.

**Bài học quy trình (từ phản hồi của user):** không làm 1 đợt khảo sát rộng
quét hết `src/` một lần rồi vá lung tung. Từ epic này trở đi: **mỗi task rà
soát chỉ phạm vi đúng 1 module** (`domain/`, `application/`, `infrastructure/`,
`presentation/cli/`, ...), nhưng cộng lại toàn bộ task phải phủ hết `src/`
— không bỏ sót module nào. Bảng task con dưới đây vừa là danh sách "đã rà
soát" vừa là checklist "còn phải rà soát", để việc rà soát trở thành 1 quy
trình lặp lại được, không phải 1 lần làm rồi thôi.

## 2. Task con

### Rà soát (mỗi task = đúng 1 module, chưa từng có task riêng trước epic này)

| ID | Phạm vi | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-018C](incomplete/EPIC-018C_ra_soat_domain.md)** | `src/domain/` (entities, events, value_objects, models, indicators, indicator_scripts, scripting, strategies, backtesting) | 🟡 Đã có 1 finding sơ bộ (D7, bị từ chối) từ đợt khảo sát rộng — **chưa có 1 pass riêng, đúng phạm vi module** |
| **[EPIC-018D](incomplete/EPIC-018D_ra_soat_application.md)** | `src/application/` (use_cases, services, ports, events, event_handlers) | 🟡 Đã có 2 finding sơ bộ (D2, D4) — **chưa có 1 pass riêng** |
| **[EPIC-018E](incomplete/EPIC-018E_ra_soat_infrastructure.md)** | `src/infrastructure/` (binance, persistence, engine_adapters) | 🟡 Đã có 2 finding sơ bộ (D5, D6) — **chưa có 1 pass riêng** |
| **[EPIC-018F](incomplete/EPIC-018F_ra_soat_presentation_cli.md)** | `src/presentation/cli/` + `src/config/` + composition root (`src/binance_bot_module.py`, `src/main.py`) | 🟡 Đã có 1 finding sơ bộ (D1, đã sửa) — **chưa có 1 pass riêng** |

`src/presentation/ui/` **không** cần task rà soát mới ở epic này — đã rà
soát sâu và fix xong ở `EPIC-016`/`EPIC-017`/`EPIC-003G` (3 epic riêng,
nhiều vòng verify độc lập với test thật).

### Sửa (từ finding đã verify chắc ở đợt khảo sát rộng)

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-018A](completed/EPIC-018A_data_management_timeframe_enum.md)** | Data Management: hoàn thiện chuyển `"1m"` → `TimeFrame` (D2) | ✅ Hoàn thành |
| **[EPIC-018B](completed/EPIC-018B_sqlalchemy_repository_split.md)** | `sqlalchemy_repository.py`: tách mapping/query-building (D5) + sửa docstring gây hiểu lầm (D6) | ✅ Hoàn thành |

### Đã sửa trước khi có task/ADR (ghi nhận, không lặp lại quy trình này)

| Việc | Commit | ADR mục |
| :--- | :--- | :--- |
| `sync_cli_handler.py` dead-code failure branch | `50fbd0e` | D1 |
| `app_bootstrapper.py` hasattr dead branch (x4) | `50fbd0e` | D3 |
| `RunBacktestCommand` hasattr dead code | `50fbd0e` | D4 |

## 3. Không nằm trong epic này

- `_KLINE_STREAM_CHUNK_SIZE` gộp thành 1 constant — **từ chối** (ADR D6),
  2 tunable độc lập có chủ đích, chỉ sửa docstring gây hiểu lầm (gộp vào `018B`).
- Tách `base_indicator_script.py` — **từ chối** (ADR D7), DSL cohesive hợp lệ.
