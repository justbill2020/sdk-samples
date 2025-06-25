// SimSelector Dashboard JavaScript - Main Dashboard Logic

class SimSelectorDashboard {
    constructor() {
        this.apiBase = '/api/v1';
        this.refreshInterval = 5000; // 5 seconds
        this.refreshTimer = null;
        this.autoScroll = true;
        this.lastUpdate = null;
        
        // Initialize dashboard when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    /**
     * Initialize the dashboard
     */
    async init() {
        try {
            this.showLoading(true);
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Initial data load
            await this.loadInitialData();
            
            // Start refresh timer
            this.startRefreshTimer();
            
            // Hide loading overlay
            this.showLoading(false);
            
            this.log('Dashboard initialized successfully', 'success');
            
        } catch (error) {
            console.error('Dashboard initialization failed:', error);
            this.showNotification('Failed to initialize dashboard', 'error');
            this.showLoading(false);
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Window events
        window.addEventListener('beforeunload', () => this.cleanup());
        window.addEventListener('focus', () => this.handleWindowFocus());
        window.addEventListener('blur', () => this.handleWindowBlur());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.startRefreshTimer();
                } else {
                    this.stopRefreshTimer();
                }
            });
        }
    }
    
    /**
     * Load initial dashboard data
     */
    async loadInitialData() {
        const promises = [
            this.updatePhaseStatus(),
            this.updateSimStatus(),
            this.updateSignalStatus(),
            this.updateSecurityStatus(),
            this.updateSystemInfo()
        ];
        
        await Promise.allSettled(promises);
        this.updateLastRefresh();
    }
    
    /**
     * Update phase status
     */
    async updatePhaseStatus() {
        try {
            const response = await this.apiCall('/phase');
            const data = response.data;
            
            // Update phase display
            const phaseNumber = document.getElementById('phase-number');
            const phaseName = document.getElementById('phase-name');
            const phaseDescription = document.getElementById('phase-description');
            const phaseProgress = document.getElementById('phase-progress');
            const progressText = document.getElementById('progress-text');
            
            if (phaseNumber) phaseNumber.textContent = data.current_phase;
            if (phaseName) phaseName.textContent = data.phase_name;
            if (phaseDescription) phaseDescription.textContent = data.description || 'Loading...';
            
            // Update progress bar
            const progressPercent = this.calculatePhaseProgress(data);
            if (phaseProgress) {
                phaseProgress.style.width = `${progressPercent}%`;
            }
            if (progressText) {
                progressText.textContent = `${progressPercent}% Complete`;
            }
            
            // Update phase indicator colors
            this.updatePhaseIndicators(data.current_phase);
            
            // Update available actions based on phase
            this.updatePhaseActions(data);
            
        } catch (error) {
            console.error('Failed to update phase status:', error);
            this.log('Failed to update phase status', 'error');
        }
    }
    
    /**
     * Update SIM status
     */
    async updateSimStatus() {
        try {
            const response = await this.apiCall('/sims');
            const sims = response.data.sims || [];
            
            const simList = document.getElementById('sim-status');
            const simSummary = document.getElementById('sim-summary');
            const simStatusIndicator = document.getElementById('sim-status-indicator');
            
            if (simList) {
                if (sims.length === 0) {
                    simList.innerHTML = '<div class="loading-spinner">No SIMs detected</div>';
                } else {
                    simList.innerHTML = sims.map(sim => this.renderSimItem(sim)).join('');
                }
            }
            
            if (simSummary) {
                const activeCount = sims.filter(sim => sim.status === 'active').length;
                simSummary.innerHTML = `
                    <span class="sim-count">${sims.length} SIMs detected</span>
                    <span class="sim-active">${activeCount} active</span>
                `;
            }
            
            // Update status indicator
            if (simStatusIndicator) {
                const hasActiveSim = sims.some(sim => sim.status === 'active');
                simStatusIndicator.className = `card-status ${hasActiveSim ? 'status-1' : 'status-0'}`;
            }
            
        } catch (error) {
            console.error('Failed to update SIM status:', error);
            this.log('Failed to update SIM status', 'error');
        }
    }
    
    /**
     * Update signal status
     */
    async updateSignalStatus() {
        try {
            const response = await this.apiCall('/signal');
            const signal = response.data;
            
            const signalDisplay = document.getElementById('signal-status');
            const signalStatusIndicator = document.getElementById('signal-status-indicator');
            
            if (signalDisplay) {
                signalDisplay.innerHTML = this.renderSignalInfo(signal);
            }
            
            // Update status indicator based on signal strength
            if (signalStatusIndicator) {
                const signalClass = this.getSignalStatusClass(signal.strength);
                signalStatusIndicator.className = `card-status ${signalClass}`;
            }
            
        } catch (error) {
            console.error('Failed to update signal status:', error);
            this.log('Failed to update signal status', 'error');
        }
    }
    
    /**
     * Update security status
     */
    async updateSecurityStatus() {
        try {
            const response = await this.apiCall('/security');
            const security = response.data;
            
            const securityInfo = document.getElementById('security-status');
            const securityStatusIndicator = document.getElementById('security-status-indicator');
            
            if (securityInfo) {
                securityInfo.innerHTML = this.renderSecurityInfo(security);
            }
            
            // Update status indicator
            if (securityStatusIndicator) {
                const isSecure = security.level === 'HIGH' && security.status === 'active';
                securityStatusIndicator.className = `card-status ${isSecure ? 'status-1' : 'status-0'}`;
            }
            
        } catch (error) {
            console.error('Failed to update security status:', error);
            this.log('Failed to update security status', 'error');
        }
    }
    
    /**
     * Update system information
     */
    async updateSystemInfo() {
        try {
            const response = await this.apiCall('/status');
            const status = response.data;
            
            // Update system uptime
            const systemUptime = document.getElementById('system-uptime');
            if (systemUptime && status.uptime) {
                systemUptime.textContent = this.formatDuration(status.uptime);
            }
            
            // Update phase duration
            const phaseDuration = document.getElementById('phase-duration');
            if (phaseDuration && status.phase_duration) {
                phaseDuration.textContent = this.formatDuration(status.phase_duration);
            }
            
        } catch (error) {
            console.error('Failed to update system info:', error);
            this.log('Failed to update system info', 'error');
        }
    }
    
    /**
     * Make API call with error handling
     */
    async apiCall(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            ...options
        };
        
        const response = await fetch(url, defaultOptions);
        
        if (!response.ok) {
            throw new Error(`API call failed: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    /**
     * Render SIM item HTML
     */
    renderSimItem(sim) {
        const statusClass = sim.status === 'active' ? 'success' : 'warning';
        const signalBars = this.getSignalBars(sim.signal_strength);
        
        return `
            <div class="sim-item">
                <div class="sim-info">
                    <div class="sim-name">${sim.name || `SIM ${sim.slot}`}</div>
                    <div class="sim-carrier">${sim.carrier || 'Unknown'}</div>
                </div>
                <div class="sim-status">
                    <span class="status-badge ${statusClass}">${sim.status}</span>
                    <span class="signal-bars">${signalBars}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Render signal information
     */
    renderSignalInfo(signal) {
        return `
            <div class="signal-item">
                <div class="signal-info">
                    <div class="signal-strength">Signal: ${signal.strength || 0}%</div>
                    <div class="signal-type">${signal.type || 'Unknown'}</div>
                </div>
                <div class="signal-bars">${this.getSignalBars(signal.strength)}</div>
            </div>
            <div class="signal-details">
                <div class="signal-detail">
                    <span class="label">RSSI:</span>
                    <span class="value">${signal.rssi || 'N/A'} dBm</span>
                </div>
                <div class="signal-detail">
                    <span class="label">SINR:</span>
                    <span class="value">${signal.sinr || 'N/A'} dB</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Render security information
     */
    renderSecurityInfo(security) {
        const levelClass = security.level === 'HIGH' ? 'success' : 'warning';
        
        return `
            <div class="security-item">
                <div class="security-info">
                    <div class="security-level">Level: ${security.level || 'Unknown'}</div>
                    <div class="security-status">Status: ${security.status || 'Unknown'}</div>
                </div>
                <span class="status-badge ${levelClass}">${security.level}</span>
            </div>
            <div class="security-details">
                <div class="security-detail">
                    <span class="label">Firewall:</span>
                    <span class="value">${security.firewall ? 'Active' : 'Inactive'}</span>
                </div>
                <div class="security-detail">
                    <span class="label">Access Control:</span>
                    <span class="value">${security.access_control ? 'Enabled' : 'Disabled'}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Get signal bars representation
     */
    getSignalBars(strength) {
        const bars = Math.ceil((strength || 0) / 25);
        return '█'.repeat(Math.max(0, Math.min(4, bars))) + '░'.repeat(4 - Math.max(0, Math.min(4, bars)));
    }
    
    /**
     * Get signal status class
     */
    getSignalStatusClass(strength) {
        if (strength >= 75) return 'status-1';
        if (strength >= 50) return 'status-0';
        return 'status-2';
    }
    
    /**
     * Calculate phase progress percentage
     */
    calculatePhaseProgress(phaseData) {
        // Simple progress calculation based on phase and duration
        const baseProgress = phaseData.current_phase * 33.33;
        const timeProgress = Math.min(10, (phaseData.duration || 0) / 60); // Max 10% for time
        return Math.min(100, Math.round(baseProgress + timeProgress));
    }
    
    /**
     * Update phase indicators
     */
    updatePhaseIndicators(currentPhase) {
        const indicators = document.querySelectorAll('.phase-indicator, .card-status');
        indicators.forEach(indicator => {
            indicator.className = indicator.className.replace(/phase-\d+|status-\d+/g, '');
            indicator.classList.add(`phase-${currentPhase}`, `status-${currentPhase}`);
        });
    }
    
    /**
     * Update phase-specific actions
     */
    updatePhaseActions(phaseData) {
        const actionButtons = document.getElementById('action-buttons');
        if (!actionButtons) return;
        
        // Clear existing buttons except refresh
        const existingButtons = actionButtons.querySelectorAll('.btn:not([onclick*="refreshStatus"])');
        existingButtons.forEach(btn => btn.remove());
        
        // Add phase-specific buttons
        const phaseActions = this.getPhaseActions(phaseData.current_phase);
        phaseActions.forEach(action => {
            const button = document.createElement('button');
            button.className = `btn ${action.class}`;
            button.innerHTML = `<i class="${action.icon}"></i> ${action.label}`;
            button.onclick = () => this.executeAction(action.action);
            if (action.disabled) button.disabled = true;
            actionButtons.appendChild(button);
        });
    }
    
    /**
     * Get available actions for current phase
     */
    getPhaseActions(phase) {
        const actions = {
            0: [ // STAGING
                { label: 'Run Tests', action: 'run_tests', class: 'btn-primary', icon: 'icon-play' },
                { label: 'Advance Phase', action: 'advance_phase', class: 'btn-success', icon: 'icon-forward' }
            ],
            1: [ // INSTALL
                { label: 'Install SIMs', action: 'install_sims', class: 'btn-primary', icon: 'icon-download' },
                { label: 'Configure Network', action: 'configure_network', class: 'btn-secondary', icon: 'icon-settings' },
                { label: 'Deploy', action: 'deploy', class: 'btn-success', icon: 'icon-upload' }
            ],
            2: [ // DEPLOYED
                { label: 'View Logs', action: 'view_logs', class: 'btn-secondary', icon: 'icon-list' },
                { label: 'Maintenance Mode', action: 'maintenance_mode', class: 'btn-warning', icon: 'icon-wrench' }
            ]
        };
        
        return actions[phase] || [];
    }
    
    /**
     * Execute dashboard action
     */
    async executeAction(action) {
        try {
            this.log(`Executing action: ${action}`, 'info');
            
            switch (action) {
                case 'run_tests':
                    await this.runTests();
                    break;
                case 'advance_phase':
                    await this.advancePhase();
                    break;
                case 'install_sims':
                    await this.installSims();
                    break;
                case 'configure_network':
                    await this.configureNetwork();
                    break;
                case 'deploy':
                    await this.deploy();
                    break;
                case 'view_logs':
                    this.viewLogs();
                    break;
                case 'maintenance_mode':
                    await this.enterMaintenanceMode();
                    break;
                default:
                    this.log(`Unknown action: ${action}`, 'warning');
            }
        } catch (error) {
            console.error(`Action ${action} failed:`, error);
            this.showNotification(`Action failed: ${error.message}`, 'error');
        }
    }
    
    /**
     * Refresh dashboard status
     */
    async refreshStatus() {
        try {
            this.log('Refreshing dashboard status...', 'info');
            await this.loadInitialData();
            this.showNotification('Dashboard refreshed', 'success');
        } catch (error) {
            console.error('Refresh failed:', error);
            this.showNotification('Refresh failed', 'error');
        }
    }
    
    /**
     * Clear logs
     */
    clearLogs() {
        const logContent = document.getElementById('log-content');
        if (logContent) {
            logContent.innerHTML = '<div class="log-entry"><span class="log-time">[' + 
                new Date().toLocaleTimeString() + ']</span><span class="log-level info">INFO</span>' +
                '<span class="log-message">Logs cleared</span></div>';
        }
    }
    
    /**
     * Toggle auto-scroll for logs
     */
    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        const btn = event.target;
        btn.textContent = this.autoScroll ? 'Auto-scroll' : 'Manual scroll';
        btn.className = this.autoScroll ? 'btn btn-small btn-success' : 'btn btn-small btn-secondary';
    }
    
    /**
     * Add log entry
     */
    log(message, level = 'info') {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="log-time">[${timestamp}]</span>
            <span class="log-level ${level}">${level.toUpperCase()}</span>
            <span class="log-message">${message}</span>
        `;
        
        logContent.appendChild(logEntry);
        
        // Auto-scroll if enabled
        if (this.autoScroll) {
            logContent.scrollTop = logContent.scrollHeight;
        }
        
        // Limit log entries to prevent memory issues
        const entries = logContent.querySelectorAll('.log-entry');
        if (entries.length > 100) {
            entries[0].remove();
        }
    }
    
    /**
     * Show/hide loading overlay
     */
    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.toggle('active', show);
        }
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Use the notifications.js system
        if (window.notifications) {
            window.notifications.show(message, type);
        } else {
            // Fallback to console
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }
    
    /**
     * Format duration in seconds to readable format
     */
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    /**
     * Update last refresh timestamp
     */
    updateLastRefresh() {
        this.lastUpdate = new Date();
        const elements = document.querySelectorAll('#last-updated, #footer-last-updated');
        const timeString = this.lastUpdate.toLocaleTimeString();
        elements.forEach(el => {
            if (el) el.textContent = timeString;
        });
    }
    
    /**
     * Start refresh timer
     */
    startRefreshTimer() {
        this.stopRefreshTimer();
        this.refreshTimer = setInterval(() => {
            this.loadInitialData();
        }, this.refreshInterval);
    }
    
    /**
     * Stop refresh timer
     */
    stopRefreshTimer() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    
    /**
     * Handle window focus
     */
    handleWindowFocus() {
        // Resume refresh when window gains focus
        if (!this.refreshTimer) {
            this.startRefreshTimer();
        }
        // Immediate refresh
        this.loadInitialData();
    }
    
    /**
     * Handle window blur
     */
    handleWindowBlur() {
        // Optionally pause refresh when window loses focus
        // this.stopRefreshTimer();
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeydown(event) {
        // Ctrl/Cmd + R: Refresh
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            this.refreshStatus();
        }
        
        // Escape: Clear notifications
        if (event.key === 'Escape') {
            if (window.notifications) {
                window.notifications.clearAll();
            }
        }
    }
    
    /**
     * Cleanup on page unload
     */
    cleanup() {
        this.stopRefreshTimer();
    }
    
    // Action implementations (placeholder methods)
    async runTests() {
        this.showNotification('Running tests...', 'info');
        // Implementation would call API to run tests
    }
    
    async advancePhase() {
        this.showNotification('Advancing to next phase...', 'info');
        // Implementation would call API to advance phase
    }
    
    async installSims() {
        this.showNotification('Installing SIMs...', 'info');
        // Implementation would call API to install SIMs
    }
    
    async configureNetwork() {
        this.showNotification('Configuring network...', 'info');
        // Implementation would call API to configure network
    }
    
    async deploy() {
        this.showNotification('Deploying system...', 'info');
        // Implementation would call API to deploy
    }
    
    viewLogs() {
        // Scroll to log panel
        const logPanel = document.querySelector('.log-panel');
        if (logPanel) {
            logPanel.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    async enterMaintenanceMode() {
        this.showNotification('Entering maintenance mode...', 'warning');
        // Implementation would call API to enter maintenance mode
    }
}

// Global dashboard instance
window.dashboard = new SimSelectorDashboard(); 