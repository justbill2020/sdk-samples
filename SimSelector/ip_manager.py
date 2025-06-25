"""
IP Manager for SimSelector v2.6.0 Error Handling & Edge Cases

Handles IP configuration failures and fallback scenarios:
- DHCP timeout and retry logic
- Static IP fallback configuration
- DNS resolution failures and fallbacks
- Gateway connectivity validation
- Network interface monitoring and recovery
- Comprehensive IP-related error handling

Features:
- Automatic DHCP retry with exponential backoff
- Multiple DNS server fallbacks (Google, Cloudflare, OpenDNS)
- Static IP configuration as last resort
- Network connectivity validation and monitoring
- Interface status tracking and recovery
- Comprehensive logging and error reporting
"""

import time
import threading
import subprocess
import socket
import ipaddress
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from SimSelector import Phase
    from state_manager import get_state, set_state
    from error_handler import SimSelectorError, ErrorSeverity, get_error_handler
    from network_manager import get_network_manager
except ImportError:
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2


class IPStatus(Enum):
    """IP configuration status"""
    UNKNOWN = "unknown"
    DHCP_ACTIVE = "dhcp_active"
    STATIC_ACTIVE = "static_active"
    DHCP_FAILED = "dhcp_failed"
    STATIC_FAILED = "static_failed"
    NO_IP = "no_ip"
    FALLBACK_MODE = "fallback_mode"
    RECOVERING = "recovering"


class ConnectivityStatus(Enum):
    """Network connectivity status"""
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    LIMITED = "limited"
    DISCONNECTED = "disconnected"
    DNS_FAILED = "dns_failed"
    GATEWAY_UNREACHABLE = "gateway_unreachable"


@dataclass
class IPConfiguration:
    """IP configuration information"""
    interface: str
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: List[str] = None
    dhcp_enabled: bool = True
    status: IPStatus = IPStatus.UNKNOWN
    lease_time: Optional[int] = None
    last_renewal: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ConnectivityTest:
    """Network connectivity test result"""
    timestamp: float
    status: ConnectivityStatus
    latency: Optional[float] = None
    dns_resolution_time: Optional[float] = None
    gateway_reachable: bool = False
    internet_reachable: bool = False
    error_message: Optional[str] = None


