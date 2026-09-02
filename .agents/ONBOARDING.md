---
name: Onboarding
description: Entry point for any AI agent working on Sagittarius Elite Warrior — repo layout, task/bug workflow, real verification commands, bookkeeping, and the traps that repeatedly produce broken code.
trigger: always_on
---

# ONBOARDING — Đọc file này TRƯỚC KHI viết dòng code đầu tiên

Bản đồ quy trình, không phải bản sao của rule: nó nói *khi nào* đọc rule nào, và mô tả những phần chưa được viết ở đâu cả (thao tác 2 repo, lệnh verification thật trên Linux, bookkeeping `ROADMAP.md`).

**Mọi con số trong tài liệu (số file rule, số test, số lỗi lint, trạng thái task) đều TRÔI.** Luôn đếm lại bằng lệnh thật thay vì tin con số đã viết.

---

## 1. Bản đồ tài liệu — đọc theo thứ tự này

| Thứ tự | File | Khi nào |
| :--- | :--- | :--- |
| 1 | `.agents/ONBOARDING.md` (file này) | Luôn luôn, đầu tiên |
| 2 | `.agents/AGENTS.md` | Chỉ để điều hướng — trỏ đúng file rule theo chủ đề |
| 3 | `.agents/rules/code-quality-rule.md` | Mọi thay đổi code Python trong `src/`, `scripts/` |
| 4 | `.agents/rules/architecture-rule.md` | Port/ABC, tầng, CQRS, tách file theo abstraction level |
| 5 | `.agents/rules/ci-rule.md` | Trước khi tuyên bố "xong" — 4 tầng test + lệnh gate |
| 6 | `.agents/rules/commit-rule.md` | Trước mọi commit |
| 7 | `.agents/rules/bug-fix-rule.md` | **Bắt buộc** khi user báo bug |
| 8 | `.agents/rules/logging-rule.md` | Khi thêm/sửa log, và trong mọi bug fix |
| 9 | `.agents/rules/testing-rule.md` | Khi viết test (lệnh chạy ở `ci-rule.md`) |
| 10 | `.agents/rules/async-ui-action-rule.md` | Presenter, tác vụ nền, cancellation, Coordinator |
| 11 | `.agents/rules/domain-truth-rule.md` | Khi đụng `src/domain/`, `src/application/` |
| 12 | `.agents/rules/ui-presentation-rule.md` | Khi đụng `src/presentation/` (Python) |
| 13 | `.agents/rules/qml-rule.md` | Khi đụng file `.qml` |
| 14 | `.agents/Handover.md` | **Ngay sau file này** — phiên trước dừng ở đâu, quyết định nào đừng suy luận lại |
| — | `Tasks/ROADMAP.md` | Hệ thống đang ở đâu, task nào tồn tại |
| — | `Tasks/bug_report/README.md` | Bug Board — bug nào đang mở |
| — | `Tasks/epics/README.md` | Danh sách Epic (mỗi Epic có thư mục + README riêng, §3) |
| — | **§12 của file này** | **Bắt tay vào việc đang dở**. *Trạng thái* ở `Handover.md`, không ở đây |

Đếm số file rule thật bằng `ls .agents/rules/` — **đừng nạp hết**, mỗi file có `trigger` riêng. `install-rule.md` là chuyên đề cài đặt, đọc khi task chạm đúng phạm vi. `code-rule.md` **chỉ là stub điều hướng** (nội dung thật đã tách ra các file trên); giữ stub vì `.agents/Skills/` còn trỏ vào nó (`grep -rl code-rule .agents/Skills/`). Quy tắc bảo mật sống ở `.agents/Skills/sentinel.prompt.md` + `Tasks/epics/EPIC-004_static_security_and_quality_analysis/`, **không** ở `rules/`.

---

## 2. HAI repo độc lập, không phải submodule

```
Sagittarius_Engine/                  ← repo framework (sagittarius_engine/), remote riêng
└── Sagittarius_Elite_Warrior/       ← repo app bot Binance, nhánh `master-warrior`, remote riêng
```

