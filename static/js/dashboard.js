/**
 * SimSelector Dashboard JavaScript v2.6.0
 * Main dashboard functionality with real-time updates and API integration
 */

class SimSelectorDashboard {
    constructor() {
        this.currentPhase = 0;
        this.phaseName = 'STAGING';
        this.updateInterval = null;
        this.autoScroll = true;
        this.lastUpdateTime = null;
        this.connectionStatus = 'online';
        this.apiBaseUrl = '/api';
        
        // Initialize dashboard
        this.init();
    }
    
    /**
     * Initialize dashboard functionality
     */
    init() {
        this.setupEventListeners();
        this.startRealTimeUpdates();
        this.updateLastUpdateTime();
        
        // Show loading overlay briefly
        this.showLoading('Initializing dashboard...');
        setTimeout(() => {
            this.hideLoading();
        }, 1000);
        
        console.log('SimSelector Dashboard v2.6.0 initialized');
    }
    
    /**
     * Set up event listeners for dashboard interactions
     */
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                if (link.getAttribute('href').startsWith('/')) {
                    this.updateActiveNavLink(link);
                }
            });
        });
        
        // Refresh button handlers
        document.addEventListener('click', (e) => {
            if (e.target.matches('.refresh-btn, .refresh-btn *')) {
                e.preventDefault();
                this.refreshSimData();
            }
        });
        
        // Window focus/blur for update optimization
        window.addEventListener('focus', () => {
            this.startRealTimeUpdates();
        });
        
        window.addEventListener('blur', () => {
            // Reduce update frequency when tab is not active
            if (this.updateInterval) {
                clearInterval(this.updateInterval);
                this.updateInterval = setInterval(() => {
                    this.updateDashboardData();
                }, 30000); // Update every 30 seconds when not focused
            }
        });
        
        // Handle connection status changes
        window.addEventListener('online', () => {
            this.connectionStatus = 'online';
            this.updateConnectionStatus();
            this.addLogEntry('CONNECTION', 'Network connection restored', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.connectionStatus = 'offline';
            this.updateConnectionStatus();
            this.addLogEntry('CONNECTION', 'Network connection lost', 'error');
        });
    }
    
    /**
     * Start real-time updates
     */
    startRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // Initial update
        this.updateDashboardData();
        
        // Set up regular updates (every 5 seconds)
        this.updateInterval = setInterval(() => {
            this.updateDashboardData();
        }, 5000);
    }
    
    /**
     * Update all dashboard data
     */
    async updateDashboardData() {
        try {
            // Update system status
            await this.updateSystemStatus();
            
            // Update SIM data
            await this.updateSimData();
            
            // Update phase progress
            await this.updatePhaseProgress();
            
            // Update last update time
            this.updateLastUpdateTime();
            
        } catch (error) {
            console.error('Error updating dashboard data:', error);
            this.addLogEntry('ERROR', `Failed to update dashboard: ${error.message}`, 'error');
        }
    }
    
    /**
     * Update system status information
     */
    async updateSystemStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/system/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Update system uptime
            const uptimeElement = document.getElementById('system-uptime');
            if (uptimeElement && data.system_uptime) {
                uptimeElement.textContent = this.formatUptime(data.system_uptime);
            }
            
            // Update security status
            const securityElement = document.getElementById('security-status');
            if (securityElement && data.security_level) {
                securityElement.textContent = data.security_level;
                securityElement.className = `status-value security-${data.security_level.toLowerCase()}`;
            }
            
            // Update current phase if changed
            if (data.current_phase !== undefined && data.current_phase !== this.currentPhase) {
                this.currentPhase = data.current_phase;
                this.phaseName = data.current_phase_name || this.getPhaseNameFromNumber(data.current_phase);
                this.updatePhaseDisplay();
                this.addLogEntry('PHASE', `Phase changed to ${this.phaseName}`, 'info');
            }
            
        } catch (error) {
            console.error('Error updating system status:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    /**
     * Update SIM data and signal information
     */
    async updateSimData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/sim/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Update SIM slot information
            if (data.sims && Array.isArray(data.sims)) {
                data.sims.forEach((sim, index) => {
                    const simIndex = index + 1;
                    this.updateSimSlotDisplay(simIndex, sim);
                });
            }
            
            // Update active SIM information
            if (data.active_sim) {
                const activeSimElement = document.getElementById('active-sim');
                if (activeSimElement) {
                    activeSimElement.textContent = `SIM ${data.active_sim}`;
                }
            }
            
            // Update carrier information
            if (data.carrier) {
                const carrierElement = document.getElementById('carrier-name');
                if (carrierElement) {
                    carrierElement.textContent = data.carrier;
                }
            }
            
            // Update signal quality
            if (data.signal_quality !== undefined) {
                this.updateSignalBars(data.signal_quality);
            }
            
        } catch (error) {
            console.error('Error updating SIM data:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    /**
     * Update phase progress information
     */
    async updatePhaseProgress() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/phase/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Update progress percentage
            const progressElement = document.getElementById('phase-progress-percent');
            if (progressElement && data.progress !== undefined) {
                progressElement.textContent = `${Math.round(data.progress)}%`;
            }
            
            // Update timeline steps
            this.updateTimelineSteps(this.currentPhase);
            
            // Update phase description
            const descriptionElement = document.getElementById('phase-description');
            if (descriptionElement) {
                descriptionElement.textContent = this.getPhaseDescription(this.currentPhase);
            }
            
        } catch (error) {
            console.error('Error updating phase progress:', error);
        }
    }
    
    /**
     * Update SIM slot display
     */
    updateSimSlotDisplay(simIndex, simData) {
        const statusElement = document.getElementById(`sim${simIndex}-status`);
        const rsrpElement = document.getElementById(`sim${simIndex}-rsrp`);
        
        if (statusElement) {
            statusElement.textContent = simData.status || '--';
            statusElement.className = `sim-status-badge status-${(simData.status || '').toLowerCase()}`;
        }
        
        if (rsrpElement) {
            if (simData.rsrp !== undefined && simData.rsrp !== null) {
                rsrpElement.textContent = `${simData.rsrp} dBm`;
                rsrpElement.className = `rsrp-value rsrp-${this.getRsrpQuality(simData.rsrp)}`;
            } else {
                rsrpElement.textContent = '--';
                rsrpElement.className = 'rsrp-value';
            }
        }
    }
    
    /**
     * Update signal bars display
     */
    updateSignalBars(signalQuality) {
        const signalBars = document.getElementById('signal-bars');
        const signalText = document.getElementById('signal-text');
        
        if (signalBars) {
            const bars = signalBars.querySelectorAll('.signal-bar');
            const activeCount = Math.ceil((signalQuality / 100) * bars.length);
            
            bars.forEach((bar, index) => {
                if (index < activeCount) {
                    bar.classList.add('active');
                } else {
                    bar.classList.remove('active');
                }
            });
        }
        
        if (signalText) {
            const qualityText = this.getSignalQualityText(signalQuality);
            signalText.textContent = qualityText;
        }
    }
    
    /**
     * Update timeline steps based on current phase
     */
    updateTimelineSteps(currentPhase) {
        const steps = document.querySelectorAll('.timeline-step');
        
        steps.forEach((step, index) => {
            const stepPhase = parseInt(step.dataset.phase);
            
            step.classList.remove('completed', 'active');
            
            if (stepPhase < currentPhase) {
                step.classList.add('completed');
            } else if (stepPhase === currentPhase) {
                step.classList.add('active');
            }
        });
    }
    
    /**
     * Update phase display in header
     */
    updatePhaseDisplay() {
        // Update phase indicator
        const phaseIndicator = document.querySelector('.phase-indicator');
        if (phaseIndicator) {
            phaseIndicator.className = `phase-indicator phase-${this.currentPhase}`;
        }
        
        // Update phase name
        const phaseNameElements = document.querySelectorAll('.phase-name');
        phaseNameElements.forEach(element => {
            element.textContent = this.phaseName;
        });
        
        // Update current phase display
        const currentPhaseElement = document.getElementById('current-phase');
        if (currentPhaseElement) {
            currentPhaseElement.textContent = this.phaseName;
        }
    }
    
    /**
     * Update connection status indicator
     */
    updateConnectionStatus(status = null) {
        if (status) {
            this.connectionStatus = status;
        }
        
        const systemIndicator = document.getElementById('system-status-indicator');
        const connectionIndicator = document.getElementById('connection-indicator');
        
        const updateIndicator = (indicator) => {
            if (!indicator) return;
            
            const dot = indicator.querySelector('.status-dot, .connection-dot');
            const text = indicator.querySelector('.status-text');
            
            if (dot) {
                dot.className = this.connectionStatus === 'online' ? 
                    'status-dot online' : 'status-dot offline';
            }
            
            if (text) {
                text.textContent = this.connectionStatus === 'online' ? 'Online' : 'Offline';
            }
        };
        
        updateIndicator(systemIndicator);
        updateIndicator(connectionIndicator);
    }
    
    /**
     * Update active navigation link
     */
    updateActiveNavLink(activeLink) {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        activeLink.classList.add('active');
    }
    
    /**
     * Update last update time display
     */
    updateLastUpdateTime() {
        this.lastUpdateTime = new Date();
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `Last Updated: ${this.formatTime(this.lastUpdateTime)}`;
        }
    }
    
    /**
     * Add log entry to the dashboard
     */
    addLogEntry(level, message, type = 'info') {
        const logsContainer = document.getElementById('logs-container');
        if (!logsContainer) return;
        
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        
        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = `[${this.formatTime(new Date())}]`;
        
        const logLevel = document.createElement('span');
        logLevel.className = `log-level ${type}`;
        logLevel.textContent = level;
        
        const logMessage = document.createElement('span');
        logMessage.className = 'log-message';
        logMessage.textContent = message;
        
        logEntry.appendChild(timestamp);
        logEntry.appendChild(logLevel);
        logEntry.appendChild(logMessage);
        
        logsContainer.appendChild(logEntry);
        
        // Auto-scroll if enabled
        if (this.autoScroll) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
        
        // Limit log entries (keep last 50)
        const entries = logsContainer.querySelectorAll('.log-entry');
        if (entries.length > 50) {
            entries[0].remove();
        }
    }
    
    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const text = overlay?.querySelector('.loading-text');
        
        if (overlay) {
            overlay.classList.add('show');
        }
        
        if (text) {
            text.textContent = message;
        }
    }
    
    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('show');
        }
    }
    
    /**
     * Utility functions
     */
    
    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }
    
    formatTime(date) {
        return date.toLocaleTimeString();
    }
    
    getPhaseNameFromNumber(phaseNumber) {
        const phases = {0: 'STAGING', 1: 'INSTALL', 2: 'DEPLOYED'};
        return phases[phaseNumber] || 'UNKNOWN';
    }
    
    getPhaseDescription(phase) {
        const descriptions = {
            0: 'Staging Phase: Perform basic SIM validation and signal strength assessment.',
            1: 'Install Phase: Run full SIM testing and performance optimization.',
            2: 'Deployed Phase: Production operation with automatic SIM management.'
        };
        return descriptions[phase] || 'Unknown phase operation.';
    }
    
    getRsrpQuality(rsrp) {
        if (rsrp >= -70) return 'excellent';
        if (rsrp >= -85) return 'good';
        if (rsrp >= -100) return 'fair';
        return 'poor';
    }
    
    getSignalQualityText(quality) {
        if (quality >= 80) return 'Excellent';
        if (quality >= 60) return 'Good';
        if (quality >= 40) return 'Fair';
        if (quality >= 20) return 'Poor';
        return 'No Signal';
    }
}

