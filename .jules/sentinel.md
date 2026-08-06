## 2025-02-13 - [Fix path traversal in SQLite sharding]
**Vulnerability:** Path traversal in `DatabaseManager.get_session()` allowing arbitrary SQLite databases to be created/accessed via unsanitized `symbol` names used as filenames.
**Learning:** Dynamic keys (like symbols) used to construct file paths or resource names are a common source of path traversal vulnerabilities, especially when generating shard files dynamically.
**Prevention:** Always strictly validate variables used in file paths using a regex pattern that only allows safe characters (e.g., alphanumeric and underscore) or sanitize the input explicitly.
