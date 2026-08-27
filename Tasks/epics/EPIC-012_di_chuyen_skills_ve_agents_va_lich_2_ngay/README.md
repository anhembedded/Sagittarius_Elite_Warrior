# EPIC-012 — Dời `.jules/` sang `.agents/Skills/`, xoá `.jules/`, lịch chạy 2 ngày/agent

**Trạng thái:** ✅ Hoàn thành 2026-08-27
**Nguồn:** User yêu cầu trực tiếp — *"tạo cho tôi các task định kỳ 2 ngày từ
các skill vừa làm, dời các skill đó lên dir AGENT, xong dir
Sagittarius_Elite_Warrior/.jules"*, làm rõ qua `AskUserQuestion`: dir AGENT =
`Sagittarius_Elite_Warrior/.agents/Skills`, xoá hẳn `.jules/` sau khi dời, mỗi
agent tự chạy định kỳ 2 ngày/lần (không xoay vòng).
**Phụ thuộc:** [`EPIC-011`](../EPIC-011_dong_bo_skill_dinh_ky_jules/README.md) —
epic đó dựng nội dung 7 prompt + `README.md` chung; epic này chỉ dời vị trí và
gắn lịch chạy thật, không viết lại nội dung nghiệp vụ của từng agent.

---

## 1. Vì sao hỏi trước khi làm

Yêu cầu gốc mơ hồ ở hai điểm có thể gây hại thật nếu đoán sai:

1. **"dir AGENT" là gì** — có thể là cơ chế subagent riêng của Claude Code
   (`.claude/agents/`), một thư mục mới, hay một thứ khác hẳn.
2. **Xoá `.jules/` có phá gì không** — `CLAUDE.md` (trước khi sửa) nói thẳng
   7 file `.jules/*.prompt.md` là *"quy ước của bộ công cụ khác trong repo —
   không phải của Claude Code"*, và `commit-rule.md` §6 nhắc tới nhánh
   `jules-*` như bằng chứng một cơ chế tự động thật đang tồn tại. Xoá nhầm một
   thư mục mà dịch vụ ngoài đang đọc là hành động khó hoàn tác theo đúng nghĩa
   "ảnh hưởng hệ thống ngoài phiên này".

Cả hai không thể tự suy ra chắc chắn từ chính repo — đã hỏi thẳng bằng
`AskUserQuestion` thay vì đoán. User xác nhận: `.agents/Skills`, xoá hẳn
`.jules/`, mỗi agent tự chạy 2 ngày/lần.

## 2. Việc đã làm

### 2.1. Dời nội dung, không chỉ đường dẫn

`git mv .jules/*.md .agents/Skills/` — giữ lịch sử git cho cả 9 file (`README.md`,
7 `*.prompt.md`, và `bolt.md` — journal thật đầu tiên, ghi lúc `EPIC-011` §8
tự phát hiện lỗi của chính nó).

`.agents/Skills/` nằm **sâu hơn `.jules/` một cấp** (`.agents/Skills/` = 2 cấp
từ gốc repo, `.jules/` chỉ 1 cấp). Mọi link tương đối trong 8 file `.md` phải
tính lại theo đúng cấp mới — không phải tìm-thay chuỗi:

- Link trỏ vào `.agents/rules/...`: **ngắn đi** một đoạn (`../.agents/rules/X`
  → `../rules/X`, vì giờ đã đứng trong `.agents/`).
- Link trỏ ra ngoài `.agents/` (`CLAUDE.md`, `Tasks/...`, `.claude/...`):
  **dài thêm** một `../` (`../CLAUDE.md` → `../../CLAUDE.md`).

Viết bằng script, verify bằng cách resolve từng link thật — không đoán bằng
mắt. Sau đó quét toàn bộ prose còn lại (không phải link) đổi `.jules/` →
`.agents/Skills/`.

