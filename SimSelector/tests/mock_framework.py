"""
Mock Framework - SimSelector v2.6.0

Comprehensive mock framework for simulating hardware and network conditions.
Enables testing without physical hardware dependencies.

Features:
- Mock cellular modems and SIM cards
- Simulated network interfaces and connectivity
- Configurable signal strength and carrier conditions
- Network failure and recovery scenarios
- Realistic timing and latency simulation
- Hardware event simulation (hot-swap, failures)
"""

import time
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class MockDeviceType(Enum):
    """Types of mock devices"""
    MODEM = "modem"
    SIM_CARD = "sim_card"
    NETWORK_INTERFACE = "network_interface"
    ROUTER = "router"
    FIREWALL = "firewall"


class MockDeviceState(Enum):
    """Mock device states"""
    OFFLINE = "offline"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class MockSIMCard:
    """Mock SIM card with realistic properties"""
    slot: int
    iccid: str
    imsi: str
    carrier: str
    carrier_code: str
    status: str = "present"
    rsrp: float = -85.0
    rsrq: float = -12.0
    signal_strength: int = 75
    network_type: str = "LTE"
    roaming: bool = False
    pin_required: bool = False
    pin_locked: bool = False
    data_usage: int = 0
    last_activity: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize derived properties"""
        if not hasattr(self, 'signal_bars'):
            self.signal_bars = self._calculate_signal_bars()
    
    def _calculate_signal_bars(self) -> int:
        """Calculate signal bars from RSRP"""
        if self.rsrp >= -70:
            return 4
        elif self.rsrp >= -85:
            return 3
        elif self.rsrp >= -100:
            return 2  
        elif self.rsrp >= -115:
            return 1
        else:
            return 0
    
    def simulate_signal_variation(self):
        """Simulate realistic signal variation"""
        # Add random signal variation (-5 to +5 dBm)
        variation = random.uniform(-5.0, 5.0)
        self.rsrp += variation
        
        # Keep within realistic bounds
        self.rsrp = max(-130.0, min(-40.0, self.rsrp))
        
        # Update derived values
        self.signal_bars = self._calculate_signal_bars()
        self.signal_strength = max(0, min(100, int((130 + self.rsrp) * 100 / 90)))
    
    def simulate_data_usage(self, bytes_used: int):
        """Simulate data usage"""
        self.data_usage += bytes_used
        self.last_activity = time.time()


@dataclass
class MockModem:
    """Mock cellular modem"""
    id: str
    model: str = "Generic LTE Modem"
    firmware: str = "1.0.0"
    status: MockDeviceState = MockDeviceState.CONNECTED
    temperature: float = 45.0
    sim_slots: Dict[int, Optional[MockSIMCard]] = field(default_factory=dict)
    active_sim: Optional[int] = None
    connection_time: float = field(default_factory=time.time)
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def __post_init__(self):
        """Initialize modem with default SIM slots"""
        if not self.sim_slots:
            self.sim_slots = {1: None, 2: None}
    
    def insert_sim(self, slot: int, sim_card: MockSIMCard):
        """Insert SIM card into slot"""
        if slot in self.sim_slots:
            self.sim_slots[slot] = sim_card
            sim_card.status = "present"
            return True
        return False
    
    def remove_sim(self, slot: int):
        """Remove SIM card from slot"""
        if slot in self.sim_slots and self.sim_slots[slot]:
            self.sim_slots[slot].status = "absent"
            self.sim_slots[slot] = None
            if self.active_sim == slot:
                self.active_sim = None
            return True
        return False
    
    def set_active_sim(self, slot: int) -> bool:
        """Set active SIM slot"""
        if slot in self.sim_slots and self.sim_slots[slot]:
            self.active_sim = slot
            return True
        return False
    
    def simulate_temperature_variation(self):
        """Simulate realistic temperature variation"""
        # Add random temperature variation
        variation = random.uniform(-2.0, 3.0)  # Modems tend to warm up
        self.temperature += variation
        
        # Keep within realistic bounds (20-80°C)
        self.temperature = max(20.0, min(80.0, self.temperature))
    
    def simulate_data_transfer(self, sent: int = 0, received: int = 0):
        """Simulate data transfer"""
        self.bytes_sent += sent
        self.bytes_received += received
        
        # Update active SIM data usage
        if self.active_sim and self.sim_slots[self.active_sim]:
            self.sim_slots[self.active_sim].simulate_data_usage(sent + received)


@dataclass
class MockNetworkInterface:
    """Mock network interface"""
    name: str
    mac_address: str
    ip_address: Optional[str] = None
    netmask: str = "255.255.255.0"
    gateway: Optional[str] = None
    status: str = "up"
    interface_type: str = "ethernet"
    speed: str = "1000 Mbps"
    duplex: str = "full"
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    errors: int = 0
    dropped: int = 0
    
    def simulate_traffic(self, duration_seconds: float = 1.0):
        """Simulate network traffic"""
        # Simulate realistic traffic patterns
        base_packets = int(duration_seconds * random.uniform(10, 100))
        base_bytes = base_packets * random.randint(64, 1500)
        
        self.packets_sent += base_packets
        self.packets_received += int(base_packets * random.uniform(0.8, 1.2))
        self.bytes_sent += base_bytes
        self.bytes_received += int(base_bytes * random.uniform(0.8, 1.2))
        
        # Occasional errors/drops
        if random.random() < 0.001:  # 0.1% chance
            self.errors += 1
        if random.random() < 0.0005:  # 0.05% chance
            self.dropped += 1


class MockNetworkEnvironment:
    """Mock network environment with realistic conditions"""
    
    def __init__(self):
        self.dhcp_leases: List[Dict] = []
        self.arp_table: List[Dict] = []
        self.static_routes: List[Dict] = []
        self.dns_servers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
        self.network_latency = 25.0  # Base latency in ms
        self.packet_loss = 0.0  # Packet loss percentage
        self.bandwidth_limit = None  # No limit by default
        
    def add_dhcp_lease(self, ip: str, mac: str, hostname: str = "device"):
        """Add DHCP lease to mock environment"""
        lease = {
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "lease_time": time.time(),
            "expires": time.time() + 86400  # 24 hours
        }
        self.dhcp_leases.append(lease)
    
    def add_arp_entry(self, ip: str, mac: str, interface: str = "eth0"):
        """Add ARP table entry"""
        entry = {
            "ip": ip,
            "mac": mac,
            "interface": interface,
            "timestamp": time.time()
        }
        self.arp_table.append(entry)
    
    def simulate_network_conditions(self, condition: str):
        """Simulate different network conditions"""
        conditions = {
            "excellent": {"latency": 15.0, "packet_loss": 0.0},
            "good": {"latency": 25.0, "packet_loss": 0.1},
            "fair": {"latency": 75.0, "packet_loss": 0.5},
            "poor": {"latency": 150.0, "packet_loss": 2.0},
            "very_poor": {"latency": 300.0, "packet_loss": 5.0},
            "congested": {"latency": 200.0, "packet_loss": 1.0},
            "unstable": {"latency": random.uniform(50, 500), "packet_loss": random.uniform(0, 3)}
        }
        
        if condition in conditions:
            self.network_latency = conditions[condition]["latency"]
            self.packet_loss = conditions[condition]["packet_loss"]
    
    def test_connectivity(self, target: str = "8.8.8.8") -> Dict:
        """Mock connectivity test"""
        # Simulate ping test
        if random.random() < (self.packet_loss / 100):
            return {"success": False, "error": "Packet loss"}
        
        # Add jitter to latency
        jitter = random.uniform(-5.0, 15.0)
        actual_latency = max(1.0, self.network_latency + jitter)
        
        return {
            "success": True,
            "latency": actual_latency,
            "target": target,
            "timestamp": time.time()
        }
    
    def run_speed_test(self) -> Dict:
        """Mock speed test"""
        base_download = 50.0  # 50 Mbps base
        base_upload = 10.0    # 10 Mbps base
        
        # Apply network conditions
        latency_factor = max(0.1, 1.0 - (self.network_latency - 25) / 200)
        loss_factor = max(0.1, 1.0 - self.packet_loss / 10)
        
        download_speed = base_download * latency_factor * loss_factor
        upload_speed = base_upload * latency_factor * loss_factor
        
        # Add some randomness
        download_speed *= random.uniform(0.8, 1.2)
        upload_speed *= random.uniform(0.8, 1.2)
        
        return {
            "success": True,
            "download_speed": max(1.0, download_speed),
            "upload_speed": max(0.5, upload_speed),
            "latency": self.network_latency,
            "jitter": random.uniform(1.0, 10.0),
            "server": "Mock Speed Test Server"
        }


class MockHardwareSimulator:
    """Comprehensive hardware simulator"""
    
    def __init__(self):
        self.modems: Dict[str, MockModem] = {}
        self.network_interfaces: Dict[str, MockNetworkInterface] = {}
        self.network_environment = MockNetworkEnvironment()
        self.simulation_active = False
        self.simulation_thread = None
        self.event_callbacks = []
        
        # Initialize default hardware
        self._initialize_default_hardware()
    
    def _initialize_default_hardware(self):
        """Initialize default mock hardware"""
        # Create default modem
        modem = MockModem(
            id="modem0",
            model="SimSelector Test Modem",
            firmware="2.6.0"
        )
        self.modems["modem0"] = modem
        
        # Create default SIM cards
        sim1 = MockSIMCard(
            slot=1,
            iccid="89014103211118510720",
            imsi="310410118510720",
            carrier="Verizon",
            carrier_code="311480",
            rsrp=-75.0,
            signal_strength=85
        )
        
        sim2 = MockSIMCard(
            slot=2,
            iccid="89014103211118510721", 
            imsi="310410118510721",
            carrier="AT&T",
            carrier_code="310410",
            rsrp=-85.0,
            signal_strength=75
        )
        
        modem.insert_sim(1, sim1)
        modem.insert_sim(2, sim2)
        modem.set_active_sim(1)
        
        # Create network interfaces
        eth_interface = MockNetworkInterface(
            name="enp1s0",
            mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.100",
            interface_type="ethernet"
        )
        
        wwan_interface = MockNetworkInterface(
            name="wwan0",
            mac_address="00:11:22:33:44:56",
            ip_address="10.0.0.100",
            interface_type="cellular"
        )
        
        self.network_interfaces["enp1s0"] = eth_interface
        self.network_interfaces["wwan0"] = wwan_interface
        
        # Setup network environment
        self.network_environment.add_dhcp_lease("192.168.1.10", "aa:bb:cc:dd:ee:ff", "device1")
        self.network_environment.add_dhcp_lease("192.168.1.11", "11:22:33:44:55:66", "device2")
        self.network_environment.add_arp_entry("192.168.1.1", "00:11:22:33:44:11", "enp1s0")
    
    def add_event_callback(self, callback):
        """Add callback for hardware events"""
        self.event_callbacks.append(callback)
    
    def _trigger_event(self, event_type: str, data: Dict):
        """Trigger hardware event"""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        }
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Event callback error: {e}")
    
    def start_simulation(self):
        """Start hardware simulation thread"""
        if not self.simulation_active:
            self.simulation_active = True
            self.simulation_thread = threading.Thread(target=self._simulation_loop)
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
    
    def stop_simulation(self):
        """Stop hardware simulation"""
        self.simulation_active = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
    
    def _simulation_loop(self):
        """Main simulation loop"""
        while self.simulation_active:
            try:
                # Simulate signal variations
                for modem in self.modems.values():
                    for sim in modem.sim_slots.values():
                        if sim:
                            sim.simulate_signal_variation()
                    
                    modem.simulate_temperature_variation()
                
                # Simulate network traffic
                for interface in self.network_interfaces.values():
                    if interface.status == "up":
                        interface.simulate_traffic(1.0)
                
                # Random events (low probability)
                if random.random() < 0.01:  # 1% chance per second
                    self._simulate_random_event()
                
                time.sleep(1.0)
                
            except Exception as e:
                print(f"Simulation error: {e}")
                time.sleep(1.0)
    
    def _simulate_random_event(self):
        """Simulate random hardware events"""
        events = [
            "signal_fluctuation",
            "temperature_spike", 
            "network_congestion",
            "modem_restart"
        ]
        
        event_type = random.choice(events)
        
        if event_type == "signal_fluctuation":
            # Cause temporary signal degradation
            modem = random.choice(list(self.modems.values()))
            if modem.active_sim and modem.sim_slots[modem.active_sim]:
                sim = modem.sim_slots[modem.active_sim]
                original_rsrp = sim.rsrp
                sim.rsrp -= random.uniform(10, 30)  # Temporary degradation
                
                self._trigger_event("signal_fluctuation", {
                    "modem_id": modem.id,
                    "sim_slot": modem.active_sim,
                    "original_rsrp": original_rsrp,
                    "new_rsrp": sim.rsrp
                })
        
        elif event_type == "temperature_spike":
            modem = random.choice(list(self.modems.values()))
            modem.temperature += random.uniform(5, 15)
            
            self._trigger_event("temperature_spike", {
                "modem_id": modem.id,
                "temperature": modem.temperature
            })
        
        elif event_type == "network_congestion":
            # Temporarily degrade network conditions
            original_latency = self.network_environment.network_latency
            self.network_environment.network_latency *= random.uniform(2, 5)
            
            self._trigger_event("network_congestion", {
                "original_latency": original_latency,
                "new_latency": self.network_environment.network_latency
            })
    
    def simulate_sim_hotswap(self, modem_id: str, slot: int, action: str):
        """Simulate SIM card hot-swap"""
        if modem_id not in self.modems:
            return False
        
        modem = self.modems[modem_id]
        
        if action == "remove":
            if modem.remove_sim(slot):
                self._trigger_event("sim_removed", {
                    "modem_id": modem_id,
                    "slot": slot
                })
                return True
        
        elif action == "insert":
            # Create new SIM card
            new_sim = MockSIMCard(
                slot=slot,
                iccid=f"8901410321111851072{slot}",
                imsi=f"31041011851072{slot}",
                carrier=random.choice(["Verizon", "AT&T", "T-Mobile"]),
                carrier_code="311480"
            )
            
            if modem.insert_sim(slot, new_sim):
                self._trigger_event("sim_inserted", {
                    "modem_id": modem_id,
                    "slot": slot,
                    "sim_data": {
                        "iccid": new_sim.iccid,
                        "carrier": new_sim.carrier
                    }
                })
                return True
        
        return False
    
    def simulate_network_failure(self, interface_name: str, duration: float = 30.0):
        """Simulate network interface failure"""
        if interface_name in self.network_interfaces:
            interface = self.network_interfaces[interface_name]
            original_status = interface.status
            interface.status = "down"
            
            self._trigger_event("interface_down", {
                "interface": interface_name,
                "duration": duration
            })
            
            # Schedule recovery
            def recover():
                time.sleep(duration)
                interface.status = original_status
                self._trigger_event("interface_up", {
                    "interface": interface_name
                })
            
            recovery_thread = threading.Thread(target=recover)
            recovery_thread.daemon = True
            recovery_thread.start()
            
            return True
        return False
    
    def get_modem_status(self, modem_id: str) -> Dict:
        """Get comprehensive modem status"""
        if modem_id not in self.modems:
            return {"error": "Modem not found"}
        
        modem = self.modems[modem_id]
        
        sim_data = {}
        for slot, sim in modem.sim_slots.items():
            if sim:
                sim_data[f"sim{slot}"] = {
                    "iccid": sim.iccid,
                    "imsi": sim.imsi,
                    "carrier": sim.carrier,
                    "carrier_code": sim.carrier_code,
                    "rsrp": sim.rsrp,
                    "rsrq": sim.rsrq,
                    "signal_strength": sim.signal_strength,
                    "signal_bars": sim.signal_bars,
                    "network_type": sim.network_type,
                    "roaming": sim.roaming,
                    "data_usage": sim.data_usage,
                    "status": sim.status
                }
        
        return {
            "id": modem.id,
            "model": modem.model,
            "firmware": modem.firmware,
            "status": modem.status.value,
            "temperature": modem.temperature,
            "active_sim": modem.active_sim,
            "bytes_sent": modem.bytes_sent,
            "bytes_received": modem.bytes_received,
            "connection_time": modem.connection_time,
            "sims": sim_data
        }
    
    def get_network_interfaces(self) -> Dict:
        """Get network interface information"""
        interfaces = {}
        
        for name, iface in self.network_interfaces.items():
            interfaces[name] = {
                "name": name,
                "mac": iface.mac_address,
                "ip": iface.ip_address,
                "netmask": iface.netmask,
                "gateway": iface.gateway,
                "status": iface.status,
                "type": iface.interface_type,
                "speed": iface.speed,
                "duplex": iface.duplex,
                "bytes_sent": iface.bytes_sent,
                "bytes_received": iface.bytes_received,
                "packets_sent": iface.packets_sent,
                "packets_received": iface.packets_received,
                "errors": iface.errors,
                "dropped": iface.dropped
            }
        
        return interfaces
    
    def get_network_environment(self) -> Dict:
        """Get network environment information"""
        return {
            "dhcp_leases": self.network_environment.dhcp_leases,
            "arp_table": self.network_environment.arp_table,
            "static_routes": self.network_environment.static_routes,
            "dns_servers": self.network_environment.dns_servers,
            "network_conditions": {
                "latency": self.network_environment.network_latency,
                "packet_loss": self.network_environment.packet_loss,
                "bandwidth_limit": self.network_environment.bandwidth_limit
            }
        }


class MockFrameworkClient:
    """Mock CS client that interfaces with hardware simulator"""
    
    def __init__(self, hardware_simulator: MockHardwareSimulator):
        self.simulator = hardware_simulator
        self.logs = []
    
    def log(self, message: str):
        """Log message"""
        self.logs.append({
            "timestamp": time.time(),
            "message": message
        })
        print(f"MockClient: {message}")
    
    def get(self, path: str) -> Any:
        """Handle GET requests to mock API"""
        if path == "status/wan/devices":
            return self._get_wan_devices()
        elif path.startswith("status/wan/devices/") and path.endswith("/sim1"):
            modem_id = path.split("/")[3]
            return self._get_sim_details(modem_id, 1)
        elif path.startswith("status/wan/devices/") and path.endswith("/sim2"):
            modem_id = path.split("/")[3]
            return self._get_sim_details(modem_id, 2)
        elif path == "status/system/network/interfaces":
            return {"interfaces": list(self.simulator.get_network_interfaces().values())}
        elif path == "status/system/network/arp":
            return {"entries": self.simulator.network_environment.arp_table}
        elif path == "status/system/network/statistics":
            return self._get_network_statistics()
        else:
            return None
    
    def _get_wan_devices(self) -> Dict:
        """Get WAN device information"""
        modems_data = []
        
        for modem_id, modem in self.simulator.modems.items():
            sim_slots = []
            for slot, sim in modem.sim_slots.items():
                sim_slots.append({
                    "slot": slot,
                    "status": sim.status if sim else "absent"
                })
            
            modems_data.append({
                "id": modem_id,
                "status": modem.status.value,
                "model": modem.model,
                "sim_slots": sim_slots
            })
        
        return {
            "modem_count": len(self.simulator.modems),
            "sim_slots": 2,
            "modems": modems_data,
            "dhcp_leases": self.simulator.network_environment.dhcp_leases
        }
    
    def _get_sim_details(self, modem_id: str, slot: int) -> Optional[Dict]:
        """Get SIM card details"""
        if modem_id not in self.simulator.modems:
            return None
        
        modem = self.simulator.modems[modem_id]
        if slot not in modem.sim_slots or not modem.sim_slots[slot]:
            return None
        
        sim = modem.sim_slots[slot]
        return {
            "iccid": sim.iccid,
            "imsi": sim.imsi,
            "carrier": sim.carrier,
            "carrier_code": sim.carrier_code,
            "rsrp": sim.rsrp,
            "rsrq": sim.rsrq,
            "signal_strength": sim.signal_strength,
            "network_type": sim.network_type,
            "roaming": sim.roaming,
            "data_usage": sim.data_usage
        }
    
    def _get_network_statistics(self) -> Dict:
        """Get network statistics"""
        interfaces = {}
        
        for name, iface in self.simulator.network_interfaces.items():
            interfaces[name] = {
                "bytes_sent": iface.bytes_sent,
                "bytes_received": iface.bytes_received,
                "packets_sent": iface.packets_sent,
                "packets_received": iface.packets_received,
                "errors": iface.errors,
                "dropped": iface.dropped
            }
        
        return {"interfaces": interfaces}
    
    def put(self, path: str, data: Dict) -> Dict:
        """Handle PUT requests"""
        self.log(f"PUT {path}: {data}")
        return {"success": True}


# Convenience functions for creating specific test scenarios
def create_single_sim_scenario() -> MockHardwareSimulator:
    """Create mock environment with single SIM configuration"""
    simulator = MockHardwareSimulator()
    
    # Keep only SIM in slot 1
    modem = simulator.modems["modem0"]
    modem.remove_sim(2)
    
    return simulator


def create_dual_sim_scenario() -> MockHardwareSimulator:
    """Create mock environment with dual SIM configuration"""
    return MockHardwareSimulator()  # Default configuration


def create_poor_signal_scenario() -> MockHardwareSimulator:
    """Create mock environment with poor signal conditions"""
    simulator = MockHardwareSimulator()
    
    # Degrade all SIM signals
    for modem in simulator.modems.values():
        for sim in modem.sim_slots.values():
            if sim:
                sim.rsrp = -115.0  # Very poor signal
                sim.signal_strength = 25
    
    # Set poor network conditions
    simulator.network_environment.simulate_network_conditions("poor")
    
    return simulator


def create_network_conflict_scenario() -> MockHardwareSimulator:
    """Create mock environment with IP conflicts"""
    simulator = MockHardwareSimulator()
    
    # Add conflicting DHCP leases
    simulator.network_environment.add_dhcp_lease("192.168.1.50", "aa:bb:cc:dd:ee:01", "conflicting_device1")
    simulator.network_environment.add_dhcp_lease("192.168.1.51", "aa:bb:cc:dd:ee:02", "conflicting_device2")
    simulator.network_environment.add_dhcp_lease("192.168.1.52", "aa:bb:cc:dd:ee:03", "conflicting_device3")
    
    # Add ARP entries
    simulator.network_environment.add_arp_entry("192.168.1.60", "aa:bb:cc:dd:ee:04")
    simulator.network_environment.add_arp_entry("192.168.1.61", "aa:bb:cc:dd:ee:05")
    
    return simulator


if __name__ == "__main__":
    # Example usage and testing
    print("🔧 Mock Framework Test")
    print("=" * 50)
    
    # Create simulator
    simulator = MockHardwareSimulator()
    client = MockFrameworkClient(simulator)
    
    # Start simulation
    simulator.start_simulation()
    
    # Test basic functionality
    print("Testing modem status...")
    modem_status = simulator.get_modem_status("modem0")
    print(f"Modem temperature: {modem_status['temperature']:.1f}°C")
    print(f"Active SIM: {modem_status['active_sim']}")
    
    print("\nTesting network interfaces...")
    interfaces = simulator.get_network_interfaces()
    for name, iface in interfaces.items():
        print(f"{name}: {iface['ip']} ({iface['status']})")
    
    print("\nTesting connectivity...")
    connectivity = simulator.network_environment.test_connectivity()
    print(f"Ping test: {connectivity['success']}, Latency: {connectivity.get('latency', 0):.1f}ms")
    
    print("\nTesting speed test...")
    speed_test = simulator.network_environment.run_speed_test()
    print(f"Download: {speed_test['download_speed']:.1f} Mbps, Upload: {speed_test['upload_speed']:.1f} Mbps")
    
    # Test SIM hot-swap
    print("\nTesting SIM hot-swap...")
    simulator.simulate_sim_hotswap("modem0", 2, "remove")
    time.sleep(1)
    simulator.simulate_sim_hotswap("modem0", 2, "insert")
    
    # Let simulation run briefly
    print("\nRunning simulation for 3 seconds...")
    time.sleep(3)
    
    # Stop simulation
    simulator.stop_simulation()
    
    print("\n✅ Mock framework test completed successfully!") 