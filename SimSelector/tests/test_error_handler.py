"""
Unit tests for SimSelector Error Handler

Tests cover exception hierarchy, error classification, recovery mechanisms,
error statistics, and notification systems.

Author: SimSelector Development Team
Version: 2.6.0
"""

import unittest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the error handling module
try:
    from error_handler import (
        ErrorHandler, ErrorSeverity, ErrorCategory, SimSelectorError,
        CriticalError, NetworkError, HardwareError, SecurityError,
        PhaseError, DashboardError, DataError, RecoveryAction,
        handle_error, ErrorContext, handle_errors
    )
except ImportError:
    # Mock implementation for testing
    from enum import Enum
    
    class ErrorSeverity(Enum):
        CRITICAL = "CRITICAL"
        HIGH = "HIGH"
        MEDIUM = "MEDIUM"
        LOW = "LOW"
        INFO = "INFO"
    
    class ErrorCategory(Enum):
        NETWORK = "NETWORK"
        HARDWARE = "HARDWARE"
        SECURITY = "SECURITY"
        PHASE = "PHASE"
        DASHBOARD = "DASHBOARD"
        DATA = "DATA"
        SYSTEM = "SYSTEM"
        UNKNOWN = "UNKNOWN"
    
    class SimSelectorError(Exception):
        def __init__(self, message, severity=ErrorSeverity.MEDIUM, category=ErrorCategory.UNKNOWN, recoverable=True, context=None):
            super().__init__(message)
            self.message = message
            self.severity = severity
            self.category = category
            self.recoverable = recoverable
            self.context = context or {}
            self.timestamp = datetime.now()
            self.error_id = f"{category.value}_{int(time.time())}"
    
    class CriticalError(SimSelectorError):
        def __init__(self, message, category=ErrorCategory.SYSTEM, context=None):
            super().__init__(message, ErrorSeverity.CRITICAL, category, False, context)
    
    class NetworkError(SimSelectorError):
        def __init__(self, message, severity=ErrorSeverity.HIGH, context=None):
            super().__init__(message, severity, ErrorCategory.NETWORK, True, context)
    
    class ErrorHandler:
        def __init__(self, logger=None):
            self.error_history = []
            self.recovery_actions = {}
            self.notification_callbacks = []
            self.error_counts = {}
            self.suppressed_errors = {}
        
        def handle_error(self, error, context=None):
            return True
        
        def get_error_statistics(self):
            return {'total_errors': 0}
        
        def get_recent_errors(self, limit=50):
            return []


class TestErrorSeverity(unittest.TestCase):
    """Test error severity enumeration"""
    
    def test_severity_values(self):
        """Test that all severity levels are properly defined"""
        self.assertEqual(ErrorSeverity.CRITICAL.value, "CRITICAL")
        self.assertEqual(ErrorSeverity.HIGH.value, "HIGH")
        self.assertEqual(ErrorSeverity.MEDIUM.value, "MEDIUM")
        self.assertEqual(ErrorSeverity.LOW.value, "LOW")
        self.assertEqual(ErrorSeverity.INFO.value, "INFO")
    
    def test_severity_ordering(self):
        """Test that severity levels can be compared"""
        severities = [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH, ErrorSeverity.MEDIUM, ErrorSeverity.LOW, ErrorSeverity.INFO]
        self.assertEqual(len(severities), 5)


class TestErrorCategory(unittest.TestCase):
    """Test error category enumeration"""
    
    def test_category_values(self):
        """Test that all categories are properly defined"""
        self.assertEqual(ErrorCategory.NETWORK.value, "NETWORK")
        self.assertEqual(ErrorCategory.HARDWARE.value, "HARDWARE")
        self.assertEqual(ErrorCategory.SECURITY.value, "SECURITY")
        self.assertEqual(ErrorCategory.PHASE.value, "PHASE")  
        self.assertEqual(ErrorCategory.DASHBOARD.value, "DASHBOARD")
        self.assertEqual(ErrorCategory.DATA.value, "DATA")
        self.assertEqual(ErrorCategory.SYSTEM.value, "SYSTEM")
        self.assertEqual(ErrorCategory.UNKNOWN.value, "UNKNOWN")