**Tai nạn nhỏ giữa chừng:** `git checkout -- .agents/Skills/doctor.prompt.md`
lỡ phục hồi file về đúng bản đã `git mv` nhưng **chưa** áp bản sửa link (vì
sửa link xảy ra sau `git mv`, trước khi `git add` lại) — xoá mất công sửa của
chính file đó. Phát hiện ngay qua guard tự báo lỗi, sửa lại, và từ đó `git add`
ngay sau mỗi lần sửa thay vì để rời.

### 2.2. Guard `.jules` → guard mới, và một lỗ hổng thật lộ ra khi dời

`scripts/check_jules_prompt_references.py` → `scripts/check_skill_prompt_references.py`
(xoá file cũ, tạo file mới — không giữ cả hai). Đổi `CHECKED_ROOTS` từ quét
`.jules/*.md` sang `.agents/Skills/*.md`.

**Phát hiện khi viết lại:** `CHECKED_ROOTS` bản cũ **không có** `.claude/` —
nghĩa là link `../.claude/skills/test-health/contract.json` trong
`scout.prompt.md` **chưa bao giờ được guard thật sự kiểm tra** kể từ khi
`EPIC-011` tạo ra guard này. Đã thêm `.claude/` vào `CHECKED_ROOTS` — không
phải scope creep, mà là đóng đúng một lỗ mà việc dời file tình cờ lộ ra.

Verify hai chiều trên guard mới, y hệt cách `EPIC-011G` đã làm:
- Chạy sạch: `OK: every repository path referenced by .agents/Skills/*.md resolves.`
- Bơm lỗi cố ý (`.agents/rules/ghost-rule.md`) → exit 1, gọi đúng tên file +
  đường dẫn. Khôi phục bằng `cp` từ bản sao lưu (không dùng `git checkout --`
  lần này, để tránh lặp lại tai nạn ở §2.1).

