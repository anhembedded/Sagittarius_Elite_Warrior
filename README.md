# Sagittarius Elite Warrior

Trading bot cho **Binance USD-M Futures**, gồm một **ứng dụng desktop PySide6** và một **CLI
headless**, xây trên framework [Sagittarius Engine](https://github.com/anhembedded/Sagittarius_Engine)
theo **Clean Architecture** (Domain → Application → Infrastructure/Presentation).

> [!IMPORTANT]
> **Rào an toàn vốn:** bot **chỉ** đặt lệnh trên **Binance USD-M Futures Testnet**. Đường đi lệnh
> tiền thật **không tồn tại trong code** — value object
> [`TradingVenue`](src/support/binance_gateway/contracts/trading_venue.py) cố ý **không có member `MAINNET`**:
> mở giao dịch thật là một epic phải thêm member đó và chịu review, không phải một cờ cấu hình
> ai cũng bật được.

| | |
| :--- | :--- |
| **Python** | ≥ 3.12 (sàn thật, được `tests/sanity/test_python_floor.py` canh — xem [`install-rule.md`](.claude/rules/install-rule.md) §1b) |
| **UI** | PySide6 (QtWidgets) + pyqtgraph cho chart; **không còn QML cho code mới** (ADR D20, 2026-09-13) — phần QML còn sót được `EPIC-025` gỡ dần, guard chặn file `.qml` mới |
| **Lưu trữ** | SQLite (WAL) qua SQLAlchemy |
| **Cổng kiểm thử bắt buộc** | [`scripts/ci-local.ps1 -Full`](scripts/ci-local.ps1) + [GitHub Actions](.github/workflows/ci.yml) |
| **Trạng thái / lộ trình** | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) · [Bug Board](Tasks/bug_report/README.md) |

---

## 1. Bot làm được gì hôm nay

| Năng lực | Mô tả |
| :--- | :--- |
| **Đồng bộ dữ liệu lịch sử** | Tải nến OHLCV từ Binance về SQLite (WAL mode, sharding theo symbol/timeframe), lưu mốc thời gian chuẩn UTC. |
| **Luồng thị trường realtime** | Websocket async, phát `MarketTickEvent` lên Event Bus cho chart và chiến lược. |
| **Indicator & Strategy Engine** | EMA/WMA/RSI/MACD/Support-Resistance; các chiến lược dùng chung cho cả backtest lẫn live (`src/domain/strategies/`), tham số khai báo qua parameter schema chứ không hard-code. |
| **Backtest** | `PaperExchange` mô phỏng khớp lệnh futures (SHORT + đòn bẩy), phí, exit reason, equity curve, bộ metrics, và tách **out-of-sample** để kiểm định chiến lược. |
| **Ứng dụng desktop** | 5 màn hình: Dashboard/Dev Board, Backtest, Data Management, **Giao dịch**, Settings — chung `PageShell` (header / context bar / workspace + rail / console). |
| **Giao dịch trên Futures Testnet** | Kiểm tra kết nối, chuẩn hoá lệnh theo filter của sàn (step/tick/minNotional), dry-run qua `POST /fapi/v1/order/test`, đặt lệnh thật trên testnet, User Data Stream nối vào `OrderFeed`; banner môi trường hiện ở mọi màn hình (qua `PageShell`), **Emergency Stop** nằm trên màn Giao dịch. |
| **Chiến lược sống trên màn Giao dịch** | Chọn chiến lược + Thông số Chiến lược lúc đang chạy, vẽ chỉ báo/vùng xu hướng của chính chiến lược đó lên chart live; chưa nạp chiến lược thì **không bật được** giao dịch. |

**Chưa có (có chủ đích):** giao dịch tiền thật (mainnet); daemon giao dịch chạy liên tục —
`trade-once` chạy đúng **một** vòng đánh giá rồi thoát.

---

## 2. Kiến trúc

Bốn lớp, phụ thuộc luôn hướng vào trong. Chi tiết và lý do từng quyết định nằm ở
[`.claude/rules/architecture-rule.md`](.claude/rules/architecture-rule.md) và
[`Docs/Diagrams/architecture.md`](Docs/Diagrams/architecture.md).

