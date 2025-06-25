/**
 * SimSelector Help System v2.6.0
 * Interactive help documentation with search, phase-specific content, and troubleshooting guides
 */

class HelpSystem {
    constructor() {
        this.currentPhase = 0;
        this.phaseName = 'STAGING';
        this.searchIndex = [];
        this.expandedSections = new Set(['phase-guide']); // Default expanded sections
        
        this.phaseContent = {
            0: { // STAGING
                name: 'STAGING',
                description: 'Initial setup and SIM validation phase. Dashboard is fully accessible for configuration and monitoring.',
                objectives: 'Validate SIM cards, check network connectivity, and prepare for installation testing.',
                duration: 'Typically 15-30 minutes depending on network conditions.',
                nextSteps: 'Once SIM validation is complete, the system will automatically progress to Install phase.',
                steps: [
                    'Insert both SIM cards into designated slots',
                    'Verify SIM card detection and carrier identification',
                    'Check initial signal strength for both carriers',
                    'Validate network connectivity and registration',
                    'Monitor dashboard for any errors or warnings'
                ]
            },
            1: { // INSTALL
                name: 'INSTALL',
                description: 'Comprehensive testing and validation phase. Full dashboard access for monitoring installation progress.',
                objectives: 'Perform speed tests, validate failover mechanisms, and ensure optimal performance.',
                duration: 'Typically 30-60 minutes for complete testing cycle.',
                nextSteps: 'After successful testing, system will transition to Deployed phase and disable dashboard.',
                steps: [
                    'Execute speed tests on both SIM connections',
                    'Validate automatic failover between carriers',
                    'Monitor RSRP values and signal quality',
                    'Test connectivity under various load conditions',
                    'Verify all performance metrics meet requirements'
                ]
            },
            2: { // DEPLOYED
                name: 'DEPLOYED',
                description: 'Production mode with dashboard disabled for security. System is fully operational.',
                objectives: 'Maintain optimal performance and handle failover automatically.',
                duration: 'Indefinite - system remains in this phase during normal operation.',
                nextSteps: 'Use NCM for remote monitoring and management. Dashboard is disabled for security.',
                steps: [
                    'System operates automatically in production mode',
                    'Failover happens transparently based on performance',
                    'Monitor via NCM dashboard for remote management',
                    'Contact support if intervention is needed',
                    'Dashboard access is disabled for security reasons'
                ]
            }
        };
        
        this.troubleshootingGuides = {
            'no-dashboard-access': {
                title: 'Dashboard Not Accessible',
                keywords: ['dashboard', 'access', 'login', 'connection', 'browser'],
                severity: 'high',
                phase: 'all',
                steps: [
                    'Check if device is in Staging or Install phase (dashboard disabled in Deployed)',
                    'Verify network connection to device LAN interface',
                    'Ensure browser is accessing correct IP address',
                    'Check firewall settings and port accessibility',
                    'Try different browser or clear cache/cookies',
                    'Restart dashboard service if problem persists'
                ]
            },
            'poor-signal': {
                title: 'Poor Signal Quality',
                keywords: ['signal', 'rsrp', 'strength', 'antenna', 'coverage'],
                severity: 'medium',
                phase: 'all',
                steps: [
                    'Check antenna connections and cable integrity',
                    'Verify antenna positioning and orientation',
                    'Check RSRP values in dashboard (should be > -100 dBm)',
                    'Consider external antenna for better reception',
                    'Verify carrier coverage in installation area',
                    'Check for interference from nearby devices'
                ]
            },
            'sim-detection': {
                title: 'SIM Card Detection Issues',
                keywords: ['sim', 'detection', 'card', 'slot', 'carrier'],
                severity: 'high',
                phase: 'staging',
                steps: [
                    'Power down device completely',
                    'Remove SIM cards and inspect for damage',
                    'Clean SIM card contacts with soft cloth',
                    'Reinsert SIM cards ensuring proper seating',
                    'Power up device and check dashboard status',
                    'Verify SIM cards are activated with carriers'
                ]
            },
            'speed-test-failure': {
                title: 'Speed Test Failures',
                keywords: ['speed', 'test', 'bandwidth', 'throughput', 'performance'],
                severity: 'medium',
                phase: 'install',
                steps: [
                    'Check signal strength for both SIM cards',
                    'Verify carrier data plans are active and not throttled',
                    'Ensure no data caps or restrictions are in effect',
                    'Check for network congestion during test times',
                    'Restart speed test from dashboard',
                    'Contact carrier if persistent issues occur'
                ]
            },
            'failover-issues': {
                title: 'Failover Not Working',
                keywords: ['failover', 'switching', 'backup', 'redundancy', 'automatic'],
                severity: 'high',
                phase: 'install',
                steps: [
                    'Verify both SIM cards have active data connections',
                    'Check failover thresholds and timing in configuration',
                    'Monitor dashboard during manual failover test',
                    'Ensure primary connection degradation is detected',
                    'Check for stuck connections or routing issues',
                    'Review failover logs and error messages'
                ]
            },
            'rate-limit-blocked': {
                title: 'Rate Limit or Access Blocked',
                keywords: ['blocked', 'rate', 'limit', 'too many requests', '429'],
                severity: 'low',
                phase: 'all',
                steps: [
                    'Wait 5 minutes for automatic unblocking',
                    'Avoid rapid refresh or multiple concurrent requests',
                    'Check for scripts or automation causing high request rates',
                    'Use single browser session for dashboard access',
                    'Contact support if blocking persists',
                    'Review rate limiting documentation'
                ]
            }
        };
        
        this.apiEndpoints = {
            '/api/system/status': {
                method: 'GET',
                description: 'Get comprehensive system status',
                parameters: 'None',
                response: 'JSON object with system information'
            },
            '/api/sim/status': {
                method: 'GET',
                description: 'Get SIM card status and signal information',
                parameters: 'None',
                response: 'JSON object with SIM details'
            },
            '/api/phase/status': {
                method: 'GET',
                description: 'Get current phase and transition status',
                parameters: 'None',
                response: 'JSON object with phase information'
            },
            '/api/phase/transition': {
                method: 'POST',
                description: 'Request phase transition',
                parameters: 'JSON: {"target_phase": number, "force": boolean}',
                response: 'JSON object with transition result'
            },
            '/api/test/start': {
                method: 'POST',
                description: 'Start system testing',
                parameters: 'JSON: {"test_type": string, "duration": number}',
                response: 'JSON object with test initiation result'
            }
        };
    }
    
