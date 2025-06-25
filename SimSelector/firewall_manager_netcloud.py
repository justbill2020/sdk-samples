"""
NetCloud Firewall Manager for SimSelector v2.6.0 Tech Dashboard

Manages network firewall configuration via NetCloud SDK for dashboard access control:
- STAGING: Dashboard accessible on LAN (port 8080)
- INSTALL: Dashboard accessible on LAN (port 8080) 
- DEPLOYED: Dashboard blocked (no access)

Features:
- NetCloud SDK-based firewall configuration
- Phase-based access control
- Configuration backup and restore
- Temporary rule management
- Comprehensive validation and error handling
"""

import time
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Import core systems
try:
    from SimSelector import Phase
    from state_manager import get_state, set_state, set_secure_state
except ImportError as e:
    print(f"Warning: Could not import core systems: {e}")
    # Fallback definitions for testing
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class FirewallRule:
    """Represents a firewall rule for NetCloud configuration"""
    
    def __init__(self, name: str, enabled: bool = True, 
                 source_zones: List[str] = None, dest_zones: List[str] = None,
                 services: List[str] = None, action: str = "allow",
                 description: str = None):
        self.name = name
        self.enabled = enabled
        self.source_zones = source_zones or ["lan"]
        self.dest_zones = dest_zones or ["lan"] 
        self.services = services or []
        self.action = action
        self.description = description
    
    def to_netcloud_config(self) -> Dict[str, Any]:
        """Convert to NetCloud firewall rule configuration"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "source_zones": self.source_zones,
            "destination_zones": self.dest_zones,
            "services": self.services,
            "action": self.action,
            "description": self.description or f"SimSelector v2.6.0 - {self.name}"
        }
    
    def __str__(self):
        return f"FirewallRule({self.name}, {self.action}, enabled={self.enabled})"


class NetCloudFirewallManager:
    """Manages NetCloud firewall configuration for SimSelector dashboard access"""
    
    # Dashboard port and service configuration
    DASHBOARD_PORT = 8080
    DASHBOARD_SERVICE = "simselector-dashboard"
    
    # Rule names for identification
    RULE_PREFIX = "SimSelector-v2.6.0"
    
    def __init__(self, client=None):
        self.client = client
        self._active_rules = []
        self._original_config = None
        self._config_backup = None
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log firewall operations"""
        if self.client:
            self.client.log(f"FIREWALL [{level}] {message}")
        else:
            print(f"FIREWALL [{level}] {message}")
    
    def _get_firewall_config(self) -> Optional[Dict[str, Any]]:
        """Get current firewall configuration from NetCloud"""
        try:
            if not self.client:
                self._log("No client available - using mock configuration", "WARNING")
                return {"rules": [], "services": {"custom": []}}
            
            config_tree = self.client.get("config/firewall")
            return config_tree if config_tree else {}
                
        except Exception as e:
            self._log(f"Error getting firewall config: {str(e)}", "ERROR")
            return None
    
    def _set_firewall_config(self, config: Dict[str, Any]) -> bool:
        """Set firewall configuration via NetCloud"""
        try:
            if not self.client:
                self._log("No client available - simulating config update", "WARNING")
                return True
            
            success = self.client.put("config/firewall", config)
            if success:
                self._log("Firewall configuration updated successfully")
                return True
            else:
                self._log("Failed to update firewall configuration", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error setting firewall config: {str(e)}", "ERROR")
            return False
    
    def _create_dashboard_service(self) -> Dict[str, Any]:
        """Create custom service definition for dashboard"""
        return {
            "name": self.DASHBOARD_SERVICE,
            "protocol": "tcp",
            "ports": [str(self.DASHBOARD_PORT)],
            "description": "SimSelector v2.6.0 Tech Dashboard Service"
        }
    
    def _backup_current_config(self) -> bool:
        """Create backup of current firewall configuration"""
        try:
            current_config = self._get_firewall_config()
            if current_config:
                self._config_backup = {
                    'timestamp': time.time(),
                    'config': current_config.copy()
                }
                
                # Save backup to secure state
                set_secure_state('firewall_backup', self._config_backup)
                self._log("Firewall configuration backed up")
                return True
            else:
                self._log("Failed to backup firewall configuration", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error backing up config: {str(e)}", "ERROR")
            return False
    
    def _restore_config_backup(self) -> bool:
        """Restore firewall configuration from backup"""
        try:
            if self._config_backup:
                backup_config = self._config_backup['config']
            else:
                # Try to load from secure state
                backup_data = get_state('firewall_backup')
                if backup_data:
                    backup_config = backup_data['config']
                else:
                    self._log("No backup configuration available", "WARNING")
                    return False
            
            success = self._set_firewall_config(backup_config)
            if success:
                self._log("Firewall configuration restored from backup")
                return True
            else:
                self._log("Failed to restore firewall configuration", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error restoring config: {str(e)}", "ERROR")
            return False
    
    def configure_dashboard_access(self, phase_id: int) -> bool:
        """Configure dashboard access based on phase"""
        try:
            self._log(f"Configuring dashboard access for phase {phase_id}")
            
            current_config = self._get_firewall_config()
            if not current_config:
                self._log("Failed to get current firewall configuration", "ERROR")
                return False
            
            # Ensure required structure exists
            if 'rules' not in current_config:
                current_config['rules'] = []
            if 'services' not in current_config:
                current_config['services'] = {'custom': []}
            if 'custom' not in current_config['services']:
                current_config['services']['custom'] = []
            
            # Remove existing SimSelector rules
            current_config['rules'] = [
                rule for rule in current_config['rules'] 
                if not rule.get('name', '').startswith(self.RULE_PREFIX)
            ]
            
            # Remove existing dashboard service
            current_config['services']['custom'] = [
                service for service in current_config['services']['custom']
                if service.get('name') != self.DASHBOARD_SERVICE
            ]
            
            # Configure based on phase
            if phase_id in [Phase.STAGING, Phase.INSTALL]:
                self._log(f"Enabling dashboard access for phase {phase_id}")
                
                # Add dashboard service
                dashboard_service = self._create_dashboard_service()
                current_config['services']['custom'].append(dashboard_service)
                
                # Add firewall rule
                dashboard_rule = FirewallRule(
                    name=f"{self.RULE_PREFIX}-dashboard-access-phase-{phase_id}",
                    enabled=True,
                    source_zones=["lan"],
                    dest_zones=["lan"],
                    services=[self.DASHBOARD_SERVICE],
                    action="allow",
                    description=f"Allow dashboard access in {Phase.get_name(phase_id)} phase"
                )
                
                current_config['rules'].append(dashboard_rule.to_netcloud_config())
                self._active_rules.append(dashboard_rule)
                
            elif phase_id == Phase.DEPLOYED:
                self._log("Disabling dashboard access for deployed phase")
                # Rules already removed above
                
            # Apply the updated configuration
            success = self._set_firewall_config(current_config)
            if success:
                self._log(f"Dashboard access configured for phase {phase_id}")
                return True
            else:
                self._log(f"Failed to configure dashboard access for phase {phase_id}", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error configuring dashboard access: {str(e)}", "ERROR")
            return False
    
    def remove_all_simselector_rules(self) -> bool:
        """Remove all SimSelector firewall rules"""
        try:
            self._log("Removing all SimSelector firewall rules")
            
            current_config = self._get_firewall_config()
            if not current_config:
                return False
            
            # Remove SimSelector rules
            if 'rules' in current_config:
                original_count = len(current_config['rules'])
                current_config['rules'] = [
                    rule for rule in current_config['rules'] 
                    if not rule.get('name', '').startswith(self.RULE_PREFIX)
                ]
                removed_rules = original_count - len(current_config['rules'])
                self._log(f"Removed {removed_rules} SimSelector firewall rules")
            
            # Remove dashboard service
            if 'services' in current_config and 'custom' in current_config['services']:
                original_count = len(current_config['services']['custom'])
                current_config['services']['custom'] = [
                    service for service in current_config['services']['custom']
                    if service.get('name') != self.DASHBOARD_SERVICE
                ]
                removed_services = original_count - len(current_config['services']['custom'])
                if removed_services > 0:
                    self._log(f"Removed {removed_services} SimSelector services")
            
            # Apply cleaned configuration
            success = self._set_firewall_config(current_config)
            if success:
                self._active_rules.clear()
                self._log("All SimSelector firewall rules removed")
                return True
            else:
                self._log("Failed to remove SimSelector firewall rules", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error removing firewall rules: {str(e)}", "ERROR")
            return False
    
    def get_firewall_status(self) -> Dict[str, Any]:
        """Get current firewall status"""
        try:
            current_config = self._get_firewall_config()
            if not current_config:
                return {'error': 'Failed to get firewall configuration'}
            
            simselector_rules = []
            if 'rules' in current_config:
                simselector_rules = [
                    rule for rule in current_config['rules'] 
                    if rule.get('name', '').startswith(self.RULE_PREFIX)
                ]
            
            dashboard_service_exists = False
            if ('services' in current_config and 'custom' in current_config['services']):
                dashboard_service_exists = any(
                    service.get('name') == self.DASHBOARD_SERVICE
                    for service in current_config['services']['custom']
                )
            
            return {
                'total_rules': len(current_config.get('rules', [])),
                'simselector_rules': len(simselector_rules),
                'simselector_rule_names': [rule['name'] for rule in simselector_rules],
                'dashboard_service_configured': dashboard_service_exists,
                'dashboard_port': self.DASHBOARD_PORT,
                'backup_available': self._config_backup is not None,
                'active_rules_count': len(self._active_rules)
            }
            
        except Exception as e:
            self._log(f"Error getting firewall status: {str(e)}", "ERROR")
            return {'error': str(e)}
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current firewall configuration"""
        try:
            status = self.get_firewall_status()
            
            validation_results = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'recommendations': []
            }
            
            if 'error' in status:
                validation_results['valid'] = False
                validation_results['errors'].append(f"Configuration error: {status['error']}")
                return validation_results
            
            # Check for conflicting rules
            if status['simselector_rules'] > 2:
                validation_results['warnings'].append(
                    f"Multiple SimSelector rules detected: {status['simselector_rules']}"
                )
            
            # Check dashboard service configuration
            if not status['dashboard_service_configured'] and status['simselector_rules'] > 0:
                validation_results['warnings'].append(
                    "SimSelector rules exist but dashboard service not configured"
                )
            
            # Recommendations
            if not status['backup_available']:
                validation_results['recommendations'].append(
                    "Create configuration backup before making changes"
                )
            
            return validation_results
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'recommendations': []
            }


# Global firewall manager instance
_firewall_manager = None

def get_firewall_manager(client=None):
    """Get global NetCloud firewall manager instance"""
    global _firewall_manager
    if _firewall_manager is None:
        _firewall_manager = NetCloudFirewallManager(client)
    return _firewall_manager

def configure_phase_firewall(phase_id: int, client=None) -> bool:
    """Quick function to configure firewall for a specific phase"""
    firewall_manager = get_firewall_manager(client)
    return firewall_manager.configure_dashboard_access(phase_id)

def cleanup_firewall_rules(client=None) -> bool:
    """Quick function to clean up all SimSelector firewall rules"""
    firewall_manager = get_firewall_manager(client)
    return firewall_manager.remove_all_simselector_rules() 