```text
Presentation  (PySide6 UI, CLI)          ─┐
Infrastructure (Binance, SQLAlchemy,      │  adapter — biết framework
                engine adapters)          │
Application   (use case CQRS, port)      ─┤  hợp đồng — không biết framework
Domain        (entity, indicator,        ─┘  thuần Python
               strategy, backtest)
```

Ba ràng buộc quyết định phần lớn cách code được tổ chức:

1. **Shared Kernel đúng 2 symbol.** `src/domain/` và `src/application/` chỉ được import
   `IDomainEvent` và `BaseEvent` từ engine; mọi thứ khác phải đi qua một **port** trong
   `src/application/ports/` với adapter trong `src/infrastructure/engine_adapters/`. Có test khoá
   allow-list này.
2. **Hợp đồng phải tường minh** — cấm duck-typing ngầm. `abc.ABC` là mặc định; `typing.Protocol`
   chỉ khi kế thừa bất khả thi (lớp `QObject`, đã có base khác, lớp bên thứ ba) và docstring phải
   nói rõ lý do nào.
3. **Tách theo mức trừu tượng.** Hai thứ khác mức trừu tượng không chung file, cũng không chung
   thư mục; file > 400 dòng hoặc class > 15 public method là bắt buộc phải tách.

**Hai repository độc lập, không phải submodule.** `Sagittarius_Engine` (framework) và
`Sagittarius_Elite_Warrior` (app này) có remote riêng, cây rule riêng (`.claude/`), task board riêng — commit
và push tách bạch, không có bước "bump" con trỏ nào cả.

---

## 3. Cấu trúc thư mục

```text
Sagittarius_Elite_Warrior/
├── src/
│   ├── domain/              # Thuần Python: entity, value object, indicator, strategy,
│   │                        # backtesting (PaperExchange, metrics, out-of-sample), trading
│   ├── application/         # Use case (CQRS: command/query/handler), port, service,
│   │                        # event handler — không biết framework nào
│   ├── infrastructure/      # Adapter: binance/, persistence/ (SQLAlchemy), credentials/,
│   │                        # engine_adapters/
│   ├── presentation/
│   │   ├── cli/             # Parser theo cấu hình JSON, interactive shell, các lệnh headless
│   │   └── ui/              # PySide6: app_bootstrapper, main_window, screens/, components/,
│   │                        # kit/ (widget dùng chung), registry/, state/
│   ├── config/              # app_config.json, user_config.json, cli_commands.json
│   └── main.py              # Entry point CLI (headless + interactive shell)
├── tests/                   # unit/ · integration/ · sanity/ · testnet/ (opt-in)
├── scripts/                 # ci-local.ps1, run.ps1, run-ui.ps1, preview-qml.ps1, probe/benchmark
├── Tasks/                   # ROADMAP.md, epics/, bug_report/, backlog/, completed/, reports/
├── Docs/                    # Sơ đồ kiến trúc, ý định dự án, thiết kế chi tiết
├── .claude/                 # ONBOARDING.md, rules/, skills/, agents/, templates/ — quy trình cho người & AI agent
└── database/                # trading.db (không commit)
```

---

## 4. Cài đặt

**Lưu ý quan trọng về `PYTHONPATH`:** code import theo package tuyệt đối
(`Sagittarius_Elite_Warrior.src...`), nên `PYTHONPATH` phải trỏ tới **thư mục cha** chứa repo này,
và tên thư mục repo phải là `Sagittarius_Elite_Warrior` (dùng dấu gạch dưới).

### Windows (PowerShell) — script tự lo môi trường

```powershell
.\scripts\run.ps1        # tạo .venv, cài dependency + engine, chạy CLI
.\scripts\run-ui.ps1     # như trên, nhưng khởi chạy ứng dụng desktop
```

### Thủ công (Linux/macOS/Windows)

```bash
python3.12 -m venv .venv
source .venv/bin/activate                 # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git
```

Khi cần phát triển/debug engine song song với app, cài bản local thay vì bản GitHub:

