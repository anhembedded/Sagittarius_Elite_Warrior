## 2025-02-13 - [Fix path traversal in SQLite sharding]
**Vulnerability:** Path traversal in `DatabaseManager.get_session()` allowing arbitrary SQLite databases to be created/accessed via unsanitized `symbol` names used as filenames.
**Learning:** Dynamic keys (like symbols) used to construct file paths or resource names are a common source of path traversal vulnerabilities, especially when generating shard files dynamically.
**Prevention:** Always strictly validate variables used in file paths using a regex pattern that only allows safe characters (e.g., alphanumeric and underscore) or sanitize the input explicitly.
## 2025-02-28 - [Mitigate QML UI Injection in Trade Logs]
**Vulnerability:** Untrusted text in model data (`entryReasonText`, `exitReasonText`) bound to QML `Text` components lacking explicit formatting constraint.
**Learning:** By default, QML's `Text` element uses `Text.AutoText` which automatically interprets strings containing HTML-like syntax as Rich Text. This can result in UI injection (QML's XSS equivalent) if untrusted input is displayed.
**Prevention:** Always explicitly set `textFormat: Text.PlainText` on QML `Text` elements displaying dynamic, user-controlled, or untrusted string data.
## 2025-03-01 - [Database Path Traversal Mitigation]
**Vulnerability:** Path traversal in database shard manager (`DatabaseManager.get_session`).
**Learning:** Even if `symbol` is validated with regex, `db_dir` itself isn't checked when `db_path` is formed or we need to guarantee the resulting `db_path` stays within `db_dir` via `os.path.abspath`.
**Prevention:** Use `os.path.normpath` and enforce that `os.path.commonpath([base_dir, abs_db_path]) == base_dir` before using the path to robustly prevent partial directory name matches.