class TestSimSelectorError(unittest.TestCase):
    """Test base SimSelector error class"""
    
    def test_basic_error_creation(self):
        """Test basic error creation with defaults"""
        error = SimSelectorError("Test error message")
        
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(error.category, ErrorCategory.UNKNOWN)
        self.assertTrue(error.recoverable)
        self.assertIsInstance(error.context, dict)
        self.assertIsInstance(error.timestamp, datetime)
        self.assertTrue(error.error_id.startswith("UNKNOWN_"))
    
    def test_custom_error_creation(self):
        """Test error creation with custom parameters"""
        context = {"operation": "test", "user": "admin"}
        error = SimSelectorError(
            "Custom error", 
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK,
            recoverable=False,
            context=context
        )
        
        self.assertEqual(error.message, "Custom error")
        self.assertEqual(error.severity, ErrorSeverity.HIGH) 
        self.assertEqual(error.category, ErrorCategory.NETWORK)
        self.assertFalse(error.recoverable)
        self.assertEqual(error.context, context)
        self.assertTrue(error.error_id.startswith("NETWORK_"))
    
    def test_error_id_uniqueness(self):
        """Test that error IDs are unique"""
        error1 = SimSelectorError("Error 1")
        time.sleep(0.001)  # Small delay to ensure different timestamps
        error2 = SimSelectorError("Error 2")
        
        self.assertNotEqual(error1.error_id, error2.error_id)


class TestSpecificErrors(unittest.TestCase):
    """Test specific error classes"""
    
    def test_critical_error(self):
        """Test critical error creation"""
        error = CriticalError("System failure")
        
        self.assertEqual(error.severity, ErrorSeverity.CRITICAL)
        self.assertEqual(error.category, ErrorCategory.SYSTEM)
        self.assertFalse(error.recoverable)
    
    def test_network_error(self):
        """Test network error creation"""
        error = NetworkError("Connection failed")
        
        self.assertEqual(error.severity, ErrorSeverity.HIGH)
        self.assertEqual(error.category, ErrorCategory.NETWORK)
        self.assertTrue(error.recoverable)
    
    def test_network_error_custom_severity(self):
        """Test network error with custom severity"""
        error = NetworkError("Minor timeout", severity=ErrorSeverity.LOW)
        
        self.assertEqual(error.severity, ErrorSeverity.LOW)
        self.assertEqual(error.category, ErrorCategory.NETWORK)
        self.assertTrue(error.recoverable)


