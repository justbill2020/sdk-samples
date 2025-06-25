"""
Firewall Manager for SimSelector v2.6.0 Tech Dashboard

Manages dynamic iptables rules for phase-based dashboard access:
- Safe rule addition/removal with rollback capability
- Rule validation and conflict detection
- Firewall state backup and restore functionality
- Phase-specific firewall configurations
- Integration with security manager for access control

Firewall Rules by Phase:
- STAGING: Port 8080 open for LAN dashboard access
- INSTALL: Port 8080 open for LAN dashboard access  
- DEPLOYED: Port 8080 closed for LAN (NCM remote connect only)
"""

import subprocess
import re
import time
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Import our phase system
try:
    from SimSelector import Phase
except ImportError:
    # Fallback for testing
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class FirewallRule:
    """Represents an iptables firewall rule"""
    
    def __init__(self, chain: str, target: str, protocol: str = None, 
                 port: int = None, source: str = None, interface: str = None,
                 comment: str = None):
        self.chain = chain
        self.target = target
        self.protocol = protocol
        self.port = port
        self.source = source
        self.interface = interface
        self.comment = comment or f"SimSelector-v2.6.0-{int(time.time())}"
    
    def to_iptables_command(self, action: str = "-A") -> List[str]:
        """Convert rule to iptables command"""
        cmd = ["iptables", action, self.chain]
        
        if self.interface:
            cmd.extend(["-i", self.interface])
        
        if self.protocol:
            cmd.extend(["-p", self.protocol])
        
        if self.port:
            cmd.extend(["--dport", str(self.port)])
        
        if self.source:
            cmd.extend(["-s", self.source])
        
        cmd.extend(["-j", self.target])
        
        if self.comment:
            cmd.extend(["-m", "comment", "--comment", self.comment])
        
        return cmd
    
    def __str__(self):
        return f"FirewallRule({self.chain}, {self.target}, port={self.port}, comment={self.comment})"


