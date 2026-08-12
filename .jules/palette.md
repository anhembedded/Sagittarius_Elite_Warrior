## 2024-08-12 - PySide6 Cursor Styling
**Learning:** Qt style sheets (QSS) do not reliably support setting cursor properties (like `cursor: pointing-hand;`). This means standard UI hover affordances are often missing on custom widgets if relied solely on CSS-like styling.
**Action:** Always assign cursor shapes programmatically to PySide6 widgets (e.g., `button.setCursor(QtCore.Qt.PointingHandCursor)`) rather than trying to set them via QSS.
