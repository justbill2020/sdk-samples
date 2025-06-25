"""
Unit Tests for SIM Manager - SimSelector v2.6.0

Tests all SIM management functionality including:
- Single SIM detection and handling
- Hot-swap scenarios and detection
- Carrier selection logic
- SIM quality assessment
- Error handling and fallback modes
- Mock data simulation for testing
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_manager import (
    SIMManager, SIMCard, SIMStatus, SIMType, 
    get_sim_manager, detect_sim_configuration, get_sim_status
)


class MockCSClient:
    """Mock CS client for testing"""
    def __init__(self):
        self.logs = []
        self.get_responses = {}
    
    def log(self, message):
        self.logs.append(message)
        print(f"MockClient: {message}")
    
    def get(self, path):
        return self.get_responses.get(path, None)
    
    def set_response(self, path, response):
        self.get_responses[path] = response


class TestSIMManager(unittest.TestCase):
    """Test cases for SIM Manager functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        self.client = MockCSClient()
        self.sim_manager = SIMManager(self.client)
        
        # Reset global instance for clean testing
        import sim_manager
        sim_manager._sim_manager = None
    
    def tearDown(self):
        """Clean up after each test"""
        if self.sim_manager.monitoring_enabled:
            self.sim_manager.stop_monitoring()
    
    def test_sim_manager_initialization(self):
        """Test SIM manager initialization"""
        self.assertIsNotNone(self.sim_manager)
        self.assertEqual(self.sim_manager.client, self.client)
        self.assertFalse(self.sim_manager.monitoring_enabled)
        self.assertFalse(self.sim_manager.single_sim_mode)
        self.assertEqual(self.sim_manager.sim_cards, {})
        self.assertIsNone(self.sim_manager.active_sim)
    
    def test_sim_card_dataclass(self):
        """Test SIM card data structure"""
        sim_card = SIMCard(
            slot=1,
            status=SIMStatus.PRESENT,
            iccid="89014103211118510720",
            imsi="310410118510720",
            carrier="Verizon",
            rsrp=-85.5
        )
        
        self.assertEqual(sim_card.slot, 1)
        self.assertEqual(sim_card.status, SIMStatus.PRESENT)
        self.assertEqual(sim_card.iccid, "89014103211118510720")
        self.assertEqual(sim_card.carrier, "Verizon")
        self.assertEqual(sim_card.rsrp, -85.5)
        self.assertEqual(sim_card.error_count, 0)
    
    def test_no_sims_detected_scenario(self):
        """Test scenario with no SIMs detected"""
        # Mock modem info with no SIMs
        self.client.set_response("status/wan/devices", {
            "modem_count": 1,
            "sim_slots": 2,
            "modems": [
                {
                    "id": "modem0",
                    "status": "connected",
                    "sim_slots": [
                        {"slot": 1, "status": "absent"},
                        {"slot": 2, "status": "absent"}
                    ]
                }
            ]
        })
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "no_sims_detected")
        self.assertTrue(result["fallback_mode"])
        self.assertIn("No SIM cards detected", result["warnings"])
        self.assertIn("Insert at least one activated SIM card", result["recommendations"])
    
    def test_single_sim_detection(self):
        """Test single SIM detection and configuration"""
        # Mock modem info with single SIM
        self.client.set_response("status/wan/devices", {
            "modem_count": 1,
            "sim_slots": 2,
            "modems": [
                {
                    "id": "modem0",
                    "status": "connected",
                    "sim_slots": [
                        {"slot": 1, "status": "present"},
                        {"slot": 2, "status": "absent"}
                    ]
                }
            ]
        })
        
        # Mock SIM details
        self.client.set_response("status/wan/devices/modem0/sim1", {
            "iccid": "89014103211118510720",
            "imsi": "310410118510720",
            "carrier": "Verizon",
            "carrier_code": "311480",
            "rsrp": -85.5,
            "rsrq": -12.0,
            "signal_strength": 75,
            "network_type": "LTE",
            "roaming": False
        })
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertTrue(result["success"])
        self.assertEqual(result["config_type"], "single_sim")
        self.assertEqual(result["present_sims"], 1)
        self.assertEqual(result["active_sim"], 1)
        self.assertTrue(result["single_sim_mode"])
        self.assertTrue(self.sim_manager.single_sim_mode)
        self.assertEqual(self.sim_manager.active_sim, 1)
        self.assertIn("Single SIM configuration", result["warnings"])
    
    def test_dual_sim_detection(self):
        """Test dual SIM detection and primary selection"""
        # Mock modem info with dual SIMs
        self.client.set_response("status/wan/devices", {
            "modem_count": 1,
            "sim_slots": 2,
            "modems": [
                {
                    "id": "modem0",
                    "status": "connected",
                    "sim_slots": [
                        {"slot": 1, "status": "present"},
                        {"slot": 2, "status": "present"}
                    ]
                }
            ]
        })
        
        # Mock SIM details - Slot 1 has better signal
        self.client.set_response("status/wan/devices/modem0/sim1", {
            "iccid": "89014103211118510720",
            "imsi": "310410118510720",
            "carrier": "Verizon",
            "rsrp": -75.0,  # Better signal
            "signal_strength": 85,
            "network_type": "LTE"
        })
        
        self.client.set_response("status/wan/devices/modem0/sim2", {
            "iccid": "89014103211118510721",
            "imsi": "310410118510721",
            "carrier": "AT&T",
            "rsrp": -95.0,  # Weaker signal
            "signal_strength": 65,
            "network_type": "LTE"
        })
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertTrue(result["success"])
        self.assertEqual(result["config_type"], "dual_sim")
        self.assertEqual(result["present_sims"], 2)
        self.assertEqual(result["active_sim"], 1)  # Should select slot 1 (better signal)
        self.assertFalse(result["single_sim_mode"])
    
    def test_primary_sim_selection_logic(self):
        """Test primary SIM selection based on signal quality and carrier"""
        # Create test SIMs with different characteristics
        sim1 = SIMCard(slot=1, status=SIMStatus.PRESENT, carrier="T-Mobile", rsrp=-90.0)
        sim2 = SIMCard(slot=2, status=SIMStatus.PRESENT, carrier="Verizon", rsrp=-85.0)
        
        sims = {1: sim1, 2: sim2}
        
        primary = self.sim_manager._select_primary_sim(sims)
        
        # Should select Verizon (better signal + carrier preference)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.slot, 2)
        self.assertEqual(primary.carrier, "Verizon")
    
    def test_sim_quality_validation(self):
        """Test SIM quality validation"""
        # Create SIMs with various quality issues
        good_sim = SIMCard(
            slot=1, status=SIMStatus.PRESENT, 
            carrier="Verizon", rsrp=-80.0, network_type="LTE"
        )
        
        poor_signal_sim = SIMCard(
            slot=2, status=SIMStatus.PRESENT,
            carrier="AT&T", rsrp=-120.0, network_type="LTE"  # Very poor signal
        )
        
        no_carrier_sim = SIMCard(
            slot=3, status=SIMStatus.PRESENT,
            carrier=None, rsrp=-85.0  # No carrier identification
        )
        
        sims = {1: good_sim, 2: poor_signal_sim, 3: no_carrier_sim}
        
        issues = self.sim_manager._validate_sim_quality(sims)
        
        self.assertGreater(len(issues), 0)
        self.assertTrue(any("Poor signal strength" in issue for issue in issues))
        self.assertTrue(any("Carrier not identified" in issue for issue in issues))
    
    def test_hot_swap_detection(self):
        """Test SIM hot-swap detection"""
        # Initial configuration - single SIM
        old_config = {
            1: SIMCard(slot=1, status=SIMStatus.PRESENT, carrier="Verizon")
        }
        
        # New configuration - SIM removed, new SIM inserted
        new_config = {
            1: SIMCard(slot=1, status=SIMStatus.ABSENT),
            2: SIMCard(slot=2, status=SIMStatus.PRESENT, carrier="AT&T")
        }
        
        self.sim_manager.active_sim = 1  # Set active SIM
        
        # Mock detect_sim_configuration to avoid actual detection
        with patch.object(self.sim_manager, 'detect_sim_configuration') as mock_detect:
            mock_detect.return_value = {"success": True}
            
            result = self.sim_manager.handle_hot_swap(old_config, new_config)
            
            self.assertTrue(result)
            mock_detect.assert_called_once()
    
    def test_active_sim_removal_handling(self):
        """Test handling of active SIM removal"""
        # Setup with active SIM that will be removed
        self.sim_manager.active_sim = 1
        
        # Remaining SIMs after removal
        remaining_sims = {
            2: SIMCard(slot=2, status=SIMStatus.PRESENT, carrier="AT&T", rsrp=-85.0)
        }
        
        # Mock _select_primary_sim to return the remaining SIM
        with patch.object(self.sim_manager, '_select_primary_sim') as mock_select:
            mock_select.return_value = remaining_sims[2]
            
            self.sim_manager._handle_active_sim_removal(remaining_sims)
            
            # Should switch to slot 2
            self.assertEqual(self.sim_manager.active_sim, 2)
            mock_select.assert_called_once_with(remaining_sims)
    
    def test_active_sim_removal_no_alternatives(self):
        """Test active SIM removal with no alternatives"""
        self.sim_manager.active_sim = 1
        
        # No remaining SIMs
        remaining_sims = {}
        
        # Mock error handler
        with patch.object(self.sim_manager, 'error_handler') as mock_error_handler:
            mock_error_handler.handle_error = Mock()
            
            self.sim_manager._handle_active_sim_removal(remaining_sims)
            
            # Should clear active SIM and trigger error handling
            self.assertIsNone(self.sim_manager.active_sim)
            self.assertFalse(self.sim_manager.single_sim_mode)
            mock_error_handler.handle_error.assert_called_once()
    
    def test_monitoring_start_stop(self):
        """Test SIM monitoring thread management"""
        # Start monitoring
        result = self.sim_manager.start_monitoring()
        self.assertTrue(result)
        self.assertTrue(self.sim_manager.monitoring_enabled)
        self.assertIsNotNone(self.sim_manager.monitoring_thread)
        
        # Stop monitoring
        result = self.sim_manager.stop_monitoring()
        self.assertTrue(result)
        self.assertFalse(self.sim_manager.monitoring_enabled)
    
    def test_force_sim_rescan(self):
        """Test forced SIM rescan"""
        # Mock detect_sim_configuration
        with patch.object(self.sim_manager, 'detect_sim_configuration') as mock_detect:
            mock_detect.return_value = {"success": True, "config_type": "dual_sim"}
            
            result = self.sim_manager.force_sim_rescan()
            
            self.assertTrue(result["success"])
            mock_detect.assert_called_once()
    
    def test_set_active_sim_valid(self):
        """Test setting active SIM to valid slot"""
        # Add a valid SIM
        self.sim_manager.sim_cards[1] = SIMCard(slot=1, status=SIMStatus.PRESENT)
        
        result = self.sim_manager.set_active_sim(1)
        
        self.assertTrue(result)
        self.assertEqual(self.sim_manager.active_sim, 1)
    
    def test_set_active_sim_invalid(self):
        """Test setting active SIM to invalid slot"""
        result = self.sim_manager.set_active_sim(99)  # Non-existent slot
        
        self.assertFalse(result)
        self.assertIsNone(self.sim_manager.active_sim)
    
    def test_sim_status_comprehensive(self):
        """Test comprehensive SIM status reporting"""
        # Add test SIMs
        self.sim_manager.sim_cards[1] = SIMCard(
            slot=1, status=SIMStatus.ACTIVE, carrier="Verizon",
            rsrp=-85.0, signal_strength=75
        )
        self.sim_manager.active_sim = 1
        self.sim_manager.single_sim_mode = True
        
        status = self.sim_manager.get_sim_status()
        
        self.assertIn("sim_cards", status)
        self.assertIn(1, status["sim_cards"])
        self.assertEqual(status["active_sim"], 1)
        self.assertTrue(status["single_sim_mode"])
        self.assertIn("scan_count", status)
        self.assertIn("detection_failures", status)
    
    def test_sim_change_callbacks(self):
        """Test SIM change callback system"""
        callback_called = False
        test_sim_cards = {}
        
        def test_callback(sim_cards):
            nonlocal callback_called, test_sim_cards
            callback_called = True
            test_sim_cards = sim_cards
        
        # Add callback
        self.sim_manager.add_sim_change_callback(test_callback)
        
        # Trigger notification
        self.sim_manager.sim_cards[1] = SIMCard(slot=1, status=SIMStatus.PRESENT)
        self.sim_manager._notify_sim_change()
        
        self.assertTrue(callback_called)
        self.assertEqual(test_sim_cards, self.sim_manager.sim_cards)
    
    def test_error_handling_integration(self):
        """Test integration with error handling system"""
        # Test with no modem info (should trigger error)
        self.client.set_response("status/wan/devices", None)
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertFalse(result["success"])
        self.assertTrue(result["fallback_mode"])
        self.assertIn("error", result)