class IPManager:
    """Comprehensive IP configuration management with error handling"""
    
    def __init__(self, client=None):
        self.client = client
        self.interfaces = {}  # interface -> IPConfiguration
        self.connectivity_status = ConnectivityStatus.UNKNOWN
        self.monitoring_thread = None
        self.monitoring_enabled = False
        
        # Configuration
        self.dhcp_timeout = 60  # seconds
        self.dhcp_retry_attempts = 5
        self.dhcp_retry_delay = 10  # seconds
        self.connectivity_check_interval = 30  # seconds
        self.dns_timeout = 5  # seconds
        self.ping_timeout = 3  # seconds
        
        # Fallback configurations
        self.fallback_dns_servers = [
            "8.8.8.8",      # Google Primary
            "8.8.4.4",      # Google Secondary
            "1.1.1.1",      # Cloudflare Primary
            "1.0.0.1",      # Cloudflare Secondary
            "208.67.222.222",  # OpenDNS Primary
            "208.67.220.220"   # OpenDNS Secondary
        ]
        
        self.static_ip_fallbacks = {
            "cellular": {
                "ip": "192.168.1.100",
                "netmask": "255.255.255.0",
                "gateway": "192.168.1.1"
            },
            "ethernet": {
                "ip": "10.0.0.100", 
                "netmask": "255.255.255.0",
                "gateway": "10.0.0.1"
            }
        }
        
        # Test targets for connectivity validation
        self.connectivity_test_hosts = [
            "8.8.8.8",          # Google DNS
            "1.1.1.1",          # Cloudflare DNS
            "google.com",       # Domain resolution test
            "cloudflare.com"    # Backup domain test
        ]
        
        # State tracking
        self.last_connectivity_check = 0
        self.connectivity_failures = 0
        self.dhcp_failures = 0
        self.static_fallback_active = False
        self.connectivity_callbacks = []
        
        # Error handling
        try:
            self.error_handler = get_error_handler()
        except:
            self.error_handler = None
            
        try:
            self.network_manager = get_network_manager()
        except:
            self.network_manager = None
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log IP operations"""
        if self.client:
            self.client.log(f"IP [{level}] {message}")
        else:
            print(f"IP [{level}] {message}")
    
    def _run_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run system command and return success, stdout, stderr"""
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timeout"
        except Exception as e:
            return False, "", str(e)
    
    def get_interface_ip_config(self, interface: str) -> Optional[IPConfiguration]:
        """Get current IP configuration for interface"""
        try:
            # Get IP address using ifconfig (more compatible than ip command)
            success, stdout, stderr = self._run_command(["ifconfig", interface])
            if not success:
                self._log(f"Failed to get IP config for {interface}: {stderr}", "ERROR")
                return None
            
            config = IPConfiguration(interface=interface)
            
            # Parse IP address and netmask from ifconfig output
            for line in stdout.split('\n'):
                line = line.strip()
                if 'inet ' in line:
                    # Look for inet address
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'inet' and i + 1 < len(parts):
                            config.ip_address = parts[i + 1]
                        elif part == 'netmask' and i + 1 < len(parts):
                            # Convert hex netmask to dotted decimal
                            netmask_hex = parts[i + 1]
                            if netmask_hex.startswith('0x'):
                                try:
                                    netmask_int = int(netmask_hex, 16)
                                    config.netmask = socket.inet_ntoa(netmask_int.to_bytes(4, 'big'))
                                except:
                                    config.netmask = "255.255.255.0"  # Default
                            else:
                                config.netmask = netmask_hex
                    break
            
            # Get gateway using route command
            success, stdout, stderr = self._run_command(["route", "-n", "get", "default"])
            if success:
                for line in stdout.split('\n'):
                    if 'gateway:' in line:
                        config.gateway = line.split('gateway:')[1].strip()
                        break
            
            # Get DNS servers
            try:
                with open('/etc/resolv.conf', 'r') as f:
                    dns_servers = []
                    for line in f:
                        if line.startswith('nameserver'):
                            parts = line.split()
                            if len(parts) >= 2:
                                dns_servers.append(parts[1])
                    config.dns_servers = dns_servers
            except Exception as e:
                self._log(f"Could not read DNS config: {str(e)}", "WARNING")
                config.dns_servers = []
            
            # Determine if DHCP is active (simplified check)
            if config.ip_address:
                config.status = IPStatus.DHCP_ACTIVE  # Assume DHCP unless proven otherwise
                config.dhcp_enabled = True
            else:
                config.status = IPStatus.NO_IP
            
            return config
            
        except Exception as e:
            self._log(f"Error getting IP config for {interface}: {str(e)}", "ERROR")
            return None
    
    def configure_dhcp(self, interface: str, timeout: Optional[int] = None) -> bool:
        """Configure interface for DHCP with retry logic"""
        try:
            timeout = timeout or self.dhcp_timeout
            self._log(f"Configuring DHCP for {interface} (timeout: {timeout}s)")
            
            # On macOS, use networksetup for DHCP configuration
            success, stdout, stderr = self._run_command([
                "networksetup", "-setdhcp", interface
            ])
            
            if success:
                self._log(f"DHCP configuration initiated for {interface}")
                
                # Wait for IP assignment
                for i in range(timeout):
                    time.sleep(1)
                    config = self.get_interface_ip_config(interface)
                    if config and config.ip_address:
                        config.status = IPStatus.DHCP_ACTIVE
                        self.interfaces[interface] = config
                        self._log(f"DHCP successful for {interface}: {config.ip_address}")
                        return True
                
                self._log(f"DHCP timeout for {interface}", "WARNING")
                return False
            else:
                self._log(f"DHCP configuration failed for {interface}: {stderr}", "ERROR")
                self.dhcp_failures += 1
                return False
                
        except Exception as e:
            self._log(f"Error configuring DHCP for {interface}: {str(e)}", "ERROR")
            self.dhcp_failures += 1
            return False
    
    def configure_static_ip(self, interface: str, ip_config: Dict[str, str]) -> bool:
        """Configure static IP for interface"""
        try:
            ip_addr = ip_config.get("ip")
            netmask = ip_config.get("netmask")
            gateway = ip_config.get("gateway")
            dns_servers = ip_config.get("dns_servers", self.fallback_dns_servers[:2])
            
            if not all([ip_addr, netmask, gateway]):
                self._log(f"Invalid static IP configuration for {interface}", "ERROR")
                return False
            
            self._log(f"Configuring static IP for {interface}: {ip_addr}/{netmask}")
            
            # On macOS, use networksetup for static IP configuration
            success, stdout, stderr = self._run_command([
                "networksetup", "-setmanual", interface, ip_addr, netmask, gateway
            ])
            
            if not success:
                self._log(f"Failed to set static IP on {interface}: {stderr}", "ERROR")
                return False
            
            # Configure DNS
            if dns_servers:
                dns_cmd = ["networksetup", "-setdnsservers", interface] + dns_servers
                success, stdout, stderr = self._run_command(dns_cmd)
                if not success:
                    self._log(f"Failed to set DNS for {interface}: {stderr}", "WARNING")
            
            # Verify configuration
            time.sleep(3)
            config = self.get_interface_ip_config(interface)
            if config and config.ip_address == ip_addr:
                config.status = IPStatus.STATIC_ACTIVE
                config.dhcp_enabled = False
                self.interfaces[interface] = config
                self._log(f"Static IP configuration successful for {interface}")
                return True
            else:
                self._log(f"Static IP configuration verification failed for {interface}", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error configuring static IP for {interface}: {str(e)}", "ERROR")
            return False
    
    def configure_interface_with_fallback(self, interface: str, interface_type: str = "cellular") -> bool:
        """Configure interface with DHCP and static fallback"""
        try:
            self._log(f"Configuring {interface} ({interface_type}) with fallback logic")
            
            # Attempt DHCP configuration with retries
            for attempt in range(self.dhcp_retry_attempts):
                self._log(f"DHCP attempt {attempt + 1}/{self.dhcp_retry_attempts} for {interface}")
                
                if self.configure_dhcp(interface, timeout=self.dhcp_timeout):
                    self._log(f"DHCP successful for {interface}")
                    self.static_fallback_active = False
                    return True
                
                if attempt < self.dhcp_retry_attempts - 1:
                    delay = self.dhcp_retry_delay * (2 ** attempt)  # Exponential backoff
                    self._log(f"DHCP failed, retrying in {delay} seconds...")
                    time.sleep(delay)
            
            # DHCP failed, try static fallback
            self._log(f"DHCP failed for {interface}, attempting static IP fallback", "WARNING")
            
            if interface_type in self.static_ip_fallbacks:
                static_config = self.static_ip_fallbacks[interface_type].copy()
                static_config["dns_servers"] = self.fallback_dns_servers[:2]
                
                if self.configure_static_ip(interface, static_config):
                    self._log(f"Static IP fallback successful for {interface}")
                    self.static_fallback_active = True
                    
                    # Update interface status
                    if interface in self.interfaces:
                        self.interfaces[interface].status = IPStatus.FALLBACK_MODE
                    
                    return True
                else:
                    self._log(f"Static IP fallback failed for {interface}", "ERROR")
            else:
                self._log(f"No static fallback configuration for {interface_type}", "ERROR")
            
            # All configuration attempts failed
            if interface in self.interfaces:
                self.interfaces[interface].status = IPStatus.STATIC_FAILED
            
            # Trigger error handling
            if self.error_handler:
                self.error_handler.handle_error(
                    SimSelectorError(
                        f"IP configuration failed for {interface}",
                        ErrorSeverity.HIGH,
                        "ip_configuration_failure"
                    ),
                    context=f"interface_{interface}"
                )
            
            return False
            
        except Exception as e:
            self._log(f"Error in fallback configuration for {interface}: {str(e)}", "ERROR")
            return False
    
    def test_connectivity(self, interface: Optional[str] = None) -> ConnectivityTest:
        """Test network connectivity comprehensively"""
        try:
            test_start = time.time()
            test = ConnectivityTest(timestamp=test_start, status=ConnectivityStatus.UNKNOWN)
            
            # Test DNS resolution
            dns_start = time.time()
            dns_working = False
            
            for host in ["google.com", "cloudflare.com"]:
                try:
                    socket.gethostbyname(host)
                    dns_working = True
                    break
                except socket.gaierror:
                    continue
            
            test.dns_resolution_time = time.time() - dns_start
            
            if not dns_working:
                test.status = ConnectivityStatus.DNS_FAILED
                test.error_message = "DNS resolution failed"
                return test
            
            # Test gateway connectivity
            gateway_reachable = False
            if interface and interface in self.interfaces:
                config = self.interfaces[interface]
                if config.gateway:
                    gateway_reachable = self._ping_host(config.gateway)
                    test.gateway_reachable = gateway_reachable
            
            # Test internet connectivity
            internet_reachable = False
            total_latency = 0
            successful_pings = 0
            
            for host in self.connectivity_test_hosts:
                latency = self._ping_host(host, return_latency=True)
                if latency is not None:
                    internet_reachable = True
                    total_latency += latency
                    successful_pings += 1
            
            test.internet_reachable = internet_reachable
            
            if successful_pings > 0:
                test.latency = total_latency / successful_pings
            
            # Determine overall status
            if internet_reachable:
                test.status = ConnectivityStatus.CONNECTED
            elif gateway_reachable:
                test.status = ConnectivityStatus.LIMITED
                test.error_message = "Internet unreachable but gateway accessible"
            elif not gateway_reachable and interface:
                test.status = ConnectivityStatus.GATEWAY_UNREACHABLE
                test.error_message = "Gateway unreachable"
            else:
                test.status = ConnectivityStatus.DISCONNECTED
                test.error_message = "No network connectivity"
            
            return test
            
        except Exception as e:
            return ConnectivityTest(
                timestamp=time.time(),
                status=ConnectivityStatus.UNKNOWN,
                error_message=str(e)
            )
    
    def _ping_host(self, host: str, return_latency: bool = False) -> Optional[float]:
        """Ping host and return success or latency"""
        try:
            success, stdout, stderr = self._run_command([
                "ping", "-c", "1", "-W", str(self.ping_timeout * 1000), host
            ])
            
            if not success:
                return None if return_latency else False
            
            if return_latency:
                # Extract latency from ping output
                for line in stdout.split('\n'):
                    if 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        try:
                            return float(time_part)
                        except ValueError:
                            pass
                return None
            else:
                return True
                
        except Exception:
            return None if return_latency else False
    
    def recover_interface(self, interface: str) -> bool:
        """Attempt to recover failed interface"""
        try:
            self._log(f"Attempting to recover interface {interface}")
            
            # Get interface type from network manager
            interface_type = "cellular"
            if self.network_manager:
                interfaces = self.network_manager.get_available_interfaces()
                for iface_info in interfaces:
                    if iface_info.get("name") == interface:
                        interface_type = iface_info.get("type", "cellular")
                        break
            
            # Mark as recovering
            if interface in self.interfaces:
                self.interfaces[interface].status = IPStatus.RECOVERING
            
            # Reset interface (macOS approach)
            self._run_command(["ifconfig", interface, "down"])
            time.sleep(2)
            self._run_command(["ifconfig", interface, "up"])
            time.sleep(5)
            
            # Attempt reconfiguration
            success = self.configure_interface_with_fallback(interface, interface_type)
            
            if success:
                self._log(f"Interface {interface} recovery successful")
                # Test connectivity
                connectivity = self.test_connectivity(interface)
                if connectivity.status in [ConnectivityStatus.CONNECTED, ConnectivityStatus.LIMITED]:
                    return True
            
            self._log(f"Interface {interface} recovery failed", "ERROR")
            return False
            
        except Exception as e:
            self._log(f"Error recovering interface {interface}: {str(e)}", "ERROR")
            return False
    
    def start_monitoring(self) -> bool:
        """Start IP and connectivity monitoring"""
        try:
            if self.monitoring_enabled:
                return True
            
            self.monitoring_enabled = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            self._log("IP monitoring started")
            return True
            
        except Exception as e:
            self._log(f"Error starting IP monitoring: {str(e)}", "ERROR")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop IP and connectivity monitoring"""
        try:
            self.monitoring_enabled = False
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            self._log("IP monitoring stopped")
            return True
            
        except Exception as e:
            self._log(f"Error stopping IP monitoring: {str(e)}", "ERROR")
            return False
    
    def _monitoring_loop(self):
        """IP and connectivity monitoring loop"""
        while self.monitoring_enabled:
            try:
                # Test connectivity for all configured interfaces
                for interface in list(self.interfaces.keys()):
                    connectivity = self.test_connectivity(interface)
                    
                    if connectivity.status == ConnectivityStatus.DISCONNECTED:
                        self.connectivity_failures += 1
                        self._log(f"Connectivity lost on {interface}, attempting recovery", "WARNING")
                        
                        # Attempt recovery
                        if self.recover_interface(interface):
                            self.connectivity_failures = 0
                        else:
                            # Escalate if multiple failures
                            if self.connectivity_failures >= 3:
                                if self.error_handler:
                                    self.error_handler.handle_error(
                                        SimSelectorError(
                                            f"Persistent connectivity failure on {interface}",
                                            ErrorSeverity.CRITICAL,
                                            "connectivity_failure"
                                        ),
                                        context=f"monitoring_{interface}"
                                    )
                    else:
                        self.connectivity_failures = 0
                
                # Update overall connectivity status
                self._update_connectivity_status()
                
                # Notify callbacks
                self._notify_connectivity_change()
                
                time.sleep(self.connectivity_check_interval)
                
            except Exception as e:
                self._log(f"Error in IP monitoring loop: {str(e)}", "ERROR")
                time.sleep(10)  # Longer sleep on error
    
    def _update_connectivity_status(self):
        """Update overall connectivity status"""
        if not self.interfaces:
            self.connectivity_status = ConnectivityStatus.DISCONNECTED
            return
        
        # Check if any interface has good connectivity
        for interface, config in self.interfaces.items():
            if config.status in [IPStatus.DHCP_ACTIVE, IPStatus.STATIC_ACTIVE, IPStatus.FALLBACK_MODE]:
                connectivity = self.test_connectivity(interface)
                if connectivity.status == ConnectivityStatus.CONNECTED:
                    self.connectivity_status = ConnectivityStatus.CONNECTED
                    return
                elif connectivity.status == ConnectivityStatus.LIMITED:
                    self.connectivity_status = ConnectivityStatus.LIMITED
        
        # No good connectivity found
        self.connectivity_status = ConnectivityStatus.DISCONNECTED
    
    def add_connectivity_callback(self, callback):
        """Add callback for connectivity changes"""
        self.connectivity_callbacks.append(callback)
    
    def _notify_connectivity_change(self):
        """Notify callbacks of connectivity changes"""
        for callback in self.connectivity_callbacks:
            try:
                callback(self.connectivity_status, self.interfaces)
            except Exception as e:
                self._log(f"Error in connectivity callback: {str(e)}", "ERROR")
    
    def get_ip_status(self) -> Dict[str, Any]:
        """Get comprehensive IP status"""
        return {
            "interfaces": {
                interface: {
                    "ip_address": config.ip_address,
                    "gateway": config.gateway,
                    "dns_servers": config.dns_servers,
                    "status": config.status.value,
                    "dhcp_enabled": config.dhcp_enabled,
                    "error_count": config.error_count,
                    "last_error": config.last_error
                }
                for interface, config in self.interfaces.items()
            },
            "connectivity_status": self.connectivity_status.value,
            "static_fallback_active": self.static_fallback_active,
            "monitoring_enabled": self.monitoring_enabled,
            "dhcp_failures": self.dhcp_failures,
            "connectivity_failures": self.connectivity_failures,
            "last_connectivity_check": self.last_connectivity_check
        }
    
    def force_interface_reconfigure(self, interface: str) -> bool:
        """Force interface reconfiguration"""
        self._log(f"Forcing reconfiguration of {interface}")
        
        # Determine interface type
        interface_type = "cellular"
        if "eth" in interface.lower():
            interface_type = "ethernet"
        
        return self.configure_interface_with_fallback(interface, interface_type)


# Global IP manager instance
_ip_manager = None

def get_ip_manager(client=None):
    """Get or create IP manager instance"""
    global _ip_manager
    if _ip_manager is None:
        _ip_manager = IPManager(client)
    return _ip_manager

def configure_interface_ip(interface: str, client=None, interface_type: str = "cellular") -> bool:
    """Configure interface IP with fallback"""
    ip_manager = get_ip_manager(client)
    return ip_manager.configure_interface_with_fallback(interface, interface_type)

def test_network_connectivity(interface: Optional[str] = None, client=None) -> ConnectivityTest:
    """Test network connectivity"""
    ip_manager = get_ip_manager(client)
    return ip_manager.test_connectivity(interface) 