class FirewallManager:
    """Manages iptables rules for SimSelector dashboard access"""
    
    # Dashboard port configuration
    DASHBOARD_PORT = 8080
    
    # Rule comments for identification
    RULE_COMMENT_PREFIX = "SimSelector-v2.6.0"
    
    # Backup file for rule state
    BACKUP_FILE = "/tmp/simselector_firewall_backup.json"
    
    def __init__(self, client=None):
        self.client = client
        self._active_rules = []
        self._backup_rules = []
        self._dry_run = False  # For testing
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log firewall operations"""
        if self.client:
            self.client.log(f"FIREWALL [{level}] {message}")
        else:
            print(f"FIREWALL [{level}] {message}")
    
    def _execute_command(self, cmd: List[str]) -> Tuple[bool, str]:
        """Execute iptables command with error handling"""
        if self._dry_run:
            self._log(f"DRY RUN: {' '.join(cmd)}")
            return True, "dry run success"
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                self._log(f"Command successful: {' '.join(cmd)}")
                return True, result.stdout
            else:
                self._log(f"Command failed: {' '.join(cmd)} - {result.stderr}", "ERROR")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            self._log(f"Command timeout: {' '.join(cmd)}", "ERROR")
            return False, "Command timeout"
        except Exception as e:
            self._log(f"Command error: {' '.join(cmd)} - {str(e)}", "ERROR")
            return False, str(e)
    
    def _check_iptables_available(self) -> bool:
        """Check if iptables is available and accessible"""
        success, output = self._execute_command(["iptables", "--version"])
        return success
    
    def _get_existing_rules(self) -> List[str]:
        """Get existing iptables rules with SimSelector comments"""
        success, output = self._execute_command(["iptables", "-L", "-n", "--line-numbers"])
        
        if not success:
            return []
        
        simselector_rules = []
        for line in output.split('\n'):
            if self.RULE_COMMENT_PREFIX in line:
                simselector_rules.append(line)
        
        return simselector_rules
    
    def _validate_rule(self, rule: FirewallRule) -> bool:
        """Validate firewall rule before applying"""
        # Check required fields
        if not rule.chain or not rule.target:
            self._log(f"Invalid rule: missing chain or target", "ERROR")
            return False
        
        # Validate chain names
        valid_chains = ["INPUT", "OUTPUT", "FORWARD"]
        if rule.chain not in valid_chains:
            self._log(f"Invalid chain: {rule.chain}", "ERROR")
            return False
        
        # Validate target
        valid_targets = ["ACCEPT", "DROP", "REJECT"]
        if rule.target not in valid_targets:
            self._log(f"Invalid target: {rule.target}", "ERROR")
            return False
        
        # Validate port range
        if rule.port and (rule.port < 1 or rule.port > 65535):
            self._log(f"Invalid port: {rule.port}", "ERROR")
            return False
        
        return True
    
    def _check_rule_conflicts(self, new_rule: FirewallRule) -> List[str]:
        """Check for potential rule conflicts"""
        conflicts = []
        
        existing_rules = self._get_existing_rules()
        
        for existing in existing_rules:
            # Check for duplicate port rules
            if (new_rule.port and 
                str(new_rule.port) in existing and 
                new_rule.target in existing):
                conflicts.append(f"Duplicate rule for port {new_rule.port}")
        
        return conflicts
    
    def add_rule(self, rule: FirewallRule, force: bool = False) -> bool:
        """Add firewall rule with validation and conflict checking"""
        try:
            # Validate rule
            if not self._validate_rule(rule):
                return False
            
            # Check for conflicts unless forced
            if not force:
                conflicts = self._check_rule_conflicts(rule)
                if conflicts:
                    self._log(f"Rule conflicts detected: {conflicts}", "WARNING")
                    return False
            
            # Create backup before making changes
            self._create_backup()
            
            # Add the rule
            cmd = rule.to_iptables_command("-A")
            success, output = self._execute_command(cmd)
            
            if success:
                self._active_rules.append(rule)
                self._log(f"Added firewall rule: {rule}")
                return True
            else:
                self._log(f"Failed to add rule: {output}", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error adding rule: {str(e)}", "ERROR")
            return False
    
    def remove_rule(self, rule: FirewallRule) -> bool:
        """Remove firewall rule"""
        try:
            # Create backup before making changes
            self._create_backup()
            
            # Remove the rule
            cmd = rule.to_iptables_command("-D")
            success, output = self._execute_command(cmd)
            
            if success:
                if rule in self._active_rules:
                    self._active_rules.remove(rule)
                self._log(f"Removed firewall rule: {rule}")
                return True
            else:
                self._log(f"Failed to remove rule: {output}", "WARNING")
                # Rule might not exist, which is okay
                return True
                
        except Exception as e:
            self._log(f"Error removing rule: {str(e)}", "ERROR")
            return False
    
    def _create_backup(self) -> bool:
        """Create backup of current firewall state"""
        try:
            # Get current iptables rules
            success, output = self._execute_command(["iptables-save"])
            
            if success:
                backup_data = {
                    'timestamp': time.time(),
                    'rules': output,
                    'active_simselector_rules': [str(rule) for rule in self._active_rules]
                }
                
                # Save to backup file
                with open(self.BACKUP_FILE, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                
                self._log("Firewall backup created")
                return True
            else:
                self._log("Failed to create firewall backup", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error creating backup: {str(e)}", "ERROR")
            return False
    
    def restore_backup(self) -> bool:
        """Restore firewall state from backup"""
        try:
            if not os.path.exists(self.BACKUP_FILE):
                self._log("No backup file found", "WARNING")
                return False
            
            with open(self.BACKUP_FILE, 'r') as f:
                backup_data = json.load(f)
            
            # Restore using iptables-restore
            cmd = ["iptables-restore"]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=backup_data['rules'])
            
            if process.returncode == 0:
                self._log("Firewall backup restored successfully")
                self._active_rules = []  # Clear tracked rules
                return True
            else:
                self._log(f"Failed to restore backup: {stderr}", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error restoring backup: {str(e)}", "ERROR")
            return False
    
    def configure_dashboard_access(self, phase_id: int) -> bool:
        """Configure firewall rules based on current phase"""
        try:
            self._log(f"Configuring dashboard access for phase {phase_id}")
            
            # Remove existing SimSelector rules
            self.remove_all_simselector_rules()
            
            if phase_id in [Phase.STAGING, Phase.INSTALL]:
                # Allow dashboard access on port 8080
                rule = FirewallRule(
                    chain="INPUT",
                    target="ACCEPT",
                    protocol="tcp",
                    port=self.DASHBOARD_PORT,
                    comment=f"{self.RULE_COMMENT_PREFIX}-dashboard-access-phase-{phase_id}"
                )
                
                if self.add_rule(rule):
                    self._log(f"Dashboard access enabled for phase {phase_id}")
                    return True
                else:
                    self._log(f"Failed to enable dashboard access for phase {phase_id}", "ERROR")
                    return False
                    
            elif phase_id == Phase.DEPLOYED:
                # Dashboard access disabled in deployed phase
                self._log("Dashboard access disabled for deployed phase")
                return True
            
            else:
                self._log(f"Unknown phase: {phase_id}", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error configuring dashboard access: {str(e)}", "ERROR")
            return False
    
    def remove_all_simselector_rules(self) -> bool:
        """Remove all SimSelector-related firewall rules"""
        try:
            # Get all iptables rules with line numbers
            success, output = self._execute_command(["iptables", "-L", "INPUT", "-n", "--line-numbers"])
            
            if not success:
                return False
            
            # Find SimSelector rules and collect line numbers
            lines_to_remove = []
            for line in output.split('\n'):
                if self.RULE_COMMENT_PREFIX in line:
                    # Extract line number (first field)
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        lines_to_remove.append(int(parts[0]))
            
            # Remove rules in reverse order to maintain line numbers
            lines_to_remove.sort(reverse=True)
            
            for line_num in lines_to_remove:
                cmd = ["iptables", "-D", "INPUT", str(line_num)]
                success, output = self._execute_command(cmd)
                if success:
                    self._log(f"Removed SimSelector rule at line {line_num}")
                else:
                    self._log(f"Failed to remove rule at line {line_num}: {output}", "WARNING")
            
            # Clear tracked rules
            self._active_rules = []
            
            self._log(f"Removed {len(lines_to_remove)} SimSelector firewall rules")
            return True
            
        except Exception as e:
            self._log(f"Error removing SimSelector rules: {str(e)}", "ERROR")
            return False
    
    def get_firewall_status(self) -> Dict[str, Any]:
        """Get current firewall status and configuration"""
        return {
            'iptables_available': self._check_iptables_available(),
            'active_rules': len(self._active_rules),
            'dashboard_port': self.DASHBOARD_PORT,
            'backup_exists': os.path.exists(self.BACKUP_FILE),
            'simselector_rules': self._get_existing_rules(),
            'dry_run_mode': self._dry_run
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current firewall configuration"""
        issues = []
        warnings = []
        
        # Check if iptables is available
        if not self._check_iptables_available():
            issues.append("iptables not available or not accessible")
        
        # Check for conflicting rules
        existing_rules = self._get_existing_rules()
        if len(existing_rules) > 10:
            warnings.append(f"Many SimSelector rules found: {len(existing_rules)}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'existing_rules_count': len(existing_rules)
        }
    
    def set_dry_run(self, enabled: bool) -> None:
        """Enable/disable dry run mode for testing"""
        self._dry_run = enabled
        self._log(f"Dry run mode: {'enabled' if enabled else 'disabled'}")


# Global firewall manager instance
_firewall_manager = None

def get_firewall_manager(client=None):
    """Get global firewall manager instance"""
    global _firewall_manager
    if _firewall_manager is None:
        _firewall_manager = FirewallManager(client)
    return _firewall_manager

def configure_phase_firewall(phase_id: int, client=None) -> bool:
    """Quick function to configure firewall for current phase"""
    firewall_manager = get_firewall_manager(client)
    return firewall_manager.configure_dashboard_access(phase_id)

def cleanup_firewall_rules(client=None) -> bool:
    """Quick function to clean up all SimSelector firewall rules"""
    firewall_manager = get_firewall_manager(client)
    return firewall_manager.remove_all_simselector_rules() 