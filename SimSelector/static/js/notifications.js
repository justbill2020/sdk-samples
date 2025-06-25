// SimSelector Dashboard - Notification System

class NotificationSystem {
    constructor() {
        this.container = null;
        this.notifications = new Map();
        this.maxNotifications = 5;
        this.defaultDuration = 5000; // 5 seconds
        this.init();
    }
    
    /**
     * Initialize the notification system
     */
    init() {
        this.container = document.getElementById('notification-container');
        if (!this.container) {
            console.warn('Notification container not found');
            return;
        }
        
        // Set up container styles if needed
        this.container.style.position = 'fixed';
        this.container.style.top = '20px';
        this.container.style.right = '20px';
        this.container.style.zIndex = '10000';
        this.container.style.maxWidth = '400px';
    }
    
    /**
     * Show a notification
     * @param {string} message - The notification message
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in milliseconds (0 for persistent)
     * @param {Object} options - Additional options
     */
    show(message, type = 'info', duration = null, options = {}) {
        if (!this.container) {
            console.log(`${type.toUpperCase()}: ${message}`);
            return null;
        }
        
        // Generate unique ID
        const id = this.generateId();
        
        // Create notification element
        const notification = this.createNotification(id, message, type, options);
        
        // Add to container
        this.container.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Store reference
        this.notifications.set(id, {
            element: notification,
            type: type,
            message: message,
            timestamp: Date.now()
        });
        
        // Auto-dismiss if duration is set
        const dismissDuration = duration !== null ? duration : this.defaultDuration;
        if (dismissDuration > 0) {
            setTimeout(() => {
                this.dismiss(id);
            }, dismissDuration);
        }
        
        // Limit number of notifications
        this.enforceLimit();
        
        return id;
    }
    
    /**
     * Create notification element
     */
    createNotification(id, message, type, options) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.setAttribute('data-id', id);
        
        // Icon based on type
        const icon = this.getIcon(type);
        
        // Title (optional)
        const title = options.title || this.getDefaultTitle(type);
        
        notification.innerHTML = `
            <div class="notification-icon">${icon}</div>
            <div class="notification-content">
                ${title ? `<div class="notification-title">${title}</div>` : ''}
                <div class="notification-message">${message}</div>
            </div>
            <button class="notification-close" onclick="notifications.dismiss('${id}')" aria-label="Close notification">
                ×
            </button>
        `;
        
        // Add click handler for the entire notification if specified
        if (options.onClick) {
            notification.style.cursor = 'pointer';
            notification.addEventListener('click', (e) => {
                if (!e.target.classList.contains('notification-close')) {
                    options.onClick();
                    this.dismiss(id);
                }
            });
        }
        
