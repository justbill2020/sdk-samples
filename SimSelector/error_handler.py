"""
SimSelector Error Handling and Recovery System

This module provides comprehensive error handling capabilities for the SimSelector application,
including custom exception hierarchies, graceful degradation, automatic recovery mechanisms,
and detailed error reporting with severity levels.

Author: SimSelector Development Team
Version: 2.6.0
"""

import logging
import traceback
import time
import json
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
import threading


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling"""
    CRITICAL = "CRITICAL"      # System failure, requires immediate attention
    HIGH = "HIGH"              # Major functionality impacted, needs urgent fix
    MEDIUM = "MEDIUM"          # Partial functionality impacted, should be addressed
    LOW = "LOW"                # Minor issues, can be handled gracefully
    INFO = "INFO"              # Informational, no action required


class ErrorCategory(Enum):
    """Error categories for classification and specialized handling"""
    NETWORK = "NETWORK"        # Network connectivity, API failures
    HARDWARE = "HARDWARE"      # SIM detection, device communication
    SECURITY = "SECURITY"      # Authentication, access control
    PHASE = "PHASE"            # Phase transitions, state management
    DASHBOARD = "DASHBOARD"    # Web server, UI, API endpoints
    DATA = "DATA"              # File I/O, data parsing, validation
    SYSTEM = "SYSTEM"          # System resources, permissions
    UNKNOWN = "UNKNOWN"        # Unclassified errors


class SimSelectorError(Exception):
    """Base exception class for all SimSelector errors"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 recoverable: bool = True, context: Dict = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.now()
        self.error_id = f"{category.value}_{int(time.time())}"


class CriticalError(SimSelectorError):
    """Critical system failures that require immediate attention"""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.SYSTEM, context: Dict = None):
        super().__init__(message, ErrorSeverity.CRITICAL, category, False, context)


class NetworkError(SimSelectorError):
    """Network-related errors with retry capabilities"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.NETWORK, True, context)


class HardwareError(SimSelectorError):
    """Hardware-related errors (SIM detection, device communication)"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.HARDWARE, True, context)


class SecurityError(SimSelectorError):
    """Security-related errors with elevated concern"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.SECURITY, False, context)


class PhaseError(SimSelectorError):
    """Phase transition and state management errors"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.PHASE, True, context)


class DashboardError(SimSelectorError):
    """Dashboard and web interface errors"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.DASHBOARD, True, context)


class DataError(SimSelectorError):
    """Data processing and validation errors"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Dict = None):
        super().__init__(message, severity, ErrorCategory.DATA, True, context)


class RecoveryAction:
    """Represents a recovery action that can be taken for an error"""
    
    def __init__(self, name: str, action: Callable, max_attempts: int = 3, 
                 delay: float = 1.0, backoff_multiplier: float = 2.0):
        self.name = name
        self.action = action
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_multiplier = backoff_multiplier
        self.attempts = 0
        self.last_attempt = None