```bash
pip install -e ../Sagittarius_Engine        # chạy từ thư mục workspace cha
```

Trên Linux còn cần `pwsh` để chạy được **cổng kiểm thử bắt buộc**, và vài thư viện hệ thống cho Qt
chạy `offscreen` (`libegl1`, `libgl1`, `libxkbcommon0`, `libfontconfig1`, `libdbus-1-3` trên một
container sạch — cứ để `ImportError` gọi tên file `.so` còn thiếu). Hướng dẫn đầy đủ:
[`.claude/rules/install-rule.md`](.claude/rules/install-rule.md) §2b, §3.

### Khai báo API key cho Futures Testnet

Thứ tự ưu tiên: **biến môi trường trước, file sau** — biến môi trường luôn thắng, để chạy headless
(CI/VPS) mà không bao giờ ghi secret xuống đĩa.

```bash
export BINANCE_FUTURES_TESTNET_API_KEY=...
export BINANCE_FUTURES_TESTNET_API_SECRET=...
```

Không đặt biến môi trường thì app đọc `src/config/secrets.local.json` (đã nằm trong `.gitignore`;
màn hình Settings ghi vào đúng file này). Tên biến gắn chặt với **venue** chứ không đặt tên chung
chung — nhầm key giữa các môi trường là đúng thứ rào chắn này sinh ra để chặn.

---

## 5. Chạy ứng dụng

### 5.1 Ứng dụng desktop (PySide6)

```powershell
.\scripts\run-ui.ps1                 # bình thường
.\scripts\run-ui.ps1 -Dev            # log DEBUG → logs/dev-<timestamp>.log, bật đo FPS/click log
.\scripts\run-ui.ps1 -Debug          # log TRACE → logs/debug-<timestamp>.log (bao hàm luôn -Dev)
```

Tương đương thủ công (chạy từ thư mục workspace cha):

```bash
PYTHONPATH=. python -m Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper
```

Cờ `--self-check` boot app thật, quay vòng lặp sự kiện đúng một nhịp rồi thoát với mã thoát thật —
dùng để kiểm chứng app thực sự khởi động và **thực sự thoát** được, không phải chỉ trong tiến trình
pytest.

### 5.2 CLI