    initialize(phase, phaseName) {
        this.currentPhase = phase;
        this.phaseName = phaseName;
        
        this.buildSearchIndex();
        this.updatePhaseContent();
        this.setupEventListeners();
        this.restoreExpandedSections();
        
        console.log(`Help system initialized for ${phaseName} phase`);
    }
    
    buildSearchIndex() {
        this.searchIndex = [];
        
        // Index phase content
        const phaseData = this.phaseContent[this.currentPhase];
        if (phaseData) {
            this.searchIndex.push({
                section: 'phase-guide',
                title: `${phaseData.name} Phase Guide`,
                content: `${phaseData.description} ${phaseData.objectives} ${phaseData.steps.join(' ')}`,
                keywords: [phaseData.name.toLowerCase(), 'phase', 'guide', 'objectives', 'steps']
            });
        }
        
        // Index troubleshooting guides
        Object.entries(this.troubleshootingGuides).forEach(([key, guide]) => {
            if (guide.phase === 'all' || guide.phase === this.phaseName.toLowerCase()) {
                this.searchIndex.push({
                    section: 'troubleshooting',
                    title: guide.title,
                    content: guide.steps.join(' '),
                    keywords: guide.keywords
                });
            }
        });
        
        // Index API documentation
        Object.entries(this.apiEndpoints).forEach(([endpoint, data]) => {
            this.searchIndex.push({
                section: 'api-docs',
                title: `${data.method} ${endpoint}`,
                content: data.description,
                keywords: ['api', 'endpoint', endpoint.split('/').pop(), data.method.toLowerCase()]
            });
        });
        
        // Index general content
        this.searchIndex.push({
            section: 'quick-start',
            title: 'Quick Start Guide',
            content: 'first time setup dashboard access sim cards network connectivity',
            keywords: ['quick', 'start', 'setup', 'first', 'time', 'beginner']
        });
        
        this.searchIndex.push({
            section: 'security',
            title: 'Security Information',
            content: 'dashboard security access control ip whitelist rate limiting ssl tls encryption',
            keywords: ['security', 'access', 'control', 'whitelist', 'rate', 'limit', 'ssl', 'encryption']
        });
    }
    
