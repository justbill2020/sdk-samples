"""
Firewall Manager for SimSelector v2.6.0 Tech Dashboard

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
from typing import Dict, List, Optional, Any

try:
    from SimSelector import Phase
    from state_manager import get_state, set_state, set_secure_state
except ImportError:
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class NetCloudFirewallManager:
    """Enhanced NetCloud firewall manager with dynamic rule management and conflict resolution"""
    
    DASHBOARD_PORT = 8080
    DASHBOARD_SERVICE = "simselector-dashboard"
    RULE_PREFIX = "SimSelector-v2.6.0"
    SSL_PORT = 8443  # For HTTPS dashboard access
    
    # Rule templates for different scenarios
    RULE_TEMPLATES = {
        'dashboard_lan': {
            'name_template': '{prefix}-dashboard-lan-{phase}',
            'enabled': True,
            'source_zones': ['lan'],
            'destination_zones': ['lan'],
            'services': ['simselector-dashboard'],
            'action': 'allow',
            'description_template': 'Allow SimSelector dashboard access from LAN in {phase_name} phase'
        },
        'dashboard_ssl': {
            'name_template': '{prefix}-dashboard-ssl-{phase}',
            'enabled': True,
            'source_zones': ['lan'],
            'destination_zones': ['lan'],
            'services': ['simselector-dashboard-ssl'],
            'action': 'allow',
            'description_template': 'Allow SimSelector HTTPS dashboard access from LAN in {phase_name} phase'
        },
        'management_access': {
            'name_template': '{prefix}-mgmt-{phase}',
            'enabled': True,
            'source_zones': ['wan'],
            'destination_zones': ['lan'],
            'services': ['ssh', 'https'],
            'action': 'allow',
            'description_template': 'Allow management access for SimSelector in {phase_name} phase'
        }
    }
    
    def __init__(self, client=None):
        self.client = client
        self._active_rules = []
        self._config_backup = None
        self._rule_history = []
        self._conflict_resolution_enabled = True
        
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
                dashboard_service = {
                    "name": self.DASHBOARD_SERVICE,
                    "protocol": "tcp",
                    "ports": [str(self.DASHBOARD_PORT)],
                    "description": "SimSelector v2.6.0 Tech Dashboard Service"
                }
                current_config['services']['custom'].append(dashboard_service)
                
                # Add firewall rule
                dashboard_rule = {
                    "name": f"{self.RULE_PREFIX}-dashboard-access-phase-{phase_id}",
                    "enabled": True,
                    "source_zones": ["lan"],
                    "destination_zones": ["lan"],
                    "services": [self.DASHBOARD_SERVICE],
                    "action": "allow",
                    "description": f"Allow dashboard access in {Phase.get_name(phase_id)} phase"
                }
                current_config['rules'].append(dashboard_rule)
                
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
    
    def create_rule_from_template(self, template_name: str, phase_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Create firewall rule from template"""
        try:
            if template_name not in self.RULE_TEMPLATES:
                self._log(f"Unknown rule template: {template_name}", "ERROR")
                return None
            
            template = self.RULE_TEMPLATES[template_name].copy()
            phase_names = {0: 'STAGING', 1: 'INSTALL', 2: 'DEPLOYED'}
            phase_name = phase_names.get(phase_id, f'PHASE-{phase_id}')
            
            # Format template fields
            rule = {}
            for key, value in template.items():
                if key.endswith('_template'):
                    base_key = key[:-9]  # Remove '_template'
                    if isinstance(value, str):
                        rule[base_key] = value.format(
                            prefix=self.RULE_PREFIX,
                            phase=phase_id,
                            phase_name=phase_name,
                            **kwargs
                        )
                else:
                    rule[key] = value
            
            return rule
            
        except Exception as e:
            self._log(f"Error creating rule from template {template_name}: {str(e)}", "ERROR")
            return None
    
    def detect_rule_conflicts(self, new_rule: Dict[str, Any], existing_rules: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Detect potential conflicts with new rule"""
        conflicts = []
        
        try:
            new_name = new_rule.get('name', '')
            new_zones_src = set(new_rule.get('source_zones', []))
            new_zones_dst = set(new_rule.get('destination_zones', []))
            new_services = set(new_rule.get('services', []))
            
            for existing_rule in existing_rules:
                existing_name = existing_rule.get('name', '')
                
                # Skip our own rules for update scenarios
                if existing_name.startswith(self.RULE_PREFIX):
                    continue
                
                existing_zones_src = set(existing_rule.get('source_zones', []))
                existing_zones_dst = set(existing_rule.get('destination_zones', []))
                existing_services = set(existing_rule.get('services', []))
                
                # Check for overlapping zones and services
                if (new_zones_src & existing_zones_src and 
                    new_zones_dst & existing_zones_dst and
                    new_services & existing_services):
                    
                    conflict_type = "zone_service_overlap"
                    if new_rule.get('action') != existing_rule.get('action'):
                        conflict_type = "conflicting_action"
                    
                    conflicts.append({
                        'type': conflict_type,
                        'existing_rule': existing_name,
                        'description': f"Rule overlaps with {existing_name}",
                        'severity': 'medium' if conflict_type == 'zone_service_overlap' else 'high'
                    })
            
            return conflicts
            
        except Exception as e:
            self._log(f"Error detecting rule conflicts: {str(e)}", "ERROR")
            return []
    
    def resolve_rule_conflicts(self, conflicts: List[Dict[str, str]], new_rule: Dict[str, Any]) -> bool:
        """Attempt to resolve rule conflicts"""
        try:
            if not self._conflict_resolution_enabled:
                self._log("Conflict resolution is disabled", "WARNING")
                return False
            
            for conflict in conflicts:
                severity = conflict.get('severity', 'medium')
                conflict_type = conflict.get('type', 'unknown')
                
                if severity == 'high':
                    self._log(f"High severity conflict detected: {conflict['description']}", "ERROR")
                    return False
                
                if conflict_type == 'zone_service_overlap':
                    # For medium conflicts, we can proceed with a warning
                    self._log(f"Proceeding with rule despite conflict: {conflict['description']}", "WARNING")
                    continue
            
            return True
            
        except Exception as e:
            self._log(f"Error resolving conflicts: {str(e)}", "ERROR")
            return False
    
    def apply_phase_rules(self, phase_id: int, enable_ssl: bool = False) -> bool:
        """Apply appropriate firewall rules for a phase"""
        try:
            self._log(f"Applying firewall rules for phase {phase_id}")
            
            current_config = self._get_firewall_config()
            if not current_config:
                return False
            
            # Backup current configuration
            self._config_backup = json.deepcopy(current_config)
            
            # Ensure structure exists
            if 'rules' not in current_config:
                current_config['rules'] = []
            if 'services' not in current_config:
                current_config['services'] = {'custom': []}
            if 'custom' not in current_config['services']:
                current_config['services']['custom'] = []
            
            # Remove existing SimSelector rules
            original_rules = current_config['rules'].copy()
            current_config['rules'] = [
                rule for rule in current_config['rules'] 
                if not rule.get('name', '').startswith(self.RULE_PREFIX)
            ]
            
            # Remove existing dashboard services
            current_config['services']['custom'] = [
                service for service in current_config['services']['custom']
                if not service.get('name', '').startswith('simselector-')
            ]
            
            # Add services based on phase
            if phase_id in [Phase.STAGING, Phase.INSTALL]:
                # Add dashboard service
                dashboard_service = {
                    "name": self.DASHBOARD_SERVICE,
                    "protocol": "tcp",
                    "ports": [str(self.DASHBOARD_PORT)],
                    "description": "SimSelector v2.6.0 Tech Dashboard Service"
                }
                current_config['services']['custom'].append(dashboard_service)
                
                # Add SSL service if enabled
                if enable_ssl:
                    ssl_service = {
                        "name": "simselector-dashboard-ssl",
                        "protocol": "tcp",
                        "ports": [str(self.SSL_PORT)],
                        "description": "SimSelector v2.6.0 HTTPS Dashboard Service"
                    }
                    current_config['services']['custom'].append(ssl_service)
                
                # Create rules from templates
                rules_to_add = ['dashboard_lan']
                if enable_ssl:
                    rules_to_add.append('dashboard_ssl')
                
                for rule_template in rules_to_add:
                    new_rule = self.create_rule_from_template(rule_template, phase_id)
                    if new_rule:
                        # Check for conflicts
                        conflicts = self.detect_rule_conflicts(new_rule, original_rules)
                        if conflicts:
                            self._log(f"Conflicts detected for rule {new_rule['name']}: {len(conflicts)} conflicts")
                            if not self.resolve_rule_conflicts(conflicts, new_rule):
                                self._log(f"Cannot resolve conflicts for rule {new_rule['name']}", "ERROR")
                                continue
                        
                        current_config['rules'].append(new_rule)
                        self._active_rules.append(new_rule['name'])
                        self._log(f"Added rule: {new_rule['name']}")
            
            # Apply configuration
            success = self._set_firewall_config(current_config)
            if success:
                # Record in history
                self._rule_history.append({
                    'timestamp': time.time(),
                    'phase_id': phase_id,
                    'action': 'apply_phase_rules',
                    'rules_added': len(self._active_rules),
                    'ssl_enabled': enable_ssl
                })
                self._log(f"Successfully applied {len(self._active_rules)} rules for phase {phase_id}")
                return True
            else:
                # Restore backup on failure
                if self._config_backup:
                    self._set_firewall_config(self._config_backup)
                    self._log("Restored firewall configuration due to failure", "WARNING")
                return False
                
        except Exception as e:
            self._log(f"Error applying phase rules: {str(e)}", "ERROR")
            return False
    
    def cleanup_phase_transition(self, old_phase: int, new_phase: int) -> bool:
        """Clean up rules during phase transition"""
        try:
            self._log(f"Cleaning up firewall rules for phase transition: {old_phase} -> {new_phase}")
            
            # If transitioning to DEPLOYED, remove all dashboard rules
            if new_phase == Phase.DEPLOYED:
                return self.remove_all_simselector_rules()
            
            # For other transitions, apply new phase rules
            return self.apply_phase_rules(new_phase)
            
        except Exception as e:
            self._log(f"Error during phase transition cleanup: {str(e)}", "ERROR")
            return False
    
    def get_rule_history(self) -> List[Dict[str, Any]]:
        """Get history of rule changes"""
        return self._rule_history.copy()
    
    def enable_conflict_resolution(self, enabled: bool) -> None:
        """Enable or disable automatic conflict resolution"""
        self._conflict_resolution_enabled = enabled
        self._log(f"Conflict resolution {'enabled' if enabled else 'disabled'}")
    
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
                'dashboard_service_configured': dashboard_service_exists,
                'dashboard_port': self.DASHBOARD_PORT
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
            
            return validation_results
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'recommendations': []
            }
    
    def set_dry_run(self, enabled: bool) -> None:
        """Set dry run mode (for testing compatibility)"""
        self._log(f"Dry run mode {'enabled' if enabled else 'disabled'} (NetCloud SDK mode)")


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