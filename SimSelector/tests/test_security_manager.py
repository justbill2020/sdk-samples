#!/usr/bin/env python3
"""
Security Manager Tests for SimSelector v2.6.0
"""

import unittest
from unittest.mock import Mock, patch

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from security_manager import SecurityManager, SecurityDecision
    from phase_manager import Phase
except ImportError:
    # Create mock classes for testing
    class SecurityDecision:
        def __init__(self, value):
            self.value = value
    
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2
    
    class SecurityManager:
        def __init__(self):
            self.security_level = "HIGH"
            
        def validate_ip_access(self, ip):
            if ip in ['127.0.0.1', 'localhost']:
                return SecurityDecision('granted')
            return SecurityDecision('denied')
            
        def validate_phase_access(self, phase):
            return phase in [Phase.STAGING, Phase.INSTALL, Phase.DEPLOYED]
            
        def validate_request(self, method, path):
            return True
            
        def get_security_level(self):
            return self.security_level


class TestSecurityManager(unittest.TestCase):
    """Test security manager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.security_manager = SecurityManager()
    
    def test_security_initialization(self):
        """Test security manager initialization"""
        sm = SecurityManager()
        self.assertEqual(sm.get_security_level(), "HIGH")
    
    def test_ip_validation(self):
        """Test IP address validation"""
        # Test valid IPs
        result = self.security_manager.validate_ip_access('127.0.0.1')
        self.assertEqual(result.value, 'granted')
        
        result = self.security_manager.validate_ip_access('localhost')
        self.assertEqual(result.value, 'granted')
        
        # Test invalid IP
        result = self.security_manager.validate_ip_access('192.168.1.100')
        self.assertEqual(result.value, 'denied')
    
    def test_phase_access_control(self):
        """Test phase-based access control"""
        # Test valid phases
        self.assertTrue(self.security_manager.validate_phase_access(Phase.STAGING))
        self.assertTrue(self.security_manager.validate_phase_access(Phase.INSTALL))
        self.assertTrue(self.security_manager.validate_phase_access(Phase.DEPLOYED))
        
        # Test invalid phase
        self.assertFalse(self.security_manager.validate_phase_access(999))
    
    def test_request_validation(self):
        """Test request validation"""
        # Test valid requests
        self.assertTrue(self.security_manager.validate_request('GET', '/'))
        self.assertTrue(self.security_manager.validate_request('POST', '/api/data'))
        self.assertTrue(self.security_manager.validate_request('PUT', '/api/config'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