    updatePhaseContent() {
        const phaseData = this.phaseContent[this.currentPhase];
        if (!phaseData) return;
        
        // Update phase-specific content
        const elements = {
            'phase-description': phaseData.description,
            'phase-objectives': phaseData.objectives,
            'phase-duration': phaseData.duration,
            'phase-next-steps': phaseData.nextSteps
        };
        
        Object.entries(elements).forEach(([id, content]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = content;
            }
        });
        
        // Update phase steps
        const stepsContainer = document.getElementById('phase-steps');
        if (stepsContainer && phaseData.steps) {
            stepsContainer.innerHTML = '';
            phaseData.steps.forEach(step => {
                const li = document.createElement('li');
                li.textContent = step;
                stepsContainer.appendChild(li);
            });
        }
    }
    
    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('help-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.performSearch(e.target.value);
            });
            
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this.clearSearch();
                }
            });
        }
        
        // Section toggle tracking
        document.querySelectorAll('.section-header').forEach(header => {
            header.addEventListener('click', () => {
                const section = header.closest('.help-section');
                const sectionId = section.getAttribute('data-section');
                
                if (this.expandedSections.has(sectionId)) {
                    this.expandedSections.delete(sectionId);
                } else {
                    this.expandedSections.add(sectionId);
                }
                
                this.saveExpandedSections();
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'f':
                        e.preventDefault();
                        this.focusSearch();
                        break;
                    case 'k':
                        e.preventDefault();
                        this.focusSearch();
                        break;
                }
            }
        });
    }
    
    performSearch(query) {
        const searchTerm = query.toLowerCase().trim();
        const sections = document.querySelectorAll('.help-section');
        const noResults = document.getElementById('no-results');
        
        if (!searchTerm) {
            // Show all sections
            sections.forEach(section => {
                section.classList.remove('hidden');
                this.clearHighlights(section);
            });
            noResults.style.display = 'none';
            return;
        }
        
        let hasResults = false;
        
        sections.forEach(section => {
            const sectionId = section.getAttribute('data-section');
            const matches = this.searchIndex.filter(item => 
                item.section === sectionId && this.matchesSearch(item, searchTerm)
            );
            
            if (matches.length > 0) {
                section.classList.remove('hidden');
                this.highlightMatches(section, searchTerm);
                
                // Auto-expand matching sections
                const content = section.querySelector('.section-content');
                if (content && !content.classList.contains('expanded')) {
                    this.toggleSection(section.querySelector('.section-header'));
                }
                
                hasResults = true;
            } else {
                section.classList.add('hidden');
                this.clearHighlights(section);
            }
        });
        
        noResults.style.display = hasResults ? 'none' : 'block';
    }
    
    matchesSearch(item, searchTerm) {
        // Check title
        if (item.title.toLowerCase().includes(searchTerm)) return true;
        
        // Check content
        if (item.content.toLowerCase().includes(searchTerm)) return true;
        
        // Check keywords
        return item.keywords.some(keyword => 
            keyword.toLowerCase().includes(searchTerm) || 
            searchTerm.includes(keyword.toLowerCase())
        );
    }
    
    highlightMatches(section, searchTerm) {
        this.clearHighlights(section);
        
        const walker = document.createTreeWalker(
            section,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        const textNodes = [];
        let node;
        
        while (node = walker.nextNode()) {
            if (node.parentNode.tagName !== 'SCRIPT' && node.parentNode.tagName !== 'STYLE') {
                textNodes.push(node);
            }
        }
        
        textNodes.forEach(textNode => {
            const text = textNode.textContent;
            const regex = new RegExp(`(${searchTerm})`, 'gi');
            
            if (regex.test(text)) {
                const highlightedText = text.replace(regex, '<span class="highlight">$1</span>');
                const span = document.createElement('span');
                span.innerHTML = highlightedText;
                textNode.parentNode.replaceChild(span, textNode);
            }
        });
    }
    
    clearHighlights(section) {
        const highlights = section.querySelectorAll('.highlight');
        highlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize();
        });
    }
    
    clearSearch() {
        const searchInput = document.getElementById('help-search');
        if (searchInput) {
            searchInput.value = '';
            this.performSearch('');
        }
    }
    
    focusSearch() {
        const searchInput = document.getElementById('help-search');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }
    
    toggleSection(header) {
        const section = header.closest('.help-section');
        const content = section.querySelector('.section-content');
        const toggle = header.querySelector('.section-toggle');
        
        if (content.classList.contains('expanded')) {
            content.classList.remove('expanded');
            toggle.textContent = '▼';
        } else {
            content.classList.add('expanded');
            toggle.textContent = '▲';
        }
    }
    
    saveExpandedSections() {
        try {
            localStorage.setItem('helpExpandedSections', JSON.stringify([...this.expandedSections]));
        } catch (e) {
            console.warn('Could not save expanded sections to localStorage');
        }
    }
    
    restoreExpandedSections() {
        try {
            const saved = localStorage.getItem('helpExpandedSections');
            if (saved) {
                this.expandedSections = new Set(JSON.parse(saved));
            }
        } catch (e) {
            console.warn('Could not restore expanded sections from localStorage');
        }
        
        // Apply expanded state to sections
        document.querySelectorAll('.help-section').forEach(section => {
            const sectionId = section.getAttribute('data-section');
            const content = section.querySelector('.section-content');
            const toggle = section.querySelector('.section-toggle');
            
            if (this.expandedSections.has(sectionId)) {
                content.classList.add('expanded');
                toggle.textContent = '▲';
            } else {
                content.classList.remove('expanded');
                toggle.textContent = '▼';
            }
        });
    }
    
    getContextHelp(topic) {
        const guides = Object.entries(this.troubleshootingGuides)
            .filter(([key, guide]) => {
                return guide.keywords.some(keyword => 
                    topic.toLowerCase().includes(keyword.toLowerCase())
                );
            })
            .map(([key, guide]) => guide);
        
        return guides.length > 0 ? guides[0] : null;
    }
    
    getPhaseSpecificHelp() {
        return this.phaseContent[this.currentPhase];
    }
    
    exportHelpData() {
        return {
            phase: this.currentPhase,
            phaseName: this.phaseName,
            phaseContent: this.phaseContent[this.currentPhase],
            troubleshooting: Object.entries(this.troubleshootingGuides)
                .filter(([key, guide]) => guide.phase === 'all' || guide.phase === this.phaseName.toLowerCase())
                .reduce((acc, [key, guide]) => {
                    acc[key] = guide;
                    return acc;
                }, {}),
            apiEndpoints: this.apiEndpoints
        };
    }
}

// Global help system instance
let helpSystem = null;

// Global functions for template integration
function initializeHelp(phase, phaseName) {
    helpSystem = new HelpSystem();
    helpSystem.initialize(phase, phaseName);
}

function toggleSection(header) {
    if (helpSystem) {
        helpSystem.toggleSection(header);
    }
}

function clearSearch() {
    if (helpSystem) {
        helpSystem.clearSearch();
    }
}

function focusSearch() {
    if (helpSystem) {
        helpSystem.focusSearch();
    }
}

function getContextHelp(topic) {
    return helpSystem ? helpSystem.getContextHelp(topic) : null;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { HelpSystem, initializeHelp, toggleSection, clearSearch, focusSearch, getContextHelp };
} 