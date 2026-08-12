from sagittarius_engine.extensions.pyside_mvc import BasePresenter

class BackTestPresenter(BasePresenter):
    """
    Presenter for the BackTest Screen.
    Handles user actions from the View and commands the Engine.
    """
    def __init__(self, view, container):
        super().__init__(view, container)
        
        # Load a default chart for UI purposes
        self.view.render_symbol_cards(["BTC/USDT"])