Từ commit `a1efcd6` (2026-08-21) khai báo submodule đã bị xoá hẳn. Hai thư mục chỉ là 2 **repo Git hoàn toàn độc lập**, tình cờ nằm lồng nhau trên đĩa — **không có con trỏ nào cần đồng bộ**.

- Việc trong `Sagittarius_Elite_Warrior/` (gần như mọi task nghiệp vụ): vào đúng thư mục đó, `git commit`/`git push` — chỉ 1 repo.
- Việc trong `sagittarius_engine/` (hiếm — chỉ khi thật sự thiếu cơ chế nền): commit/push riêng trong `Sagittarius_Engine`, không liên quan tới app.

Tài liệu/thói quen cũ nhắc "bump submodule pointer" là quy trình **đã hết hiệu lực**; xác nhận bằng `git ls-files -s Sagittarius_Elite_Warrior` từ superproject (rỗng = đã detach, đừng bump gì cả).

**Không bao giờ `git push` nếu user không yêu cầu rõ ràng.** Commit là mặc định-hỏi (§7); push là mặc định-cấm.

---

## 3. Vòng đời một TASK (tính năng mới)

1. **Task file** trong `Tasks/backlog/` theo mẫu `BOT-XXX_short_description.md` (số kế tiếp số lớn nhất đang tồn tại). User yêu cầu tính năng chưa có task → tạo file task trước, rồi mới code. Epic lớn thì tách task con `BOT-XXXA`, `BOT-XXXB`… và epic phải có bảng liệt kê task con.
2. **Nội dung task file** viết tiếng Việt, tối thiểu: Bối cảnh & vấn đề thật (không chung chung), Thiết kế + **lý do** cho quyết định không hiển nhiên, Thay đổi theo từng file, Kiểm thử.
3. **Code + test.** Xem §5 để biết tầng test nào là đúng.
4. **Hoàn thành:** `git mv Tasks/backlog/BOT-XXX_*.md Tasks/completed/`, đổi trạng thái thành `✅ Hoàn thành (YYYY-MM-DD)`, thêm mục "Ghi chú Triển khai" ghi **bug thật đã phát hiện trong lúc làm**, quyết định thiết kế, số test. Đây là giá trị lớn nhất của task file với người đọc sau — đừng viết cho có.
5. **Bookkeeping `ROADMAP.md`:** xem §6.

Epic **không** chuyển sang `completed/` cho đến khi *tất cả* task con xong; trong lúc đó cập nhật trạng thái tại chỗ (`1/3 xong`).

---

## 4. Vòng đời một BUG

`.agents/rules/bug-fix-rule.md` là nguồn chuẩn — đọc nguyên văn. Ba điểm bị vi phạm nhiều nhất:

- **Viết regression test TRƯỚC khi sửa, và chạy nó để xác nhận nó FAIL đúng lý do.** Test viết sau khi sửa, hoặc fail vì lý do khác (import sai, fixture thiếu), không chứng minh được gì.
- **Chọn đúng tầng test.** Nếu chỗ crash nằm trong method mà test double thay thế thì test đó *không thể* tái hiện bug — `Mock` không chạy thân hàm thật. `BUG-013` "tái hiện" nhầm kiểu này hai lần liên tiếp với `Mock(spec=...)`, pass ngay cả khi chưa sửa gì.
- **Bug report bắt buộc:** `Tasks/bug_report/incomplete/BUG-XXX_mô_tả.md` (sửa xong `git mv` sang `completed/`), có Symptom (bằng chứng thật: traceback/log/ảnh, không diễn giải lại), Root cause (cơ chế thật kèm file:line), Fix, Regression test. Xong thì **thêm dòng vào [Bug Board](../Tasks/bug_report/README.md)** — chỗ duy nhất thấy được bug đang mở; `ROADMAP.md` chỉ hiện bug đã sửa.

User dán log/ảnh vào chat thì **đọc chúng bằng công cụ thật** (Read ảnh, đọc file log) trước khi đưa giả thuyết. Ở `BUG-018`, ô "Database Size" đúng trong khi ô "Stored Records" sai đã khoanh vùng ngay lỗi ở hàm cộng số liệu từ bảng chứ không phải tầng đọc đĩa.