class TestSIMManagerUtilityFunctions(unittest.TestCase):
    """Test utility functions for SIM manager"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset global instance
        import sim_manager
        sim_manager._sim_manager = None
    
    def test_get_sim_manager_singleton(self):
        """Test SIM manager singleton pattern"""
        client = MockCSClient()
        
        # First call creates instance
        manager1 = get_sim_manager(client)
        self.assertIsNotNone(manager1)
        
        # Second call returns same instance
        manager2 = get_sim_manager()
        self.assertIs(manager1, manager2)
    
    def test_detect_sim_configuration_function(self):
        """Test detect_sim_configuration utility function"""
        client = MockCSClient()
        
        # Mock successful detection
        with patch('sim_manager.get_sim_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.detect_sim_configuration.return_value = {"success": True}
            mock_get_manager.return_value = mock_manager
            
            result = detect_sim_configuration(client)
            
            self.assertTrue(result["success"])
            mock_manager.detect_sim_configuration.assert_called_once()
    
    def test_get_sim_status_function(self):
        """Test get_sim_status utility function"""
        client = MockCSClient()
        
        # Mock status retrieval
        with patch('sim_manager.get_sim_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_sim_status.return_value = {"active_sim": 1}
            mock_get_manager.return_value = mock_manager
            
            result = get_sim_status(client)
            
            self.assertEqual(result["active_sim"], 1)
            mock_manager.get_sim_status.assert_called_once()


class TestSIMManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = MockCSClient()
        self.sim_manager = SIMManager(self.client)
        
        # Reset global instance
        import sim_manager
        sim_manager._sim_manager = None
    
    def test_malformed_modem_response(self):
        """Test handling of malformed modem response"""
        # Set malformed response
        self.client.set_response("status/wan/devices", {"invalid": "data"})
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertFalse(result["success"])
        self.assertTrue(result["fallback_mode"])
    
    def test_sim_details_unavailable(self):
        """Test SIM detection when details are unavailable"""
        # Mock modem info with SIM present
        self.client.set_response("status/wan/devices", {
            "modems": [
                {
                    "id": "modem0",
                    "sim_slots": [{"slot": 1, "status": "present"}]
                }
            ]
        })
        
        # No SIM details available
        self.client.set_response("status/wan/devices/modem0/sim1", None)
        
        result = self.sim_manager.detect_sim_configuration()
        
        # Should still detect SIM but without details
        self.assertTrue(result["success"])
        self.assertEqual(result["present_sims"], 1)
    
    def test_multiple_sims_scenario(self):
        """Test scenario with more than 2 SIMs"""
        # Mock modem info with 3 SIMs
        self.client.set_response("status/wan/devices", {
            "modems": [
                {
                    "id": "modem0", 
                    "sim_slots": [
                        {"slot": 1, "status": "present"},
                        {"slot": 2, "status": "present"},
                        {"slot": 3, "status": "present"}
                    ]
                }
            ]
        })
        
        # Mock SIM details for all slots
        for slot in [1, 2, 3]:
            self.client.set_response(f"status/wan/devices/modem0/sim{slot}", {
                "carrier": f"Carrier{slot}",
                "rsrp": -80.0 - (slot * 5)  # Decreasing signal quality
            })
        
        result = self.sim_manager.detect_sim_configuration()
        
        self.assertTrue(result["success"])
        self.assertEqual(result["config_type"], "multi_sim")
        self.assertEqual(result["present_sims"], 3)
        self.assertIn("Unusual configuration", result["warnings"])
    
    def test_sim_manager_without_client(self):
        """Test SIM manager operation without CS client"""
        sim_manager = SIMManager(client=None)
        
        # Should use mock data
        result = sim_manager.detect_sim_configuration()
        
        # Mock data should show single SIM in slot 1
        self.assertTrue(result["success"])
        self.assertGreater(result["present_sims"], 0)
    
    def test_concurrent_monitoring_start(self):
        """Test concurrent monitoring start attempts"""
        # Start monitoring twice
        result1 = self.sim_manager.start_monitoring()
        result2 = self.sim_manager.start_monitoring()
        
        self.assertTrue(result1)
        self.assertTrue(result2)  # Should return True (already running)
        self.assertTrue(self.sim_manager.monitoring_enabled)
        
        # Clean up
        self.sim_manager.stop_monitoring()


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SIM Manager Test Results")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100:.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1) 