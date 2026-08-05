import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QVBoxLayout, QPushButton, QStackedWidget, QLabel
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
        app_title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
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
        
        self.sidebar.addWidget(self.btn_dashboard)
        self.sidebar.addWidget(self.btn_backtest)

    def _setup_screens(self):
        from Binace_Bot.src.presentation.ui.router import RouterManager
        
        self.router = RouterManager(self.stacked_widget, self.app)
        
        # Register Factory functions for screens
        self.router.register_route("dashboard", self._factory_dashboard)
        self.router.register_route("backtest", self._factory_backtest)
        
        # Navigate to default screen
        self.router.navigate("dashboard")

    def _factory_dashboard(self, app):
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import DashboardView
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import DashboardPresenter
        
        view = DashboardView()
        # Keep a reference to the presenter so it isn't garbage collected
        view.presenter = DashboardPresenter(view, app)
        return view

    def _factory_backtest(self, app):
        from PySide6.QtWidgets import QLabel
        # Placeholder for Backtest Screen (To be replaced by BacktestView)
        backtest_widget = QLabel("Backtest Screen (Under Construction)")
        backtest_widget.setAlignment(Qt.AlignCenter)
        backtest_widget.setStyleSheet("font-size: 24px; color: #d4d4d4;")
        return backtest_widget

    def switch_screen(self, route_name: str):
        self.router.navigate(route_name)
        # Update button states manually
        self.btn_dashboard.setChecked(route_name == "dashboard")
        self.btn_backtest.setChecked(route_name == "backtest")

def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from Binace_Bot.src.main import create_app
    from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
    from sagittarius_engine.utils.path_utils import PathUtils
    import os

    # 1. Boot the Application Engine
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_json = os.path.join(base_dir, "config", "app_config.json")
    user_json = os.path.join(base_dir, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    app_engine = create_app(config_manager)
    app_engine.boot()

    # 2. Boot PySide UI
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Clean look across all OS
    
    # Load Global QSS
    qss_path = os.path.join(base_dir, "src", "presentation", "ui", "qss", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            
    window = MainWindow(app_engine)
    window.show()
    
    exit_code = app.exec()
    
    # 3. Shutdown Engine
    app_engine.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