---

## 5. Chạy verification THẬT

`ci-rule.md` quy định `scripts/ci-local.ps1 -Full` là cổng bắt buộc. `pwsh` **có sẵn** trên máy Linux này (`which pwsh`), script chạy được thật:

```bash
pwsh -NoProfile -Command "./scripts/ci-local.ps1 -Full"
# chạy từ thư mục Sagittarius_Elite_Warrior/ (đây là $botRoot, khác mọi lệnh
# bash bên dưới vốn chạy từ superproject)
```

Ưu tiên `pwsh` khi cần đúng cổng CI thật (nó nối dây đúng `mypy`, coverage, sanity tuần tự). Bộ lệnh bash dưới đây dùng cho kiểm tra nhanh có chủ đích — chạy **từ thư mục superproject**:

```bash
# Unit (~3 phút; đếm số test thật bằng chính lệnh này, đừng tin số ghi ở đâu)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/unit/ -q

# Sanity (~35 giây)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/sanity/ -q

# Lint (read-only, không bao giờ để CI tự --fix)
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff check  <file...>
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff format --check <file...>

# Mypy (EPIC-002, gate thật — src VÀ scripts PHẢI chung 1 lệnh, xem lý do
# ở ci-rule.md §1 và Tasks/reports/EPIC-002A_mypy_baseline_audit.md §3)
PYTHONPATH=. \
  Sagittarius_Elite_Warrior/.venv/bin/mypy --config-file Sagittarius_Elite_Warrior/pyproject.toml \
  --namespace-packages --explicit-package-bases \
  Sagittarius_Elite_Warrior/src Sagittarius_Elite_Warrior/scripts
```

**Bẫy đọc kết quả — quan trọng.** Ở chế độ `offscreen`, QML xả rất nhiều `TypeError: Cannot read property '...' of null` ra stderr; chúng vô hại và xuất hiện *sau* dòng tổng kết của pytest, nên `tail` cho bạn xem nhầm đống nhiễu đó. Luôn ghi ra file rồi grep:

```bash
... -q > /tmp/run.log 2>&1; grep -E "^[0-9]+ (passed|failed)|failed," /tmp/run.log | tail -3
```

**Áp dụng cho MỌI lệnh verification, kể cả `ci-local.ps1 -Full`** — lý do nặng hơn "nhiễu": `| tail -N` có thể **mất hẳn** dòng lỗi thật. Bằng chứng (`BUG-029`/`BUG-030`): agent trước chỉ chạy `pytest` thô; khi cuối cùng chạy `ci-local.ps1 -Full` và redirect toàn bộ ra file (`> file 2>&1`, không phải pipe/tail), lộ ra 2 bug thật cùng lúc — (1) `Join-Path` chỉ chạy trên PowerShell 7+, phá cổng CI trên PowerShell 5.1 mà script tự khai hỗ trợ; (2) `-n 6` (song song) làm 1 worker chết sau `ResourceWarning: unclosed database`, tái hiện 2/2 lần, không flaky. Cả hai chỉ lộ ra vì có file log đầy đủ để đọc lại. Luôn `> logfile 2>&1`, không `| tail`.

**Về lint:** repo luôn có sẵn vài lỗi `I001` (import chưa sort) từ phiên khác không do bạn gây ra — kiểm thật bằng `ruff check src tests`. Chỉ sửa lint trong **file bạn đang sửa cho task hiện tại**, không đi dọn file vô can (diff bug-fix lẫn thay đổi không liên quan thì không ai review nổi). Muốn dọn toàn repo thì làm một commit `style:` riêng, sau khi hỏi user.

---

## 6. Bookkeeping `Tasks/ROADMAP.md` — phần hay bị làm ẩu nhất

Mỗi task/bug hoàn thành phải cập nhật **cả ba** chỗ:

