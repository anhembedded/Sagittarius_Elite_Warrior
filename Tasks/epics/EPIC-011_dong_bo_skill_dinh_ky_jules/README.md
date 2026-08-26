# EPIC-011 — Đồng bộ 7 skill chạy định kỳ (`.jules/`) với repo hiện tại

**Trạng thái:** 🟡 Đang làm — 7/8 task con xong (26/08). Còn `EPIC-011H`
(nối guard vào `ci-local.ps1`) vì chưa verify được ở môi trường hiện tại.
**Loại:** Agent tooling / chống trôi tài liệu
**Nguồn:** User yêu cầu trực tiếp — *"update các skill này cho map với project
hiện tại, cố gắng không hard code"*, kèm làm rõ: *"đây là các skill chạy định
kỳ, đảm bảo chúng meaningful"*.

---

## 1. Vì sao epic này tồn tại

7 file `.jules/*.prompt.md` là **system prompt của 7 agent chạy định kỳ**, không
có người ngồi cạnh. Mỗi lần chạy, agent chỉ đọc đúng file prompt của nó rồi tự
quyết định làm gì.

Điều đó tạo ra một lớp lỗi mà code không có: **agent không thể tự phát hiện bản
mô tả về chính nó đã lỗi thời.** Nó sẽ tiếp tục đi săn thứ repo đã xoá, tiếp tục
trích dẫn một file luật chưa bao giờ tồn tại, và tiếp tục báo cáo thành công. Lỗi
không nổ ra — nó chỉ âm thầm biến mỗi lần chạy định kỳ thành vô nghĩa.

Đây chính là bệnh `CLAUDE.md` đã gọi tên (*"Không chép luật vào đây"* — bản sao
sẽ trôi) và `.agents/ONBOARDING.md` §8 đã ghi nhận **hai lần**, chỉ khác là lần
này nó nằm trong prompt chứ không nằm trong file rule.

## 2. Đã sai những gì (đối chiếu thực tế trên đĩa, 2026-08-26)

| # | Chỗ sai | File | Bằng chứng | Hậu quả nếu để nguyên |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Cổng pre-commit sai**: cả 7 prompt bắt agent chạy `ci-local.ps1 -UnitOnly` rồi commit | cả 7 | `ci-rule.md` §1 nói nguyên văn `-UnitOnly` *"is diagnostic-only and never sufficient for handoff or commit"*; `commit-rule.md` §1 yêu cầu `-Full` | **Nặng nhất.** Mọi commit của cả 7 agent định kỳ đều đi vòng qua lint, format, `mypy` (`EPIC-002`), cổng bảo mật Ruff (`EPIC-004`) và ngưỡng coverage |
| 2 | Trỏ tới `.agents/rules/sentinel-rule.md` — **file chưa bao giờ tồn tại** | `sentinel` | `ls .agents/rules/`; `ONBOARDING.md` §8 mục 1 đã ghi nhận đúng file này | Agent bảo mật được lệnh quét theo "ma trận lỗ hổng" của một file rỗng → không có tiêu chí nào để quét |
| 3 | Journal `.jules/<agent>.md` **không tồn tại**, prompt lại khẳng định là có | `bolt`, `palette` khẳng định; 5 file còn lại trỏ vào | `git log --all -- .jules/bolt.md` rỗng — chưa từng có ở bất kỳ nhánh nào | `palette` dặn agent *"đã có entry thật, đừng khám phá lại"* một bài học chưa ai viết → agent tin vào ký ức không tồn tại |
| 4 | Stack ghi **"PySide6/QML"** | `doctor`, `janitor`, `scout`, `scribe`, `sentinel`, `palette` | `find src -name '*.qml' \| wc -l` → `0`; `EPIC-006` đóng 2026-08-25 | 6/7 agent nhắm vào tầng công nghệ đã bị gỡ khỏi app |
| 5 | **Toàn bộ bãi săn của Palette là QML**: `Accessible.name`, `ToolTip.visible: hovered`, `StatefulButton`, `Sidebar.qml`, `BotParamsDialog.qml` | `palette` | không còn file `.qml` nào trong `src/`; `StatefulButton` chỉ còn trong test QML probe của Engine | Agent UX chạy định kỳ mà **không còn gì để làm** — đúng cái user hỏi ("đảm bảo chúng meaningful") |
| 6 | Verify bằng `quick_widget.errors() == []` | `scout`, `palette` | `.claude/skills/test-health/contract.json` gọi thẳng đó là *"the retired `quick_widget.errors()` clause"*, đã có clause kế nhiệm | Agent test tự xác nhận bằng một điều kiện không còn được chạy |
| 7 | Số test ghi cứng: *"839+ Unit tests + 21 Sanity tests"* | `doctor` | `ls tests/sanity/` → 6 file test, và `EPIC-009` đã xây lại toàn bộ tầng này | `ONBOARDING.md` §8 mục 2 ghi con số kiểu này đã sai **3 lần liên tiếp** trong repo |
| 8 | Bước "verify zero callers" dựa trên *"tất cả file `.qml`"* | `janitor` | không còn `.qml` | Bước chống-xoá-nhầm mất hiệu lực, trong khi cơ chế động **thật** hiện nay là DI container, `EventRegistry` và các chỗ scan-thay-vì-liệt-kê của `EPIC-009` |
| 9 | Không agent nào neo vào một epic đang sống | cả 7 | `EPIC-002D` (danh sách nợ `mypy`), `EPIC-003`, `EPIC-004` đều đang mở | Mỗi lần chạy phải tự nghĩ ra việc, thay vì rút việc từ nguồn có sẵn và tự làm mới |

