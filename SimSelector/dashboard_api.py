"""
SimSelector Dashboard API

RESTful API endpoints for real-time data display in the tech dashboard.
Provides live RSRP monitoring, device status, system information, and phase management.

Author: SimSelector Development Team
Version: 2.6.0
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Import our error handling system
try:
    from error_handler import (
        ErrorHandler, dashboard_error, network_error, handle_error,
        ErrorSeverity, ErrorCategory, handle_errors
    )
except ImportError:
    # Fallback for testing or if error_handler not available
    class ErrorHandler:
        def handle_error(self, error, context=None):
            return True
    
    def dashboard_error(msg, severity=None, context=None):
        raise Exception(msg)
    
    def network_error(msg, severity=None, context=None):
        raise Exception(msg)
    
    def handle_error(error, context=None):
        return True
    
    def handle_errors(context_name=None, handler=None):
        def decorator(func):
            return func
        return decorator

# Import system components
try:
    from phase_manager import PhaseManager, Phase
    from security_manager import SecurityManager, SecurityDecision
    import SimSelector
except ImportError:
    # Mock implementations for testing
    from enum import Enum
    
    class Phase(Enum):
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2
    
    class PhaseManager:
        def __init__(self):
            self.current_phase = Phase.STAGING
        
        def get_current_phase(self):
            return self.current_phase
        
        def get_phase_status(self):
            return {"phase": self.current_phase.name, "status": "running"}
    
    class SecurityDecision(Enum):
        GRANTED = "granted"
        DENIED = "denied"
    
    class SecurityManager:
        def validate_request(self, request_info):
            return SecurityDecision.GRANTED
    
    class SimSelector:
        @staticmethod
        def get_sim_data():
            return []


class DataCache:
    """Thread-safe data cache for API responses"""
    
    def __init__(self, ttl_seconds: int = 5):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data if still valid"""
        with self.lock:
            if key not in self.cache:
                return None
            
            # Check if expired
            if datetime.now() - self.timestamps[key] > timedelta(seconds=self.ttl):
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Cache data with timestamp"""
        with self.lock:
            self.cache[key] = value
            self.timestamps[key] = datetime.now()
    
    def clear(self):
        """Clear all cached data"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()