1. **Thêm 1 dòng vào ĐẦU mục `🟢 Completed`** (mới-nhất-trước). Dòng đó phải tóm tắt root cause / quyết định thiết kế, không chỉ nhắc lại tên task.
2. **Tính lại bảng số lượng bằng lệnh thật, không đếm tay:**
   ```bash
   for d in completed in_progress backlog cancelled; do
     printf "%s %s\n" "$d" "$(ls Tasks/$d/*.md 2>/dev/null | wc -l)"
   done
   ```
   Rồi cập nhật cả 4 dòng + tổng + tỷ lệ %. (Bug report trong `Tasks/bug_report/` **không** tính vào các con số này.)
3. **Cập nhật dòng epic tại chỗ** trong bảng nhóm tương ứng, và ghi chú "Cập nhật <ngày>" ở đầu file.

Sau khi thêm task file mới có link chéo, **kiểm tra link không gãy**:

```bash
cd Tasks/backlog && grep -oh "](\.\./\?[^)]*\.md)" BOT-XXX*.md | tr -d '](' | sed 's/)$//' \
  | sort -u | while read -r l; do [ -f "$l" ] || echo "BROKEN: $l"; done
```

**Epic lớn (nhiều task con, nhiều lần cập nhật trạng thái) dùng `Tasks/epics/EPIC-XXX_slug/` riêng, không phải 1 dòng trong `ROADMAP.md`** (chi tiết ở `Tasks/epics/README.md`). Cấu trúc: `README.md` (tổng quan + bảng task con) + `incomplete/`/`completed/` (mã task con `EPIC-XXXA`, `EPIC-XXXB`…). `ROADMAP.md` khi đó **chỉ giữ 1 dòng liên kết** tới `README.md` của epic — không chép nội dung. Xong 1 task con thì cập nhật cả 3 nơi: `README.md` của epic, `Tasks/epics/README.md` (đếm lại X/N), và dòng 1-liên-kết ở `ROADMAP.md`. (Epic kiểu cũ, phẳng trong `Tasks/backlog/`/`completed/` — `BOT-109`, `BOT-112`, `BOT-115` — giữ nguyên định dạng cũ.)

Đề xuất kiến trúc chưa thành task (chưa ai duyệt) sống ở `Tasks/proposal/PRO-XXX.md` — khác `Tasks/backlog/` (đã được chấp nhận) và khác `Tasks/epics/` (đã tách task con cụ thể). Khi được duyệt, chuyển hoá thành `BOT-XXX`/`EPIC-XXX` thật; `PRO-XXX.md` không tự thực thi được.

---

## 7. Quyền hạn — cái gì được tự làm, cái gì phải hỏi

| Hành động | Quy tắc |
| :--- | :--- |
| Đọc, phân tích, chạy test | Tự do |
| Sửa code trong phạm vi user yêu cầu | Tự do |
| `git commit` | **Hỏi trước.** Không bao giờ commit tự phát |
| `git push` | **Chỉ khi user yêu cầu rõ ràng**, và mỗi repo (app / engine) là 1 lần xác nhận riêng — 2 repo độc lập từ §2, không còn liên đới nhau |
| Sửa file ngoài phạm vi task | Không, trừ khi user yêu cầu |
| Xoá/ghi đè file của user | Đọc nội dung trước, hỏi trước |

### Tự quyết là mặc định — đừng hỏi user cho từng lựa chọn nhỏ

> **Phương châm quyết định (user chốt 2026-08-30; mở rộng 2026-09-02 ra ngoài
> phạm vi kiến trúc).** Trước đây phương châm này chỉ nằm trong
> `rules/architecture-rule.md` và **không file điều hướng nào trỏ tới nó** —
> tồn tại mà như không có. Nó là luật về **quyền tự quyết**, nên thuộc mục này.

Áp cho **mọi** quyết định kỹ thuật, không riêng kiến trúc:

- **Nhiều hướng đều có lý, không có "đúng tuyệt đối" → quyết theo best
  practice / design pattern / architecture pattern đã được kiểm chứng.**
- **Phân vân thì tham chiếu cách các dự án lớn, đã được cộng đồng kiểm chứng,
  đang làm** — ưu tiên pattern **có tên, có tiền lệ rộng** hơn tự sáng chế một
  hình dạng mới không ai kiểm chứng.
