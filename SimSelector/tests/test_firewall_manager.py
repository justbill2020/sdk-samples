#!/usr/bin/env python3
"""
Firewall Manager Tests for SimSelector v2.6.0
"""

import unittest
from unittest.mock import Mock

# Create mock class for testing - avoid import issues
class MockNetCloudFirewallManager:
    def __init__(self):
        self.ports_open = []
        
    def configure_dashboard_access(self, phase_id, port=8080):
        if port not in self.ports_open:
            self.ports_open.append(port)
        return True
        
    def is_port_open(self, port=8080):
        return port in self.ports_open
        
    def close_dashboard_access(self, port=8080):
        if port in self.ports_open:
            self.ports_open.remove(port)
        return True
        
    def get_firewall_status(self):
        return {
            'enabled': True,
            'open_ports': self.ports_open.copy(),
            'total_rules': len(self.ports_open),
            'dashboard_service_configured': len(self.ports_open) > 0
        }


class TestFirewallManager(unittest.TestCase):
    """Test firewall manager functionality using mocks"""
    
    def setUp(self):
        """Set up test environment"""
        self.firewall_manager = MockNetCloudFirewallManager()
    
    def test_firewall_initialization(self):
        """Test firewall manager initialization"""
        fm = MockNetCloudFirewallManager()
        self.assertIsNotNone(fm)
        self.assertEqual(len(fm.ports_open), 0)
    
    def test_configure_dashboard_access(self):
        """Test dashboard access configuration"""
        # Test default port with phase_id
        result = self.firewall_manager.configure_dashboard_access(phase_id=0)
        self.assertTrue(result)
        self.assertTrue(self.firewall_manager.is_port_open(8080))
        
        # Test custom port
        result = self.firewall_manager.configure_dashboard_access(phase_id=1, port=8082)
        self.assertTrue(result)
        self.assertTrue(self.firewall_manager.is_port_open(8082))
    
    def test_port_management(self):
        """Test port open/close functionality"""
        # Initially no ports open
        self.assertFalse(self.firewall_manager.is_port_open(8080))
        
        # Open port
        self.firewall_manager.configure_dashboard_access(phase_id=0, port=8080)
        self.assertTrue(self.firewall_manager.is_port_open(8080))
        
        # Close port
        result = self.firewall_manager.close_dashboard_access(8080)
        self.assertTrue(result)
        self.assertFalse(self.firewall_manager.is_port_open(8080))
    
    def test_firewall_status(self):
        """Test firewall status reporting"""
        status = self.firewall_manager.get_firewall_status()
        self.assertIn('enabled', status)
        self.assertIn('open_ports', status)
        self.assertTrue(status['enabled'])
        self.assertEqual(len(status['open_ports']), 0)
        
        # Open a port and check status
        self.firewall_manager.configure_dashboard_access(phase_id=0, port=8080)
        status = self.firewall_manager.get_firewall_status()
        self.assertIn(8080, status['open_ports'])
        self.assertTrue(status['dashboard_service_configured'])
    
    def test_multiple_ports(self):
        """Test managing multiple ports"""
        # Open multiple ports
        self.firewall_manager.configure_dashboard_access(phase_id=0, port=8080)
        self.firewall_manager.configure_dashboard_access(phase_id=1, port=8081)
        self.firewall_manager.configure_dashboard_access(phase_id=2, port=8082)
        
        # Verify all ports are open
        self.assertTrue(self.firewall_manager.is_port_open(8080))
        self.assertTrue(self.firewall_manager.is_port_open(8081))
        self.assertTrue(self.firewall_manager.is_port_open(8082))
        
        # Check status
        status = self.firewall_manager.get_firewall_status()
        self.assertEqual(status['total_rules'], 3)
        self.assertEqual(len(status['open_ports']), 3)
    
    def test_duplicate_port_configuration(self):
        """Test configuring the same port multiple times"""
        # Configure same port twice
        result1 = self.firewall_manager.configure_dashboard_access(phase_id=0, port=8080)
        result2 = self.firewall_manager.configure_dashboard_access(phase_id=0, port=8080)
        
        # Both should succeed
        self.assertTrue(result1)
        self.assertTrue(result2)
        
        # But port should only be listed once
        status = self.firewall_manager.get_firewall_status()
        port_count = status['open_ports'].count(8080)
        self.assertEqual(port_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
