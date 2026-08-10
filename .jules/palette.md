## 2024-08-10 - Hover Cursors on QWidgets
**Learning:** PySide6 QPushButtons without pointing hand cursors lack interactive cues. While styling often happens via stylesheets, some widget instances are dynamically created without cursor styles.
**Action:** Use `btn.setCursor(QtCore.Qt.PointingHandCursor)` on interactive elements in PyQt/PySide widgets for a better UX.
