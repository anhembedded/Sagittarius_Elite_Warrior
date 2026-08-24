# Epic EPIC-004 — Static security & quality analysis gate (Ruff: Bandit + magic-number + code-smell rules)

**Trạng thái:** 🟡 Đang làm — 3/4 xong (24/08): `A`, `B`, `D` xong. Còn `C`.
**Nguồn:** User hỏi trực tiếp — `mypy` chỉ bắt lỗi kiểu dữ liệu, cần thêm lớp
kiểm tra "an toàn/chất lượng" kiểu MISRA (C++) cho Python, ví dụ magic number.

---

## 1. Bối cảnh

`EPIC-002` đã nối `mypy` vào CI cục bộ — nhưng `mypy` chỉ lo type, không bắt
được: hardcoded secret, `subprocess` không an toàn, magic number chưa đặt tên
hằng số (`code-rule.md` §2.7 đã cấm nhưng chưa từng được máy verify), code
chết, exception bị nuốt im lặng. Không có "MISRA cho Python" 1-1 (Python
không có lớp rủi ro undefined-behavior/con trỏ MISRA nhắm tới), nhưng
**Bandit** — đã có sẵn trong Ruff qua prefix rule `S`, không cần cài thêm
binary nào — là tương đương gần nhất cho lớp rủi ro bảo mật; các nhóm rule
khác của Ruff (`PLR2004` magic number, `B` bug pattern, `SIM` code smell,
`ERA` dead code, `N` naming) phủ nốt phần "chất lượng" còn lại.

## 2. Mục tiêu Epic

Nối một tập rule Ruff mở rộng (bảo mật + chất lượng) vào `ci-local.ps1 -Full`,
cạnh `ruff check`/`ruff format`/`mypy` đã có — theo đúng phương pháp đã chứng
minh hiệu quả ở `EPIC-002`: đo baseline thật trước, phân loại nhiễu-hệ-thống
vs tín-hiệu-thật, rồi mới quyết định gate. Không bật `--strict`/toàn bộ `PLR`
ngay từ đầu — rollout từng bước như `BOT-098F`/`EPIC-002`.

## 3. Task con

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-004A](completed/EPIC-004A_ruff_baseline_audit.md)** | Đo baseline: rule `S`/`PLR2004`/`B`/`SIM`/`ERA`/`N` bắt bao nhiêu lỗi thật | ✅ Xong (22/08) — [báo cáo đầy đủ](../../reports/EPIC-004A_ruff_security_quality_baseline_audit.md). 4491 lỗi thô, nhưng ~99% là nhiễu hệ thống có giải thích (assert trong test, Qt method override bắt buộc camelCase); tín hiệu thật chỉ ~48 lỗi trong `src`/`scripts`. |
| **[EPIC-004B](completed/EPIC-004B_wire_gate_into_ci_local.md)** | Nối rule set (với per-file-ignores đã xác định) vào `ci-local.ps1 -Full` | ✅ Xong (24/08) — gate fail-cứng, false-positive ignore theo phạm vi, full CI pass. |
| **[EPIC-004C](incomplete/EPIC-004C_document_gate_in_rules.md)** | Ghi nhận cổng mới vào `code-rule.md`/`ci-rule.md`/`ONBOARDING.md` | 🔴 Chưa làm |
| **[EPIC-004D](completed/EPIC-004D_fix_real_findings_and_rollout.md)** | Sửa ~48 lỗi thật tìm được ở `004A` + lộ trình mở rộng rule set dần | ✅ Xong (24/08) — finding thật đã sửa, Ruff sạch. |

Thứ tự bắt buộc: `A` → `B` → `C`. `D` có thể làm song song sau `B`, không
chặn `C`.
