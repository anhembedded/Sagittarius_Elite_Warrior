import os
import sys
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest

def test_dashboard_loads():
    """
    Test that the Streamlit dashboard loads without throwing exceptions.
    We mock the get_market_data_repo to avoid loading the real DB.
    """
    # Create a mock for the repository
    mock_repo = Mock()
    mock_repo.get_klines.return_value = []

    # We no longer mock the container, we mock the repo function directly

    # Path to the dashboard script
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../src/presentation/ui/dashboard.py")
    )

    # Patch the bootstrapper so we don't start the real engine in tests
    with patch("Binace_Bot.src.presentation.ui.dashboard.get_market_data_repo", return_value=mock_repo):
        at = AppTest.from_file(script_path)
        
        # Run the app
        at.run()
        
        # Verify no unhandled exceptions occurred
        assert not at.exception
        
        # Verify title exists
        assert at.title[0].value == "🤖 Binance Bot Real-time Dashboard"
        
        # Verify a warning is shown since mock_repo returns []
        assert len(at.warning) > 0
        assert "No data available" in at.warning[0].value
