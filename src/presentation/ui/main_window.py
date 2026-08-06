import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
    QLabel,
)
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    """
    @brief The Router window managing multi-screen navigation via QStackedWidget.
    @details Follows Rule 4: Multi-Screen Navigation.
    """

    def __init__(self, app_engine):
        super().__init__()
        self.app = app_engine
        self.setWindowTitle("Binance Bot Desktop - Clean Architecture")
        self.resize(1200, 800)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar for navigation
        sidebar_widget = QWidget()
        sidebar_widget.setMaximumWidth(250)
        sidebar_widget.setStyleSheet("background-color: #2b2b2b; color: white;")
        self.sidebar = QVBoxLayout(sidebar_widget)
        self.sidebar.setAlignment(Qt.AlignTop)
        self.sidebar.setContentsMargins(10, 20, 10, 20)
        self.sidebar.setSpacing(10)

        # Stacked widget for multiple screens
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background-color: #1e1e1e; color: white;")

        # Add to main layout
        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.stacked_widget)

        self._setup_sidebar()
        self._setup_screens()

    def _setup_sidebar(self):
        # App Title in Sidebar
        app_title = QLabel("Binance Bot")
        app_title.setStyleSheet(
            "font-size: 20px; font-weight: bold; margin-bottom: 20px;"
        )
        app_title.setAlignment(Qt.AlignCenter)
        self.sidebar.addWidget(app_title)

        # Dashboard Button
        self.btn_dashboard = QPushButton("Dashboard")
        self.btn_dashboard.setCheckable(True)
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.setMinimumHeight(40)
        self.btn_dashboard.clicked.connect(lambda: self.switch_screen("dashboard"))

        # Backtest Button
        self.btn_backtest = QPushButton("Backtest")
        self.btn_backtest.setCheckable(True)
        self.btn_backtest.setMinimumHeight(40)
        self.btn_backtest.clicked.connect(lambda: self.switch_screen("backtest"))

        # Database Button
        self.btn_database = QPushButton("Database")
        self.btn_database.setCheckable(True)
        self.btn_database.setMinimumHeight(40)
        self.btn_database.clicked.connect(lambda: self.switch_screen("data_management"))

        self.sidebar.addWidget(self.btn_dashboard)
        self.sidebar.addWidget(self.btn_backtest)
        self.sidebar.addWidget(self.btn_database)

    def _setup_screens(self):
        from sagittarius_engine.extensions.pyside_mvc import PresenterManager

        self.router = PresenterManager(self.app.context.container, self.stacked_widget)

        # Register Factory functions for screens
        # Backtest is currently a placeholder without a presenter class
        self.router.register("dashboard", self._get_dashboard_presenter_class(), self._factory_dashboard_view)
        
        # We handle backtest uniquely since it doesn't have a presenter yet
        self.router._registry["backtest"] = {
            "presenter_class": None,
            "view_factory": self._factory_backtest,
            "view_instance": None,
            "presenter_instance": None,
            "stacked_index": -1,
        }
        
        self.router.register("data_management", self._get_data_management_presenter_class(), self._factory_data_management_view)

        # Navigate to default screen
        self.router.navigate_to("dashboard")

    def _get_dashboard_presenter_class(self):
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import DashboardPresenter
        return DashboardPresenter

    def _factory_dashboard_view(self):
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import DashboardView
        view = DashboardView()
        return view

    def _factory_backtest(self):
        from PySide6.QtWidgets import QLabel

        # Placeholder for Backtest Screen (To be replaced by BacktestView)
        backtest_widget = QLabel("Backtest Screen (Under Construction)")
        backtest_widget.setAlignment(Qt.AlignCenter)
        backtest_widget.setStyleSheet("font-size: 24px; color: #d4d4d4;")
        return backtest_widget

    def _get_data_management_presenter_class(self):
        from Binace_Bot.src.presentation.ui.screens.data_management.data_management_presenter import DataManagementPresenter
        return DataManagementPresenter

    def _factory_data_management_view(self):
        from Binace_Bot.src.presentation.ui.screens.data_management.data_management_view import DataManagementView
        view = DataManagementView()
        return view

    def switch_screen(self, route_name: str):
        # Handle backtest explicitly since it doesn't have a presenter
        if route_name == "backtest":
            config = self.router._registry["backtest"]
            if config["view_instance"] is None:
                view = config["view_factory"]()
                config["view_instance"] = view
                index = self.router.stacked_widget.addWidget(view)
                config["stacked_index"] = index
            self.router.stacked_widget.setCurrentIndex(config["stacked_index"])
            self.router._current_screen_name = "backtest"
            self.router.sig_screen_changed.emit("backtest", None)
        else:
            self.router.navigate_to(route_name)
        # Update button states manually
        self.btn_dashboard.setChecked(route_name == "dashboard")
        self.btn_backtest.setChecked(route_name == "backtest")
        self.btn_database.setChecked(route_name == "data_management")


def main():
    from Binace_Bot.src.main import create_app
    from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
    import os

    # 1. Boot the Application Engine
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_json = os.path.join(base_dir, "config", "app_config.json")
    user_json = os.path.join(base_dir, "config", "user_config.json")
    ui_matrix_json = os.path.join(base_dir, "config", "ui_matrix.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    try:
        config_manager.load_json(ui_matrix_json)
    except FileNotFoundError:
        print("Warning: ui_matrix.json not found")

    app_engine = create_app(config_manager)
    app_engine.boot()

    # 2. Boot PySide UI
    app = QApplication(sys.argv)

    # Setup Global Exception Handler for Qt
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        from PySide6.QtWidgets import QMessageBox
        import traceback

        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # Log to Sagittarius Engine if possible
        if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger"):
            app_engine.context.logger.error(
                f"Uncaught UI Exception: {exc_value}\n{tb_str}"
            )
        else:
            print(f"Uncaught UI Exception: {tb_str}")

        # Display Native Error Dialog
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Critical System Error")
        msg_box.setText("An unexpected error occurred in the UI layer.")
        msg_box.setInformativeText(str(exc_value))
        msg_box.setDetailedText(tb_str)
        msg_box.exec()

    sys.excepthook = global_exception_handler

    from PySide6.QtGui import QFont

    app_font = QFont("JetBrainsMono Nerd Font", 10)
    app_font.setStyleHint(QFont.Monospace)
    app_font.insertSubstitutions(
        "JetBrainsMono Nerd Font",
        ["CaskaydiaCove Nerd Font", "FiraCode Nerd Font", "MesloLGS NF", "Consolas"],
    )
    app.setFont(app_font)
    # Apply global Dark Theme matching Binance Bot identity (Compatible with pyqtdarktheme v0.1.x)
    import qdarktheme

    raw_stylesheet = qdarktheme.load_stylesheet("dark")
    # Override default Material Blue with Binance Yellow
    custom_stylesheet = raw_stylesheet.replace(
        "rgba(138.000, 180.000, 247.000, 1.000)", "#F3BA2F"
    )
    app.setStyleSheet(custom_stylesheet)

    window = MainWindow(app_engine)
    window.show()

    exit_code = app.exec()

    # 3. Shutdown Engine
    app_engine.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