- **Không ngại redesign** một phần đã có nếu thiết kế hiện tại là *hard design*
  (cứng, chắp vá, khó mở rộng). **"Đang chạy được" không phải lý do giữ
  nguyên.**
- **Agent tự quyết và làm tiếp** — không dừng lại hỏi user cho từng lựa chọn
  nhỏ.

**Chỉ hỏi khi rơi vào đúng một trong ba nhóm này:**

1. Đánh đổi **thật sự lớn hoặc không đảo ngược được** (đổi kiến trúc nền, đổi
   contract công khai, di trú dữ liệu).
2. Hành động nằm trong **bảng "phải hỏi" ngay trên** — `commit`, `push`, xoá,
   ghi đè, sửa ngoài phạm vi task. Phương châm này **không** nới nhóm đó.
3. Thiếu một thông tin **chỉ user mới có** (ý định nghiệp vụ, thứ tự ưu tiên).

Phương châm quyết **hướng nào đúng**, **không** đổi **quy trình làm sao**: vẫn
task + ADR trước khi code (§3, §12.2), vẫn qua đúng cổng CI (`ci-rule.md`) và
commit (`commit-rule.md`) như cũ.

### Phản biện là bắt buộc, không phải tuỳ chọn

- The AI assistant MUST actively challenge/refute user requests if they introduce inconsistencies, anti-patterns, layer violations, or break established domain principles.
- Never blindly follow contradictory instructions; explain the root issue and propose a clean, consistent alternative.

Tức là: yêu cầu của user tạo mâu thuẫn kiến trúc, vi phạm ranh giới tầng, hoặc phá nguyên tắc đã chốt → phải nói ra và đề xuất phương án sạch, không im lặng làm theo. Nhưng nếu user đã nghe và vẫn quyết giữ nguyên yêu cầu thì làm đầy đủ theo họ.

---

## 8. Mười một cái bẫy khiến agent khác tạo ra code lỗi

Tất cả đều đã xảy ra thật trong repo này, không phải giả định.

