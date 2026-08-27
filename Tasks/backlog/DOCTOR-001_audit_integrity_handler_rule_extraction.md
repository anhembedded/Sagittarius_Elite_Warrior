# DOCTOR-001 — Phân rã `AuditDatabaseIntegrityQueryHandler.execute()` thành các rule độc lập

**Nguồn:** chạy `.jules/doctor.prompt.md`
**Ưu tiên:** P2 — không sửa lỗi nào; gỡ một god method và **kéo theo 7/21 lỗi `mypy`** của file khỏi danh sách nợ
**Trạng thái:** 🔴 Chưa làm
**Tầng:** Application (`use_cases/queries/`)
**Liên quan:** [`EPIC-002D`](../epics/EPIC-002_static_type_checking_in_local_ci/incomplete/EPIC-002D_incremental_strictness_rollout.md) — file này đang nằm trong `[tool.mypy]` exclude

---

## 1. Code smell

`src/application/use_cases/queries/audit_database_integrity/handler.py:25` —
`execute()` dài **123 dòng**, là hàm dài thứ 7 trong `src/` và là hàm dài nhất
**không phải** `__init__`/`_build_*` (những cái kia là dựng widget, dài có lý do).

Nó làm 3 việc ở 3 mức trừu tượng khác nhau trong cùng một thân hàm:

1. **Điều phối** — gọi repository, gom `anomalies`, dựng `DatabaseAuditResultDTO`.
2. **Sáu quy tắc nghiệp vụ độc lập**, viết thẳng inline:
   `NON_FINITE_VALUE`, `NON_POSITIVE_PRICE`, `NEGATIVE_VOLUME`,
   `HIGH_LESS_THAN_LOW`, `HIGH_NOT_MAXIMUM`, `LOW_NOT_MINIMUM`.
3. **Khử trùng lặp timestamp** — quy tắc thứ 7, nhưng khác loại: nó cần state
   xuyên vòng lặp (`seen_timestamps`), 6 cái trên thì không.

Hệ quả đo được, không phải cảm tính:

- **Thêm quy tắc thứ 8 = sửa `execute()`.** Đúng vi phạm OCP mà
  `architecture-rule.md` nói tới. Sáu quy tắc hiện tại **không phụ thuộc nhau**,
  nên không có lý do kỹ thuật nào bắt chúng sống chung một hàm.
- **7 lỗi `mypy` giống hệt nhau**, một lỗi cho mỗi chỗ dựng `DataAnomalyDTO`:
  ```
  Argument "raw_values" to "DataAnomalyDTO" has incompatible type
  "dict[str, float]"; expected "dict[str, float | str]"  [arg-type]
  ```
  `raw` được suy kiểu `dict[str, float]`, `dict` thì invariant. **Một annotation
  duy nhất** trên `raw` dập cả 7 — nhưng chỉ khi có **một** chỗ dựng nó, tức là
  sau khi tách rule ra.
- **`anomaly_type` là magic string lặp 7 lần.** `code-quality-rule.md` cấm giá
  trị viết cứng, nhưng Ruff `PLR2004` chỉ bắt magic **number**, không bắt string
  — nên máy không thấy. Đây đúng phần "giá trị của Doctor là thứ không rule nào
  chấm được" mà prompt nói.

## 2. Hướng sửa đề xuất

Giữ `execute()` đúng một việc — **fetch → chạy rule → gom kết quả**:

```python
def execute(self, query: AuditDatabaseIntegrityQuery) -> DatabaseAuditResultDTO:
    klines = self._repository.get_klines(...)
    anomalies = self._collect_anomalies(klines)
    return DatabaseAuditResultDTO(...)
```

Mỗi quy tắc thành một hàm thuần nhỏ nhận `kline` + `raw`, trả `DataAnomalyDTO | None`.
`anomaly_type` thành hằng số có tên (hoặc `enum.StrEnum`) đặt cạnh DTO.

**Ràng buộc bắt buộc — có một hành vi tinh vi phải giữ nguyên:** quy tắc
`NON_FINITE_VALUE` kết thúc bằng `continue`. Nghĩa là một nến non-finite
**không bao giờ được đưa vào `seen_timestamps`**, nên timestamp của nó không thể
kích hoạt `DUPLICATE_TIMESTAMP` cho nến sau. Đó là hành vi hiện tại, dù có chủ ý
hay không. Đây là một lần chạy **behaviour-preserving**: giữ y nguyên, và nếu
thấy nó sai thì mở bug riêng, **không** sửa lén trong task này.

## 3. Acceptance

- [ ] `execute()` xuống dưới ~30 dòng, mỗi rule là một đơn vị đọc được độc lập.
- [ ] `anomaly_type` không còn là string viết cứng rải rác.
- [ ] **5 test hiện có ở `tests/unit/application/use_cases/queries/test_audit_database_integrity.py`
      pass mà KHÔNG sửa dòng nào.** Phải sửa test nghĩa là đã đổi hành vi — dừng lại.
- [ ] Nếu 7 lỗi `mypy` hết: **gỡ file khỏi `[tool.mypy]` exclude** trong
      `pyproject.toml` (đúng việc `EPIC-002D` §2.4). Nếu còn lỗi khác, ghi rõ
      còn gì, đừng gỡ.
- [ ] `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` exit `0`, và đã `grep`
      file `LOG_FILE:` cho `FAILED|ERROR|Traceback|ResourceWarning` (`CLAUDE.md` §2).

## 4. Ngoài phạm vi

Không đụng `DataAnomalyDTO`/`query.py` (đổi schema DTO là việc khác, có
consumer ở tầng UI). Không thêm quy tắc kiểm tra mới. Không sửa hành vi
`continue` ở mục 2.
