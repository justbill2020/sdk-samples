"""
Network Manager for SimSelector v2.6.0 Tech Dashboard

Manages network interface detection and dashboard binding for LAN access control:
- Detects all available LAN interfaces (ethernet, WiFi)
- Binds dashboard server to appropriate interfaces based on phase
- Implements phase-based access control policies
- Monitors network interface changes and adapts automatically

Features:
- NetCloud SDK-based network interface management
- Dynamic interface detection and monitoring
- Phase-aware interface binding
- Network interface state tracking
- Automatic adaptation to interface changes
"""

import time
import socket
import subprocess
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

try:
    from SimSelector import Phase
    from state_manager import get_state, set_state
    from firewall_manager import get_firewall_manager
except ImportError:
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    type: str  # ethernet, wifi, cellular, loopback
    ip_address: Optional[str]
    netmask: Optional[str]
    mac_address: Optional[str]
    status: str  # up, down, unknown
    is_lan: bool
    interface_index: Optional[int] = None
    mtu: Optional[int] = None
    gateway: Optional[str] = None


class NetworkManager:
    """Manages network interfaces and dashboard binding for SimSelector"""
    
    def __init__(self, client=None):
        self.client = client
        self.interfaces = {}
        self.lan_interfaces = []
        self.monitoring_thread = None
        self.monitoring_enabled = False
        self.last_scan_time = 0
        self.interface_change_callbacks = []
        
        # Dashboard binding configuration
        self.dashboard_bind_interfaces = []
        self.dashboard_port = 8080
        self.current_phase = Phase.STAGING
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log network operations"""
        if self.client:
            self.client.log(f"NETWORK [{level}] {message}")
        else:
            print(f"NETWORK [{level}] {message}")
    
    def _get_system_interfaces(self) -> List[Dict[str, Any]]:
        """Get system network interfaces via NetCloud SDK or system calls"""
        try:
            if self.client:
                # Try to get interfaces from NetCloud SDK
                interfaces = self.client.get("status/network/interfaces")
                if interfaces:
                    return interfaces
            
            # Fallback to system commands
            return self._get_interfaces_from_system()
            
        except Exception as e:
            self._log(f"Error getting system interfaces: {str(e)}", "ERROR")
            return []
    
    def _get_interfaces_from_system(self) -> List[Dict[str, Any]]:
        """Get network interfaces using system commands"""
        interfaces = []
        
        try:
            # Use ip command for Linux systems
            result = subprocess.run(['ip', '-j', 'addr', 'show'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                ip_data = json.loads(result.stdout)
                
                for iface_data in ip_data:
                    interface_info = self._parse_ip_interface_data(iface_data)
                    if interface_info:
                        interfaces.append(interface_info)
            
        except Exception as e:
            self._log(f"Error getting interfaces from system: {str(e)}", "WARNING")
            # Fallback to basic socket interface enumeration
            interfaces = self._get_basic_interfaces()
        
        return interfaces
    
    def _parse_ip_interface_data(self, iface_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse interface data from ip command output"""
        try:
            name = iface_data.get('ifname', '')
            flags = iface_data.get('flags', [])
            
            # Determine interface type
            iface_type = 'unknown'
            if name.startswith('eth') or name.startswith('en'):
                iface_type = 'ethernet'
            elif name.startswith('wlan') or name.startswith('wl') or name.startswith('wifi'):
                iface_type = 'wifi'
            elif name == 'lo' or name.startswith('lo'):
                iface_type = 'loopback'
            elif name.startswith('wwan') or name.startswith('ppp'):
                iface_type = 'cellular'
            
            # Get IP addresses
            ip_address = None
            netmask = None
            
            for addr_info in iface_data.get('addr_info', []):
                if addr_info.get('family') == 'inet':
                    ip_address = addr_info.get('local')
                    prefix_len = addr_info.get('prefixlen')
                    if prefix_len:
                        # Convert prefix length to netmask
                        netmask = self._prefix_to_netmask(prefix_len)
                    break
            
            # Determine if this is a LAN interface
            is_lan = (iface_type in ['ethernet', 'wifi'] and 
                     'UP' in flags and 
                     ip_address and 
                     not name.startswith('lo'))
            
            return {
                'name': name,
                'type': iface_type,
                'ip_address': ip_address,
                'netmask': netmask,
                'mac_address': iface_data.get('address'),
                'status': 'up' if 'UP' in flags else 'down',
                'is_lan': is_lan,
                'interface_index': iface_data.get('ifindex'),
                'mtu': iface_data.get('mtu')
            }
            
        except Exception as e:
            self._log(f"Error parsing interface data: {str(e)}", "WARNING")
            return None
    
    def _prefix_to_netmask(self, prefix_len: int) -> str:
        """Convert prefix length to netmask string"""
        mask = (0xffffffff >> (32 - prefix_len)) << (32 - prefix_len)
        return socket.inet_ntoa(mask.to_bytes(4, byteorder='big'))
    
    def _get_basic_interfaces(self) -> List[Dict[str, Any]]:
        """Basic interface detection using socket"""
        interfaces = []
        
        try:
            import netifaces
            
            for iface_name in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface_name)
                
                # Get IPv4 address
                ip_address = None
                netmask = None
                if netifaces.AF_INET in addrs:
                    ipv4_info = addrs[netifaces.AF_INET][0]
                    ip_address = ipv4_info.get('addr')
                    netmask = ipv4_info.get('netmask')
                
                # Get MAC address
                mac_address = None
                if netifaces.AF_LINK in addrs:
                    mac_address = addrs[netifaces.AF_LINK][0].get('addr')
                
                # Determine interface type and LAN status
                iface_type = 'unknown'
                if iface_name.startswith('eth') or iface_name.startswith('en'):
                    iface_type = 'ethernet'
                elif iface_name.startswith('wlan') or iface_name.startswith('wl'):
                    iface_type = 'wifi'
                elif iface_name == 'lo':
                    iface_type = 'loopback'
                
                is_lan = (iface_type in ['ethernet', 'wifi'] and 
                         ip_address and 
                         iface_name != 'lo')
                
                interfaces.append({
                    'name': iface_name,
                    'type': iface_type,
                    'ip_address': ip_address,
                    'netmask': netmask,
                    'mac_address': mac_address,
                    'status': 'up' if ip_address else 'down',
                    'is_lan': is_lan
                })
                
        except ImportError:
            self._log("netifaces module not available, using minimal detection", "WARNING")
            # Minimal fallback
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            interfaces.append({
                'name': 'eth0',
                'type': 'ethernet',
                'ip_address': local_ip,
                'netmask': '255.255.255.0',
                'mac_address': None,
                'status': 'up',
                'is_lan': True
            })
        
        return interfaces
    
    def scan_interfaces(self) -> Dict[str, NetworkInterface]:
        """Scan and update network interface information"""
        try:
            self._log("Scanning network interfaces...")
            
            system_interfaces = self._get_system_interfaces()
            new_interfaces = {}
            new_lan_interfaces = []
            
            for iface_data in system_interfaces:
                interface = NetworkInterface(
                    name=iface_data['name'],
                    type=iface_data['type'],
                    ip_address=iface_data.get('ip_address'),
                    netmask=iface_data.get('netmask'),
                    mac_address=iface_data.get('mac_address'),
                    status=iface_data['status'],
                    is_lan=iface_data.get('is_lan', False),
                    interface_index=iface_data.get('interface_index'),
                    mtu=iface_data.get('mtu'),
                    gateway=iface_data.get('gateway')
                )
                
                new_interfaces[interface.name] = interface
                
                if interface.is_lan and interface.status == 'up':
                    new_lan_interfaces.append(interface)
            
            # Check for changes
            old_lan_count = len(self.lan_interfaces)
            self.interfaces = new_interfaces
            self.lan_interfaces = new_lan_interfaces
            self.last_scan_time = time.time()
            
            new_lan_count = len(self.lan_interfaces)
            self._log(f"Interface scan complete: {len(new_interfaces)} total, {new_lan_count} LAN interfaces")
            
            # Notify callbacks if LAN interfaces changed
            if old_lan_count != new_lan_count:
                self._notify_interface_change()
            
            return self.interfaces
            
        except Exception as e:
            self._log(f"Error scanning interfaces: {str(e)}", "ERROR")
            return {}
    
    def get_lan_interfaces(self) -> List[NetworkInterface]:
        """Get all available LAN interfaces"""
        return [iface for iface in self.lan_interfaces if iface.status == 'up']
    
    def get_dashboard_bind_addresses(self, phase_id: int) -> List[str]:
        """Get appropriate bind addresses for dashboard based on phase"""
        bind_addresses = []
        
        try:
            if phase_id == Phase.DEPLOYED:
                # No dashboard binding in deployed phase
                return []
            
            if phase_id in [Phase.STAGING, Phase.INSTALL]:
                # Bind to all LAN interfaces
                lan_interfaces = self.get_lan_interfaces()
                
                if not lan_interfaces:
                    self._log("No LAN interfaces available for dashboard binding", "WARNING")
                    # Fallback to localhost
                    bind_addresses.append('127.0.0.1')
                else:
                    for interface in lan_interfaces:
                        if interface.ip_address:
                            bind_addresses.append(interface.ip_address)
                            self._log(f"Dashboard will bind to {interface.name}: {interface.ip_address}")
                
                # Always include localhost for local access
                if '127.0.0.1' not in bind_addresses:
                    bind_addresses.append('127.0.0.1')
            
            return bind_addresses
            
        except Exception as e:
            self._log(f"Error getting dashboard bind addresses: {str(e)}", "ERROR")
            return ['127.0.0.1']  # Safe fallback
    
    def configure_phase_access(self, phase_id: int) -> bool:
        """Configure network access control for phase"""
        try:
            self._log(f"Configuring network access for phase {phase_id}")
            self.current_phase = phase_id
            
            # Update interface scan
            self.scan_interfaces()
            
            # Get appropriate bind addresses
            bind_addresses = self.get_dashboard_bind_addresses(phase_id)
            self.dashboard_bind_interfaces = bind_addresses
            
            # Configure firewall rules
            firewall_manager = get_firewall_manager(self.client)
            if firewall_manager:
                success = firewall_manager.apply_phase_rules(phase_id)
                if not success:
                    self._log("Failed to apply firewall rules", "WARNING")
            
            self._log(f"Network access configured for phase {phase_id}: {len(bind_addresses)} bind addresses")
            return True
            
        except Exception as e:
            self._log(f"Error configuring phase access: {str(e)}", "ERROR")
            return False
    
    def start_monitoring(self) -> bool:
        """Start network interface monitoring"""
        try:
            if self.monitoring_enabled:
                return True
            
            self.monitoring_enabled = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            self._log("Network interface monitoring started")
            return True
            
        except Exception as e:
            self._log(f"Error starting monitoring: {str(e)}", "ERROR")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop network interface monitoring"""
        try:
            self.monitoring_enabled = False
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            self._log("Network interface monitoring stopped")
            return True
            
        except Exception as e:
            self._log(f"Error stopping monitoring: {str(e)}", "ERROR")
            return False
    
    def _monitoring_loop(self):
        """Network interface monitoring loop"""
        while self.monitoring_enabled:
            try:
                # Scan interfaces every 30 seconds
                self.scan_interfaces()
                time.sleep(30)
                
            except Exception as e:
                self._log(f"Error in monitoring loop: {str(e)}", "ERROR")
                time.sleep(10)  # Shorter sleep on error
    
    def add_interface_change_callback(self, callback):
        """Add callback for interface changes"""
        self.interface_change_callbacks.append(callback)
    
    def _notify_interface_change(self):
        """Notify callbacks of interface changes"""
        for callback in self.interface_change_callbacks:
            try:
                callback(self.lan_interfaces)
            except Exception as e:
                self._log(f"Error in interface change callback: {str(e)}", "ERROR")
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get comprehensive network status"""
        return {
            'total_interfaces': len(self.interfaces),
            'lan_interfaces': len(self.lan_interfaces),
            'dashboard_bind_addresses': self.dashboard_bind_interfaces,
            'current_phase': self.current_phase,
            'monitoring_enabled': self.monitoring_enabled,
            'last_scan_time': self.last_scan_time,
            'interfaces': [
                {
                    'name': iface.name,
                    'type': iface.type,
                    'ip_address': iface.ip_address,
                    'status': iface.status,
                    'is_lan': iface.is_lan
                }
                for iface in self.interfaces.values()
            ]
        }
    
    def validate_dashboard_access(self, client_ip: str) -> bool:
        """Validate if client IP should have dashboard access"""
        try:
            # Always allow localhost
            if client_ip in ['127.0.0.1', '::1', 'localhost']:
                return True
            
            # Check if IP is from a LAN interface
            for interface in self.lan_interfaces:
                if interface.ip_address and interface.netmask:
                    if self._ip_in_subnet(client_ip, interface.ip_address, interface.netmask):
                        return True
            
            return False
            
        except Exception as e:
            self._log(f"Error validating dashboard access: {str(e)}", "ERROR")
            return False
    
    def _ip_in_subnet(self, ip: str, network_ip: str, netmask: str) -> bool:
        """Check if IP is in subnet"""
        try:
            import ipaddress
            
            network = ipaddress.IPv4Network(f"{network_ip}/{netmask}", strict=False)
            client = ipaddress.IPv4Address(ip)
            
            return client in network
            
        except Exception:
            return False


# Global network manager instance
_network_manager = None

def get_network_manager(client=None):
    """Get or create network manager instance"""
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager(client)
    return _network_manager

def configure_network_access(phase_id: int, client=None) -> bool:
    """Configure network access for phase"""
    network_manager = get_network_manager(client)
    return network_manager.configure_phase_access(phase_id)

def get_dashboard_bind_addresses(phase_id: int, client=None) -> List[str]:
    """Get dashboard bind addresses for phase"""
    network_manager = get_network_manager(client)
    return network_manager.get_dashboard_bind_addresses(phase_id) 