/**
 * Global dashboard functions
 */

// Dashboard instance
let dashboard = null;

/**
 * Initialize dashboard with phase information
 */
function initializeDashboard(currentPhase, phaseName) {
    dashboard = new SimSelectorDashboard();
    dashboard.currentPhase = currentPhase;
    dashboard.phaseName = phaseName;
    dashboard.updatePhaseDisplay();
    
    console.log(`Dashboard initialized for ${phaseName} phase`);
}

/**
 * Refresh dashboard data
 */
function refreshDashboard() {
    if (dashboard) {
        dashboard.showLoading('Refreshing dashboard...');
        dashboard.updateDashboardData().then(() => {
            dashboard.hideLoading();
            dashboard.addLogEntry('SYSTEM', 'Dashboard refreshed manually', 'info');
        });
    }
}

/**
 * Refresh SIM data specifically
 */
function refreshSimData() {
    if (dashboard) {
        dashboard.addLogEntry('SIM', 'Refreshing SIM data...', 'info');
        dashboard.updateSimData();
    }
}

/**
 * Run system test
 */
async function runSystemTest() {
    if (!dashboard) return;
    
    dashboard.showLoading('Running system test...');
    dashboard.addLogEntry('TEST', 'Starting system test...', 'info');
    
    try {
        const response = await fetch('/api/test/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({test_type: 'full'})
        });
        
        const result = await response.json();
        
        if (response.ok) {
            dashboard.addLogEntry('TEST', 'System test completed successfully', 'success');
        } else {
            dashboard.addLogEntry('TEST', `System test failed: ${result.error}`, 'error');
        }
        
    } catch (error) {
        dashboard.addLogEntry('TEST', `System test error: ${error.message}`, 'error');
    } finally {
        dashboard.hideLoading();
    }
}

/**
 * Clear log entries
 */
function clearLogs() {
    const logsContainer = document.getElementById('logs-container');
    if (logsContainer) {
        logsContainer.innerHTML = '';
        if (dashboard) {
            dashboard.addLogEntry('SYSTEM', 'Log entries cleared', 'info');
        }
    }
}

/**
 * Toggle auto-scroll for logs
 */
function toggleAutoScroll() {
    if (dashboard) {
        dashboard.autoScroll = !dashboard.autoScroll;
        const button = document.getElementById('autoscroll-btn');
        if (button) {
            button.textContent = `Auto-scroll: ${dashboard.autoScroll ? 'ON' : 'OFF'}`;
        }
        dashboard.addLogEntry('SYSTEM', `Auto-scroll ${dashboard.autoScroll ? 'enabled' : 'disabled'}`, 'info');
    }
} 