class ErrorHandler:
    """Comprehensive error handling and recovery system"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or self._setup_logger()
        self.error_history: List[SimSelectorError] = []
        self.recovery_actions: Dict[ErrorCategory, List[RecoveryAction]] = {}
        self.notification_callbacks: List[Callable] = []
        self.error_counts: Dict[str, int] = {}
        self.suppressed_errors: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        
        # Register default recovery actions
        self._register_default_recovery_actions()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for error handling"""
        logger = logging.getLogger('SimSelector.ErrorHandler')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def handle_error(self, error: Exception, context: Dict = None) -> bool:
        """
        Main error handling entry point
        
        Args:
            error: The exception to handle
            context: Additional context information
            
        Returns:
            bool: True if error was handled successfully, False otherwise
        """
        try:
            # Convert to SimSelectorError if needed
            if not isinstance(error, SimSelectorError):
                error = self._classify_generic_error(error, context)
            
            # Add to error history
            with self.lock:
                self.error_history.append(error)
                # Keep only last 1000 errors
                if len(self.error_history) > 1000:
                    self.error_history = self.error_history[-1000:]
            
            # Log the error
            self._log_error(error)
            
            # Check if error should be suppressed
            if self._should_suppress_error(error):
                return True
            
            # Attempt recovery if possible
            recovery_success = False
            if error.recoverable:
                recovery_success = self._attempt_recovery(error)
            
            # Send notifications
            self._send_notifications(error, recovery_success)
            
            # Update error statistics
            self._update_error_stats(error)
            
            return recovery_success
            
        except Exception as e:
            # Fallback error handling to prevent infinite loops
            self.logger.critical(f"Error in error handler: {str(e)}")
            return False
    
    def _classify_generic_error(self, error: Exception, context: Dict = None) -> SimSelectorError:
        """Classify generic exceptions into SimSelector error types"""
        error_str = str(error)
        error_type = type(error).__name__
        
        # Network-related errors
        if any(keyword in error_str.lower() for keyword in 
               ['connection', 'timeout', 'network', 'socket', 'dns', 'http']):
            return NetworkError(f"{error_type}: {error_str}", context=context)
        
        # File/Data errors
        elif any(keyword in error_str.lower() for keyword in 
                ['file', 'permission', 'io', 'json', 'parse']):
            return DataError(f"{error_type}: {error_str}", context=context)
        
        # Security-related errors
        elif any(keyword in error_str.lower() for keyword in 
                ['access', 'permission', 'auth', 'security', 'forbidden']):
            return SecurityError(f"{error_type}: {error_str}", context=context)
        
        # System resource errors
        elif any(keyword in error_str.lower() for keyword in 
                ['memory', 'resource', 'system', 'os']):
            return CriticalError(f"{error_type}: {error_str}", context=context)
        
        else:
            return SimSelectorError(f"{error_type}: {error_str}", context=context)
    
    def _log_error(self, error: SimSelectorError):
        """Log error with appropriate severity level"""
        log_message = (
            f"[{error.error_id}] {error.category.value} - {error.message}"
        )
        
        if error.context:
            log_message += f" | Context: {json.dumps(error.context, default=str)}"
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        elif error.severity == ErrorSeverity.LOW:
            self.logger.info(log_message)
        else:
            self.logger.debug(log_message)
    
    def _should_suppress_error(self, error: SimSelectorError) -> bool:
        """Check if error should be suppressed to prevent spam"""
        error_key = f"{error.category.value}_{error.message[:100]}"
        current_time = datetime.now()
        
        # Check if this error was recently suppressed
        if error_key in self.suppressed_errors:
            time_diff = current_time - self.suppressed_errors[error_key]
            if time_diff < timedelta(minutes=5):  # Suppress for 5 minutes
                return True
        
        # Check error frequency
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Suppress if too frequent
        if self.error_counts[error_key] > 10:  # More than 10 times
            self.suppressed_errors[error_key] = current_time
            self.logger.warning(f"Suppressing frequent error: {error_key}")
            return True
        
        return False
    
    def _attempt_recovery(self, error: SimSelectorError) -> bool:
        """Attempt automatic recovery for the error"""
        if error.category not in self.recovery_actions:
            return False
        
        recovery_actions = self.recovery_actions[error.category]
        
        for recovery_action in recovery_actions:
            if recovery_action.attempts >= recovery_action.max_attempts:
                continue
            
            try:
                self.logger.info(f"Attempting recovery: {recovery_action.name}")
                
                # Apply delay with backoff
                if recovery_action.attempts > 0:
                    delay = recovery_action.delay * (recovery_action.backoff_multiplier ** recovery_action.attempts)
                    time.sleep(delay)
                
                recovery_action.attempts += 1
                recovery_action.last_attempt = datetime.now()
                
                # Execute recovery action
                success = recovery_action.action(error)
                
                if success:
                    self.logger.info(f"Recovery successful: {recovery_action.name}")
                    # Reset attempt counter on success
                    recovery_action.attempts = 0
                    return True
                
            except Exception as e:
                self.logger.error(f"Recovery action failed: {recovery_action.name} - {str(e)}")
        
        return False
    
    def _send_notifications(self, error: SimSelectorError, recovery_success: bool):
        """Send error notifications to registered callbacks"""
        notification_data = {
            'error_id': error.error_id,
            'message': error.message,
            'severity': error.severity.value,
            'category': error.category.value,
            'timestamp': error.timestamp.isoformat(),
            'recoverable': error.recoverable,
            'recovery_success': recovery_success,
            'context': error.context
        }
        
        for callback in self.notification_callbacks:
            try:
                callback(notification_data)
            except Exception as e:
                self.logger.error(f"Notification callback failed: {str(e)}")
    
    def _update_error_stats(self, error: SimSelectorError):
        """Update error statistics for monitoring and analysis"""
        stats_key = f"{error.category.value}_{error.severity.value}"
        self.error_counts[stats_key] = self.error_counts.get(stats_key, 0) + 1
    
    def _register_default_recovery_actions(self):
        """Register default recovery actions for common error categories"""
        
        # Network recovery actions
        network_actions = [
            RecoveryAction("retry_connection", self._retry_network_connection),
            RecoveryAction("reset_network_state", self._reset_network_state)
        ]
        self.recovery_actions[ErrorCategory.NETWORK] = network_actions
        
        # Hardware recovery actions
        hardware_actions = [
            RecoveryAction("rescan_hardware", self._rescan_hardware),
            RecoveryAction("reset_hardware_state", self._reset_hardware_state)
        ]
        self.recovery_actions[ErrorCategory.HARDWARE] = hardware_actions
        
        # Phase recovery actions
        phase_actions = [
            RecoveryAction("reset_phase_state", self._reset_phase_state),
            RecoveryAction("reload_phase_config", self._reload_phase_config)
        ]
        self.recovery_actions[ErrorCategory.PHASE] = phase_actions
        
        # Dashboard recovery actions
        dashboard_actions = [
            RecoveryAction("restart_dashboard_server", self._restart_dashboard_server),
            RecoveryAction("clear_dashboard_cache", self._clear_dashboard_cache)
        ]
        self.recovery_actions[ErrorCategory.DASHBOARD] = dashboard_actions
    
    def _retry_network_connection(self, error: SimSelectorError) -> bool:
        """Retry network connection with validation"""
        try:
            import socket
            # Test basic connectivity
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return True
        except:
            return False
    
    def _reset_network_state(self, error: SimSelectorError) -> bool:
        """Reset network state (placeholder for actual implementation)"""
        self.logger.info("Network state reset attempted")
        return True
    
    def _rescan_hardware(self, error: SimSelectorError) -> bool:
        """Rescan hardware (placeholder for actual implementation)"""
        self.logger.info("Hardware rescan attempted")
        return True
    
    def _reset_hardware_state(self, error: SimSelectorError) -> bool:
        """Reset hardware state (placeholder for actual implementation)"""
        self.logger.info("Hardware state reset attempted")
        return True
    
    def _reset_phase_state(self, error: SimSelectorError) -> bool:
        """Reset phase state (placeholder for actual implementation)"""
        self.logger.info("Phase state reset attempted")
        return True
    
    def _reload_phase_config(self, error: SimSelectorError) -> bool:
        """Reload phase configuration (placeholder for actual implementation)"""
        self.logger.info("Phase config reload attempted")
        return True
    
    def _restart_dashboard_server(self, error: SimSelectorError) -> bool:
        """Restart dashboard server (placeholder for actual implementation)"""
        self.logger.info("Dashboard server restart attempted")
        return True
    
    def _clear_dashboard_cache(self, error: SimSelectorError) -> bool:
        """Clear dashboard cache (placeholder for actual implementation)"""
        self.logger.info("Dashboard cache cleared")
        return True
    
    def register_recovery_action(self, category: ErrorCategory, action: RecoveryAction):
        """Register a custom recovery action"""
        if category not in self.recovery_actions:
            self.recovery_actions[category] = []
        self.recovery_actions[category].append(action)
    
    def register_notification_callback(self, callback: Callable):
        """Register a notification callback function"""
        self.notification_callbacks.append(callback)
    
    def get_error_statistics(self) -> Dict:
        """Get error statistics for monitoring and analysis"""
        with self.lock:
            recent_errors = [e for e in self.error_history 
                           if datetime.now() - e.timestamp < timedelta(hours=24)]
            
            stats = {
                'total_errors': len(self.error_history),
                'recent_errors_24h': len(recent_errors),
                'error_counts': self.error_counts.copy(),
                'suppressed_errors': len(self.suppressed_errors),
                'categories': {},
                'severities': {}
            }
            
            # Count by category and severity
            for error in recent_errors:
                cat = error.category.value
                sev = error.severity.value
                
                stats['categories'][cat] = stats['categories'].get(cat, 0) + 1
                stats['severities'][sev] = stats['severities'].get(sev, 0) + 1
            
            return stats
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Get recent errors for display in dashboard"""
        with self.lock:
            recent = self.error_history[-limit:] if self.error_history else []
            
            return [{
                'error_id': e.error_id,
                'message': e.message,
                'severity': e.severity.value,
                'category': e.category.value,
                'timestamp': e.timestamp.isoformat(),
                'recoverable': e.recoverable,
                'context': e.context
            } for e in reversed(recent)]
    
    def clear_error_history(self):
        """Clear error history (for testing or maintenance)"""
        with self.lock:
            self.error_history.clear()
            self.error_counts.clear()
            self.suppressed_errors.clear()


# Global error handler instance
error_handler = ErrorHandler()


def handle_error(error: Exception, context: Dict = None) -> bool:
    """Convenience function for global error handling"""
    return error_handler.handle_error(error, context)


def critical_error(message: str, category: ErrorCategory = ErrorCategory.SYSTEM, context: Dict = None):
    """Raise a critical error"""
    raise CriticalError(message, category, context)


def network_error(message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
    """Raise a network error"""
    raise NetworkError(message, severity, context)


def hardware_error(message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
    """Raise a hardware error"""
    raise HardwareError(message, severity, context)


def security_error(message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
    """Raise a security error"""
    raise SecurityError(message, severity, context)


def phase_error(message: str, severity: ErrorSeverity = ErrorSeverity.HIGH, context: Dict = None):
    """Raise a phase error"""
    raise PhaseError(message, severity, context)


def dashboard_error(message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Dict = None):
    """Raise a dashboard error"""
    raise DashboardError(message, severity, context)


def data_error(message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Dict = None):
    """Raise a data error"""
    raise DataError(message, severity, context)


# Context manager for error handling
class ErrorContext:
    """Context manager for handling errors in specific code blocks"""
    
    def __init__(self, context_name: str, handler: ErrorHandler = None):
        self.context_name = context_name
        self.handler = handler or error_handler
        self.context_data = {'operation': context_name}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.handler.handle_error(exc_val, self.context_data)
            # Don't suppress the exception, let caller decide
        return False
    
    def add_context(self, key: str, value: Any):
        """Add additional context information"""
        self.context_data[key] = value


# Decorator for automatic error handling
def handle_errors(context_name: str = None, handler: ErrorHandler = None):
    """Decorator for automatic error handling in functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            ctx_name = context_name or f"{func.__module__}.{func.__name__}"
            error_handler_instance = handler or error_handler
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args) if args else None,
                    'kwargs': str(kwargs) if kwargs else None
                }
                
                handled = error_handler_instance.handle_error(e, context)
                if not handled:
                    raise  # Re-raise if not handled successfully
        
        return wrapper
    return decorator 