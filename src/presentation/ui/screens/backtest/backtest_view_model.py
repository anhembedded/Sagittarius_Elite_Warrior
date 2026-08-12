from PySide6.QtCore import QObject, Property

class BackTestViewModel(QObject):
    """
    ViewModel for the BackTest Screen.
    Contains properties bound to the QML UI for strategy selection, parameters, and results.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._strategy_list = ["SMA Crossover", "RSI Mean Reversion", "MACD Trend"]
        self._initial_capital = "10000"
        
        self._total_pnl = "0.00"
        self._win_rate = "0.00%"
        self._max_drawdown = "0.00%"
        self._profit_factor = "0.00"

    # Properties
    @Property("QStringList", constant=True)
    def strategyList(self):
        return self._strategy_list
        
    @Property(str, constant=True)
    def initialCapital(self):
        return self._initial_capital
        
    @Property(str, constant=True)
    def totalPnl(self):
        return self._total_pnl
        
    @Property(str, constant=True)
    def winRate(self):
        return self._win_rate
        
    @Property(str, constant=True)
    def maxDrawdown(self):
        return self._max_drawdown
        
    @Property(str, constant=True)
    def profitFactor(self):
        return self._profit_factor
