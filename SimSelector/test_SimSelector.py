import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock cp before importing
sys.modules['cp'] = MagicMock()

# Mock state_manager
sys.modules['state_manager'] = MagicMock()

# Mock speedtest
sys.modules['speedtest'] = MagicMock()

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from SimSelector import SimSelector

class TestSimSelector:
    @patch('SimSelector.cp')
    def test_classify_signal_good(self, mock_cp):
        simselector = SimSelector.__new__(SimSelector)  # Create without __init__
        result = simselector.classify_signal(-80)
        assert result == "Good"

    @patch('SimSelector.cp')
    def test_classify_signal_weak(self, mock_cp):
        simselector = SimSelector.__new__(SimSelector)
        result = simselector.classify_signal(-95)
        assert result == "Weak"

    @patch('SimSelector.cp')
    def test_classify_signal_bad(self, mock_cp):
        simselector = SimSelector.__new__(SimSelector)
        result = simselector.classify_signal(-110)
        assert result == "Bad"

    @patch('SimSelector.cp')
    def test_classify_signal_unknown(self, mock_cp):
        simselector = SimSelector.__new__(SimSelector)
        result = simselector.classify_signal(None)
        assert result == "Unknown"

    @patch('SimSelector.cp')
    def test_check_if_run_before_true(self, mock_cp):
        mock_cp.get.return_value = 'SimSelector 2.5.9'
        simselector = SimSelector.__new__(SimSelector)
        simselector.APP_NAME = 'SimSelector 2.5.9'
        simselector.ONLY_RUN_ONCE = True
        result = simselector.check_if_run_before()
        assert result == True
        mock_cp.log.assert_called_with('SimSelector 2.5.9 has been run before!')

    @patch('SimSelector.cp')
    def test_check_if_run_before_false(self, mock_cp):
        mock_cp.get.return_value = None
        simselector = SimSelector.__new__(SimSelector)
        simselector.ONLY_RUN_ONCE = True
        result = simselector.check_if_run_before()
        assert result == False

if __name__ == "__main__":
    pytest.main()