1. **Tự tính giá trị kỳ vọng của test bằng đầu thay vì chạy code thật.** Ở `BOT-106A`, một chuỗi return hằng số về mặt toán học vẫn cho `statistics.stdev()` ra ~1e-16 chứ không phải `0.0`, khiến Sharpe bung ra ~3.2×10¹⁵. Chạy code thật rồi mới chốt số kỳ vọng.
2. **So sánh float bằng `== 0` hoặc `if value:`.** Dùng `math.isclose(x, 0.0, abs_tol=1e-9)`. Xem bẫy 1 để biết hậu quả.
3. **Assert số lượng bằng hằng số cứng** (`len(cards) == 9`). Task sau thêm 1 card là test vỡ dù không có gì sai. Assert theo *thứ có ý nghĩa* (có mặt/không có mặt, thứ tự tương đối), không theo số đếm.
4. **Assert bằng full-dict equality** trên output của `to_dict()`. Phiên khác thêm field hợp lệ là test vỡ. Assert subset đúng field test thật sự quan tâm.
5. **Thêm field vào dataclass đã đóng băng mà không đặt default.** `Trade`, `BacktestMetrics`, `BacktestRunConfig` có hàng trăm call site dựng trực tiếp trong test. Field mới **luôn** phải có giá trị mặc định.
6. **Đổi công thức dùng chung mà không rẽ nhánh bảo toàn hành vi cũ.** `BOT-114` thêm đòn bẩy vào `PaperExchange`: công thức PnL kiểu "spot" của LONG sai hoàn toàn khi `margin != notional`. Cách đúng là giữ **nguyên si** nhánh cũ cho `leverage == 1.0` và chỉ dùng công thức mới khi thật sự có đòn bẩy — bằng chứng là 47 test cũ pass không sửa dòng nào.
7. **Gọi `fsm.transition_to(X)` khi đang ở đúng `X`.** Ma trận FSM không có cạnh tự thân, sẽ raise; `@safe_ui_action` nuốt lỗi nên app không chết nhưng slot **chết giữa chừng**, mọi dòng phía sau không chạy. Đây chính là `BUG-018`. Worker nền chưa từng khoá UI thì **không được** phát tín hiệu unlock.
8. **Quên rằng `@safe_ui_action` nuốt exception.** Một slot có thể chết im lặng ở giữa. Đừng đặt việc quan trọng (refresh dữ liệu) *sau* một lời gọi có thể ném lỗi.
9. **Thêm `logger.info()` vào một vòng lặp nóng.** Log **không** miễn phí: `SignalLogHandler` gắn vào logger **gốc** `"App"` ở mức INFO (`data_management_presenter.py`), nên **mọi** `App.*` của **mọi** subsystem đều bị đẩy qua queued cross-thread signal sang UI thread, rồi mỗi dòng chạy trọn một chu kỳ `beginInsertRows`/`endInsertRows`/`countChanged` trong `LogListModel`. `BUG-042`: `PaperExchange` log INFO mỗi lệnh khớp → 838 trades sinh **5.028 dòng trong 2 giây** → UI đơ cứng, đơ tuyến tính theo số trade. Log nằm ở màn hình nào **không** quan trọng — handler bắt ở logger gốc. Trong vòng lặp chạy nhiều lần (mỗi trade, mỗi nến, mỗi tick) dùng `logger.debug()`, hoặc gộp/throttle trước khi log — xem `ProgressThrottle` (`BUG-033`) làm mẫu cho đúng đường signal.
10. **Sửa file `.qml` mà quên logic phải nằm ở Python.** QML chỉ khai báo và binding; state machine, validate, tính toán đều thuộc Presenter/ViewModel. Và `.qml` > 300 dòng thì tách component.
11. **Thêm `@abstractmethod` mới vào một Port rồi chỉ cập nhật implementer "chính".** `ruff` không bắt được — kiểm 1 class có implement đủ interface hay không là việc của type checker. `BUG-026`: một script probe implement `IExchangeClient` bị bỏ quên khi interface thêm method, crash ngay lúc khởi tạo (`TypeError: Can't instantiate abstract class`). Khi đổi 1 Port, grep implementer ở **cả `src/`, `scripts/`, VÀ `tests/`** — bỏ sót `scripts/` chính là lỗi lúc sửa `BUG-025`, để lọt 1 defect sống y hệt. `mypy` (gate `src`+`scripts` chung 1 lệnh, §5) là lưới an toàn thứ hai — nhưng đừng chỉ dựa vào tool, grep vẫn phải làm khi đổi interface.

---

## 9. Hai bộ `.agents/` — đừng đọc nhầm repo

`Sagittarius_Engine` (framework) và `Sagittarius_Elite_Warrior` (app bot, thư mục này) đều có `.agents/` riêng, là **2 repo Git độc lập** (§2), chỉ tình cờ nằm lồng nhau trên đĩa. Đây là chỗ nhầm lẫn nguy hiểm nhất với agent mới.

| | `../.agents/` (`Sagittarius_Engine`) | `.agents/` (`Sagittarius_Elite_Warrior` — thư mục này) |
| :--- | :--- | :--- |
| Phục vụ | framework `sagittarius_engine/` | app bot |
| Bảng task | `../Tasks/README.md` (Kanban, mã `TASK-XXX`) | `Tasks/ROADMAP.md` (mã `BOT-XXX`/`BUG-XXX`/`EPIC-XXX`) |
| Entry point | `PLAYBOOK.md` + `manifest.yml` | `ONBOARDING.md` (file này) + `AGENTS.md` |
| Remote Git | riêng, repo `Sagittarius_Engine` | riêng, repo `Sagittarius_Elite_Warrior` |

Khi làm việc trong app, **luôn ưu tiên rule của repo này**. Rule của `Sagittarius_Engine` chỉ áp dụng khi bạn thật sự sửa code framework — và khi đó là 1 commit/push hoàn toàn tách biệt (§2). Hai bảng task không liên quan gì nhau — đừng ghi task app vào `Tasks/README.md` của engine và ngược lại.

