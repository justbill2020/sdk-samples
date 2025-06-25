/**
 * SimSelector Dashboard Notifications v2.6.0
 * User notifications and alert system
 */

class NotificationSystem {
    constructor() {
        this.notifications = [];
        this.notificationId = 0;
        this.container = null;
        this.maxNotifications = 5;
        this.defaultDuration = 5000; // 5 seconds
        
        this.init();
    }
    
    /**
     * Initialize notification system
     */
    init() {
        this.createNotificationContainer();
        this.setupKeyboardHandlers();
        
        console.log('Notification system initialized');
    }
    
    /**
     * Create notification container
     */
    createNotificationContainer() {
        this.container = document.createElement('div');
        this.container.id = 'notification-container';
        this.container.className = 'notification-container';
        
        // Add CSS styles
        const style = document.createElement('style');
        style.textContent = `
            .notification-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
                pointer-events: none;
            }
            
            .notification {
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                padding: 16px;
                display: flex;
                align-items: flex-start;
                gap: 12px;
                transform: translateX(100%);
                transition: all 0.3s ease-in-out;
                pointer-events: auto;
                border-left: 4px solid #3498db;
                max-width: 100%;
                word-wrap: break-word;
            }
            
            .notification.show {
                transform: translateX(0);
            }
            
            .notification.success {
                border-left-color: #27ae60;
            }
            
            .notification.warning {
                border-left-color: #f39c12;
            }
            
            .notification.error {
                border-left-color: #e74c3c;
            }
            
            .notification.info {
                border-left-color: #3498db;
            }
            
            .notification-icon {
                font-size: 20px;
                line-height: 1;
                margin-top: 2px;
                min-width: 20px;
            }
            
            .notification-content {
                flex: 1;
                min-width: 0;
            }
            
            .notification-title {
                font-weight: 600;
                color: #2c3e50;
                margin: 0 0 4px 0;
                font-size: 14px;
                line-height: 1.4;
            }
            
            .notification-message {
                color: #6c757d;
                margin: 0;
                font-size: 13px;
                line-height: 1.4;
            }
            
            .notification-close {
                background: none;
                border: none;
                font-size: 18px;
                color: #95a5a6;
                cursor: pointer;
                padding: 0;
                line-height: 1;
                min-width: 18px;
                transition: color 0.2s ease;
            }
            
            .notification-close:hover {
                color: #7f8c8d;
            }
            
            .notification-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 2px;
                background: rgba(52, 152, 219, 0.3);
                transition: width linear;
                border-radius: 0 0 8px 8px;
            }
            
            .notification-progress.success {
                background: rgba(39, 174, 96, 0.3);
            }
            
            .notification-progress.warning {
                background: rgba(243, 156, 18, 0.3);
            }
            
            .notification-progress.error {
                background: rgba(231, 76, 60, 0.3);
            }
            
            /* Mobile responsiveness */
            @media (max-width: 480px) {
                .notification-container {
                    left: 10px;
                    right: 10px;
                    top: 10px;
                    max-width: none;
                }
                
                .notification {
                    padding: 12px;
                    transform: translateY(-100%);
                }
                
                .notification.show {
                    transform: translateY(0);
                }
            }
            
            /* Dark mode support */
            @media (prefers-color-scheme: dark) {
                .notification {
                    background: #2d2d2d;
                    color: #ffffff;
                }
                
                .notification-title {
                    color: #ffffff;
                }
                
                .notification-message {
                    color: #b3b3b3;
                }
                
                .notification-close {
                    color: #808080;
                }
                
                .notification-close:hover {
                    color: #ffffff;
                }
            }
            
            /* High contrast mode */
            @media (prefers-contrast: high) {
                .notification {
                    border: 2px solid #000000;
                }
                
                .notification-close {
                    border: 1px solid transparent;
                }
                
                .notification-close:hover {
                    border-color: #000000;
                }
            }
            
            /* Reduced motion */
            @media (prefers-reduced-motion: reduce) {
                .notification {
                    transition: none;
                }
                
                .notification-progress {
                    transition: none;
                }
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(this.container);
    }
    
    /**
     * Setup keyboard handlers for notifications
     */
    setupKeyboardHandlers() {
        document.addEventListener('keydown', (e) => {
            // Escape key closes all notifications
            if (e.key === 'Escape') {
                this.clearAll();
            }
        });
    }
    
    /**
     * Show notification
     */
    show(title, message = '', type = 'info', duration = null) {
        const notification = this.createNotification(title, message, type, duration);
        this.addNotification(notification);
        return notification.id;
    }
    
    /**
     * Show success notification
     */
    success(title, message = '', duration = null) {
        return this.show(title, message, 'success', duration);
    }
    
    /**
     * Show warning notification
     */
    warning(title, message = '', duration = null) {
        return this.show(title, message, 'warning', duration);
    }
    
    /**
     * Show error notification
     */
    error(title, message = '', duration = null) {
        return this.show(title, message, 'error', duration || 8000); // Errors show longer
    }
    
    /**
     * Show info notification
     */
    info(title, message = '', duration = null) {
        return this.show(title, message, 'info', duration);
    }
    
    /**
     * Create notification element
     */
    createNotification(title, message, type, duration) {
        const id = ++this.notificationId;
        const actualDuration = duration || this.defaultDuration;
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.dataset.id = id;
        
        // Icon based on type
        const icons = {
            success: '✓',
            warning: '⚠',
            error: '✕',
            info: 'ℹ'
        };
        
        notification.innerHTML = `
            <div class="notification-icon">${icons[type] || icons.info}</div>
            <div class="notification-content">
                <div class="notification-title">${this.escapeHtml(title)}</div>
                ${message ? `<div class="notification-message">${this.escapeHtml(message)}</div>` : ''}
            </div>
            <button class="notification-close" title="Close notification">×</button>
            <div class="notification-progress ${type}"></div>
        `;
        
        // Setup close button
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.remove(id);
        });
        
        return {
            id,
            element: notification,
            type,
            duration: actualDuration,
            startTime: Date.now()
        };
    }
    
    /**
     * Add notification to container
     */
    addNotification(notification) {
        // Remove oldest notifications if we have too many
        if (this.notifications.length >= this.maxNotifications) {
            const oldest = this.notifications.shift();
            this.removeElement(oldest.element);
        }
        
        this.notifications.push(notification);
        this.container.appendChild(notification.element);
        
        // Trigger show animation
        requestAnimationFrame(() => {
            notification.element.classList.add('show');
        });
        
        // Setup auto-dismiss
        if (notification.duration > 0) {
            this.setupProgressBar(notification);
            setTimeout(() => {
                this.remove(notification.id);
            }, notification.duration);
        }
    }
    
    /**
     * Setup progress bar animation
     */
    setupProgressBar(notification) {
        const progressBar = notification.element.querySelector('.notification-progress');
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.style.transitionDuration = `${notification.duration}ms`;
            
            requestAnimationFrame(() => {
                progressBar.style.width = '0%';
            });
        }
    }
    
    /**
     * Remove notification by ID
     */
    remove(id) {
        const index = this.notifications.findIndex(n => n.id === id);
        if (index === -1) return;
        
        const notification = this.notifications[index];
        this.notifications.splice(index, 1);
        this.removeElement(notification.element);
    }
    
    /**
     * Remove notification element with animation
     */
    removeElement(element) {
        element.classList.remove('show');
        
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
        }, 300);
    }
    
    /**
     * Clear all notifications
     */
    clearAll() {
        this.notifications.forEach(notification => {
            this.removeElement(notification.element);
        });
        this.notifications = [];
    }
    
    /**
     * Get active notification count
     */
    getCount() {
        return this.notifications.length;
    }
    
    /**
     * Update notification
     */
    update(id, title, message = '', type = null) {
        const notification = this.notifications.find(n => n.id === id);
        if (!notification) return false;
        
        const titleElement = notification.element.querySelector('.notification-title');
        const messageElement = notification.element.querySelector('.notification-message');
        const iconElement = notification.element.querySelector('.notification-icon');
        
        if (titleElement) {
            titleElement.textContent = title;
        }
        
        if (messageElement) {
            messageElement.textContent = message;
        } else if (message) {
            // Add message element if it doesn't exist
            const content = notification.element.querySelector('.notification-content');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'notification-message';
            messageDiv.textContent = message;
            content.appendChild(messageDiv);
        }
        
        if (type && type !== notification.type) {
            notification.element.className = `notification ${type} show`;
            notification.type = type;
            
            const icons = {
                success: '✓',
                warning: '⚠',
                error: '✕',
                info: 'ℹ'
            };
            
            if (iconElement) {
                iconElement.textContent = icons[type] || icons.info;
            }
        }
        
        return true;
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global notification system instance
let notifications = null;

/**
 * Initialize notification system
 */
function initNotifications() {
    if (!notifications) {
        notifications = new NotificationSystem();
    }
    return notifications;
}

/**
 * Show notification (global function)
 */
function showNotification(title, message = '', type = 'info', duration = null) {
    if (!notifications) {
        initNotifications();
    }
    return notifications.show(title, message, type, duration);
}

/**
 * Show success notification (global function)
 */
function showSuccess(title, message = '', duration = null) {
    if (!notifications) {
        initNotifications();
    }
    return notifications.success(title, message, duration);
}

/**
 * Show warning notification (global function)
 */
function showWarning(title, message = '', duration = null) {
    if (!notifications) {
        initNotifications();
    }
    return notifications.warning(title, message, duration);
}

/**
 * Show error notification (global function)
 */
function showError(title, message = '', duration = null) {
    if (!notifications) {
        initNotifications();
    }
    return notifications.error(title, message, duration);
}

/**
 * Show info notification (global function)
 */
function showInfo(title, message = '', duration = null) {
    if (!notifications) {
        initNotifications();
    }
    return notifications.info(title, message, duration);
}

/**
 * Clear all notifications (global function)
 */
function clearAllNotifications() {
    if (notifications) {
        notifications.clearAll();
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initNotifications();
});

// Integration with dashboard logging
if (typeof dashboard !== 'undefined' && dashboard) {
    // Override dashboard addLogEntry to also show notifications for important events
    const originalAddLogEntry = dashboard.addLogEntry;
    dashboard.addLogEntry = function(level, message, type = 'info') {
        // Call original method
        originalAddLogEntry.call(this, level, message, type);
        
        // Show notification for important events
        if (type === 'error' || type === 'warning' || level === 'PHASE') {
            const notificationType = type === 'warning' ? 'warning' : 
                                   type === 'error' ? 'error' : 'info';
            showNotification(level, message, notificationType);
        }
    };
} 