`scripts/ci-local.ps1` và `.github/workflows/ci.yml` (thêm ở `EPIC-011H`/PR #139):
đổi tên bước từ *"Jules Prompts - Repository Reference Check"* sang *"Skill
Prompts - Repository Reference Check"*, trỏ đúng script mới.

### 2.3. Sửa mọi con trỏ sống trong tài liệu gốc

`CLAUDE.md`, `.agents/AGENTS.md`, `.agents/ONBOARDING.md`, `.agents/Handover.md`,
`.agents/rules/code-rule.md`, `.agents/rules/ci-rule.md` — mỗi chỗ **đang** trỏ
vào `.jules/...` như một sự thật hiện tại đã sửa theo vị trí mới, kèm ghi chú
"Sửa 2026-08-27 (EPIC-012)" theo đúng khuôn mẫu các note trước đó đã dùng.

**Cố ý không đụng vào:** các file lịch sử đã đóng (`Tasks/completed/BOLT-001...`,
`Tasks/completed/DOCTOR-001...`, `Tasks/completed/DOCTOR-002...`,
`Tasks/epics/EPIC-011_.../**`, `Tasks/reports/BOLT-001...`,
`Tasks/bug_report/completed/BUG-058...`) — chúng ghi lại sự thật **tại thời
điểm đó**, ví dụ "Nguồn: chạy `.jules/bolt.prompt.md`". Viết lại thành
`.agents/Skills/bolt.prompt.md` sẽ là xuyên tạc lịch sử: file đó **thật sự**
từng ở `.jules/` khi task đó chạy. Đúng chính triết lý mà `EPIC-011` §8 đã
nói: "resolve xong không có nghĩa được sửa thành khác đi lịch sử".

### 2.4. Lịch chạy 2 ngày/agent — Routine bền, không phải Cron phiên

Dùng `create_trigger` (Routine bền, sống ngoài phiên), **không** dùng `CronCreate`
(chỉ sống trong phiên này, tự xoá sau 7 ngày — không phù hợp cho lịch dài hạn).

Mỗi agent một Routine riêng, `create_new_session_on_fire: true` (phiên mới hoàn
toàn mỗi lần bắn, không có ngữ cảnh cũ — đúng tinh thần "agent chạy không người
trông" mà `.agents/Skills/README.md` mô tả). Cách diễn đạt "2 ngày" bằng cron
chuẩn 5 trường: `<phút> <giờ> 1-31/2 * *` — bắn vào các ngày **lẻ** trong tháng,
giờ/phút riêng cho từng agent để không đụng nhau:

| Agent | Trigger ID | Cron (UTC) | Lần chạy kế tiếp |
| :--- | :--- | :--- | :--- |
| Bolt ⚡ | `trig_01BwA1JYYbXAHqmQM1zfCurA` | `7 2 1-31/2 * *` | 2026-08-29 02:07 |
| Doctor 🩺 | `trig_01Fc7YdUiKGk8Pq77myGYoZw` | `15 3 1-31/2 * *` | 2026-08-29 03:15 |
| Janitor 🧹 | `trig_01Y1N97jU1ShQMx9sPAxaTV7` | `22 4 1-31/2 * *` | 2026-08-27 04:22 |
| Palette 🎨 | `trig_019Nxd6Wh9a39kRA3FSv7QEg` | `37 5 1-31/2 * *` | 2026-08-27 05:37 |
| Scout 🧪 | `trig_01Y29RwEyYwnMpNBG2XMZvAH` | `44 6 1-31/2 * *` | 2026-08-27 06:44 |
| Scribe 📝 | `trig_01ADe5DVZNqgWPh6CEG4igcU` | `51 7 1-31/2 * *` | 2026-08-27 07:51 |
| Sentinel 🛡️ | `trig_01GrR9rKNNYbLF6WytZZnsaE` | `8 9 1-31/2 * *` | 2026-08-27 09:08 |

**Giới hạn thật của cách diễn đạt này, nói thẳng chứ không giấu:** `N/2` trên
trường ngày-trong-tháng xấp xỉ "mỗi 2 ngày", không chính xác tuyệt đối qua ranh
giới tháng — tháng 31 ngày thì khoảng cách ngày 31 → ngày 1 tháng sau chỉ 1
ngày (không phải 2); tháng ngắn hơn thì khoảng cách có thể giãn ra 2-3 ngày.
Đây là giới hạn cố hữu của cron 5 trường cho chu kỳ > 1 ngày, không phải lỗi
cấu hình — chấp nhận được cho một agent "chạy 1 việc nhỏ mỗi lần, không có gì
nếu lệch 1 ngày".

**Giờ/phút cố ý không tròn (`:00`/`:30`)** để không dồn vào đúng lúc hàng loạt
worker khác trên hạ tầng cùng bắn giờ tròn.

### 2.5. Lỗ hổng phát hiện lúc gắn lịch: phiên bắn ra không có tool GitHub

`create_trigger` cảnh báo rõ ở cả 7 lần gọi: *"this trigger stores no MCP
connectors, so the sessions it fires will run without connector tools"*.
Kiểm bằng `ListConnectors`: tài khoản chỉ có connector `Gmail` đăng ký ở cấp
account; `github` mà phiên hiện tại đang dùng đến từ cơ chế repo-scope của
CCR, không phải connector cấp account — nên **không có gì để chuyển tiếp**
cho phiên mới mỗi lần Routine bắn.

**Hệ quả (bị đoán quá bi quan lúc PR #140 mới merge, sửa ngay sau đó — xem
§2.6):** ban đầu ghi là mỗi phiên do Routine tạo ra "rất có thể không gọi
được" `create_pull_request`. Prompt của cả 7 Routine khi đó được sửa thành
*thử* mở PR nếu có tool, không thì chỉ push nhánh.

### 2.6. Sửa 2026-08-27 (cùng ngày, sau khi user hỏi thẳng): kết luận ở §2.5 sai cơ chế

User phản ứng đúng: *"chạy mà không public PR được thì có ý nghĩa gì nữa"* —
một agent chạy định kỳ mà chỉ push nhánh rồi bỏ đó, không ai review, không
khác gì không chạy. Đáng để tìm cách sửa thật thay vì chấp nhận giới hạn.

**Đã kiểm chứng lại bằng hành động thật, không suy đoán lần hai:** gọi
`add_repo(owner="anhembedded", repo="Sagittarius_Elite_Warrior", access="push")`
ngay trong phiên này. Kết quả: repo đã gắn sẵn, không cần cấp lại — nhưng quan
trọng hơn là đọc đúng mô tả của chính tool đó: `access: "push"` kích hoạt
*"the full repository-access checks"*, một cơ chế cấp quyền theo **tài khoản +
repo** (giống hệt cơ chế mà chính phiên này đang dùng để gọi
`create_pull_request` suốt cả buổi) — **hoàn toàn khác** với "connector" kiểu
Gmail/Slack mà `create_trigger`/`ListConnectors` nói tới ở §2.5. Cảnh báo
"no MCP connectors" của `create_trigger` là **có thật nhưng lạc đề** — nó nói
về loại cấp quyền không liên quan tới cách phiên này thật sự có tool GitHub.

**Sửa:** cả 7 prompt Routine đổi bước 1 thành gọi `add_repo` với
`access: "push"` tường minh (chứ không chỉ "add nếu chưa có" — mặc định của
`add_repo` là `"read"`, không đủ để mở PR), và bước 5 đổi từ "thử, không thì
push nhánh thôi" thành lệnh thẳng: commit, push, mở PR, theo dõi tới khi merge
— vẫn giữ đúng một câu dự phòng cho trường hợp cực hiếm cơ chế này không hoạt
động như tài liệu tool mô tả.

**Chưa thể xác nhận 100% bằng một lần bắn thật** — không có cách ép Routine
bắn ngay và chờ nó chạy xong trong phiên này để xem kết quả cuối. Janitor đã
bắn một lần lúc 04:22 UTC (trước khi sửa) và không tạo branch nào — tức nó
không tìm ra việc để làm (kết quả hợp lệ theo brief), không phải bằng chứng
cho cả hai chiều của giả thuyết này.

**Bằng chứng gián tiếp mạnh cho thấy đây là vấn đề đáng sửa thật:** `git branch -r`
lộ ra **16 nhánh cũ** mang đúng tên các persona này (`bolt-*`, `doctor-*`,
`sentinel-*`, `jules-*`), từ 2026-08-10 đến 2026-08-21, **không nhánh nào được
merge** — bằng chứng một fleet tự động thật đã từng chạy trên chính repo này,
push được nhưng không ai review/merge, đúng thứ `commit-rule.md` §6 ("Stale
Branches... `jules-*`") được viết ra để xử lý hậu quả. Không dọn các nhánh đó
trong task này — ngoài phạm vi, không ai yêu cầu — nhưng đáng ghi lại vì nó
xác nhận: "chạy mà không mở PR được" là chuyện đã thật sự xảy ra và lãng phí
công ở repo này trước khi epic này tồn tại.

## 3. Xác nhận (verify)

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` trên cây đã dời — xem log
đính kèm ở PR. Guard mới chạy trong cùng cổng đó, thay guard cũ 1:1.

## 4. Ngoài phạm vi, cố ý để lại

- **Không** đăng ký `.agents/Skills/*.md` thành Claude Code subagent thật
  (`.claude/agents/*.md` với frontmatter `name`/`description`/`tools`) — user
  chỉ định rõ `.agents/Skills`, không phải `.claude/agents/`; đây vẫn là tài
  liệu thuần, không phải cơ chế subagent tự động của Claude Code.
- **Không** dọn 16 nhánh cũ của fleet trước đây (phát hiện ở §2.6) — ngoài
  phạm vi, không ai yêu cầu; chỉ ghi lại làm bằng chứng.
- **Không** sửa lại nội dung nghiệp vụ của 7 prompt (bãi săn, boundary, process)
  — đó là việc `EPIC-011` đã làm; epic này chỉ dời vị trí.