        return notification;
    }
    
    /**
     * Get icon for notification type
     */
    getIcon(type) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        return icons[type] || icons.info;
    }
    
    /**
     * Get default title for notification type
     */
    getDefaultTitle(type) {
        const titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Information'
        };
        return titles[type] || '';
    }
    
    /**
     * Dismiss a notification
     */
    dismiss(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const element = notification.element;
        
        // Animate out
        element.classList.remove('show');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.notifications.delete(id);
        }, 300);
    }
    
    /**
     * Dismiss all notifications
     */
    dismissAll() {
        const ids = Array.from(this.notifications.keys());
        ids.forEach(id => this.dismiss(id));
    }
    
    /**
     * Clear all notifications immediately
     */
    clearAll() {
        this.notifications.forEach((notification, id) => {
            const element = notification.element;
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
        });
        this.notifications.clear();
    }
    
    /**
     * Show success notification
     */
    success(message, duration = null, options = {}) {
        return this.show(message, 'success', duration, options);
    }
    
    /**
     * Show error notification
     */
    error(message, duration = 0, options = {}) {
        return this.show(message, 'error', duration, options);
    }
    
    /**
     * Show warning notification
     */
    warning(message, duration = null, options = {}) {
        return this.show(message, 'warning', duration, options);
    }
    
    /**
     * Show info notification
     */
    info(message, duration = null, options = {}) {
        return this.show(message, 'info', duration, options);
    }
    
    /**
     * Show loading notification
     */
    loading(message, options = {}) {
        const loadingOptions = {
            ...options,
            title: 'Loading...'
        };
        return this.show(message, 'info', 0, loadingOptions);
    }
    
    /**
     * Update an existing notification
     */
    update(id, message, type = null) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const element = notification.element;
        const messageEl = element.querySelector('.notification-message');
        
        if (messageEl) {
            messageEl.textContent = message;
        }
        
        if (type && type !== notification.type) {
            element.className = `notification ${type} show`;
            const iconEl = element.querySelector('.notification-icon');
            if (iconEl) {
                iconEl.textContent = this.getIcon(type);
            }
            notification.type = type;
        }
        
        notification.message = message;
        notification.timestamp = Date.now();
    }
    
    /**
     * Get notification count by type
     */
    getCount(type = null) {
        if (type) {
            return Array.from(this.notifications.values()).filter(n => n.type === type).length;
        }
        return this.notifications.size;
    }
    
    /**
     * Check if notification exists
     */
    exists(id) {
        return this.notifications.has(id);
    }
    
    /**
     * Enforce maximum notification limit
     */
    enforceLimit() {
        if (this.notifications.size <= this.maxNotifications) return;
        
        // Remove oldest notifications
        const sortedNotifications = Array.from(this.notifications.entries())
            .sort((a, b) => a[1].timestamp - b[1].timestamp);
        
        const toRemove = sortedNotifications.slice(0, this.notifications.size - this.maxNotifications);
        toRemove.forEach(([id]) => this.dismiss(id));
    }
    
    /**
     * Generate unique ID
     */
    generateId() {
        return 'notification-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Show system status notification
     */
    showSystemStatus(status, message) {
        const types = {
            online: 'success',
            offline: 'error',
            degraded: 'warning',
            maintenance: 'info'
        };
        
        const type = types[status] || 'info';
        const title = `System ${status.charAt(0).toUpperCase() + status.slice(1)}`;
        
        return this.show(message, type, 0, { title });
    }
    
    /**
     * Show phase transition notification
     */
    showPhaseTransition(fromPhase, toPhase, message) {
        const title = `Phase Transition: ${fromPhase} → ${toPhase}`;
        return this.show(message, 'info', 8000, { title });
    }
    
    /**
     * Show security alert
     */
    showSecurityAlert(message, severity = 'high') {
        const type = severity === 'high' ? 'error' : 'warning';
        const title = 'Security Alert';
        return this.show(message, type, 0, { title });
    }
    
    /**
     * Show connectivity status
     */
    showConnectivityStatus(connected, message) {
        const type = connected ? 'success' : 'error';
        const title = connected ? 'Connected' : 'Connection Lost';
        return this.show(message, type, connected ? 3000 : 0, { title });
    }
    
    /**
     * Show batch operation progress
     */
    showBatchProgress(completed, total, operation) {
        const message = `${operation}: ${completed}/${total} completed`;
        const percentage = Math.round((completed / total) * 100);
        const title = `Progress: ${percentage}%`;
        
        return this.show(message, 'info', 0, { title });
    }
    
    /**
     * Show API error with retry option
     */
    showApiError(error, retryCallback) {
        const message = `API Error: ${error.message || 'Unknown error'}`;
        const options = {
            title: 'Connection Error',
            onClick: retryCallback
        };
        
        return this.show(message + ' (Click to retry)', 'error', 0, options);
    }
    
    /**
     * Show validation errors
     */
    showValidationErrors(errors) {
        if (Array.isArray(errors)) {
            errors.forEach((error, index) => {
                setTimeout(() => {
                    this.show(error, 'error', 6000, { title: 'Validation Error' });
                }, index * 100);
            });
        } else {
            this.show(errors, 'error', 6000, { title: 'Validation Error' });
        }
    }
    
    /**
     * Show confirmation notification
     */
    showConfirmation(message, onConfirm, onCancel) {
        const notification = document.createElement('div');
        notification.className = 'notification warning show';
        
        const id = this.generateId();
        notification.setAttribute('data-id', id);
        
        notification.innerHTML = `
            <div class="notification-icon">⚠</div>
            <div class="notification-content">
                <div class="notification-title">Confirmation Required</div>
                <div class="notification-message">${message}</div>
                <div class="notification-actions" style="margin-top: 10px; display: flex; gap: 8px;">
                    <button class="btn btn-small btn-success" onclick="notifications.handleConfirm('${id}', true)">Confirm</button>
                    <button class="btn btn-small btn-secondary" onclick="notifications.handleConfirm('${id}', false)">Cancel</button>
                </div>
            </div>
        `;
        
        this.container.appendChild(notification);
        
        // Store with callbacks
        this.notifications.set(id, {
            element: notification,
            type: 'confirmation',
            message: message,
            timestamp: Date.now(),
            onConfirm: onConfirm,
            onCancel: onCancel
        });
        
        return id;
    }
    
    /**
     * Handle confirmation response
     */
    handleConfirm(id, confirmed) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        if (confirmed && notification.onConfirm) {
            notification.onConfirm();
        } else if (!confirmed && notification.onCancel) {
            notification.onCancel();
        }
        
        this.dismiss(id);
    }
}

// Initialize global notification system
window.notifications = new NotificationSystem();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationSystem;
} 