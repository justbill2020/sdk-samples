"""
Unit Tests for IP Manager - SimSelector v2.6.0

Tests all IP management functionality including:
- IP conflict detection and resolution
- Dashboard IP selection strategies
- DHCP reservation management
- Network interface monitoring
- Static IP configuration
- Subnet validation and management
"""

import unittest
import ipaddress
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ip_manager import (
    IPManager, IPConflict, ConflictSeverity, ResolutionStrategy,
    get_ip_manager, validate_ip_configuration, is_ip_available
)


class MockCSClient:
    """Mock CS client for testing"""
    def __init__(self):
        self.logs = []
        self.get_responses = {}
        self.put_calls = []
    
    def log(self, message):
        self.logs.append(message)
        print(f"MockClient: {message}")
    
    def get(self, path):
        return self.get_responses.get(path, None)
    
    def put(self, path, data):
        self.put_calls.append({"path": path, "data": data})
        return {"success": True}
    
    def set_response(self, path, response):
        self.get_responses[path] = response


class TestIPManager(unittest.TestCase):
    """Test cases for IP Manager functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        self.client = MockCSClient()
        self.ip_manager = IPManager(self.client)
        
        # Reset global instance for clean testing
        import ip_manager
        ip_manager._ip_manager = None
        
        # Mock network interfaces
        self.mock_interfaces = {
            "enp1s0": {"ip": "192.168.1.100", "mask": "255.255.255.0", "status": "up"},
            "wlan0": {"ip": "10.0.0.50", "mask": "255.255.255.0", "status": "up"},
            "eth0": {"ip": "172.16.1.10", "mask": "255.255.0.0", "status": "down"}
        }
    
    def test_ip_manager_initialization(self):
        """Test IP manager initialization"""
        self.assertIsNotNone(self.ip_manager)
        self.assertEqual(self.ip_manager.client, self.client)
        self.assertEqual(self.ip_manager.conflicts, [])
        self.assertEqual(self.ip_manager.reserved_ips, set())
        self.assertIsNone(self.ip_manager.dashboard_ip)
    
    def test_ip_conflict_dataclass(self):
        """Test IP conflict data structure"""
        conflict = IPConflict(
            ip="192.168.1.10",
            severity=ConflictSeverity.HIGH,
            source="DHCP lease",
            interface="enp1s0",
            detected_at=1234567890,
            resolution=ResolutionStrategy.CHANGE_IP
        )
        
        self.assertEqual(conflict.ip, "192.168.1.10")
        self.assertEqual(conflict.severity, ConflictSeverity.HIGH)
        self.assertEqual(conflict.source, "DHCP lease")
        self.assertEqual(conflict.interface, "enp1s0")
        self.assertEqual(conflict.resolution, ResolutionStrategy.CHANGE_IP)
    
    def test_network_interface_detection(self):
        """Test network interface detection"""
        # Mock network interface responses
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [
                {"name": "enp1s0", "ip": "192.168.1.100", "netmask": "255.255.255.0", "status": "up"},
                {"name": "wlan0", "ip": "10.0.0.50", "netmask": "255.255.255.0", "status": "up"}
            ]
        })
        
        interfaces = self.ip_manager.get_network_interfaces()
        
        self.assertEqual(len(interfaces), 2)
        self.assertIn("enp1s0", interfaces)
        self.assertIn("wlan0", interfaces)
        self.assertEqual(interfaces["enp1s0"]["ip"], "192.168.1.100")
        self.assertEqual(interfaces["wlan0"]["ip"], "10.0.0.50")
    
    def test_conflict_detection_dhcp_lease(self):
        """Test conflict detection from DHCP leases"""
        # Mock DHCP lease information
        self.client.set_response("status/wan/devices", {
            "dhcp_leases": [
                {"ip": "192.168.1.10", "mac": "aa:bb:cc:dd:ee:ff", "hostname": "device1"},
                {"ip": "192.168.1.11", "mac": "11:22:33:44:55:66", "hostname": "device2"}
            ]
        })
        
        # Set dashboard IP that would conflict
        self.ip_manager.dashboard_ip = "192.168.1.10"
        
        conflicts = self.ip_manager.detect_ip_conflicts()
        
        self.assertGreater(len(conflicts), 0)
        conflict = conflicts[0]
        self.assertEqual(conflict.ip, "192.168.1.10")
        self.assertEqual(conflict.severity, ConflictSeverity.HIGH)
        self.assertIn("DHCP lease", conflict.source)
    
    def test_conflict_detection_arp_table(self):
        """Test conflict detection from ARP table"""
        # Mock ARP table
        self.client.set_response("status/system/network/arp", {
            "entries": [
                {"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:ff", "interface": "enp1s0"},
                {"ip": "192.168.1.21", "mac": "11:22:33:44:55:66", "interface": "enp1s0"}
            ]
        })
        
        # Set dashboard IP that would conflict
        self.ip_manager.dashboard_ip = "192.168.1.20"
        
        conflicts = self.ip_manager.detect_ip_conflicts()
        
        self.assertGreater(len(conflicts), 0)
        conflict = conflicts[0]
        self.assertEqual(conflict.ip, "192.168.1.20")
        self.assertEqual(conflict.severity, ConflictSeverity.MEDIUM)
        self.assertIn("ARP table", conflict.source)
    
    def test_conflict_detection_static_routes(self):
        """Test conflict detection from static IP configurations"""
        # Mock static IP configurations
        self.client.set_response("config/system/network/static", {
            "interfaces": [
                {"name": "eth1", "ip": "10.0.1.100", "gateway": "10.0.1.1"},
                {"name": "eth2", "ip": "172.16.0.50", "gateway": "172.16.0.1"}
            ]
        })
        
        # Set dashboard IP that would conflict
        self.ip_manager.dashboard_ip = "10.0.1.100"
        
        conflicts = self.ip_manager.detect_ip_conflicts()
        
        self.assertGreater(len(conflicts), 0)
        conflict = conflicts[0]
        self.assertEqual(conflict.ip, "10.0.1.100")
        self.assertEqual(conflict.severity, ConflictSeverity.CRITICAL)
        self.assertIn("Static IP", conflict.source)
    
    def test_dashboard_ip_selection_no_conflicts(self):
        """Test dashboard IP selection with no conflicts"""
        # Mock clean network environment
        self.client.set_response("status/wan/devices", {"dhcp_leases": []})
        self.client.set_response("status/system/network/arp", {"entries": []})
        self.client.set_response("config/system/network/static", {"interfaces": []})
        
        # Mock network interfaces
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [{"name": "enp1s0", "ip": "192.168.1.100", "netmask": "255.255.255.0"}]
        })
        
        result = self.ip_manager.select_dashboard_ip()
        
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["ip"])
        self.assertEqual(len(result["conflicts"]), 0)
        self.assertIn("192.168.1", result["ip"])  # Should be in same subnet
    
    def test_dashboard_ip_selection_with_conflicts(self):
        """Test dashboard IP selection when conflicts exist"""
        # Mock conflicted environment
        self.client.set_response("status/wan/devices", {
            "dhcp_leases": [{"ip": "192.168.1.10", "mac": "aa:bb:cc:dd:ee:ff"}]
        })
        
        # Mock network interfaces
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [{"name": "enp1s0", "ip": "192.168.1.100", "netmask": "255.255.255.0"}]
        })
        
        # Try to select IP that would conflict
        with patch.object(self.ip_manager, '_generate_candidate_ips') as mock_candidates:
            mock_candidates.return_value = ["192.168.1.10", "192.168.1.11", "192.168.1.12"]
            
            result = self.ip_manager.select_dashboard_ip()
            
            self.assertTrue(result["success"])
            # Should skip conflicted IP and select next available
            self.assertNotEqual(result["ip"], "192.168.1.10")
    
    def test_ip_validation_valid_addresses(self):
        """Test IP address validation for valid addresses"""
        valid_ips = [
            "192.168.1.10",
            "10.0.0.1",
            "172.16.255.254",
            "127.0.0.1"
        ]
        
        for ip in valid_ips:
            self.assertTrue(self.ip_manager.validate_ip_address(ip))
    
    def test_ip_validation_invalid_addresses(self):
        """Test IP address validation for invalid addresses"""
        invalid_ips = [
            "256.1.1.1",      # Invalid octet
            "192.168.1",      # Incomplete
            "192.168.1.1.1",  # Too many octets
            "not.an.ip",      # Non-numeric
            "",               # Empty string
            None              # None value
        ]
        
        for ip in invalid_ips:
            self.assertFalse(self.ip_manager.validate_ip_address(ip))
    
    def test_subnet_validation(self):
        """Test subnet validation and IP range checking"""
        # Test valid subnet
        result = self.ip_manager.validate_subnet("192.168.1.0/24", "192.168.1.100")
        self.assertTrue(result["valid"])
        self.assertTrue(result["ip_in_subnet"])
        
        # Test IP not in subnet
        result = self.ip_manager.validate_subnet("192.168.1.0/24", "192.168.2.100")
        self.assertTrue(result["valid"])
        self.assertFalse(result["ip_in_subnet"])
        
        # Test invalid subnet
        result = self.ip_manager.validate_subnet("invalid/subnet", "192.168.1.100")
        self.assertFalse(result["valid"])
    
    def test_dhcp_reservation_management(self):
        """Test DHCP reservation creation and management"""
        # Test creating reservation
        result = self.ip_manager.create_dhcp_reservation(
            ip="192.168.1.50",
            mac="aa:bb:cc:dd:ee:ff",
            hostname="simselector-dashboard"
        )
        
        self.assertTrue(result["success"])
        self.assertIn("aa:bb:cc:dd:ee:ff", result["reservation_id"])
        
        # Verify PUT call was made
        self.assertEqual(len(self.client.put_calls), 1)
        put_call = self.client.put_calls[0]
        self.assertIn("dhcp/reservations", put_call["path"])
        self.assertEqual(put_call["data"]["ip"], "192.168.1.50")
    
    def test_ip_conflict_resolution_change_ip(self):
        """Test IP conflict resolution by changing IP"""
        # Create a conflict
        conflict = IPConflict(
            ip="192.168.1.10",
            severity=ConflictSeverity.HIGH,
            source="DHCP lease",
            interface="enp1s0",
            resolution=ResolutionStrategy.CHANGE_IP
        )
        
        self.ip_manager.conflicts = [conflict]
        self.ip_manager.dashboard_ip = "192.168.1.10"
        
        # Mock new IP selection
        with patch.object(self.ip_manager, 'select_dashboard_ip') as mock_select:
            mock_select.return_value = {"success": True, "ip": "192.168.1.15", "conflicts": []}
            
            result = self.ip_manager.resolve_conflicts()
            
            self.assertTrue(result["success"])
            self.assertEqual(result["resolutions"], 1)
            self.assertEqual(self.ip_manager.dashboard_ip, "192.168.1.15")
    
    def test_ip_conflict_resolution_create_reservation(self):
        """Test IP conflict resolution by creating DHCP reservation"""
        # Create a low-severity conflict
        conflict = IPConflict(
            ip="192.168.1.10",
            severity=ConflictSeverity.LOW,
            source="ARP table",
            interface="enp1s0",
            resolution=ResolutionStrategy.CREATE_RESERVATION
        )
        
        self.ip_manager.conflicts = [conflict]
        self.ip_manager.dashboard_ip = "192.168.1.10"
        
        # Mock MAC address retrieval
        with patch.object(self.ip_manager, '_get_dashboard_mac') as mock_mac:
            mock_mac.return_value = "aa:bb:cc:dd:ee:ff"
            
            result = self.ip_manager.resolve_conflicts()
            
            self.assertTrue(result["success"])
            self.assertEqual(result["resolutions"], 1)
            # Should create DHCP reservation
            self.assertEqual(len(self.client.put_calls), 1)
    
    def test_ip_availability_check(self):
        """Test IP availability checking"""
        # Mock ping responses
        with patch('subprocess.run') as mock_run:
            # First IP - no response (available)
            mock_run.return_value = Mock(returncode=1)
            available = self.ip_manager.is_ip_available("192.168.1.50")
            self.assertTrue(available)
            
            # Second IP - responds (not available)
            mock_run.return_value = Mock(returncode=0)
            available = self.ip_manager.is_ip_available("192.168.1.51")
            self.assertFalse(available)
    
    def test_candidate_ip_generation(self):
        """Test candidate IP generation for dashboard"""
        subnet = ipaddress.IPv4Network("192.168.1.0/24")
        reserved = {"192.168.1.1", "192.168.1.100", "192.168.1.255"}
        
        candidates = self.ip_manager._generate_candidate_ips(subnet, reserved)
        
        self.assertGreater(len(candidates), 0)
        self.assertLess(len(candidates), 250)  # Should exclude some IPs
        
        # Check that reserved IPs are not in candidates
        for ip in reserved:
            self.assertNotIn(ip, candidates)
        
        # Check that all candidates are in subnet
        for ip in candidates:
            self.assertIn(ipaddress.IPv4Address(ip), subnet)
    
    def test_network_monitoring_setup(self):
        """Test network interface monitoring setup"""
        # Mock callback
        callback_called = False
        test_interfaces = {}
        
        def test_callback(interfaces):
            nonlocal callback_called, test_interfaces
            callback_called = True
            test_interfaces = interfaces
        
        # Add callback
        self.ip_manager.add_network_change_callback(test_callback)
        
        # Trigger network change
        self.ip_manager._notify_network_change(self.mock_interfaces)
        
        self.assertTrue(callback_called)
        self.assertEqual(test_interfaces, self.mock_interfaces)
    
    def test_static_ip_configuration(self):
        """Test static IP configuration for dashboard"""
        result = self.ip_manager.configure_static_ip(
            interface="enp1s0",
            ip="192.168.1.50",
            netmask="255.255.255.0",
            gateway="192.168.1.1"
        )
        
        self.assertTrue(result["success"])
        
        # Verify configuration was sent
        self.assertEqual(len(self.client.put_calls), 1)
        put_call = self.client.put_calls[0]
        self.assertIn("network/interface", put_call["path"])
        self.assertEqual(put_call["data"]["ip"], "192.168.1.50")
    
    def test_ip_manager_status_report(self):
        """Test comprehensive IP manager status reporting"""
        # Add some test data
        self.ip_manager.dashboard_ip = "192.168.1.50"
        self.ip_manager.reserved_ips.add("192.168.1.50")
        self.ip_manager.conflicts = [
            IPConflict(ip="192.168.1.10", severity=ConflictSeverity.MEDIUM, source="Test")
        ]
        
        status = self.ip_manager.get_status()
        
        self.assertIn("dashboard_ip", status)
        self.assertIn("reserved_ips", status)
        self.assertIn("conflicts", status)
        self.assertIn("network_interfaces", status)
        self.assertEqual(status["dashboard_ip"], "192.168.1.50")
        self.assertEqual(len(status["conflicts"]), 1)
    
    def test_ip_range_scanning(self):
        """Test IP range scanning for conflicts"""
        # Mock ping responses for range scan
        with patch('subprocess.run') as mock_run:
            # Simulate some IPs responding, others not
            def ping_response(args, **kwargs):
                ip = args[1]  # ping command format: ping -c 1 <ip>
                if "192.168.1.10" in ip or "192.168.1.11" in ip:
                    return Mock(returncode=0)  # Responds
                return Mock(returncode=1)  # No response
            
            mock_run.side_effect = ping_response
            
            active_ips = self.ip_manager.scan_ip_range("192.168.1.0/28")  # Small range for testing
            
            self.assertIn("192.168.1.10", active_ips)
            self.assertIn("192.168.1.11", active_ips)
            self.assertGreater(len(active_ips), 0)


class TestIPManagerUtilityFunctions(unittest.TestCase):
    """Test utility functions for IP manager"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset global instance
        import ip_manager
        ip_manager._ip_manager = None
    
    def test_get_ip_manager_singleton(self):
        """Test IP manager singleton pattern"""
        client = MockCSClient()
        
        # First call creates instance
        manager1 = get_ip_manager(client)
        self.assertIsNotNone(manager1)
        
        # Second call returns same instance
        manager2 = get_ip_manager()
        self.assertIs(manager1, manager2)
    
    def test_validate_ip_configuration_function(self):
        """Test validate_ip_configuration utility function"""
        client = MockCSClient()
        
        # Mock successful validation
        with patch('ip_manager.get_ip_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_ip_address.return_value = True
            mock_get_manager.return_value = mock_manager
            
            result = validate_ip_configuration("192.168.1.10", client)
            
            self.assertTrue(result)
            mock_manager.validate_ip_address.assert_called_once_with("192.168.1.10")
    
    def test_is_ip_available_function(self):
        """Test is_ip_available utility function"""
        client = MockCSClient()
        
        # Mock availability check
        with patch('ip_manager.get_ip_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.is_ip_available.return_value = True
            mock_get_manager.return_value = mock_manager
            
            result = is_ip_available("192.168.1.10", client)
            
            self.assertTrue(result)
            mock_manager.is_ip_available.assert_called_once_with("192.168.1.10")


class TestIPManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = MockCSClient()
        self.ip_manager = IPManager(self.client)
        
        # Reset global instance
        import ip_manager
        ip_manager._ip_manager = None
    
    def test_network_api_unavailable(self):
        """Test operation when network API is unavailable"""
        # No network interface data available
        self.client.set_response("status/system/network/interfaces", None)
        
        interfaces = self.ip_manager.get_network_interfaces()
        
        # Should return empty dict but not crash
        self.assertEqual(interfaces, {})
    
    def test_malformed_network_response(self):
        """Test handling of malformed network response"""
        # Set malformed network response
        self.client.set_response("status/system/network/interfaces", {"invalid": "format"})
        
        interfaces = self.ip_manager.get_network_interfaces()
        
        # Should handle gracefully
        self.assertEqual(interfaces, {})
    
    def test_dhcp_lease_api_error(self):
        """Test handling of DHCP lease API errors"""
        # Mock API error
        self.client.set_response("status/wan/devices", None)
        
        conflicts = self.ip_manager.detect_ip_conflicts()
        
        # Should not crash, may return empty conflicts
        self.assertIsInstance(conflicts, list)
    
    def test_ping_command_failure(self):
        """Test handling of ping command failures"""
        # Mock ping command failure
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Ping command failed")
            
            # Should handle exception gracefully
            available = self.ip_manager.is_ip_available("192.168.1.50")
            
            # Should assume IP is not available when ping fails
            self.assertFalse(available)
    
    def test_invalid_subnet_operations(self):
        """Test operations with invalid subnet configurations"""
        # Test with invalid subnet
        candidates = self.ip_manager._generate_candidate_ips("invalid_subnet", set())
        
        # Should return empty list for invalid subnet
        self.assertEqual(candidates, [])
    
    def test_empty_network_environment(self):
        """Test operation in empty network environment"""
        # Mock empty environment
        self.client.set_response("status/system/network/interfaces", {"interfaces": []})
        self.client.set_response("status/wan/devices", {"dhcp_leases": []})
        self.client.set_response("status/system/network/arp", {"entries": []})
        
        # Should handle empty environment gracefully
        result = self.ip_manager.select_dashboard_ip()
        
        # May not succeed but should not crash
        self.assertIn("success", result)
    
    def test_concurrent_conflict_resolution(self):
        """Test concurrent conflict resolution attempts"""
        # Add multiple conflicts
        conflicts = [
            IPConflict(ip="192.168.1.10", severity=ConflictSeverity.HIGH, source="Test1"),
            IPConflict(ip="192.168.1.11", severity=ConflictSeverity.MEDIUM, source="Test2")
        ]
        self.ip_manager.conflicts = conflicts
        
        # Should handle multiple conflicts
        result = self.ip_manager.resolve_conflicts()
        
        self.assertIn("success", result)
        self.assertIn("resolutions", result)
    
    def test_ip_manager_without_client(self):
        """Test IP manager operation without CS client"""
        ip_manager = IPManager(client=None)
        
        # Should use mock/fallback behavior
        result = ip_manager.get_network_interfaces()
        
        # Should not crash
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"IP Manager Test Results")
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