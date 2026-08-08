## 2026-08-08 - QSS Cursor Support
**Learning:** PySide6 QSS does not reliably support setting cursor properties like `cursor: pointing-hand;`. Attempting to do so results in unknown property errors.
**Action:** Always assign cursor shapes programmatically using `widget.setCursor(Qt.PointingHandCursor)` rather than trying to set them via stylesheets.
