from PySide6.QtWidgets import QStackedWidget
from sagittarius_engine import App

class RouterManager:
    """
    @brief Manages screens and lazy loading to optimize memory and startup time.
    @details Instead of instantiating all screens at startup, screens are built 
    only when requested by mapping route names to Factory functions.
    """
    def __init__(self, stacked_widget: QStackedWidget, app: App):
        self.stacked_widget = stacked_widget
        self.app = app
        
        # Maps route names to a dict of {'factory': callable, 'instance': QWidget | None, 'index': int}
        self.routes = {}
        
    def register_route(self, route_name: str, factory: callable):
        """
        @brief Registers a route with a factory function that will create the View when needed.
        """
        self.routes[route_name] = {
            'factory': factory,
            'instance': None,
            'index': -1 # Will be assigned when added to the stacked widget
        }

    def navigate(self, route_name: str):
        """
        @brief Navigates to the given route, instantiating it if it doesn't exist yet.
        """
        if route_name not in self.routes:
            raise ValueError(f"Route '{route_name}' not registered.")
            
        route_info = self.routes[route_name]
        
        # Lazy Loading Check
        if route_info['instance'] is None:
            # Instantiate using the factory
            view = route_info['factory'](self.app)
            route_info['instance'] = view
            
            # Add to stacked widget and record the index
            index = self.stacked_widget.addWidget(view)
            route_info['index'] = index
            
        # Switch the screen
        self.stacked_widget.setCurrentIndex(route_info['index'])
