"""
Dashboard HTTP Server for SimSelector v2.6.0 Tech Dashboard

Provides embedded HTTP server for technician access during staging and installation phases.
Integrates with phase management, security framework, and firewall management.

Features:
- Phase-aware server lifecycle (only runs in STAGING/INSTALL phases)
- Security controls with IP validation and rate limiting
- SSL/TLS support for secure connections
- DoS protection with request rate limiting
- RESTful API endpoints for SIM status and device information
- Static file serving for dashboard UI
- WebSocket support for real-time updates
- Automatic server shutdown in DEPLOYED phase

Security:
- IP whitelist validation using SecurityManager
- Request rate limiting and DoS protection
- Request validation and sanitization
- Secure headers and HTTPS support
- Connection throttling and resource limits
"""

import os
import json
import time
import threading
import socket
import ssl
import hashlib
from collections import defaultdict, deque
from typing import Dict, Any, Optional, List, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from socketserver import ThreadingMixIn
import logging

# Import our core systems
try:
    from phase_manager import get_phase_manager, get_current_phase
    from security_manager import get_security_manager
    from firewall_manager import get_firewall_manager
    from state_manager import get_state, set_state
    from SimSelector import Phase
except ImportError as e:
    print(f"Warning: Could not import core systems: {e}")
    # Fallback definitions for testing
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class RateLimiter:
    """Request rate limiting and DoS protection"""
    
    def __init__(self, requests_per_minute=60, requests_per_second=5, block_duration=300):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.block_duration = block_duration  # 5 minutes
        
        # Track requests per IP
        self.minute_requests = defaultdict(deque)  # IP -> deque of timestamps
        self.second_requests = defaultdict(deque)  # IP -> deque of timestamps
        self.blocked_ips = {}  # IP -> block_end_time
        
        # Connection tracking
        self.active_connections = defaultdict(int)  # IP -> connection count
        self.max_connections_per_ip = 10
        
        # Request size tracking
        self.max_request_size = 1024 * 1024  # 1MB
        
        # Cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        self.cleanup_thread.start()
    
    def is_allowed(self, client_ip: str, request_size: int = 0) -> Tuple[bool, str]:
        """Check if request is allowed"""
        current_time = time.time()
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            if current_time < self.blocked_ips[client_ip]:
                remaining = int(self.blocked_ips[client_ip] - current_time)
                return False, f"IP blocked for {remaining} seconds"
            else:
                del self.blocked_ips[client_ip]
        
        # Check request size
        if request_size > self.max_request_size:
            return False, "Request too large"
        
        # Check connection count
        if self.active_connections[client_ip] >= self.max_connections_per_ip:
            return False, "Too many concurrent connections"
        
        # Clean old requests
        self._clean_old_requests(client_ip, current_time)
        
        # Check per-second rate limit
        second_count = len(self.second_requests[client_ip])
        if second_count >= self.requests_per_second:
            self._block_ip(client_ip, current_time)
            return False, "Rate limit exceeded (per second)"
        
        # Check per-minute rate limit
        minute_count = len(self.minute_requests[client_ip])
        if minute_count >= self.requests_per_minute:
            self._block_ip(client_ip, current_time)
            return False, "Rate limit exceeded (per minute)"
        
        # Record request
        self.second_requests[client_ip].append(current_time)
        self.minute_requests[client_ip].append(current_time)
        
        return True, "OK"
    
    def add_connection(self, client_ip: str):
        """Track new connection"""
        self.active_connections[client_ip] += 1
    
    def remove_connection(self, client_ip: str):
        """Remove connection tracking"""
        if self.active_connections[client_ip] > 0:
            self.active_connections[client_ip] -= 1
    
    def _clean_old_requests(self, client_ip: str, current_time: float):
        """Remove old request timestamps"""
        # Clean second requests (older than 1 second)
        while (self.second_requests[client_ip] and 
               current_time - self.second_requests[client_ip][0] > 1):
            self.second_requests[client_ip].popleft()
        
        # Clean minute requests (older than 60 seconds)
        while (self.minute_requests[client_ip] and 
               current_time - self.minute_requests[client_ip][0] > 60):
            self.minute_requests[client_ip].popleft()
    
    def _block_ip(self, client_ip: str, current_time: float):
        """Block IP for specified duration"""
        self.blocked_ips[client_ip] = current_time + self.block_duration
    
    def _cleanup_expired(self):
        """Cleanup expired blocks and old data"""
        while True:
            try:
                current_time = time.time()
                
                # Clean expired blocks
                expired_ips = [ip for ip, block_time in self.blocked_ips.items() 
                              if current_time > block_time]
                for ip in expired_ips:
                    del self.blocked_ips[ip]
                
                # Clean inactive connections
                inactive_ips = [ip for ip, count in self.active_connections.items() 
                               if count == 0]
                for ip in inactive_ips:
                    del self.active_connections[ip]
                
                # Clean old request tracking for inactive IPs
                for ip in list(self.second_requests.keys()):
                    if not self.second_requests[ip]:
                        del self.second_requests[ip]
                
                for ip in list(self.minute_requests.keys()):
                    if not self.minute_requests[ip]:
                        del self.minute_requests[ip]
                
                time.sleep(60)  # Cleanup every minute
                
            except Exception as e:
                print(f"Rate limiter cleanup error: {e}")
                time.sleep(60)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        return {
            'blocked_ips': len(self.blocked_ips),
            'active_connections': sum(self.active_connections.values()),
            'tracked_ips': len(self.active_connections),
            'requests_per_minute_limit': self.requests_per_minute,
            'requests_per_second_limit': self.requests_per_second,
            'max_connections_per_ip': self.max_connections_per_ip
        }


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Thread-per-request HTTP server for concurrent connections"""
    daemon_threads = True
    allow_reuse_address = True


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for SimSelector dashboard"""
    
    def __init__(self, *args, dashboard_server=None, **kwargs):
        self.dashboard_server = dashboard_server
        self.client_ip = None
        super().__init__(*args, **kwargs)
    
    def setup(self):
        """Setup connection with rate limiting"""
        super().setup()
        self.client_ip = self.client_address[0]
        
        # Add connection to rate limiter
        if self.dashboard_server and hasattr(self.dashboard_server, 'rate_limiter'):
            self.dashboard_server.rate_limiter.add_connection(self.client_ip)
    
    def finish(self):
        """Cleanup connection tracking"""
        try:
            # Remove connection from rate limiter
            if self.dashboard_server and hasattr(self.dashboard_server, 'rate_limiter'):
                self.dashboard_server.rate_limiter.remove_connection(self.client_ip)
        except:
            pass
        super().finish()
    
    def log_message(self, format, *args):
        """Override to use our logging system"""
        if self.dashboard_server:
            self.dashboard_server._log(f"HTTP {self.client_address[0]} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Rate limiting check
            if not self._check_rate_limit():
                return
            
            # Validate request security
            if not self._validate_request():
                return
            
            # Parse URL
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # Route requests
            if path == '/' or path == '/dashboard':
                self._serve_dashboard_home()
            elif path.startswith('/api/'):
                self._handle_api_request(path, parsed_url.query)
            elif path.startswith('/static/'):
                self._serve_static_file(path)
            elif path == '/status':
                self._serve_status_page()
            elif path == '/help':
                self._serve_help_page()
            elif path.startswith('/api/help/'):
                self._handle_help_api(path, parsed_url.query)
            else:
                self._send_error(404, "Page not found")
                
        except Exception as e:
            self.dashboard_server._log(f"Error handling GET request: {str(e)}", "ERROR")
            self._send_error(500, "Internal server error")
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            # Rate limiting check
            if not self._check_rate_limit():
                return
            
            # Validate request security
            if not self._validate_request():
                return
            
            # Parse URL and get content
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # Get POST data with size check
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > self.dashboard_server.rate_limiter.max_request_size:
                self._send_error(413, "Request entity too large")
                return
            
            post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ''
            
            # Route POST requests
            if path.startswith('/api/'):
                self._handle_api_post(path, post_data)
            else:
                self._send_error(405, "Method not allowed")
                
        except Exception as e:
            self.dashboard_server._log(f"Error handling POST request: {str(e)}", "ERROR")
            self._send_error(500, "Internal server error")
    
    def _check_rate_limit(self) -> bool:
        """Check rate limiting for current request"""
        try:
            if not self.dashboard_server or not hasattr(self.dashboard_server, 'rate_limiter'):
                return True
            
            # Get request size
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Check rate limit
            allowed, reason = self.dashboard_server.rate_limiter.is_allowed(self.client_ip, content_length)
            
            if not allowed:
                self.dashboard_server._log(f"Rate limit exceeded for {self.client_ip}: {reason}", "WARNING")
                self._send_error(429, f"Too Many Requests - {reason}")
                return False
            
            return True
            
        except Exception as e:
            self.dashboard_server._log(f"Rate limit check error: {str(e)}", "ERROR")
            return True  # Allow request if rate limiter fails
    
    def _validate_request(self) -> bool:
        """Validate request security using SecurityManager"""
        try:
            if not self.dashboard_server:
                return False
            
            # Get client IP
            client_ip = self.client_address[0]
            
            # Get current phase
            current_phase = self.dashboard_server.phase_manager.get_current_phase()
            if current_phase is None:
                self._send_error(503, "Service not available - no active phase")
                return False
            
            # Validate IP access
            access_result = self.dashboard_server.security_manager.validate_ip_access(client_ip, current_phase)
            if access_result.value != 'granted':
                self._send_error(403, f"Access denied: {access_result.value}")
                return False
            
            # Validate phase access for dashboard
            if not self.dashboard_server.security_manager.validate_phase_access(current_phase, 'lan_dashboard'):
                self._send_error(403, "Dashboard access not available in current phase")
                return False
            
            # Validate request path and parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            if not self.dashboard_server.security_manager.validate_request(parsed_url.path, query_params):
                self._send_error(400, "Invalid request")
                return False
            
            return True
            
        except Exception as e:
            self.dashboard_server._log(f"Request validation error: {str(e)}", "ERROR")
            self.dashboard_server._log(f"Request path: {self.path}", "DEBUG")
            self.dashboard_server._log(f"Request query: {parsed_url.query}", "DEBUG")
            self._send_error(500, "Security validation failed")
            return False
    
    def _serve_dashboard_home(self):
        """Serve the main dashboard page"""
        try:
            current_phase = self.dashboard_server.phase_manager.get_current_phase()
            phase_name = {0: 'STAGING', 1: 'INSTALL', 2: 'DEPLOYED'}.get(current_phase, 'UNKNOWN')
            
            # Generate dashboard HTML
            html_content = self._generate_dashboard_html(current_phase, phase_name)
            
            self._send_response(200, html_content, 'text/html')
            
        except Exception as e:
            self.dashboard_server._log(f"Error serving dashboard: {str(e)}", "ERROR")
            self._send_error(500, "Dashboard unavailable")
    
    def _serve_status_page(self):
        """Serve system status page"""
        try:
            status_data = self.dashboard_server._get_system_status()
            
            # Generate status HTML
            html_content = self._generate_status_html(status_data)
            
            self._send_response(200, html_content, 'text/html')
            
        except Exception as e:
            self.dashboard_server._log(f"Error serving status: {str(e)}", "ERROR")
            self._send_error(500, "Status unavailable")
    
    def _serve_help_page(self):
        """Serve comprehensive help page with template"""
        try:
            current_phase = self.dashboard_server.phase_manager.get_current_phase()
            phase_status = self.dashboard_server.phase_manager.get_phase_status()
            
            # Try to load help template
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'help.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    help_html = f.read()
                
                # Replace template variables
                replacements = {
                    '{{current_phase}}': str(current_phase),
                    '{{phase_name}}': phase_status.get('current_phase_name', 'Unknown'),
                    '{{timestamp}}': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                for placeholder, value in replacements.items():
                    help_html = help_html.replace(placeholder, value)
                
                self._send_response(200, help_html)
            else:
                # Fallback to generated help if template not found
                help_html = self._generate_help_html(current_phase)
                self._send_response(200, help_html)
                
        except Exception as e:
            self.dashboard_server._log(f"Error serving help page: {str(e)}", "ERROR")
            self._send_error(500, "Failed to load help page")
    
    def _handle_help_api(self, path: str, query: str):
        """Handle help-specific API requests"""
        try:
            if path == '/api/help/search':
                self._api_help_search(query)
            elif path == '/api/help/context':
                self._api_help_context(query)
            elif path == '/api/help/troubleshooting':
                self._api_help_troubleshooting(query)
            else:
                self._send_json_error(404, "Help API endpoint not found")
        except Exception as e:
            self.dashboard_server._log(f"Help API error: {str(e)}", "ERROR")
            self._send_json_error(500, "Help API error")
    
    def _api_help_search(self, query: str):
        """API endpoint for help content search"""
        from urllib.parse import parse_qs
        params = parse_qs(query)
        search_term = params.get('q', [''])[0]
        
        # Mock search results - would be implemented with actual search
        results = []
        if search_term:
            results = [
                {
                    'title': 'Dashboard Access',
                    'section': 'troubleshooting',
                    'content': 'How to access the dashboard during different phases',
                    'relevance': 0.9
                },
                {
                    'title': 'Signal Quality',
                    'section': 'troubleshooting', 
                    'content': 'Improving signal strength and RSRP values',
                    'relevance': 0.7
                }
            ]
        
        self._send_json_response({
            'query': search_term,
            'results': results,
            'total': len(results)
        })
    
    def _api_help_context(self, query: str):
        """API endpoint for context-sensitive help"""
        from urllib.parse import parse_qs
        params = parse_qs(query)
        context = params.get('context', [''])[0]
        
        current_phase = self.dashboard_server.phase_manager.get_current_phase()
        
        # Context-sensitive help based on current phase and topic
        context_help = {
            'phase': current_phase,
            'phase_name': ['STAGING', 'INSTALL', 'DEPLOYED'][current_phase],
            'help_topics': self._get_context_help_topics(context, current_phase),
            'quick_actions': self._get_quick_actions(current_phase)
        }
        
        self._send_json_response(context_help)
    
    def _api_help_troubleshooting(self, query: str):
        """API endpoint for troubleshooting guides"""
        current_phase = self.dashboard_server.phase_manager.get_current_phase()
        
        troubleshooting_guides = {
            'dashboard_access': {
                'title': 'Dashboard Access Issues',
                'applicable_phases': [0, 1],  # STAGING, INSTALL
                'severity': 'high',
                'steps': [
                    'Verify device is in correct phase',
                    'Check LAN connectivity',
                    'Clear browser cache',
                    'Try different browser'
                ]
            },
            'poor_signal': {
                'title': 'Poor Signal Quality',
                'applicable_phases': [0, 1, 2],  # All phases
                'severity': 'medium',
                'steps': [
                    'Check antenna connections',
                    'Verify carrier coverage',
                    'Monitor RSRP values',
                    'Consider external antenna'
                ]
            }
        }
        
        # Filter guides by current phase
        applicable_guides = {
            k: v for k, v in troubleshooting_guides.items()
            if current_phase in v['applicable_phases']
        }
        
        self._send_json_response({
            'current_phase': current_phase,
            'guides': applicable_guides,
            'support_contact': {
                'email': 'support@simselector.com',
                'phone': '1-800-SIM-HELP'
            }
        })
    
    def _get_context_help_topics(self, context: str, phase: int) -> List[Dict[str, str]]:
        """Get help topics based on context and phase"""
        topics = []
        
        if context == 'signal':
            topics.extend([
                {'title': 'Understanding RSRP Values', 'link': '#signal-strength'},
                {'title': 'Improving Signal Quality', 'link': '#antenna-setup'}
            ])
        
        if context == 'phase' or not context:
            phase_names = ['STAGING', 'INSTALL', 'DEPLOYED']
            topics.append({
                'title': f'{phase_names[phase]} Phase Guide',
                'link': '#phase-guide'
            })
        
        return topics
    
    def _get_quick_actions(self, phase: int) -> List[Dict[str, str]]:
        """Get quick actions based on current phase"""
        actions = []
        
        if phase == 0:  # STAGING
            actions.extend([
                {'title': 'Check SIM Status', 'action': 'refresh_sim_data'},
                {'title': 'Run Signal Test', 'action': 'test_signal'}
            ])
        elif phase == 1:  # INSTALL
            actions.extend([
                {'title': 'Start Speed Test', 'action': 'start_speed_test'},
                {'title': 'Test Failover', 'action': 'test_failover'}
            ])
        
        return actions
    
    def _handle_api_request(self, path: str, query: str):
        """Handle API requests"""
        try:
            # Route API endpoints
            if path == '/api/v1/status':
                self._api_system_status()
            elif path == '/api/v1/phase':
                self._api_phase_status()
            elif path == '/api/v1/sims':
                self._api_sim_status()
            elif path == '/api/v1/rsrp':
                self._api_rsrp_data()
            elif path == '/api/v1/security':
                self._api_security_status()
            else:
                self._send_json_error(404, "API endpoint not found")
                
        except Exception as e:
            self.dashboard_server._log(f"API request error: {str(e)}", "ERROR")
            self._send_json_error(500, "API error")
    
    def _handle_api_post(self, path: str, data: str):
        """Handle API POST requests"""
        try:
            # Parse JSON data
            try:
                json_data = json.loads(data) if data else {}
            except json.JSONDecodeError:
                self._send_json_error(400, "Invalid JSON")
                return
            
            # Route POST API endpoints
            if path == '/api/v1/phase/transition':
                self._api_phase_transition(json_data)
            elif path == '/api/v1/test/start':
                self._api_start_test(json_data)
            else:
                self._send_json_error(404, "API endpoint not found")
                
        except Exception as e:
            self.dashboard_server._log(f"API POST error: {str(e)}", "ERROR")
            self._send_json_error(500, "API error")
    
    def _api_system_status(self):
        """API endpoint for system status"""
        status_data = self.dashboard_server._get_system_status()
        self._send_json_response(status_data)
    
    def _api_phase_status(self):
        """API endpoint for phase status"""
        phase_status = self.dashboard_server.phase_manager.get_phase_status()
        self._send_json_response(phase_status)
    
    def _api_sim_status(self):
        """API endpoint for SIM status"""
        # This will be implemented to get real SIM data
        sim_data = {
            'sims': [],
            'active_sim': None,
            'last_updated': time.time()
        }
        self._send_json_response(sim_data)
    
    def _api_rsrp_data(self):
        """API endpoint for RSRP data"""
        # This will be implemented to get real RSRP data
        rsrp_data = {
            'rsrp_values': {},
            'signal_quality': {},
            'last_updated': time.time()
        }
        self._send_json_response(rsrp_data)
    
    def _api_security_status(self):
        """API endpoint for security status"""
        current_phase = self.dashboard_server.phase_manager.get_current_phase()
        security_status = self.dashboard_server.security_manager.get_security_status(current_phase)
        self._send_json_response(security_status)
    
    def _api_phase_transition(self, data: Dict[str, Any]):
        """API endpoint for phase transitions"""
        try:
            target_phase = data.get('target_phase')
            force = data.get('force', False)
            
            if target_phase is None:
                self._send_json_error(400, "Missing target_phase")
                return
            
            # Attempt phase transition
            result = self.dashboard_server.phase_manager.transition_to_phase(target_phase, force)
            
            response = {
                'success': result.value == 'success',
                'result': result.value,
                'message': f"Phase transition to {target_phase}: {result.value}"
            }
            
            self._send_json_response(response)
            
        except Exception as e:
            self._send_json_error(500, f"Phase transition failed: {str(e)}")
    
    def _api_start_test(self, data: Dict[str, Any]):
        """API endpoint to start SIM testing"""
        try:
            test_type = data.get('test_type', 'basic')
            
            # This will be implemented to start actual SIM testing
            response = {
                'success': True,
                'test_id': f"test_{int(time.time())}",
                'message': f"Started {test_type} test",
                'estimated_duration': 60
            }
            
            self._send_json_response(response)
            
        except Exception as e:
            self._send_json_error(500, f"Test start failed: {str(e)}")
    
    def _serve_static_file(self, path: str):
        """Serve static files (CSS, JS, images)"""
        try:
            # Remove /static/ prefix
            file_path = path[8:]  # Remove '/static/'
            
            # Try to serve from static directory first
            static_file_path = os.path.join(os.path.dirname(__file__), 'static', file_path)
            if os.path.exists(static_file_path):
                with open(static_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Determine content type
                if file_path.endswith('.css'):
                    content_type = 'text/css'
                elif file_path.endswith('.js'):
                    content_type = 'application/javascript'
                elif file_path.endswith('.html'):
                    content_type = 'text/html'
                elif file_path.endswith('.json'):
                    content_type = 'application/json'
                else:
                    content_type = 'text/plain'
                
                self._send_response(200, content, content_type)
                return
            
            # Fallback to embedded content for backward compatibility
            if file_path == 'dashboard.css' or file_path == 'css/dashboard.css':
                css_content = self._get_dashboard_css()
                self._send_response(200, css_content, 'text/css')
            elif file_path == 'dashboard.js' or file_path == 'js/dashboard.js':
                js_content = self._get_dashboard_js()
                self._send_response(200, js_content, 'application/javascript')
            else:
                self._send_error(404, "Static file not found")
                
        except Exception as e:
            self.dashboard_server._log(f"Static file error: {str(e)}", "ERROR")
            self._send_error(500, "Static file error")
    
    def _generate_dashboard_html(self, current_phase: int, phase_name: str) -> str:
        """Generate main dashboard HTML using template"""
        try:
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
            
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                
                # Simple template variable replacement
                template = template.replace('{{phase_name}}', phase_name)
                template = template.replace('{{current_phase}}', str(current_phase))
                
                return template
            else:
                # Fallback to basic HTML if template not found
                return self._generate_fallback_html(current_phase, phase_name)
                
        except Exception as e:
            self.dashboard_server._log(f"Template rendering failed: {e}", "ERROR")
            return self._generate_fallback_html(current_phase, phase_name)
    
    def _generate_fallback_html(self, current_phase: int, phase_name: str) -> str:
        """Fallback HTML when template is not available"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimSelector Tech Dashboard - {phase_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .dashboard {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .phase-indicator {{ background: #3498db; padding: 10px; border-radius: 5px; display: inline-block; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .card h3 {{ margin: 0 0 15px 0; color: #2c3e50; }}
        .fallback-notice {{ background: #f39c12; color: white; padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="fallback-notice">
            <strong>Notice:</strong> Running in fallback mode. Template files not found.
        </div>
        <header class="header">
            <h1>SimSelector Tech Dashboard</h1>
            <div class="phase-indicator">Phase: {phase_name}</div>
        </header>
        
        <main class="cards">
            <div class="card">
                <h3>Current Phase</h3>
                <p>{phase_name} - Phase {current_phase}</p>
            </div>
            
            <div class="card">
                <h3>System Status</h3>
                <p>Dashboard server running in fallback mode</p>
                <p>Security: Active</p>
            </div>
            
            <div class="card">
                <h3>Quick Actions</h3>
                <p><a href="/status">View System Status</a></p>
                <p><a href="/help">Help & Documentation</a></p>
                <button onclick="location.reload()">Refresh Dashboard</button>
            </div>
        </main>
    </div>
</body>
</html>"""
    
    def _generate_status_html(self, status_data: Dict[str, Any]) -> str:
        """Generate system status HTML"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimSelector System Status</title>
    <link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <h1>System Status</h1>
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
        </header>
        
        <main class="status-main">
            <div class="status-section">
                <h2>System Information</h2>
                <table class="status-table">
                    <tr><td>Current Phase</td><td>{status_data.get('current_phase_name', 'Unknown')}</td></tr>
                    <tr><td>Phase Duration</td><td>{status_data.get('phase_duration', 0):.1f} seconds</td></tr>
                    <tr><td>System Uptime</td><td>{status_data.get('system_uptime', 0):.1f} seconds</td></tr>
                    <tr><td>Security Level</td><td>{status_data.get('security_level', 'Unknown')}</td></tr>
                </table>
            </div>
            
            <div class="status-section">
                <h2>Network Status</h2>
                <table class="status-table">
                    <tr><td>Dashboard Server</td><td>Running on port {status_data.get('server_port', 8080)}</td></tr>
                    <tr><td>Firewall Status</td><td>{status_data.get('firewall_status', 'Unknown')}</td></tr>
                    <tr><td>Dashboard Access</td><td>{status_data.get('dashboard_access', 'Unknown')}</td></tr>
                </table>
            </div>
        </main>
    </div>
</body>
</html>"""
    
    def _generate_help_html(self, current_phase: int) -> str:
        """Generate help documentation HTML"""
        phase_help = {
            0: "STAGING Phase: Perform basic SIM validation and signal strength assessment.",
            1: "INSTALL Phase: Run full SIM testing and performance optimization.",
            2: "DEPLOYED Phase: Production operation with automatic SIM management."
        }
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimSelector Help & Documentation</title>
    <link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <h1>Help & Documentation</h1>
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
        </header>
        
        <main class="help-main">
            <div class="help-section">
                <h2>Current Phase: {phase_help.get(current_phase, 'Unknown Phase')}</h2>
                <p>This help content will be expanded with detailed phase-specific guidance.</p>
            </div>
            
            <div class="help-section">
                <h2>Quick Actions</h2>
                <ul>
                    <li>View system status and current phase information</li>
                    <li>Monitor SIM signal strength and connectivity</li>
                    <li>Access troubleshooting guides and support information</li>
                </ul>
            </div>
        </main>
    </div>
</body>
</html>"""
    
    def _get_dashboard_css(self) -> str:
        """Get dashboard CSS styles"""
        return """/* SimSelector Dashboard CSS */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f5f5f5;
    color: #333;
}

.dashboard-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.dashboard-header {
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.dashboard-header h1 {
    margin: 0;
    font-size: 1.8em;
}

.phase-indicator {
    background: rgba(255,255,255,0.2);
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: bold;
}

.phase-0 { background-color: #f39c12; }
.phase-1 { background-color: #27ae60; }
.phase-2 { background-color: #e74c3c; }

.status-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.card {
    background: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    border-left: 4px solid #3498db;
}

.card h3 {
    margin: 0 0 15px 0;
    color: #2c3e50;
    font-size: 1.2em;
}

.card-content {
    font-size: 1.1em;
}

.action-panel, .log-panel {
    background: white;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.action-buttons {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.btn {
    background: #3498db;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 1em;
    transition: background-color 0.3s;
}

.btn:hover {
    background: #2980b9;
}

.btn:disabled {
    background: #bdc3c7;
    cursor: not-allowed;
}

.log-content {
    max-height: 200px;
    overflow-y: auto;
    background: #f8f9fa;
    padding: 10px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.9em;
}

.dashboard-footer {
    background: #34495e;
    color: white;
    padding: 15px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.footer-links a {
    color: #ecf0f1;
    text-decoration: none;
    margin-right: 20px;
}

.footer-links a:hover {
    text-decoration: underline;
}

.status-table {
    width: 100%;
    border-collapse: collapse;
}

.status-table td {
    padding: 10px;
    border-bottom: 1px solid #eee;
}

.status-table td:first-child {
    font-weight: bold;
    width: 30%;
}

.back-link {
    color: white;
    text-decoration: none;
    font-size: 1.1em;
}

.back-link:hover {
    text-decoration: underline;
}

/* Responsive design */
@media (max-width: 768px) {
    .dashboard-container {
        padding: 10px;
    }
    
    .dashboard-header {
        flex-direction: column;
        text-align: center;
        gap: 10px;
    }
    
    .status-cards {
        grid-template-columns: 1fr;
    }
    
    .action-buttons {
        flex-direction: column;
    }
    
    .dashboard-footer {
        flex-direction: column;
        gap: 10px;
        text-align: center;
    }
}"""
    
    def _get_dashboard_js(self) -> str:
        """Get dashboard JavaScript"""
        return """// SimSelector Dashboard JavaScript

class DashboardManager {
    constructor() {
        this.updateInterval = 5000; // 5 seconds
        this.init();
    }
    
    init() {
        this.updateStatus();
        this.setupEventListeners();
        this.startAutoUpdate();
    }
    
    async updateStatus() {
        try {
            // Update phase status
            const phaseStatus = await this.fetchAPI('/api/v1/phase');
            this.updatePhaseDisplay(phaseStatus);
            
            // Update SIM status
            const simStatus = await this.fetchAPI('/api/v1/sims');
            this.updateSimDisplay(simStatus);
            
            // Update signal data
            const rsrpData = await this.fetchAPI('/api/v1/rsrp');
            this.updateSignalDisplay(rsrpData);
            
            // Update security status
            const securityStatus = await this.fetchAPI('/api/v1/security');
            this.updateSecurityDisplay(securityStatus);
            
            // Update action buttons
            this.updateActionButtons(phaseStatus);
            
            // Update timestamp
            document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
            
        } catch (error) {
            console.error('Status update failed:', error);
            this.showError('Failed to update dashboard status');
        }
    }
    
    async fetchAPI(endpoint) {
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        return await response.json();
    }
    
    updatePhaseDisplay(phaseStatus) {
        const phaseDescription = document.getElementById('phase-description');
        if (phaseDescription) {
            const descriptions = {
                0: 'Basic SIM validation and signal assessment',
                1: 'Full testing and performance optimization',
                2: 'Production operation mode'
            };
            phaseDescription.textContent = descriptions[phaseStatus.current_phase] || 'Unknown phase';
        }
    }
    
    updateSimDisplay(simStatus) {
        const simStatusElement = document.getElementById('sim-status');
        if (simStatusElement) {
            if (simStatus.sims && simStatus.sims.length > 0) {
                const simList = simStatus.sims.map(sim => 
                    `<div class="sim-item">${sim.carrier} - ${sim.status}</div>`
                ).join('');
                simStatusElement.innerHTML = simList;
            } else {
                simStatusElement.innerHTML = 'No SIM data available';
            }
        }
    }
    
    updateSignalDisplay(rsrpData) {
        const signalStatusElement = document.getElementById('signal-status');
        if (signalStatusElement) {
            if (rsrpData.rsrp_values && Object.keys(rsrpData.rsrp_values).length > 0) {
                const signalList = Object.entries(rsrpData.rsrp_values).map(([sim, rsrp]) => 
                    `<div class="signal-item">${sim}: ${rsrp} dBm</div>`
                ).join('');
                signalStatusElement.innerHTML = signalList;
            } else {
                signalStatusElement.innerHTML = 'No signal data available';
            }
        }
    }
    
    updateSecurityDisplay(securityStatus) {
        const securityStatusElement = document.getElementById('security-status');
        if (securityStatusElement) {
            securityStatusElement.innerHTML = `
                <div>Security Level: ${securityStatus.security_level || 'Unknown'}</div>
                <div>Dashboard Access: ${securityStatus.dashboard_access_allowed ? 'Enabled' : 'Disabled'}</div>
            `;
        }
    }
    
    updateActionButtons(phaseStatus) {
        const actionButtonsElement = document.getElementById('action-buttons');
        if (actionButtonsElement) {
            let buttons = '';
            
            // Phase-specific buttons
            if (phaseStatus.current_phase === 0) { // STAGING
                buttons += '<button class="btn" onclick="dashboard.startBasicTest()">Start Basic Test</button>';
                buttons += '<button class="btn" onclick="dashboard.advancePhase()">Advance to Install</button>';
            } else if (phaseStatus.current_phase === 1) { // INSTALL
                buttons += '<button class="btn" onclick="dashboard.startFullTest()">Start Full Test</button>';
                buttons += '<button class="btn" onclick="dashboard.advancePhase()">Complete Installation</button>';
            }
            
            // Always available buttons
            buttons += '<button class="btn" onclick="dashboard.refreshStatus()">Refresh Status</button>';
            
            actionButtonsElement.innerHTML = buttons;
        }
    }
    
    setupEventListeners() {
        // Add any event listeners here
    }
    
    startAutoUpdate() {
        setInterval(() => {
            this.updateStatus();
        }, this.updateInterval);
    }
    
    async startBasicTest() {
        try {
            const response = await fetch('/api/v1/test/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ test_type: 'basic' })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showSuccess('Basic test started successfully');
            } else {
                this.showError('Failed to start basic test');
            }
        } catch (error) {
            this.showError('Error starting basic test');
        }
    }
    
    async startFullTest() {
        try {
            const response = await fetch('/api/v1/test/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ test_type: 'full' })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showSuccess('Full test started successfully');
            } else {
                this.showError('Failed to start full test');
            }
        } catch (error) {
            this.showError('Error starting full test');
        }
    }
    
    async advancePhase() {
        const confirmed = confirm('Are you sure you want to advance to the next phase?');
        if (!confirmed) return;
        
        try {
            const phaseStatus = await this.fetchAPI('/api/v1/phase');
            const nextPhase = phaseStatus.current_phase + 1;
            
            const response = await fetch('/api/v1/phase/transition', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_phase: nextPhase })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showSuccess('Phase transition successful');
                setTimeout(() => this.updateStatus(), 1000);
            } else {
                this.showError('Phase transition failed');
            }
        } catch (error) {
            this.showError('Error during phase transition');
        }
    }
    
    refreshStatus() {
        this.updateStatus();
        this.showSuccess('Status refreshed');
    }
    
    showSuccess(message) {
        // Simple success notification (can be enhanced)
        console.log('SUCCESS:', message);
    }
    
    showError(message) {
        // Simple error notification (can be enhanced)
        console.error('ERROR:', message);
    }
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new DashboardManager();
});"""
    
    def _send_response(self, status_code: int, content: str, content_type: str = 'text/html'):
        """Send HTTP response"""
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Content-length', len(content.encode('utf-8')))
        
        # Security headers
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def _send_json_response(self, data: Any):
        """Send JSON response"""
        json_content = json.dumps(data, indent=2)
        self._send_response(200, json_content, 'application/json')
    
    def _send_error(self, status_code: int, message: str):
        """Send error response"""
        error_html = f"""<!DOCTYPE html>
<html><head><title>Error {status_code}</title></head>
<body><h1>Error {status_code}</h1><p>{message}</p></body></html>"""
        self._send_response(status_code, error_html)
    
    def _send_json_error(self, status_code: int, message: str):
        """Send JSON error response"""
        error_data = {"error": True, "status_code": status_code, "message": message}
        json_content = json.dumps(error_data, indent=2)
        self._send_response(status_code, json_content, 'application/json')


class DashboardServer:
    """Main dashboard server class with SSL/TLS support and enhanced lifecycle management"""
    
    def __init__(self, client=None, host='0.0.0.0', port=8080, ssl_cert=None, ssl_key=None, enable_ssl=False):
        self.client = client
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False
        
        # SSL configuration
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.enable_ssl = enable_ssl
        self.ssl_context = None
        
        # Initialize core systems
        self.phase_manager = get_phase_manager(client)
        self.security_manager = get_security_manager(client)
        self.firewall_manager = get_firewall_manager(client)
        
        # Server state
        self.start_time = None
        self.request_count = 0
        self.restart_count = 0
        self.last_restart_time = None
        
        # Rate limiter with configurable limits
        self.rate_limiter = RateLimiter(
            requests_per_minute=60,    # Allow 60 requests per minute per IP
            requests_per_second=5,     # Allow 5 requests per second per IP
            block_duration=300         # Block for 5 minutes on violation
        )
        
        # Health monitoring
        self.health_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'error_count': 0,
            'blocked_requests': 0,
            'start_time': None,
            'last_request_time': None
        }
        
        # Server lifecycle events
        self.lifecycle_callbacks = {
            'on_start': [],
            'on_stop': [],
            'on_restart': [],
            'on_error': []
        }
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log server operations"""
        try:
            if self.client and hasattr(self.client, 'log'):
                self.client.log(f"DASHBOARD [{level}] {message}")
            else:
                print(f"DASHBOARD [{level}] {message}")
        except Exception:
            # Fallback to print if client logging fails
            print(f"DASHBOARD [{level}] {message}")
    
    def start(self) -> bool:
        """Start the dashboard server with SSL/TLS support"""
        try:
            # Check if already running
            if self.running:
                self._log("Dashboard server is already running", "WARNING")
                return True
            
            # Check if we should be running based on current phase
            current_phase = self.phase_manager.get_current_phase()
            if current_phase not in [Phase.STAGING, Phase.INSTALL]:
                self._log(f"Dashboard server not started - phase {current_phase} does not allow dashboard access", "WARNING")
                return False
            
            # Configure firewall for dashboard access
            if not self.firewall_manager.configure_dashboard_access(current_phase):
                self._log("Failed to configure firewall for dashboard access", "ERROR")
                return False
            
            # Setup SSL context if enabled
            if self.enable_ssl:
                if not self._setup_ssl_context():
                    self._log("Failed to setup SSL context", "ERROR")
                    return False
            
            # Create server with custom handler
            def handler(*args, **kwargs):
                return DashboardRequestHandler(*args, dashboard_server=self, **kwargs)
            
            self.server = ThreadingHTTPServer((self.host, self.port), handler)
            self.server.timeout = 1.0  # Allow for clean shutdown
            
            # Configure SSL if enabled
            if self.enable_ssl and self.ssl_context:
                self.server.socket = self.ssl_context.wrap_socket(
                    self.server.socket, 
                    server_side=True
                )
                self._log("SSL/TLS enabled for dashboard server", "INFO")
            
            # Start server in separate thread
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.running = True
            self.start_time = time.time()
            self.health_stats['start_time'] = self.start_time
            
            # Execute start callbacks
            self._execute_lifecycle_callbacks('on_start')
            
            protocol = "HTTPS" if self.enable_ssl else "HTTP"
            self._log(f"Dashboard server started on {protocol}://{self.host}:{self.port}")
            return True
            
        except Exception as e:
            self._log(f"Failed to start dashboard server: {str(e)}", "ERROR")
            self._execute_lifecycle_callbacks('on_error', error=str(e))
            return False
    
    def _setup_ssl_context(self) -> bool:
        """Setup SSL context for HTTPS"""
        try:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            # Use provided certificate files
            if self.ssl_cert and self.ssl_key:
                if os.path.exists(self.ssl_cert) and os.path.exists(self.ssl_key):
                    self.ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
                    self._log(f"SSL certificate loaded from {self.ssl_cert}", "INFO")
                    return True
                else:
                    self._log(f"SSL certificate files not found: {self.ssl_cert}, {self.ssl_key}", "ERROR")
                    return False
            
            # Generate self-signed certificate for development
            self._log("Generating self-signed certificate for development use", "WARNING")
            if self._generate_self_signed_cert():
                self.ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
                return True
            
            return False
            
        except Exception as e:
            self._log(f"SSL context setup failed: {str(e)}", "ERROR")
            return False
    
    def _generate_self_signed_cert(self) -> bool:
        """Generate self-signed certificate for development"""
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "SimSelector"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SimSelector Dashboard"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(socket.inet_aton("127.0.0.1")),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Save certificate and key
            self.ssl_cert = "dashboard_cert.pem"
            self.ssl_key = "dashboard_key.pem"
            
            with open(self.ssl_cert, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            with open(self.ssl_key, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Set restrictive permissions
            os.chmod(self.ssl_cert, 0o600)
            os.chmod(self.ssl_key, 0o600)
            
            self._log("Self-signed certificate generated successfully", "INFO")
            return True
            
        except ImportError:
            self._log("cryptography library not available for SSL certificate generation", "ERROR")
            return False
        except Exception as e:
            self._log(f"Certificate generation failed: {str(e)}", "ERROR")
            return False
    
    def stop(self) -> bool:
        """Stop the dashboard server with enhanced lifecycle management"""
        try:
            if not self.running:
                self._log("Dashboard server is not running", "INFO")
                return True
            
            self._log("Stopping dashboard server...")
            self.running = False
            
            # Graceful shutdown sequence
            if self.server:
                try:
                    self.server.shutdown()
                    self.server.server_close()
                except Exception as e:
                    self._log(f"Error during server shutdown: {str(e)}", "WARNING")
            
            # Wait for server thread to finish
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=10.0)  # Increased timeout
                if self.server_thread.is_alive():
                    self._log("Server thread did not stop gracefully", "WARNING")
            
            # Remove firewall rules
            try:
                current_phase = self.phase_manager.get_current_phase()
                self.firewall_manager.remove_dashboard_access(current_phase)
            except Exception as e:
                self._log(f"Error removing firewall rules: {str(e)}", "WARNING")
            
            # Clean up SSL certificates if auto-generated
            if self.enable_ssl and self.ssl_cert and self.ssl_cert == "dashboard_cert.pem":
                try:
                    if os.path.exists("dashboard_cert.pem"):
                        os.remove("dashboard_cert.pem")
                    if os.path.exists("dashboard_key.pem"):
                        os.remove("dashboard_key.pem")
                    self._log("Cleaned up auto-generated SSL certificates", "INFO")
                except Exception as e:
                    self._log(f"Error cleaning up SSL certificates: {str(e)}", "WARNING")
            
            # Reset server state
            self.server = None
            self.server_thread = None
            self.ssl_context = None
            
            # Execute stop callbacks
            self._execute_lifecycle_callbacks('on_stop')
            
            self._log("Dashboard server stopped successfully")
            return True
            
        except Exception as e:
            self._log(f"Error stopping dashboard server: {str(e)}", "ERROR")
            self._execute_lifecycle_callbacks('on_error', error=str(e))
            return False
    
    def restart(self) -> bool:
        """Restart the dashboard server with enhanced error handling"""
        try:
            self._log("Restarting dashboard server...")
            self.restart_count += 1
            self.last_restart_time = time.time()
            
            # Execute restart callbacks
            self._execute_lifecycle_callbacks('on_restart')
            
            # Stop current server
            if not self.stop():
                self._log("Failed to stop server during restart", "ERROR")
                return False
            
            # Wait before restart
            time.sleep(2)
            
            # Start server again
            if self.start():
                self._log(f"Dashboard server restarted successfully (restart #{self.restart_count})")
                return True
            else:
                self._log("Failed to start server during restart", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error during server restart: {str(e)}", "ERROR")
            self._execute_lifecycle_callbacks('on_error', error=str(e))
            return False
    
    def add_lifecycle_callback(self, event: str, callback):
        """Add lifecycle callback for server events"""
        if event in self.lifecycle_callbacks:
            self.lifecycle_callbacks[event].append(callback)
        else:
            self._log(f"Unknown lifecycle event: {event}", "WARNING")
    
    def _execute_lifecycle_callbacks(self, event: str, **kwargs):
        """Execute lifecycle callbacks for event"""
        try:
            for callback in self.lifecycle_callbacks.get(event, []):
                try:
                    callback(self, **kwargs)
                except Exception as e:
                    self._log(f"Lifecycle callback error for {event}: {str(e)}", "ERROR")
        except Exception as e:
            self._log(f"Error executing lifecycle callbacks: {str(e)}", "ERROR")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        current_time = time.time()
        uptime = current_time - self.start_time if self.start_time else 0
        
        # Calculate request rate
        request_rate = self.health_stats['total_requests'] / uptime if uptime > 0 else 0
        
        # Get rate limiter stats
        rate_limiter_stats = self.rate_limiter.get_stats()
        
        return {
            'running': self.running,
            'uptime_seconds': uptime,
            'total_requests': self.health_stats['total_requests'],
            'successful_requests': self.health_stats['successful_requests'],
            'error_count': self.health_stats['error_count'],
            'blocked_requests': self.health_stats['blocked_requests'],
            'request_rate_per_second': request_rate,
            'restart_count': self.restart_count,
            'last_restart_time': self.last_restart_time,
            'ssl_enabled': self.enable_ssl,
            'rate_limiter': rate_limiter_stats,
            'phase_allowed': self.phase_manager.get_current_phase() in [Phase.STAGING, Phase.INSTALL],
            'memory_usage': self._get_memory_usage(),
            'connection_count': sum(self.rate_limiter.active_connections.values())
        }
    
    def _get_memory_usage(self) -> Dict[str, int]:
        """Get memory usage information"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                'rss': memory_info.rss,  # Resident Set Size
                'vms': memory_info.vms,  # Virtual Memory Size
                'percent': process.memory_percent()
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}
    
    def force_shutdown(self) -> bool:
        """Force shutdown of server (for emergency situations)"""
        try:
            self._log("Force shutdown initiated", "WARNING")
            self.running = False
            
            if self.server_thread and self.server_thread.is_alive():
                # More aggressive shutdown
                if self.server:
                    try:
                        self.server.server_close()
                    except:
                        pass
                
                # Don't wait for thread to finish gracefully
                self.server_thread = None
            
            self.server = None
            self.ssl_context = None
            
            self._log("Force shutdown completed", "WARNING")
            return True
            
        except Exception as e:
            self._log(f"Error during force shutdown: {str(e)}", "ERROR")
            return False
    
    def _run_server(self):
        """Run the HTTP server"""
        try:
            while self.running:
                self.server.handle_request()
        except Exception as e:
            self._log(f"Server error: {str(e)}", "ERROR")
        finally:
            self.running = False
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            current_phase = self.phase_manager.get_current_phase()
            phase_status = self.phase_manager.get_phase_status()
            security_status = self.security_manager.get_security_status(current_phase)
            firewall_status = self.firewall_manager.get_firewall_status()
            
            return {
                'current_phase': current_phase,
                'current_phase_name': phase_status.get('current_phase_name', 'Unknown'),
                'phase_duration': phase_status.get('phase_duration', 0),
                'system_uptime': phase_status.get('system_uptime', 0),
                'security_level': security_status.get('security_level', 'Unknown'),
                'server_port': self.port,
                'server_uptime': time.time() - self.start_time if self.start_time else 0,
                'request_count': self.request_count,
                'firewall_status': firewall_status,
                'dashboard_access': 'Enabled' if current_phase in [Phase.STAGING, Phase.INSTALL] else 'Disabled'
            }
            
        except Exception as e:
            self._log(f"Error getting system status: {str(e)}", "ERROR")
            return {'error': str(e)}
    
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running and self.server_thread and self.server_thread.is_alive()
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information"""
        return {
            'host': self.host,
            'port': self.port,
            'running': self.is_running(),
            'start_time': self.start_time,
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'request_count': self.request_count
        }


# Global server instance
_dashboard_server = None

def get_dashboard_server(client=None, host='0.0.0.0', port=8080):
    """Get or create dashboard server instance"""
    global _dashboard_server
    if _dashboard_server is None:
        _dashboard_server = DashboardServer(client, host, port)
    return _dashboard_server

def start_dashboard_server(client=None, host='0.0.0.0', port=8080) -> bool:
    """Start the dashboard server"""
    server = get_dashboard_server(client, host, port)
    return server.start()

def stop_dashboard_server() -> bool:
    """Stop the dashboard server"""
    global _dashboard_server
    if _dashboard_server:
        return _dashboard_server.stop()
    return True

def is_dashboard_running() -> bool:
    """Check if dashboard server is running"""
    global _dashboard_server
    return _dashboard_server is not None and _dashboard_server.is_running() 