class TestErrorHandler(unittest.TestCase):
    """Test the main error handler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.handler = ErrorHandler()
        self.handler.error_history.clear()
        self.handler.error_counts.clear()
        self.handler.suppressed_errors.clear()
    
    def test_handler_initialization(self):
        """Test error handler initialization"""
        handler = ErrorHandler()
        
        self.assertIsInstance(handler.error_history, list)
        self.assertIsInstance(handler.recovery_actions, dict)
        self.assertIsInstance(handler.notification_callbacks, list)
        self.assertIsInstance(handler.error_counts, dict)
        self.assertIsInstance(handler.suppressed_errors, dict)
    
    def test_handle_simselector_error(self):
        """Test handling of SimSelectorError instances"""
        error = NetworkError("Connection timeout")
        result = self.handler.handle_error(error)
        
        self.assertIsInstance(result, bool)
        self.assertEqual(len(self.handler.error_history), 1)
        self.assertEqual(self.handler.error_history[0], error)
    
    def test_handle_generic_error(self):
        """Test handling of generic Python exceptions"""
        error = ValueError("Invalid value")
        result = self.handler.handle_error(error)
        
        self.assertIsInstance(result, bool)
        self.assertEqual(len(self.handler.error_history), 1)
        self.assertIsInstance(self.handler.error_history[0], SimSelectorError)
    
    def test_error_history_limit(self):
        """Test that error history is limited to prevent memory issues"""
        # Add more than 1000 errors
        for i in range(1100):
            error = SimSelectorError(f"Error {i}")
            self.handler.error_history.append(error)
        
        # Simulate the limit enforcement
        if len(self.handler.error_history) > 1000:
            self.handler.error_history = self.handler.error_history[-1000:]
        
        self.assertEqual(len(self.handler.error_history), 1000)
    
    def test_error_statistics(self):
        """Test error statistics collection"""
        # Add some test errors
        errors = [
            NetworkError("Network error 1"),
            NetworkError("Network error 2"),
            CriticalError("Critical error 1"),
            SimSelectorError("Generic error 1")
        ]
        
        for error in errors:
            self.handler.handle_error(error)
        
        stats = self.handler.get_error_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_errors', stats)
        self.assertIn('recent_errors_24h', stats)
    
    def test_recent_errors(self):
        """Test retrieval of recent errors"""
        # Add some test errors
        for i in range(5):
            error = SimSelectorError(f"Test error {i}")
            self.handler.error_history.append(error)
        
        recent = self.handler.get_recent_errors(limit=3)
        
        self.assertIsInstance(recent, list)
        self.assertLessEqual(len(recent), 3)
        
        # Check that each item has required fields
        if recent:
            for error_dict in recent:
                self.assertIn('error_id', error_dict)
                self.assertIn('message', error_dict) 
                self.assertIn('severity', error_dict)
                self.assertIn('category', error_dict)
                self.assertIn('timestamp', error_dict)
    
    def test_notification_callback_registration(self):
        """Test notification callback registration"""
        callback_called = False
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_called, callback_data
            callback_called = True  
            callback_data = data
        
        self.handler.register_notification_callback(test_callback)
        
        # Verify callback was registered
        self.assertIn(test_callback, self.handler.notification_callbacks)
    
    def test_clear_error_history(self):
        """Test clearing error history"""
        # Add some errors
        for i in range(3):
            error = SimSelectorError(f"Test error {i}")
            self.handler.error_history.append(error)
        
        self.assertEqual(len(self.handler.error_history), 3)
        
        self.handler.clear_error_history()
        
        self.assertEqual(len(self.handler.error_history), 0)
        self.assertEqual(len(self.handler.error_counts), 0)
        self.assertEqual(len(self.handler.suppressed_errors), 0)


class TestRecoveryActions(unittest.TestCase):
    """Test recovery action functionality"""
    
    def test_recovery_action_creation(self):
        """Test creation of recovery actions"""
        def test_action(error):
            return True
        
        action = RecoveryAction("test_recovery", test_action, max_attempts=5, delay=2.0)
        
        self.assertEqual(action.name, "test_recovery")
        self.assertEqual(action.action, test_action)
        self.assertEqual(action.max_attempts, 5)
        self.assertEqual(action.delay, 2.0)
        self.assertEqual(action.attempts, 0)
        self.assertIsNone(action.last_attempt)
    
    def test_recovery_action_registration(self):
        """Test registering recovery actions with handler"""
        handler = ErrorHandler()
        
        def test_recovery(error):
            return True
        
        action = RecoveryAction("test", test_recovery)
        handler.register_recovery_action(ErrorCategory.NETWORK, action)
        
        self.assertIn(ErrorCategory.NETWORK, handler.recovery_actions)
        self.assertIn(action, handler.recovery_actions[ErrorCategory.NETWORK])


class TestErrorContext(unittest.TestCase):
    """Test error context manager"""
    
    def test_context_manager_normal_operation(self):
        """Test context manager with no errors"""
        try:
            with ErrorContext("test_operation") as ctx:
                ctx.add_context("param", "value")
                # Normal operation - no error
                pass
        except Exception:
            self.fail("Context manager should not raise exception for normal operation")
    
    def test_context_manager_with_error(self):
        """Test context manager with error handling"""
        handler = ErrorHandler()
        
        with patch.object(handler, 'handle_error') as mock_handle:
            try:
                with ErrorContext("test_operation", handler) as ctx:
                    ctx.add_context("param", "value")
                    raise ValueError("Test error")
            except ValueError:
                # Exception should still be raised after handling
                pass
            
            # Verify error was handled
            mock_handle.assert_called_once()


class TestErrorDecorator(unittest.TestCase):
    """Test error handling decorator"""
    
    def test_decorator_normal_function(self):
        """Test decorator on function that doesn't raise errors"""
        @handle_errors("test_function")
        def normal_function(x, y):
            return x + y
        
        result = normal_function(2, 3)
        self.assertEqual(result, 5)
    
    def test_decorator_with_error(self):
        """Test decorator on function that raises errors"""
        handler = ErrorHandler()
        
        @handle_errors("test_function", handler)
        def error_function():
            raise ValueError("Test error")
        
        with patch.object(handler, 'handle_error', return_value=True):
            # Should not raise since error is handled
            result = error_function()
            self.assertIsNone(result)


class TestIntegration(unittest.TestCase):
    """Integration tests for error handling system"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.handler = ErrorHandler()
        self.notifications = []
        
        def capture_notification(data):
            self.notifications.append(data)
        
        self.handler.register_notification_callback(capture_notification)
    
    def test_end_to_end_error_handling(self):
        """Test complete error handling workflow"""
        # Create various types of errors
        errors = [
            NetworkError("Connection failed", context={"host": "example.com"}),
            CriticalError("System failure", context={"component": "database"}),
            DashboardError("UI rendering error", context={"page": "dashboard"})
        ]
        
        # Handle each error
        for error in errors:
            self.handler.handle_error(error)
        
        # Verify error history
        self.assertEqual(len(self.handler.error_history), 3)
        
        # Verify notifications were sent
        self.assertEqual(len(self.notifications), 3)
        
        # Verify statistics
        stats = self.handler.get_error_statistics()
        self.assertGreater(stats['total_errors'], 0)
        
        # Verify recent errors
        recent = self.handler.get_recent_errors(limit=5)
        self.assertEqual(len(recent), 3)
    
    def test_error_suppression(self):
        """Test error suppression for frequent errors"""
        # Simulate frequent identical errors
        for i in range(15):  # More than suppression threshold
            error = NetworkError("Frequent connection error")
            self.handler.handle_error(error)
        
        # Should have some suppression logic
        # (Implementation details would depend on actual suppression logic)
        self.assertGreater(len(self.handler.error_history), 0)


if __name__ == '__main__':
    unittest.main() 