Không truyền tham số → **interactive shell** (`cmd`-based, gõ `help` để xem lệnh, hiện định tuyến
`sync`, `stream`, `exchange-status`). Có tham số → chạy thẳng lệnh rồi thoát, hợp cho cron/VPS.

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py            # interactive
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py <lệnh> ... # headless
```

| Lệnh | Việc nó làm |
| :--- | :--- |
| `sync --symbols BTCUSDT,ETHUSDT --interval 1m --days 30` | Đồng bộ nến lịch sử về SQLite. |
| `stream start --symbols BTCUSDT --interval 1m` / `stream stop` | Bật/tắt luồng websocket realtime. |
| `exchange-status` | Kiểm tra kết nối Futures Testnet: chữ ký, lệch đồng hồ, số dư, position mode. |
| `order-preview --symbol BTCUSDT --side BUY --qty 0.0137 --price 60000 [--json]` | Chuẩn hoá lệnh theo filter sàn (làm tròn step/tick, kiểm `minNotional`) — **không gửi đi đâu cả**. |
| `order-dry-run --symbol ... --side ... --qty ... --price ...` | Gửi tới `POST /fapi/v1/order/test`: sàn xác thực chữ ký/quyền/payload, **không tạo lệnh nào**. |
| `trade-once --symbol BTCUSDT --interval 1m --strategy <key> [--live]` | Chạy **một** vòng đánh giá chiến lược, đi trọn pipeline an toàn. Mặc định dry-run; `--live` mới thật sự đặt lệnh (trên testnet). |

Danh sách lệnh và tham số được sinh từ [`src/config/cli_commands.json`](src/config/cli_commands.json)
— thêm lệnh là sửa file cấu hình cộng một handler, không phải sửa parser.

### 5.3 Xem trước một màn hình UI, không boot cả app

```powershell
.\scripts\preview-qml.ps1 --list
.\scripts\preview-qml.ps1 <tên-màn-hình>
```

Mọi package UI đều phải có `preview.py` khai báo `build_preview() -> QWidget`; có test canh đúng
điều đó.

---

## 6. Kiểm thử & CI

### Cổng bắt buộc

```powershell
cd Sagittarius_Elite_Warrior
.\scripts\ci-local.ps1 -Full          # Linux: pwsh -NoProfile -File scripts/ci-local.ps1 -Full
```

`-Full` chạy: `ruff check` + `ruff format --check` (đã bật thêm nhóm `S`/`PLR2004`/`B`/`SIM`/`ERA`/`N`
— tương đương lớp bảo mật/chất lượng kiểu Bandit), `mypy` trên `src` **và** `scripts` **trong cùng
một lệnh**, guard tham chiếu của `.claude/`, toàn bộ test, tầng Sanity chạy tuần tự riêng, và
ngưỡng coverage 80%. Các cờ `-UnitOnly`/`-SanityOnly`/`-SkipLint`/`-SkipTests` là **công cụ chẩn
đoán**, không được dùng để đi vòng qua một cổng đang đỏ.

> [!WARNING]
> **Đừng đọc console — đọc file log.** Ở chế độ offscreen, Qt đổ rất nhiều lỗi vô hại ra stderr
> **sau** dòng tổng kết của pytest, nên `| tail` cho bạn xem đúng phần nhiễu đó và có thể **giấu
> mất** dòng lỗi thật. Luôn `> logfile 2>&1`, rồi `grep` file đó tìm
> `FAILED|ERROR|Traceback|ResourceWarning`. Hai bug thật (`BUG-029`/`BUG-030`) chỉ lộ ra nhờ có file
> log đầy đủ để đọc lại.

### Bốn tầng kiểm thử

| Tầng | Chứng minh điều gì |
| :--- | :--- |
| **Unit** (`tests/unit/`) | Hàm thuần, hợp đồng dữ liệu, bất biến, hành vi tất định của từng thành phần. |
| **Integration** (`tests/integration/`) | Hành trình người dùng/ứng dụng thật qua các collaborator thật, biên ngoài được seed/fake cục bộ. |
| **Sanity** (`tests/sanity/`) | App boot thật, DI ráp thật, **và im lặng** — `diagnostic_guard` fail khi có bất kỳ Qt message, log ≥ WARNING hay `warnings.warn` nào. Thêm màn hình mới **không** thêm test ở đây. |
| **Desktop E2E** | Hành trình thật trên phiên đồ hoạ thật (không offscreen), input Qt thật — opt-in, bắt buộc với thay đổi rendering hoặc lỗi GUI được báo. |

`tests/testnet/` **không** phải tầng thứ năm: nó chạm sàn thật bằng credential thật, bị chặn **hai
lớp** (`-Full` luôn `--ignore` nó, và chính tier tự gate bằng `SEW_TESTNET_TESTS=1` + credential
phân giải được):

```powershell
$env:SEW_TESTNET_TESTS = "1"
.\scripts\ci-local.ps1 -TestnetOnly
```

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) chạy trên mọi push/PR vào `master-warrior`.
Hai cổng này **không phải bản sao của nhau** (song song vs tuần tự, cách tách job Sanity) — đừng coi
cổng nào bao hàm cổng nào.

---

## 7. Dữ liệu

Toàn bộ nến tải về nằm ở `database/trading.db` (SQLite, WAL mode; thư mục cấu hình bằng key
`database.dir`, không được commit). Xem nhanh bằng extension **SQLite Viewer** của VS Code: chuột
phải file `.db` → *Open to the Side*, mở bảng `klines`.

Màn hình **Data Management** trong app làm được nhiều hơn: quét dữ liệu đã có theo symbol/timeframe
và soi **khoảng trống (gap)** trước khi backtest hay bật live stream.

---

## 8. Đóng góp — đọc trước khi viết dòng code đầu tiên

Repo này có quy trình bắt buộc, áp dụng cho cả người lẫn AI agent. Điểm vào duy nhất:
**[`.claude/ONBOARDING.md`](.claude/ONBOARDING.md)** — bố cục 2 repo, vòng đời task/bug, lệnh kiểm
chứng thật trên Linux, cách ghi sổ `ROADMAP.md`, và §8 liệt kê những cái bẫy **đã thật sự tạo ra
code hỏng** ở đây.

| Việc | Đọc file |
| :--- | :--- |
| Quyết một mình hay phải hỏi | [`ONBOARDING.md`](.claude/ONBOARDING.md) §7 |
| Kiến trúc: lớp, Port/ABC, Shared Kernel, đặt event ở đâu | [`architecture-rule.md`](.claude/rules/architecture-rule.md) |
| Chất lượng code: typing, magic number, cohesion, lazy import | [`code-quality-rule.md`](.claude/rules/code-quality-rule.md) |
| Trước khi tuyên bố "xong" | [`ci-rule.md`](.claude/rules/ci-rule.md) |
| Trước mỗi commit | [`commit-rule.md`](.claude/rules/commit-rule.md) |
| Khi có bug được báo (**bắt buộc**) | [`bug-fix-rule.md`](.claude/rules/bug-fix-rule.md) |
| Thêm/sửa log | [`logging-rule.md`](.claude/rules/logging-rule.md) |
| Viết test | [`testing-rule.md`](.claude/rules/testing-rule.md) |
| Làm UI: bố cục màn hình, `preview.py`, icon, cột bảng | [`ui-presentation-rule.md`](.claude/rules/ui-presentation-rule.md) |
| Bất kỳ code UI nào (QtWidgets only, không còn QML từ ADR D20) | [`ui-presentation-rule.md`](.claude/rules/ui-presentation-rule.md) |
| Tác vụ nền khởi động từ UI: sở hữu action, huỷ, tách Coordinator | [`async-ui-action-rule.md`](.claude/rules/async-ui-action-rule.md) |
| Đụng `src/domain/**` hoặc `src/application/**`: dữ liệu trung thực | [`domain-truth-rule.md`](.claude/rules/domain-truth-rule.md) |
| Dựng môi trường, thiếu công cụ | [`install-rule.md`](.claude/rules/install-rule.md) |

Bốn điều dễ mất nửa ngày nếu làm sai:

1. **Không bao giờ `git push` nếu user không yêu cầu rõ ràng.** `commit` là hỏi-trước-mặc-định;
   `push` là cấm-mặc-định. Mỗi repository là một lần xác nhận riêng.
2. **Đọc file log, đừng tin console** (xem cảnh báo ở §6).
3. **Hai repository độc lập**, không phải submodule — commit/push tách bạch.
4. **Công việc hay bị để lại chưa commit giữa các phiên.** Task board trông như chưa ai đụng
   **cộng với** working tree bẩn nghĩa là việc **đã làm rồi**, chỉ chưa ghi sổ. Chạy `git status` ở
   **cả hai** repo và đọc diff trước khi kết luận.

### Ngôn ngữ

Tài liệu trong `.claude/`: **tiếng Anh**. Code, định danh, docstring, comment, commit subject:
**tiếng Anh**. Hội thoại với user, file task, bug report, tài liệu trong `Tasks/`, và chuỗi hiển thị
trên UI: **tiếng Việt**.

---

## 9. Trạng thái & lộ trình

Các con số (số task, số test, số bug) **luôn trôi** — đừng tin con số chép trong tài liệu, hãy đọc
thẳng nguồn sự thật:

| Câu hỏi | Nguồn |
| :--- | :--- |
| Epic nào đang chạy, đi tới đâu | [`Tasks/epics/README.md`](Tasks/epics/README.md) |
| Bug nào đang mở | [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) |
| Task board tổng thể | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) |
| Vừa xảy ra chuyện gì, vì sao | `git log` (phần thân commit ở repo này có ghi lý do) |
| Đang dở dang cái gì | `git status` + diff, ở **cả hai** repo |

Ý định sản phẩm và user story đầy đủ: [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](Docs/PROJECT_INTENT_AND_USER_STORIES.md).
