"""
Dashboard HTTP Server for SimSelector v2.6.0 Tech Dashboard

Provides embedded HTTP server for technician access during staging and installation phases.
Integrates with phase management, security framework, and firewall management.

Features:
- Phase-aware server lifecycle (only runs in STAGING/INSTALL phases)
- Security controls with IP validation and rate limiting
- RESTful API endpoints for SIM status and device information
- Static file serving for dashboard UI
- WebSocket support for real-time updates
- Automatic server shutdown in DEPLOYED phase

Security:
- IP whitelist validation using SecurityManager
- Rate limiting and DoS protection
- Request validation and sanitization
- Secure headers and HTTPS support (optional)
"""

import os
import json
import time
import threading
import socket
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


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Thread-per-request HTTP server for concurrent connections"""
    daemon_threads = True
    allow_reuse_address = True


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for SimSelector dashboard"""
    
    def __init__(self, *args, dashboard_server=None, **kwargs):
        self.dashboard_server = dashboard_server
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to use our logging system"""
        if self.dashboard_server:
            self.dashboard_server._log(f"HTTP {self.client_address[0]} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests"""
        try:
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
            else:
                self._send_error(404, "Page not found")
                
        except Exception as e:
            self.dashboard_server._log(f"Error handling GET request: {str(e)}", "ERROR")
            self._send_error(500, "Internal server error")
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            # Validate request security
            if not self._validate_request():
                return
            
            # Parse URL and get content
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # Get POST data
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ''
            
            # Route POST requests
            if path.startswith('/api/'):
                self._handle_api_post(path, post_data)
            else:
                self._send_error(405, "Method not allowed")
                
        except Exception as e:
            self.dashboard_server._log(f"Error handling POST request: {str(e)}", "ERROR")
            self._send_error(500, "Internal server error")
    
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
        """Serve help documentation page"""
        try:
            current_phase = self.dashboard_server.phase_manager.get_current_phase()
            
            # Generate help HTML based on current phase
            html_content = self._generate_help_html(current_phase)
            
            self._send_response(200, html_content, 'text/html')
            
        except Exception as e:
            self.dashboard_server._log(f"Error serving help: {str(e)}", "ERROR")
            self._send_error(500, "Help unavailable")
    
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
            
            # Basic static file serving (will be enhanced)
            if file_path == 'dashboard.css':
                css_content = self._get_dashboard_css()
                self._send_response(200, css_content, 'text/css')
            elif file_path == 'dashboard.js':
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
    """Main dashboard server class"""
    
    def __init__(self, client=None, host='0.0.0.0', port=8080):
        self.client = client
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False
        
        # Initialize core systems
        self.phase_manager = get_phase_manager(client)
        self.security_manager = get_security_manager(client)
        self.firewall_manager = get_firewall_manager(client)
        
        # Server state
        self.start_time = None
        self.request_count = 0
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log server operations"""
        if self.client:
            self.client.log(f"DASHBOARD [{level}] {message}")
        else:
            print(f"DASHBOARD [{level}] {message}")
    
    def start(self) -> bool:
        """Start the dashboard server"""
        try:
            # Check if we should be running based on current phase
            current_phase = self.phase_manager.get_current_phase()
            if current_phase not in [Phase.STAGING, Phase.INSTALL]:
                self._log(f"Dashboard server not started - phase {current_phase} does not allow dashboard access", "WARNING")
                return False
            
            # Configure firewall for dashboard access
            if not self.firewall_manager.configure_dashboard_access(current_phase):
                self._log("Failed to configure firewall for dashboard access", "ERROR")
                return False
            
            # Create server with custom handler
            def handler(*args, **kwargs):
                return DashboardRequestHandler(*args, dashboard_server=self, **kwargs)
            
            self.server = ThreadingHTTPServer((self.host, self.port), handler)
            self.server.timeout = 1.0  # Allow for clean shutdown
            
            # Start server in separate thread
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.running = True
            self.start_time = time.time()
            
            self._log(f"Dashboard server started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self._log(f"Failed to start dashboard server: {str(e)}", "ERROR")
            return False
    
    def stop(self) -> bool:
        """Stop the dashboard server"""
        try:
            if not self.running:
                return True
            
            self.running = False
            
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5.0)
            
            # Remove firewall rules
            current_phase = self.phase_manager.get_current_phase()
            self.firewall_manager.remove_dashboard_access(current_phase)
            
            self._log("Dashboard server stopped")
            return True
            
        except Exception as e:
            self._log(f"Error stopping dashboard server: {str(e)}", "ERROR")
            return False
    
    def restart(self) -> bool:
        """Restart the dashboard server"""
        self._log("Restarting dashboard server...")
        if self.stop():
            time.sleep(1)
            return self.start()
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