> `bolt.prompt.md` đã được sửa một phần ở `8b3f387` (26/08) — nó là bản mẫu cho
> cách viết "hỏi cây thư mục, đừng chép sự kiện". Epic này mở rộng cách đó ra 6
> file còn lại và rút phần chung ra một chỗ.

## 3. Cách làm

Ba lớp, theo đúng thứ tự:

1. **Rút phần chung ra `.jules/README.md`** — stack, cổng CI, luật commit,
   journal, boundary, quy ước ngôn ngữ. 7 prompt **link** tới đó thay vì chép
   lại. Đây là chỗ duy nhất bản sao thứ ba có thể sinh ra, nên nó phải là chỗ
   duy nhất được viết.
2. **Mỗi prompt chỉ giữ phần riêng của vai trò nó** — và mỗi vai trò được neo
   vào một bãi săn **tự làm mới**: quét cây thư mục, đọc danh sách nợ trong
   `pyproject.toml`, đọc bảng epic — không phải một danh sách viết cứng trong
   prompt.
3. **Guard cơ học** — `scripts/check_jules_prompt_references.py` đọc lại mọi
   đường dẫn repo mà `.jules/*.md` viết trong backtick và fail nếu có cái nào
   không còn. Nó không phát hiện được "câu này lỗi thời", nhưng bắt đúng lớp lỗi
   **đã thật sự ship**: prompt trỏ vào file không có.

**Luật viết trong `.jules/` từ epic này trở đi:** *nếu một sự kiện có thể thay
đổi, đừng viết sự kiện — viết câu lệnh trả lời nó.* Cấm số đếm, cấm ngày/phiên
bản dạng "hiện tại", cấm chép luật.

## 4. Task con

| ID | Việc | Trạng thái |
| :--- | :--- | :---: |
| [`EPIC-011A`](completed/EPIC-011A_shared_context_contract.md) | `.jules/README.md` — hợp đồng context dùng chung + luật "verify, don't restate" | ✅ Xong |
| [`EPIC-011B`](completed/EPIC-011B_sentinel_prompt.md) | `sentinel.prompt.md` — gỡ authority không tồn tại, neo vào cổng `EPIC-004` | ✅ Xong |
| [`EPIC-011C`](completed/EPIC-011C_palette_prompt.md) | `palette.prompt.md` — chuyển bãi săn từ QML sang QtWidgets kit | ✅ Xong |
| [`EPIC-011D`](completed/EPIC-011D_doctor_and_janitor_prompts.md) | `doctor.prompt.md` + `janitor.prompt.md` — bỏ số đếm, bỏ QML, neo vào `EPIC-003` | ✅ Xong |
| [`EPIC-011E`](completed/EPIC-011E_scout_and_scribe_prompts.md) | `scout.prompt.md` + `scribe.prompt.md` — hợp đồng Sanity mới, neo vào `EPIC-002D` | ✅ Xong |
| [`EPIC-011F`](completed/EPIC-011F_bolt_prompt_alignment.md) | `bolt.prompt.md` — đưa về cùng khuôn, cắt phần đã nằm ở `README.md` | ✅ Xong |
| [`EPIC-011G`](completed/EPIC-011G_reference_guard_script.md) | `scripts/check_jules_prompt_references.py` — guard chống trôi | ✅ Xong |
| [`EPIC-011H`](incomplete/EPIC-011H_wire_guard_into_ci.md) | Nối guard vào `ci-local.ps1 -Full` (hoặc một test unit) | 🔴 Chưa làm |

