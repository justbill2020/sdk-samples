"""
Security Manager for SimSelector v2.6.0 Tech Dashboard

Provides comprehensive security controls for the three-phase workflow:
- Access control validation for dashboard access
- IP whitelist management for LAN access
- Request validation and sanitization
- Security logging and audit trail
- Phase-specific security enforcement

Security Levels:
- STAGING: Medium security - Basic validation, LAN access allowed
- INSTALL: Medium security - Enhanced validation, LAN access allowed  
- DEPLOYED: High security - Strict validation, LAN access blocked
"""

import ipaddress
import re
import time
import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Import our phase system
try:
    from SimSelector import Phase
except ImportError:
    # Fallback for testing
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class SecurityLevel(Enum):
    """Security level enumeration"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AccessResult(Enum):
    """Access control result enumeration"""
    GRANTED = "granted"
    DENIED = "denied"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"


class SecurityViolation(Exception):
    """Security violation exception"""
    pass


class SecurityManager:
    """Comprehensive security manager for SimSelector dashboard"""
    
    # Default allowed IP ranges for LAN access
    DEFAULT_ALLOWED_NETWORKS = [
        '192.168.0.0/16',    # Private Class C
        '10.0.0.0/8',        # Private Class A
        '172.16.0.0/12',     # Private Class B
        '127.0.0.0/8',       # Loopback
        '169.254.0.0/16',    # Link-local
    ]
    
    # Rate limiting configuration
    RATE_LIMITS = {
        'requests_per_minute': 60,
        'requests_per_hour': 1000,
        'failed_attempts_lockout': 10,
        'lockout_duration': 300  # 5 minutes
    }
    
    # Request validation patterns
    VALIDATION_PATTERNS = {
        'safe_path': re.compile(r'^[a-zA-Z0-9/_.-]+$'),
        'safe_param': re.compile(r'^[a-zA-Z0-9_.-]+$'),
        'api_endpoint': re.compile(r'^/api/v[0-9]+/[a-zA-Z0-9/_-]+$'),
        'dashboard_path': re.compile(r'^/(dashboard|static|api)/.*$'),
    }
    
    def __init__(self, client=None):
        self.client = client
        self._allowed_networks = self._load_allowed_networks()
        self._rate_limit_store = {}
        self._failed_attempts = {}
        self._security_log = []
        self._audit_trail = []
        
    def _load_allowed_networks(self) -> List[ipaddress.IPv4Network]:
        """Load allowed network ranges from configuration"""
        networks = []
        for network_str in self.DEFAULT_ALLOWED_NETWORKS:
            try:
                networks.append(ipaddress.IPv4Network(network_str))
            except ValueError as e:
                if self.client:
                    self.client.log(f"Invalid network range {network_str}: {e}")
        return networks
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any], 
                           severity: str = "INFO") -> None:
        """Log security events for audit trail"""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        self._security_log.append(event)
        
        # Keep only last 1000 events to prevent memory issues
        if len(self._security_log) > 1000:
            self._security_log = self._security_log[-1000:]
        
        # Log to client if available
        if self.client:
            self.client.log(f"SECURITY [{severity}] {event_type}: {details}")
    
    def validate_phase_access(self, phase_id: int, access_type: str) -> bool:
        """Validate if access type is allowed for current phase"""
        try:
            if access_type == 'lan_dashboard':
                # LAN dashboard access only allowed in STAGING and INSTALL phases
                allowed = phase_id in [Phase.STAGING, Phase.INSTALL]
                
                self._log_security_event(
                    'phase_access_check',
                    {
                        'phase': phase_id,
                        'access_type': access_type,
                        'result': 'granted' if allowed else 'denied'
                    },
                    'INFO' if allowed else 'WARNING'
                )
                
                return allowed
                
            elif access_type == 'ncm_dashboard':
                # NCM dashboard access allowed in all phases
                return True
                
            elif access_type == 'sim_testing':
                # SIM testing access depends on phase
                if phase_id == Phase.STAGING:
                    return True  # Basic testing allowed
                elif phase_id == Phase.INSTALL:
                    return True  # Full testing allowed
                elif phase_id == Phase.DEPLOYED:
                    return False  # Manual trigger only
                    
            return False
            
        except Exception as e:
            self._log_security_event(
                'phase_access_error',
                {'error': str(e), 'phase': phase_id, 'access_type': access_type},
                'ERROR'
            )
            return False
    
    def validate_ip_access(self, client_ip: str, phase_id: int) -> AccessResult:
        """Validate IP address access based on current phase"""
        try:
            # Parse client IP
            try:
                ip_addr = ipaddress.IPv4Address(client_ip)
            except ValueError:
                self._log_security_event(
                    'invalid_ip_format',
                    {'client_ip': client_ip},
                    'WARNING'
                )
                return AccessResult.INVALID_REQUEST
            
            # Check if IP is in allowed networks
            ip_allowed = any(ip_addr in network for network in self._allowed_networks)
            
            if not ip_allowed:
                self._log_security_event(
                    'ip_access_denied',
                    {'client_ip': client_ip, 'phase': phase_id},
                    'WARNING'
                )
                return AccessResult.DENIED
            
            # Check phase-specific access
            if phase_id == Phase.DEPLOYED:
                # In deployed phase, only NCM access is allowed
                # For now, we'll allow local access for development
                # In production, this should be more restrictive
                self._log_security_event(
                    'deployed_phase_access',
                    {'client_ip': client_ip, 'note': 'Consider restricting in production'},
                    'INFO'
                )
            
            # Check rate limiting
            rate_limit_result = self._check_rate_limit(client_ip)
            if rate_limit_result != AccessResult.GRANTED:
                return rate_limit_result
            
            self._log_security_event(
                'ip_access_granted',
                {'client_ip': client_ip, 'phase': phase_id},
                'INFO'
            )
            
            return AccessResult.GRANTED
            
        except Exception as e:
            self._log_security_event(
                'ip_validation_error',
                {'error': str(e), 'client_ip': client_ip},
                'ERROR'
            )
            return AccessResult.DENIED
    
    def _check_rate_limit(self, client_ip: str) -> AccessResult:
        """Check rate limiting for client IP"""
        current_time = time.time()
        
        # Initialize tracking for new IPs
        if client_ip not in self._rate_limit_store:
            self._rate_limit_store[client_ip] = {
                'requests': [],
                'failed_attempts': 0,
                'locked_until': 0
            }
        
        client_data = self._rate_limit_store[client_ip]
        
        # Check if client is locked out
        if current_time < client_data['locked_until']:
            self._log_security_event(
                'rate_limit_lockout',
                {'client_ip': client_ip, 'locked_until': client_data['locked_until']},
                'WARNING'
            )
            return AccessResult.RATE_LIMITED
        
        # Clean old requests (older than 1 hour)
        client_data['requests'] = [
            req_time for req_time in client_data['requests']
            if current_time - req_time < 3600
        ]
        
        # Check hourly limit
        if len(client_data['requests']) >= self.RATE_LIMITS['requests_per_hour']:
            self._log_security_event(
                'rate_limit_exceeded_hourly',
                {'client_ip': client_ip, 'requests': len(client_data['requests'])},
                'WARNING'
            )
            return AccessResult.RATE_LIMITED
        
        # Check per-minute limit
        recent_requests = [
            req_time for req_time in client_data['requests']
            if current_time - req_time < 60
        ]
        
        if len(recent_requests) >= self.RATE_LIMITS['requests_per_minute']:
            self._log_security_event(
                'rate_limit_exceeded_minute',
                {'client_ip': client_ip, 'requests': len(recent_requests)},
                'WARNING'
            )
            return AccessResult.RATE_LIMITED
        
        # Record this request
        client_data['requests'].append(current_time)
        
        return AccessResult.GRANTED
    
    def validate_request(self, request_path: str, request_params: Dict[str, str]) -> bool:
        """Validate and sanitize incoming requests"""
        try:
            # Validate request path
            if not self.VALIDATION_PATTERNS['safe_path'].match(request_path):
                self._log_security_event(
                    'invalid_request_path',
                    {'path': request_path},
                    'WARNING'
                )
                return False
            
            # Check for path traversal attempts
            if '..' in request_path or request_path.startswith('/'):
                if not self.VALIDATION_PATTERNS['dashboard_path'].match(request_path):
                    self._log_security_event(
                        'path_traversal_attempt',
                        {'path': request_path},
                        'WARNING'
                    )
                    return False
            
            # Validate request parameters
            for param_name, param_value in request_params.items():
                if not self.VALIDATION_PATTERNS['safe_param'].match(param_name):
                    self._log_security_event(
                        'invalid_parameter_name',
                        {'param': param_name},
                        'WARNING'
                    )
                    return False
                
                # Basic XSS prevention
                if any(dangerous in str(param_value).lower() for dangerous in 
                       ['<script', 'javascript:', 'onload=', 'onerror=']):
                    self._log_security_event(
                        'xss_attempt',
                        {'param': param_name, 'value': param_value},
                        'WARNING'
                    )
                    return False
            
            return True
            
        except Exception as e:
            self._log_security_event(
                'request_validation_error',
                {'error': str(e), 'path': request_path},
                'ERROR'
            )
            return False
    
    def sanitize_input(self, input_data: Any) -> Any:
        """Sanitize input data to prevent injection attacks"""
        if isinstance(input_data, str):
            # Remove potentially dangerous characters
            sanitized = re.sub(r'[<>"\';]', '', input_data)
            # Limit length to prevent buffer overflow
            sanitized = sanitized[:1000]
            return sanitized
        elif isinstance(input_data, dict):
            return {key: self.sanitize_input(value) for key, value in input_data.items()}
        elif isinstance(input_data, list):
            return [self.sanitize_input(item) for item in input_data]
        else:
            return input_data
    
    def record_failed_attempt(self, client_ip: str, attempt_type: str) -> None:
        """Record failed authentication/access attempt"""
        current_time = time.time()
        
        if client_ip not in self._failed_attempts:
            self._failed_attempts[client_ip] = []
        
        self._failed_attempts[client_ip].append({
            'timestamp': current_time,
            'type': attempt_type
        })
        
        # Clean old attempts (older than 1 hour)
        self._failed_attempts[client_ip] = [
            attempt for attempt in self._failed_attempts[client_ip]
            if current_time - attempt['timestamp'] < 3600
        ]
        
        # Check if lockout is needed
        recent_failures = len(self._failed_attempts[client_ip])
        if recent_failures >= self.RATE_LIMITS['failed_attempts_lockout']:
            if client_ip not in self._rate_limit_store:
                self._rate_limit_store[client_ip] = {
                    'requests': [],
                    'failed_attempts': 0,
                    'locked_until': 0
                }
            
            self._rate_limit_store[client_ip]['locked_until'] = (
                current_time + self.RATE_LIMITS['lockout_duration']
            )
            
            self._log_security_event(
                'client_locked_out',
                {
                    'client_ip': client_ip,
                    'failed_attempts': recent_failures,
                    'lockout_duration': self.RATE_LIMITS['lockout_duration']
                },
                'WARNING'
            )
    
    def get_security_status(self, phase_id: int) -> Dict[str, Any]:
        """Get current security status and configuration"""
        return {
            'phase': phase_id,
            'security_level': self._get_security_level(phase_id).name,
            'lan_dashboard_access': phase_id in [Phase.STAGING, Phase.INSTALL],
            'allowed_networks': [str(net) for net in self._allowed_networks],
            'rate_limits': self.RATE_LIMITS,
            'active_clients': len(self._rate_limit_store),
            'recent_violations': len([
                event for event in self._security_log[-100:]
                if event['severity'] in ['WARNING', 'ERROR']
            ])
        }
    
    def _get_security_level(self, phase_id: int) -> SecurityLevel:
        """Get security level for current phase"""
        if phase_id == Phase.STAGING:
            return SecurityLevel.MEDIUM
        elif phase_id == Phase.INSTALL:
            return SecurityLevel.MEDIUM
        elif phase_id == Phase.DEPLOYED:
            return SecurityLevel.HIGH
        else:
            return SecurityLevel.HIGH
    
    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security audit trail"""
        return self._security_log[-limit:]
    
    def clear_audit_trail(self) -> None:
        """Clear security audit trail (for testing/maintenance)"""
        self._security_log.clear()
        self._log_security_event(
            'audit_trail_cleared',
            {'cleared_by': 'system'},
            'INFO'
        )
    
    def add_allowed_network(self, network_str: str) -> bool:
        """Add an allowed network range"""
        try:
            network = ipaddress.IPv4Network(network_str)
            self._allowed_networks.append(network)
            
            self._log_security_event(
                'network_added',
                {'network': network_str},
                'INFO'
            )
            
            return True
        except ValueError as e:
            self._log_security_event(
                'invalid_network_addition',
                {'network': network_str, 'error': str(e)},
                'ERROR'
            )
            return False
    
    def remove_allowed_network(self, network_str: str) -> bool:
        """Remove an allowed network range"""
        try:
            network = ipaddress.IPv4Network(network_str)
            if network in self._allowed_networks:
                self._allowed_networks.remove(network)
                
                self._log_security_event(
                    'network_removed',
                    {'network': network_str},
                    'INFO'
                )
                
                return True
            return False
        except ValueError:
            return False


# Global security manager instance
_security_manager = None

def get_security_manager(client=None):
    """Get global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager(client)
    return _security_manager

def validate_dashboard_access(client_ip: str, phase_id: int, client=None) -> AccessResult:
    """Quick function to validate dashboard access"""
    security_manager = get_security_manager(client)
    
    # Check phase-specific access
    if not security_manager.validate_phase_access(phase_id, 'lan_dashboard'):
        return AccessResult.DENIED
    
    # Check IP access
    return security_manager.validate_ip_access(client_ip, phase_id)

def validate_request_security(request_path: str, request_params: Dict[str, str], 
                            client=None) -> bool:
    """Quick function to validate request security"""
    security_manager = get_security_manager(client)
    return security_manager.validate_request(request_path, request_params) 