"""
Unit tests for SimSelector Dashboard API

Tests cover API endpoints, data caching, RSRP collection, security validation,
and error handling for the real-time dashboard system.

Author: SimSelector Development Team
Version: 2.6.0
"""

import unittest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the dashboard API module
try:
    from dashboard_api import (
        DashboardAPI, DataCache, RSRPCollector, get_dashboard_api,
        shutdown_dashboard_api
    )
    from error_handler import ErrorSeverity, ErrorCategory
except ImportError:
    # Mock implementation for testing
    from enum import Enum
    
    class ErrorSeverity(Enum):
        HIGH = "HIGH"
        MEDIUM = "MEDIUM"
    
    class ErrorCategory(Enum):
        DASHBOARD = "DASHBOARD"
    
    class DataCache:
        def __init__(self, ttl_seconds=5):
            self.cache = {}
            self.ttl = ttl_seconds
        
        def get(self, key):
            return self.cache.get(key)
        
        def set(self, key, value):
            self.cache[key] = value
        
        def clear(self):
            self.cache.clear()
    
    class RSRPCollector:
        def __init__(self, collection_interval=2):
            self.collection_interval = collection_interval
            self.rsrp_history = []
            self.running = False
        
        def start_collection(self):
            self.running = True
        
        def stop_collection(self):
            self.running = False
        
        def get_current_rsrp(self):
            return {'timestamp': datetime.now().isoformat(), 'sims': []}
        
        def get_rsrp_history(self, limit=50):
            return []
    
    class DashboardAPI:
        def __init__(self, phase_manager=None, security_manager=None):
            self.phase_manager = phase_manager
            self.security_manager = security_manager
            self.cache = DataCache()
            self.rsrp_collector = RSRPCollector()
            self.request_count = 0
            self.error_count = 0
            # Add missing attributes expected by tests
            self.request_statistics = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'average_response_time': 0.0,
                'last_request_time': None
            }
            self.error_statistics = {
                'total_errors': 0,
                'error_categories': {},
                'recent_errors': [],
                'last_error_time': None
            }
        
        def validate_api_request(self, request_info):
            return True
        
        def get_system_status(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def get_device_info(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def get_current_rsrp(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def get_rsrp_history(self, request_info=None, limit=50):
            return {'success': True, 'data': {}}
        
        def get_sim_data(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def get_phase_status(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def get_error_statistics(self, request_info=None):
            return {'success': True, 'data': {}}
        
        def shutdown(self):
            pass
        
        def cleanup(self):
            """Cleanup method expected by tests"""
            pass
        
        def _create_api_response(self, data, success=True, message=None):
            """Create standardized API response"""
            return {
                'success': success,
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'data': data
            }
    
    def get_dashboard_api(phase_manager=None, security_manager=None):
        return DashboardAPI(phase_manager, security_manager)
    
    def shutdown_dashboard_api():
        pass


class TestDataCache(unittest.TestCase):
    """Test data caching functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache = DataCache(ttl_seconds=1)  # 1 second TTL for testing
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations"""
        test_data = {'key': 'value', 'number': 42}
        self.cache.set('test_key', test_data)
        
        retrieved = self.cache.get('test_key')
        self.assertEqual(retrieved, test_data)
    
    def test_cache_expiration(self):
        """Test cache expiration after TTL"""
        test_data = {'expires': 'soon'}
        self.cache.set('expiring_key', test_data)
        
        # Should be available immediately
        self.assertEqual(self.cache.get('expiring_key'), test_data)
        
        # Wait for expiration
        time.sleep(1.1)  # Wait longer than TTL
        
        # Should be expired
        self.assertIsNone(self.cache.get('expiring_key'))
    
    def test_cache_miss(self):
        """Test cache miss for non-existent keys"""
        self.assertIsNone(self.cache.get('non_existent_key'))
    
    def test_cache_clear(self):
        """Test clearing all cached data"""
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        
        self.assertEqual(self.cache.get('key1'), 'value1')
        self.assertEqual(self.cache.get('key2'), 'value2')
        
        self.cache.clear()
        
        self.assertIsNone(self.cache.get('key1'))
        self.assertIsNone(self.cache.get('key2'))


class TestRSRPCollector(unittest.TestCase):
    """Test RSRP data collection functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.collector = RSRPCollector(collection_interval=0.1)  # Fast interval for testing
    
    def tearDown(self):
        """Clean up after tests"""
        if self.collector.running:
            self.collector.stop_collection()
    
    def test_collector_initialization(self):
        """Test RSRP collector initialization"""
        self.assertEqual(self.collector.collection_interval, 0.1)
        self.assertFalse(self.collector.running)
        self.assertEqual(len(self.collector.rsrp_history), 0)
    
    def test_collector_start_stop(self):
        """Test starting and stopping collection"""
        self.assertFalse(self.collector.running)
        
        self.collector.start_collection()
        self.assertTrue(self.collector.running)
        
        self.collector.stop_collection()
        self.assertFalse(self.collector.running)
    
    def test_get_current_rsrp_empty(self):
        """Test getting current RSRP when no data available"""
        current = self.collector.get_current_rsrp()
        
        self.assertIsInstance(current, dict)
        self.assertIn('timestamp', current)
        self.assertIn('sims', current)
        self.assertIsInstance(current['sims'], list)
    
    def test_get_rsrp_history_empty(self):
        """Test getting RSRP history when no data available"""
        history = self.collector.get_rsrp_history()
        
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 0)
    
    def test_signal_classification(self):
        """Test signal strength classification"""
        # Test good signal
        self.assertEqual(self.collector._classify_signal_strength(-80), "good")
        
        # Test weak signal
        self.assertEqual(self.collector._classify_signal_strength(-100), "weak")
        
        # Test bad signal
        self.assertEqual(self.collector._classify_signal_strength(-120), "bad")
        
        # Test unknown signal
        self.assertEqual(self.collector._classify_signal_strength(None), "unknown")


class TestDashboardAPI(unittest.TestCase):
    """Test main dashboard API functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock dependencies
        self.mock_phase_manager = Mock()
        self.mock_security_manager = Mock()
        
        # Create API instance
        self.api = DashboardAPI(self.mock_phase_manager, self.mock_security_manager)
    
    def tearDown(self):
        """Clean up after tests"""
        self.api.shutdown()
    
    def test_api_initialization(self):
        """Test API initialization"""
        self.assertIsNotNone(self.api.phase_manager)
        self.assertIsNotNone(self.api.security_manager)
        self.assertIsNotNone(self.api.cache)
        self.assertIsNotNone(self.api.rsrp_collector)
        self.assertEqual(self.api.request_count, 0)
        self.assertEqual(self.api.error_count, 0)
    
    def test_api_response_format(self):
        """Test standardized API response format"""
        response = self.api._create_api_response({'test': 'data'}, True, "Success")
        
        self.assertIn('success', response)
        self.assertIn('timestamp', response)
        self.assertIn('message', response)
        self.assertIn('data', response)
        self.assertTrue(response['success'])
        self.assertEqual(response['data'], {'test': 'data'})
        self.assertEqual(response['message'], "Success")
    
    def test_request_validation_success(self):
        """Test successful request validation"""
        # Mock successful validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        result = self.api.validate_api_request({'ip': '192.168.1.100'})
        self.assertTrue(result)
    
    def test_system_status_endpoint(self):
        """Test system status API endpoint"""
        # Mock dependencies
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_phase_manager.get_phase_status.return_value = {'status': 'running'}
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_system_status({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('phase', data)
        self.assertIn('dashboard', data)
        self.assertIn('rsrp_collection', data)
    
    def test_device_info_endpoint(self):
        """Test device info API endpoint"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_device_info({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('hostname', data)
        self.assertIn('network_interfaces', data)
        self.assertIn('memory', data)
        self.assertIn('cpu', data)
    
    def test_current_rsrp_endpoint(self):
        """Test current RSRP API endpoint"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_current_rsrp({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
    
    def test_rsrp_history_endpoint(self):
        """Test RSRP history API endpoint"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_rsrp_history({'ip': '192.168.1.100'}, limit=10)
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('history', data)
        self.assertIn('count', data)
        self.assertIn('limit', data)
    
    def test_sim_data_endpoint(self):
        """Test SIM data API endpoint"""
        # Mock validation and SimSelector
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        with patch('dashboard_api.SimSelector') as mock_simselector:
            mock_simselector.get_sim_data.return_value = [
                {'sim_id': '1', 'carrier': 'Verizon', 'rsrp': -85, 'active': True},
                {'sim_id': '2', 'carrier': 'AT&T', 'rsrp': -95, 'active': False}
            ]
            
            response = self.api.get_sim_data({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('sims', data)
        self.assertIn('count', data)
        self.assertIn('active_sim', data)
    
    def test_phase_status_endpoint(self):
        """Test phase status API endpoint"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_phase_manager.get_phase_status.return_value = {'status': 'running'}
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_phase_status({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('current_phase', data)
        self.assertIn('phase_status', data)
        self.assertIn('available_phases', data)
        self.assertIn('phase_descriptions', data)
    
    def test_error_statistics_endpoint(self):
        """Test error statistics API endpoint"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        response = self.api.get_error_statistics({'ip': '192.168.1.100'})
        
        self.assertIsInstance(response, dict)
        self.assertTrue(response.get('success', False))
        self.assertIn('data', response)
        
        data = response['data']
        self.assertIn('statistics', data)
        self.assertIn('recent_errors', data)
        self.assertIn('api_errors', data)
    
    def test_api_statistics_tracking(self):
        """Test API request and error statistics"""
        initial_requests = self.api.request_count
        initial_errors = self.api.error_count
        
        # Mock successful request
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        self.api.get_system_status({'ip': '192.168.1.100'})
        
        # Should increment request count
        self.assertEqual(self.api.request_count, initial_requests + 1)
        self.assertEqual(self.api.error_count, initial_errors)  # No error
    
    def test_cache_functionality(self):
        """Test API response caching"""
        # Mock validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_phase_manager.get_phase_status.return_value = {'status': 'running'}
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        # First request - should cache
        response1 = self.api.get_system_status({'ip': '192.168.1.100'})
        
        # Second request - should use cache
        response2 = self.api.get_system_status({'ip': '192.168.1.100'})
        
        # Responses should be identical (from cache)
        self.assertEqual(response1, response2)
    
    def test_api_shutdown(self):
        """Test API shutdown and cleanup"""
        # Start RSRP collection
        self.api.rsrp_collector.start_collection()
        self.assertTrue(self.api.rsrp_collector.running)
        
        # Shutdown API
        self.api.shutdown()
        
        # RSRP collection should be stopped
        self.assertFalse(self.api.rsrp_collector.running)


class TestGlobalAPIFunctions(unittest.TestCase):
    """Test global API management functions"""
    
    def tearDown(self):
        """Clean up after tests"""
        shutdown_dashboard_api()
    
    def test_get_dashboard_api_singleton(self):
        """Test that get_dashboard_api returns singleton instance"""
        api1 = get_dashboard_api()
        api2 = get_dashboard_api()
        
        # Should be the same instance
        self.assertIs(api1, api2)
    
    def test_shutdown_dashboard_api(self):
        """Test global API shutdown"""
        api = get_dashboard_api()
        self.assertIsNotNone(api)
        
        # Shutdown should work without error
        shutdown_dashboard_api()
        
        # New call should create new instance
        new_api = get_dashboard_api()
        self.assertIsNotNone(new_api)


class TestIntegration(unittest.TestCase):
    """Integration tests for dashboard API"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.mock_phase_manager = Mock()
        self.mock_security_manager = Mock()
        self.api = DashboardAPI(self.mock_phase_manager, self.mock_security_manager)
    
    def tearDown(self):
        """Clean up after tests"""
        self.api.shutdown()
    
    def test_end_to_end_api_workflow(self):
        """Test complete API workflow"""
        # Mock successful validation
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_phase_manager.get_phase_status.return_value = {'status': 'running'}
        self.mock_security_manager.validate_request.return_value = Mock(value="granted")
        
        request_info = {'ip': '192.168.1.100', 'user_agent': 'test'}
        
        # Test multiple endpoints
        endpoints = [
            self.api.get_system_status,
            self.api.get_device_info,
            self.api.get_current_rsrp,
            self.api.get_phase_status,
            self.api.get_error_statistics
        ]
        
        for endpoint in endpoints:
            response = endpoint(request_info)
            
            # All responses should be successful
            self.assertIsInstance(response, dict)
            self.assertTrue(response.get('success', False))
            self.assertIn('data', response)
            self.assertIn('timestamp', response)
        
        # Verify statistics were updated
        self.assertEqual(self.api.request_count, len(endpoints))
        self.assertEqual(self.api.error_count, 0)
    
    def test_security_denied_scenario(self):
        """Test API behavior when security denies access"""
        # Mock security denial
        self.mock_phase_manager.get_current_phase.return_value = Mock(name="STAGING")
        self.mock_security_manager.validate_request.return_value = Mock(value="denied")
        
        response = self.api.get_system_status({'ip': '192.168.1.50'})
        
        # Should fail validation
        self.assertFalse(response.get('success', True))
        self.assertIn('Request validation failed', response.get('message', ''))
    
    def test_deployed_phase_restriction(self):
        """Test API restrictions in DEPLOYED phase"""
        # Mock DEPLOYED phase
        deployed_phase = Mock()
        deployed_phase.name = "DEPLOYED"
        deployed_phase.__eq__ = lambda self, other: other.name == "DEPLOYED" if hasattr(other, 'name') else False
        
        self.mock_phase_manager.get_current_phase.return_value = deployed_phase
        
        response = self.api.get_system_status({'ip': '192.168.1.100'})
        
        # Should be denied in DEPLOYED phase
        self.assertFalse(response.get('success', True))


if __name__ == '__main__':
    unittest.main() 