Các mục theo phiên trong `Handover.md` là **bản ghi lịch sử** (chính file đó cảnh báo ở khối `[!IMPORTANT]` đầu file); trạng thái hiện tại nằm ở §12.

Lưu ý: **mọi rule file của cả hai repo chỉ ghi lệnh PowerShell**. Trên Linux dùng lệnh ở §5.

---

## 10. Ngôn ngữ

- **Trao đổi với user, task file, bug report, ROADMAP:** tiếng Việt.
- **Code, tên biến, docstring, comment, commit subject:** tiếng Anh.
- **Chuỗi hiển thị trên UI:** tiếng Việt (đúng thuật ngữ domain đã chốt, ví dụ "Thông số Chiến lược" khác với cài đặt Bot chung).

---

## 11. Báo cáo với user — mức project lead, không phải mức implementation

- Khi báo cáo tiến độ, trạng thái task/epic, tóm tắt điều tra, hay kết quả test cho user trong hội thoại, viết như đang báo cáo cho một **project lead**: kết luận, trạng thái hiện tại, quyết định cần user ra, rủi ro/blocker. **Không** đi vào chi tiết implementation (tên hàm, dòng code, kiểu dữ liệu nội bộ, tên biến C++…) trừ khi user hỏi thẳng, hoặc chi tiết đó **quyết định trực tiếp** hành động tiếp theo. Ví dụ: "F4 đang bị chặn bởi BUG-015 (Windows: geometry bị rebuild khi pointer move), giả thuyết root cause đang điều tra" là đủ; không cần liệt kê `QSizeF`/tên file `.cpp`.
- **Không áp dụng cho tài liệu lưu trữ lâu dài** — task file, bug report (`Tasks/bug_report/`), báo cáo (`Tasks/reports/`) vẫn phải đầy đủ root cause/file:line/bằng chứng theo `bug-fix-rule.md` và §3/§4. Quy tắc "mức project lead" chỉ áp cho câu trả lời trong hội thoại.

---

## 12. Bắt tay vào việc đang dở — đọc mục này trước khi gõ dòng đầu tiên

### 12.1 Ba lệnh đầu tiên, lần nào cũng vậy

```bash
git -C . status
git -C ../Sagittarius_Engine status
cat Tasks/epics/README.md
```

**Việc ở dự án này thường được để lại chưa commit giữa các phiên** — theo §7, agent không tự commit. Nên `git status` không phải thủ tục: bảng task trông như chưa ai đụng **cộng với** cây làm việc bẩn nghĩa là việc **đã làm rồi**, chỉ chưa được ghi lại. Đọc diff trước khi kết luận một task còn nguyên. Tin kết quả 3 lệnh trên, không tin đoạn văn nào mô tả trạng thái.

### 12.2 Đang làm tới đâu → [`Handover.md`](Handover.md), không phải ở đây

**Mục này cố ý KHÔNG liệt kê epic nào đang chạy hay task nào tiếp theo** (bản trước có bảng đó và nó sai chỉ sau vài giờ). Trạng thái sống ở **một** chỗ: [`.agents/Handover.md`](Handover.md) §1, file được **thay thế** mỗi phiên. Ở đây chỉ giữ thứ không đổi:

- **Bắt buộc: đọc `README.md` của epic + file `DECISION_*.md` (ADR) của nó trước khi làm bất kỳ task con nào.** ADR ghi lại quyết định đã tranh luận xong với user — trong đó có vài quyết định **đảo ngược** phương án trước. Tự suy luận lại sẽ tốn một phiên và thường ra kết quả khác. Epic nào có `design/*.puml` thì xem sơ đồ trước khi động vào code.
- **Bảng task con trong mỗi epic có cột `Repo`.** Task ghi `Engine` phải commit ở repo Engine (§2, §9). Bảng xếp theo rủi ro tăng dần và ghi rõ cái nào chặn cái nào — đừng nhảy cóc.
- **Trạng thái ghi trong task file có thể đã cũ hơn code.** Trước khi tin "task này chưa làm", kiểm bằng chính code (`find`, `grep`, chạy test) — đã có task hoá ra được làm xong bởi epic khác, và task khác thì **hết đối tượng** để làm.