Thứ tự bắt buộc: `A` trước, vì 6 prompt còn lại link vào nó. `G` sau cùng trong
nhóm đã xong. `H` độc lập, cần máy chạy được `pwsh` + PySide6 + engine.

## 5. "Xong" của epic này là gì

- `python3 scripts/check_jules_prompt_references.py` exit `0`.
- Không file nào trong `.jules/` còn chứa: một con số đếm, một bản chép luật,
  hay một đường dẫn không tồn tại.
- Mỗi prompt trả lời được câu hỏi *"lần chạy hôm nay lấy việc từ đâu?"* bằng một
  lệnh quét, không bằng một danh sách viết cứng.
- Cả 7 prompt dùng đúng cổng `ci-local.ps1 -Full` mà `ci-rule.md` §1 quy định.
- `EPIC-011H` xong thì guard mới thật sự chặn được — trước đó nó vẫn phải chạy
  tay.

## 6. Giới hạn tự nhận

- **Chưa chạy được `ci-local.ps1` trong phiên tạo epic này**: môi trường không
  có `pwsh`, không có `.venv`, không có `PySide6`, và repo `sagittarius_engine`
  không nằm trên đĩa. Toàn bộ thay đổi của `A`–`F` là docs-only nên rơi đúng vào
  ngoại lệ `ci-rule.md` §1 (*"commits that touch no code file"*). Riêng
  `EPIC-011G` thêm một file `.py`: đã verify bằng `ruff check`, `ruff format
  --check` và `mypy` với đúng `pyproject.toml` của repo — ba cổng tĩnh mà file
  này thật sự đi qua — nhưng **chưa** chạy qua `-Full`.
- Guard chỉ kiểm tra **đường dẫn**. Một prompt mô tả sai một cơ chế vẫn còn tồn
  tại thì guard không thấy. Đó là lý do §3 lớp 1 và 2 quan trọng hơn lớp 3.
- Epic này **không** đụng tới lịch chạy của 7 agent (ai gọi, bao lâu một lần) —
  chỗ đó không nằm trong repo này.

## 7. Sửa lây sang `.agents/` (hệ quả trực tiếp của epic này)

Rút phần chung ra `.jules/README.md` làm hai câu ở nơi khác thành sai, nên sửa
luôn thay vì để lại đúng loại lệch mà epic này đang dọn:

- `.agents/ONBOARDING.md` §1 và `.agents/AGENTS.md` cùng ghi `code-rule.md`
  được giữ làm stub *"vì **7** file `.jules/*.prompt.md` đang trỏ vào nó"*. Sau
  epic này chỉ còn `.jules/README.md` trỏ vào. Lý do giữ stub không đổi; con số
  thì đã sai. Cả hai chỗ giờ có ghi chú sửa kèm lệnh tự đếm.
- `.agents/ONBOARDING.md` §8 mục 6 ghi `.jules/` *"chỉ có 7 file `*.prompt.md`"*
  — giờ có thêm `README.md`. Phần nói về journal vẫn đúng nguyên (chưa file nào
  tồn tại) nên chỉ thêm ghi chú, không xoá mục.

Và một chỗ **không** do epic này gây ra, nhưng phát hiện lúc đối chiếu nên ghi
lại thay vì đi đường vòng (đúng yêu cầu của chính §8):

- `.agents/ONBOARDING.md` §8 mục 5 khẳng định *"repo này không có thư mục
  `.github/` nào cả"*. **Sai tại thời điểm 2026-08-26**: `.github/workflows/ci.yml`
  có thật và đang chạy — comment đầu file nói rõ nó được khôi phục sau khi biến
  mất khỏi `master-warrior`. Đã thêm ghi chú sửa. Việc đối chiếu workflow đó với
  `ci-local.ps1` (câu hỏi gốc mà mục 5 tưởng đã đóng) **chưa ai làm** và không
  thuộc phạm vi epic này.
