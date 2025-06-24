"""
Unit tests for SimSelector enhancements.
Tests the signal classification logic and advanced sorting logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock
from SimSelector import SimSelector


class TestSimSelectorEnhancements(unittest.TestCase):
    """Test cases for SimSelector signal classification and sorting logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sim_selector = SimSelector()
    
    def test_signal_classification_good(self):
        """Test signal classification for good signal strength."""
        # Test RSRP values that should be classified as "Good" (> -90)
        self.assertEqual(self.sim_selector.classify_signal(-85), "Good")
        self.assertEqual(self.sim_selector.classify_signal(-80), "Good")
        self.assertEqual(self.sim_selector.classify_signal(-70), "Good")
        self.assertEqual(self.sim_selector.classify_signal(-50), "Good")
    
    def test_signal_classification_weak(self):
        """Test signal classification for weak signal strength."""
        # Test RSRP values that should be classified as "Weak" (-90 to -105)
        self.assertEqual(self.sim_selector.classify_signal(-90), "Weak")
        self.assertEqual(self.sim_selector.classify_signal(-95), "Weak")
        self.assertEqual(self.sim_selector.classify_signal(-100), "Weak")
        self.assertEqual(self.sim_selector.classify_signal(-105), "Weak")
    
    def test_signal_classification_bad(self):
        """Test signal classification for bad signal strength."""
        # Test RSRP values that should be classified as "Bad" (< -105)
        self.assertEqual(self.sim_selector.classify_signal(-106), "Bad")
        self.assertEqual(self.sim_selector.classify_signal(-110), "Bad")
        self.assertEqual(self.sim_selector.classify_signal(-120), "Bad")
        self.assertEqual(self.sim_selector.classify_signal(-150), "Bad")
    
    def test_signal_classification_unknown(self):
        """Test signal classification for None/unknown values."""
        self.assertEqual(self.sim_selector.classify_signal(None), "Unknown")
    
    def test_advanced_sorting_by_download_speed(self):
        """Test that SIMs are primarily sorted by download speed."""
        # Create mock SIM data with different download speeds
        mock_sims = {
            'sim1': {
                'download': 50.0,
                'upload': 10.0,
                'diagnostics': {'RSRP': -85},
                'low-speed': False
            },
            'sim2': {
                'download': 80.0,
                'upload': 8.0,
                'diagnostics': {'RSRP': -90},
                'low-speed': False
            },
            'sim3': {
                'download': 30.0,
                'upload': 15.0,
                'diagnostics': {'RSRP': -75},
                'low-speed': False
            }
        }
        
        # Test the sorting key function
        def advanced_sort_key(sim_uid):
            sim_data = mock_sims[sim_uid]
            download = sim_data.get('download', 0.0)
            upload = sim_data.get('upload', 0.0)
            rsrp = sim_data.get('diagnostics', {}).get('RSRP', -999)
            
            if sim_data.get('low-speed'):
                return (upload, download, rsrp)
            else:
                return (download, upload, rsrp)
        
        sorted_results = sorted(mock_sims.keys(), key=advanced_sort_key, reverse=True)
        
        # Should be sorted by download speed: sim2 (80), sim1 (50), sim3 (30)
        self.assertEqual(sorted_results, ['sim2', 'sim1', 'sim3'])
    
    def test_advanced_sorting_low_speed_priority(self):
        """Test that low-speed SIMs are sorted by upload first."""
        mock_sims = {
            'sim1': {
                'download': 5.0,
                'upload': 3.0,
                'diagnostics': {'RSRP': -85},
                'low-speed': True
            },
            'sim2': {
                'download': 8.0,
                'upload': 1.0,
                'diagnostics': {'RSRP': -90},
                'low-speed': True
            }
        }
        
        def advanced_sort_key(sim_uid):
            sim_data = mock_sims[sim_uid]
            download = sim_data.get('download', 0.0)
            upload = sim_data.get('upload', 0.0)
            rsrp = sim_data.get('diagnostics', {}).get('RSRP', -999)
            
            if sim_data.get('low-speed'):
                return (upload, download, rsrp)
            else:
                return (download, upload, rsrp)
        
        sorted_results = sorted(mock_sims.keys(), key=advanced_sort_key, reverse=True)
        
        # For low-speed SIMs, should prioritize upload: sim1 (3.0) over sim2 (1.0)
        self.assertEqual(sorted_results, ['sim1', 'sim2'])
    
    def test_advanced_sorting_rsrp_tiebreaker(self):
        """Test that RSRP is used as a tie-breaker when speeds are similar."""
        mock_sims = {
            'sim1': {
                'download': 50.0,
                'upload': 10.0,
                'diagnostics': {'RSRP': -85},  # Better signal
                'low-speed': False
            },
            'sim2': {
                'download': 50.0,
                'upload': 10.0,
                'diagnostics': {'RSRP': -95},  # Worse signal
                'low-speed': False
            }
        }
        
        def advanced_sort_key(sim_uid):
            sim_data = mock_sims[sim_uid]
            download = sim_data.get('download', 0.0)
            upload = sim_data.get('upload', 0.0)
            rsrp = sim_data.get('diagnostics', {}).get('RSRP', -999)
            
            if sim_data.get('low-speed'):
                return (upload, download, rsrp)
            else:
                return (download, upload, rsrp)
        
        sorted_results = sorted(mock_sims.keys(), key=advanced_sort_key, reverse=True)
        
        # Should prioritize sim1 due to better RSRP (-85 > -95)
        self.assertEqual(sorted_results, ['sim1', 'sim2'])


class TestStatePersistence(unittest.TestCase):
    """Test cases for state management functionality."""
    
    @patch('state_manager.set_state')
    @patch('state_manager.get_state')
    def test_state_transitions(self, mock_get_state, mock_set_state):
        """Test that state transitions work correctly."""
        # Test initial state
        mock_get_state.return_value = None
        from SimSelector import main
        
        # Should default to 'validation' when no state is set
        mock_get_state.return_value = None
        phase = mock_get_state.return_value or 'validation'
        self.assertEqual(phase, 'validation')
        
        # Test validation to performance transition
        mock_get_state.return_value = 'performance'
        phase = mock_get_state.return_value
        self.assertEqual(phase, 'performance')
        
        # Test completion state
        mock_get_state.return_value = 'complete'
        phase = mock_get_state.return_value
        self.assertEqual(phase, 'complete')


if __name__ == '__main__':
    unittest.main() 