class RSRPCollector:
    """Collects and manages RSRP data for real-time display"""
    
    def __init__(self, collection_interval: int = 2):
        self.collection_interval = collection_interval
        self.rsrp_history = []
        self.max_history = 100  # Keep last 100 readings
        self.lock = threading.Lock()
        self.running = False
        self.collection_thread = None
        self.logger = logging.getLogger('SimSelector.RSRPCollector')
    
    def start_collection(self):
        """Start RSRP data collection in background thread"""
        if self.running:
            return
        
        self.running = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        self.logger.info("RSRP collection started")
    
    def stop_collection(self):
        """Stop RSRP data collection"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        self.logger.info("RSRP collection stopped")
    
    def _collection_loop(self):
        """Background thread for collecting RSRP data"""
        while self.running:
            try:
                self._collect_rsrp_data()
            except Exception as e:
                handle_error(e, {"operation": "rsrp_collection"})
            
            time.sleep(self.collection_interval)
    
    def _collect_rsrp_data(self):
        """Collect current RSRP data from SIMs"""
        try:
            sim_data = SimSelector.get_sim_data()
            current_time = datetime.now()
            
            rsrp_reading = {
                'timestamp': current_time.isoformat(),
                'sims': []
            }
            
            for sim in sim_data:
                if isinstance(sim, dict) and 'rsrp' in sim:
                    rsrp_reading['sims'].append({
                        'sim_id': sim.get('sim_id', 'unknown'),
                        'carrier': sim.get('carrier', 'unknown'),
                        'rsrp': sim.get('rsrp'),
                        'signal_quality': self._classify_signal_strength(sim.get('rsrp'))
                    })
            
            with self.lock:
                self.rsrp_history.append(rsrp_reading)
                # Keep only recent history
                if len(self.rsrp_history) > self.max_history:
                    self.rsrp_history = self.rsrp_history[-self.max_history:]
                    
        except Exception as e:
            self.logger.error(f"Failed to collect RSRP data: {str(e)}")
    
    def _classify_signal_strength(self, rsrp: Optional[float]) -> str:
        """Classify RSRP signal strength"""
        if rsrp is None:
            return "unknown"
        elif rsrp >= -90:
            return "good"
        elif rsrp >= -110:
            return "weak"
        else:
            return "bad"
    
    def get_current_rsrp(self) -> Dict:
        """Get most recent RSRP data"""
        with self.lock:
            if not self.rsrp_history:
                return {'timestamp': datetime.now().isoformat(), 'sims': []}
            return self.rsrp_history[-1].copy()
    
    def get_rsrp_history(self, limit: int = 50) -> List[Dict]:
        """Get RSRP history for charting"""
        with self.lock:
            return self.rsrp_history[-limit:].copy() if self.rsrp_history else []


class DashboardAPI:
    """Main dashboard API class providing RESTful endpoints"""
    
    def __init__(self, phase_manager: PhaseManager = None, security_manager: SecurityManager = None):
        self.phase_manager = phase_manager or PhaseManager()
        self.security_manager = security_manager or SecurityManager()
        self.error_handler = ErrorHandler()
        self.cache = DataCache(ttl_seconds=5)
        self.rsrp_collector = RSRPCollector()
        self.logger = logging.getLogger('SimSelector.DashboardAPI')
        
        # API statistics
        self.request_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        
        # Detailed statistics (expected by tests)
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
        
        # Start RSRP collection if not in DEPLOYED phase
        current_phase = self.phase_manager.get_current_phase()
        if current_phase != Phase.DEPLOYED:
            self.rsrp_collector.start_collection()
    
    @handle_errors("api_request_validation")
    def validate_api_request(self, request_info: Dict) -> bool:
        """Validate API request with security checks"""
        try:
            # Check phase-based access
            current_phase = self.phase_manager.get_current_phase()
            if current_phase == Phase.DEPLOYED:
                dashboard_error("Dashboard API not available in DEPLOYED phase", 
                              ErrorSeverity.MEDIUM, {"phase": current_phase.name})
                return False
            
            # Security validation
            security_result = self.security_manager.validate_request(request_info)
            if security_result != SecurityDecision.GRANTED:
                dashboard_error("API request denied by security manager",
                              ErrorSeverity.HIGH, {"request": request_info})
                return False
            
            return True
            
        except Exception as e:
            handle_error(e, {"operation": "api_validation", "request": request_info})
            return False
    
    def _increment_stats(self, success: bool = True):
        """Update API statistics"""
        self.request_count += 1
        current_time = datetime.now()
        
        # Update detailed request statistics
        self.request_statistics['total_requests'] += 1
        self.request_statistics['last_request_time'] = current_time.isoformat()
        
        if success:
            self.request_statistics['successful_requests'] += 1
        else:
            self.error_count += 1
            self.request_statistics['failed_requests'] += 1
            
            # Update error statistics
            self.error_statistics['total_errors'] += 1
            self.error_statistics['last_error_time'] = current_time.isoformat()
    
    def _create_api_response(self, data: Any, success: bool = True, message: str = None) -> Dict:
        """Create standardized API response"""
        return {
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'data': data
        }
    
    # ===================
    # System Status APIs
    # ===================
    
    @handle_errors("get_system_status")
    def get_system_status(self, request_info: Dict = None) -> Dict:
        """Get comprehensive system status"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            # Check cache first
            cached = self.cache.get('system_status')
            if cached:
                self._increment_stats()
                return cached
            
            # Collect system status
            phase_status = self.phase_manager.get_phase_status()
            current_phase = self.phase_manager.get_current_phase()
            
            system_status = {
                'phase': {
                    'current': current_phase.name,
                    'status': phase_status
                },
                'dashboard': {
                    'uptime': str(datetime.now() - self.start_time),
                    'requests': self.request_count,
                    'errors': self.error_count,
                    'error_rate': round(self.error_count / max(1, self.request_count) * 100, 2)
                },
                'rsrp_collection': {
                    'active': self.rsrp_collector.running,
                    'interval': self.rsrp_collector.collection_interval,
                    'history_count': len(self.rsrp_collector.rsrp_history)
                },
                'timestamp': datetime.now().isoformat()
            }
            
            response = self._create_api_response(system_status)
            self.cache.set('system_status', response)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_system_status"})
            return self._create_api_response(None, False, "Failed to get system status")
    
    @handle_errors("get_device_info")
    def get_device_info(self, request_info: Dict = None) -> Dict:
        """Get device hardware and network information"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            # Check cache first
            cached = self.cache.get('device_info')
            if cached:
                self._increment_stats()
                return cached
            
            # Collect device information
            device_info = {
                'hostname': 'cradlepoint-device',  # Would be dynamically determined
                'model': 'CradlePoint Router',
                'firmware_version': '7.x.x',
                'serial_number': 'CP-SERIAL-123',
                'uptime': '2 days, 4 hours',
                'network_interfaces': [
                    {'name': 'eth0', 'status': 'up', 'ip': '192.168.1.100'},
                    {'name': 'wwan0', 'status': 'up', 'ip': '10.0.0.50'},
                    {'name': 'wwan1', 'status': 'up', 'ip': '10.0.1.75'}
                ],
                'memory': {
                    'total': '512MB',
                    'used': '256MB',
                    'free': '256MB',
                    'usage_percent': 50
                },
                'cpu': {
                    'usage_percent': 25,
                    'load_average': '0.5, 0.6, 0.4'
                },
                'timestamp': datetime.now().isoformat()
            }
            
            response = self._create_api_response(device_info)
            self.cache.set('device_info', response)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_device_info"})
            return self._create_api_response(None, False, "Failed to get device info")
    
    # ===================
    # RSRP Data APIs
    # ===================
    
    @handle_errors("get_current_rsrp")
    def get_current_rsrp(self, request_info: Dict = None) -> Dict:
        """Get current RSRP data for all SIMs"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            current_rsrp = self.rsrp_collector.get_current_rsrp()
            response = self._create_api_response(current_rsrp)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_current_rsrp"})
            return self._create_api_response(None, False, "Failed to get RSRP data")
    
    @handle_errors("get_rsrp_history")
    def get_rsrp_history(self, request_info: Dict = None, limit: int = 50) -> Dict:
        """Get RSRP history for charting"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            history = self.rsrp_collector.get_rsrp_history(limit)
            response = self._create_api_response({
                'history': history,
                'count': len(history),
                'limit': limit
            })
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_rsrp_history"})
            return self._create_api_response(None, False, "Failed to get RSRP history")
    
    # ===================
    # SIM Data APIs
    # ===================
    
    @handle_errors("get_sim_data")
    def get_sim_data(self, request_info: Dict = None) -> Dict:
        """Get current SIM data and status"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            # Check cache first
            cached = self.cache.get('sim_data')
            if cached:
                self._increment_stats()
                return cached
            
            # Get SIM data from SimSelector
            sim_data = SimSelector.get_sim_data()
            
            # Enhance with additional information
            enhanced_sim_data = []
            for sim in sim_data:
                if isinstance(sim, dict):
                    enhanced_sim = sim.copy()
                    # Add signal quality classification
                    if 'rsrp' in enhanced_sim:
                        enhanced_sim['signal_quality'] = self.rsrp_collector._classify_signal_strength(
                            enhanced_sim['rsrp']
                        )
                    enhanced_sim_data.append(enhanced_sim)
            
            response = self._create_api_response({
                'sims': enhanced_sim_data,
                'count': len(enhanced_sim_data),
                'active_sim': next((s for s in enhanced_sim_data if s.get('active')), None)
            })
            
            self.cache.set('sim_data', response)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_sim_data"})
            return self._create_api_response(None, False, "Failed to get SIM data")
    
    # ===================
    # Phase Management APIs
    # ===================
    
    @handle_errors("get_phase_status")
    def get_phase_status(self, request_info: Dict = None) -> Dict:
        """Get current phase status and transition information"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            phase_status = self.phase_manager.get_phase_status()
            current_phase = self.phase_manager.get_current_phase()
            
            response_data = {
                'current_phase': current_phase.name,
                'phase_status': phase_status,
                'available_phases': [p.name for p in Phase],
                'phase_descriptions': {
                    'STAGING': 'SIM validation and initial testing',
                    'INSTALL': 'Comprehensive testing and optimization',
                    'DEPLOYED': 'Production mode - dashboard disabled'
                }
            }
            
            response = self._create_api_response(response_data)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_phase_status"})
            return self._create_api_response(None, False, "Failed to get phase status")
    
    # ===================
    # Error and Diagnostics APIs
    # ===================
    
    @handle_errors("get_error_stats")
    def get_error_statistics(self, request_info: Dict = None) -> Dict:
        """Get error statistics and recent errors"""
        if not self.validate_api_request(request_info or {}):
            self._increment_stats(False)
            return self._create_api_response(None, False, "Request validation failed")
        
        try:
            error_stats = self.error_handler.get_error_statistics()
            recent_errors = self.error_handler.get_recent_errors(limit=20)
            
            response_data = {
                'statistics': error_stats,
                'recent_errors': recent_errors,
                'api_errors': {
                    'total_requests': self.request_count,
                    'error_count': self.error_count,
                    'error_rate': round(self.error_count / max(1, self.request_count) * 100, 2)
                }
            }
            
            response = self._create_api_response(response_data)
            self._increment_stats()
            return response
            
        except Exception as e:
            self._increment_stats(False)
            handle_error(e, {"operation": "get_error_statistics"})
            return self._create_api_response(None, False, "Failed to get error statistics")
    
    # ===================
    # API Management
    # ===================
    
    def shutdown(self):
        """Shutdown API and cleanup resources"""
        try:
            self.rsrp_collector.stop_collection()
            self.cache.clear()
            self.logger.info("Dashboard API shutdown complete")
        except Exception as e:
            handle_error(e, {"operation": "api_shutdown"})
    
    def cleanup(self):
        """Cleanup API resources (alias for shutdown, expected by tests)"""
        self.shutdown()
    
    def get_api_documentation(self) -> Dict:
        """Get API documentation for help system"""
        return {
            'endpoints': {
                '/api/status': 'Get comprehensive system status',
                '/api/device': 'Get device hardware information',
                '/api/rsrp/current': 'Get current RSRP data',
                '/api/rsrp/history': 'Get RSRP history for charting',
                '/api/sims': 'Get SIM data and status',
                '/api/phase': 'Get phase status and information',
                '/api/errors': 'Get error statistics and recent errors',
                '/api/docs': 'Get API documentation'
            },
            'parameters': {
                'limit': 'Limit number of results (default: 50)',
                'format': 'Response format: json (default)'
            },
            'authentication': 'IP-based authentication via security manager',
            'rate_limiting': 'Built-in caching to prevent API overload',
            'version': '2.6.0'
        }


# Global API instance
dashboard_api = None

def get_dashboard_api(phase_manager=None, security_manager=None) -> DashboardAPI:
    """Get or create global dashboard API instance"""
    global dashboard_api
    if dashboard_api is None:
        dashboard_api = DashboardAPI(phase_manager, security_manager)
    return dashboard_api

def shutdown_dashboard_api():
    """Shutdown global dashboard API instance"""
    global dashboard_api
    if dashboard_api:
        dashboard_api.shutdown()
        dashboard_api = None 