### 12.3 Task con tiếp theo và thứ tự

Khi làm xong một task con: `git mv incomplete/EPIC-XXXY_*.md completed/`, ghi phần "Xong <ngày>" vào cuối file đó (root cause, quyết định, bằng chứng verify), cập nhật dòng tương ứng trong bảng ở `README.md` của epic và số "x/y task con xong" ở đầu file. Đúng quy ước `Tasks/epics/README.md`.

### 12.4 Cơ chế mới ở Engine — dùng, đừng viết lại

`EPIC-008` đã dựng sẵn các cơ chế sau ở repo Engine. Viết cái khác thay thế là tái tạo lại đúng lỗi mà chúng vừa đóng. Chi tiết đầy đủ ở `Sagittarius_Engine/.agents/context/events.md`:

| Cần gì | Dùng cái gì |
| :--- | :--- |
| Định nghĩa event | kế thừa `BaseEvent` — được `event_id`/`occurred_on`/`event_name` + tự vào catalog |
| Presenter đăng ký nghe event | `self.subscribe(...)`, **không** `self.event_bus.on(...)` — tự nhảy về main thread và tự gỡ khi dispose |
| Dọn dẹp khi tắt presenter | override `shutdown()`, **không bao giờ** override `dispose()` |
| Báo lỗi handler | `report_handler_failure` |
| Logger khi không được inject | `resolve_bus_logger` — **không** `NullLogger` |

### 12.5 Bốn nguyên tắc user đã chốt, áp cho mọi task

1. **Sửa cơ chế, không hot fix.** Cùng một lỗi lặp ở nhiều nơi mà chỉ sửa mỗi chỗ được báo là không chấp nhận được. Sửa mà không giải thích được *vì sao* triệu chứng biến mất thì không tính là sửa (`bug-fix-rule.md`).
2. **Càng nhiều file càng tốt — một abstraction một file, khác abstraction thì cũng không chung thư mục.** Tách là mặc định, **gộp mới là thứ phải có lý do**. Hai ràng buộc cứng: (a) hai thứ **khác abstraction level** không được nằm chung một file (Port vs implementation, base class vs subclass); (b) file **khác abstraction level** không được nằm chung một `dir` — thư mục là một tầng, không phải cái sọt (`interfaces/` không chứa implementation, `widgets/` dùng chung không chứa widget riêng của 1 màn). Đối trọng duy nhất là Single-Scope Cohesion trong `code-quality-rule.md`, và nó **chỉ** thắng khi các định nghĩa mô tả **cùng một vòng đời** (enum + ma trận của một FSM) — "cùng feature"/"cùng màn hình" **không** tính. Ngưỡng buộc tách: **>400 dòng/file** hoặc **>15 method công khai/lớp**. Phân xử nhanh: *đổi A có bắt buộc phải sửa B không?* Có → chung file; không → tách. Toàn văn ở [`rules/architecture-rule.md`](rules/architecture-rule.md) §5 "Abstraction-Level Separation".
3. **Trình design trước khi implement** với mọi việc tái cấu trúc: PlantUML class + component, as-is và to-be, chỉ rõ cái gì dùng chung / cái gì riêng từng màn — duyệt xong mới viết task file và code.
4. **Không commit, không push nếu user không yêu cầu** (§7).

### 12.6 Bẫy khi chạy gate ở repo Engine

`scripts/ci-local.ps1` bên Engine có thể báo đỏ những test **không liên quan** tới thay đổi của bạn: `BUG-006` (hai test "no QML runtime warnings" phụ thuộc thứ tự collection — thêm một file test mới cũng đổi được kết quả) và `tests/test_agents_docs_resolve.py` (không tìm thấy `grep` trên `PATH` khi chạy qua PowerShell).

**Trước khi kết luận lỗi do mình gây ra, A/B nó:** `git stash push -u` → chạy → `git stash pop` → chạy. Mất hai phút, và đó là khác biệt giữa một regression thật với một giờ đuổi theo môi trường.
