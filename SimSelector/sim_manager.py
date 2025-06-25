"""
SIM Manager for SimSelector v2.6.0 Error Handling & Edge Cases

Handles SIM card detection, validation, and edge cases:
- Single SIM modem detection and handling
- SIM slot validation and error reporting
- Fallback logic for missing SIM scenarios
- SIM insertion detection and hot-swap support
- Comprehensive error handling for all SIM-related failures

Features:
- NetCloud SDK-based SIM status monitoring
- Automatic SIM detection and validation
- Single-SIM fallback modes
- Hot-swap detection and handling
- Comprehensive error reporting and recovery
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from SimSelector import Phase
    from state_manager import get_state, set_state
    from error_handler import SimSelectorError, ErrorSeverity, get_error_handler
except ImportError:
    class Phase:
        STAGING = 0
        INSTALL = 1
        DEPLOYED = 2
    
    class ErrorSeverity:
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    
    class SimSelectorError(Exception):
        def __init__(self, message, severity=None, error_type=None):
            super().__init__(message)
            self.severity = severity
            self.error_type = error_type
    
    def get_error_handler():
        return None


class SIMStatus(Enum):
    """SIM card status enumeration"""
    UNKNOWN = "unknown"
    PRESENT = "present"
    ABSENT = "absent"
    ACTIVE = "active"
    STANDBY = "standby"
    ERROR = "error"
    INITIALIZING = "initializing"


class SIMType(Enum):
    """SIM card type enumeration"""
    UNKNOWN = "unknown"
    STANDARD = "standard"
    MICRO = "micro"
    NANO = "nano"
    ESIM = "esim"


@dataclass
class SIMCard:
    """SIM card information"""
    slot: int
    status: SIMStatus
    iccid: Optional[str] = None
    imsi: Optional[str] = None
    carrier: Optional[str] = None
    carrier_code: Optional[str] = None
    rsrp: Optional[float] = None
    rsrq: Optional[float] = None
    signal_strength: Optional[int] = None
    network_type: Optional[str] = None
    roaming: bool = False
    sim_type: SIMType = SIMType.UNKNOWN
    last_seen: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None


class SIMManager:
    """Comprehensive SIM card management with error handling and edge cases"""
    
    def __init__(self, client=None):
        self.client = client
        self.sim_cards = {}  # slot -> SIMCard
        self.active_sim = None
        self.monitoring_thread = None
        self.monitoring_enabled = False
        self.single_sim_mode = False
        self.hot_swap_enabled = True
        
        # Configuration
        self.max_detection_retries = 3
        self.detection_timeout = 30.0
        self.hot_swap_check_interval = 10.0
        self.signal_threshold_rsrp = -110  # dBm
        
        # State tracking
        self.last_scan_time = 0
        self.scan_count = 0
        self.detection_failures = 0
        self.sim_change_callbacks = []
        
        # Error handling
        try:
            self.error_handler = get_error_handler()
        except:
            self.error_handler = None
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log SIM operations"""
        if self.client:
            self.client.log(f"SIM [{level}] {message}")
        else:
            print(f"SIM [{level}] {message}")
    
    def _get_modem_info(self) -> Dict[str, Any]:
        """Get modem information from NetCloud SDK"""
        try:
            if not self.client:
                # Mock data for testing
                return {
                    "modem_count": 1,
                    "sim_slots": 2,
                    "modems": [
                        {
                            "id": "modem0",
                            "status": "connected",
                            "sim_slots": [
                                {"slot": 1, "status": "present"},
                                {"slot": 2, "status": "absent"}
                            ]
                        }
                    ]
                }
            
            # Get real modem info from NetCloud
            modem_status = self.client.get("status/wan/devices")
            return modem_status if modem_status else {}
            
        except Exception as e:
            self._log(f"Error getting modem info: {str(e)}", "ERROR")
            return {}
    
    def _get_sim_details(self, slot: int) -> Optional[Dict[str, Any]]:
        """Get detailed SIM information for specific slot"""
        try:
            if not self.client:
                # Mock SIM data
                if slot == 1:
                    return {
                        "iccid": "89014103211118510720",
                        "imsi": "310410118510720", 
                        "carrier": "Verizon",
                        "carrier_code": "311480",
                        "rsrp": -85.5,
                        "rsrq": -12.0,
                        "signal_strength": 75,
                        "network_type": "LTE",
                        "roaming": False
                    }
                return None
            
            # Get real SIM details
            sim_info = self.client.get(f"status/wan/devices/modem0/sim{slot}")
            return sim_info
            
        except Exception as e:
            self._log(f"Error getting SIM details for slot {slot}: {str(e)}", "WARNING")
            return None
    
    def detect_sim_configuration(self) -> Dict[str, Any]:
        """Detect current SIM configuration and handle edge cases"""
        try:
            self._log("Detecting SIM configuration...")
            self.scan_count += 1
            
            modem_info = self._get_modem_info()
            if not modem_info:
                self.detection_failures += 1
                if self.error_handler:
                    raise SimSelectorError(
                        "Failed to get modem information",
                        ErrorSeverity.HIGH,
                        "sim_detection_failure"
                    )
                else:
                    raise Exception("Failed to get modem information")
            
            detected_sims = {}
            total_slots = 0
            present_sims = 0
            
            # Process each modem
            for modem in modem_info.get("modems", []):
                modem_id = modem.get("id", "unknown")
                sim_slots = modem.get("sim_slots", [])
                total_slots += len(sim_slots)
                
                for slot_info in sim_slots:
                    slot = slot_info.get("slot")
                    status = slot_info.get("status", "unknown")
                    
                    if status in ["present", "active"]:
                        present_sims += 1
                        sim_details = self._get_sim_details(slot)
                        
                        sim_card = SIMCard(
                            slot=slot,
                            status=SIMStatus.PRESENT if status == "present" else SIMStatus.ACTIVE,
                            last_seen=time.time()
                        )
                        
                        if sim_details:
                            sim_card.iccid = sim_details.get("iccid")
                            sim_card.imsi = sim_details.get("imsi")
                            sim_card.carrier = sim_details.get("carrier")
                            sim_card.carrier_code = sim_details.get("carrier_code")
                            sim_card.rsrp = sim_details.get("rsrp")
                            sim_card.rsrq = sim_details.get("rsrq")
                            sim_card.signal_strength = sim_details.get("signal_strength")
                            sim_card.network_type = sim_details.get("network_type")
                            sim_card.roaming = sim_details.get("roaming", False)
                        
                        detected_sims[slot] = sim_card
                        self._log(f"SIM detected in slot {slot}: {sim_card.carrier or 'Unknown carrier'}")
                    
                    elif status == "absent":
                        detected_sims[slot] = SIMCard(
                            slot=slot,
                            status=SIMStatus.ABSENT,
                            last_seen=time.time()
                        )
            
            # Handle edge cases
            config_result = self._handle_sim_configuration(detected_sims, total_slots, present_sims)
            
            # Update internal state
            old_sim_cards = self.sim_cards.copy()
            self.sim_cards = detected_sims
            self.last_scan_time = time.time()
            
            # Check for changes and notify
            if self._sims_changed(old_sim_cards, detected_sims):
                self._notify_sim_change()
            
            return config_result
            
        except Exception as e:
            self.detection_failures += 1
            self._log(f"SIM detection failed: {str(e)}", "ERROR")
            
            if self.error_handler:
                self.error_handler.handle_error(e, context="sim_detection")
            
            return {
                "success": False,
                "error": str(e),
                "fallback_mode": True
            }
    
    def _handle_sim_configuration(self, detected_sims: Dict[int, SIMCard], total_slots: int, present_sims: int) -> Dict[str, Any]:
        """Handle different SIM configuration scenarios"""
        try:
            config_type = "unknown"
            recommendations = []
            warnings = []
            
            if present_sims == 0:
                # No SIMs detected
                config_type = "no_sims"
                warnings.append("No SIM cards detected - system cannot operate")
                recommendations.extend([
                    "Insert at least one activated SIM card",
                    "Verify SIM cards are properly seated",
                    "Check SIM card activation status with carrier"
                ])
                
                # Enter emergency fallback mode
                return self._enter_fallback_mode("no_sims_detected", warnings, recommendations)
            
            elif present_sims == 1:
                # Single SIM configuration
                config_type = "single_sim"
                self.single_sim_mode = True
                
                active_sim = list(detected_sims.values())[0]
                self.active_sim = active_sim.slot
                
                warnings.append("Single SIM configuration - no failover capability")
                recommendations.extend([
                    "Consider installing a second SIM for redundancy",
                    "Monitor signal quality closely",
                    "Ensure primary SIM has sufficient data allowance"
                ])
                
                self._log(f"Single SIM mode enabled - using slot {active_sim.slot}")
                
            elif present_sims == 2:
                # Dual SIM configuration (optimal)
                config_type = "dual_sim"
                self.single_sim_mode = False
                
                # Select primary SIM based on signal strength
                primary_sim = self._select_primary_sim(detected_sims)
                if primary_sim:
                    self.active_sim = primary_sim.slot
                    recommendations.append(f"Primary SIM selected: Slot {primary_sim.slot} ({primary_sim.carrier})")
                
            elif present_sims > 2:
                # More than 2 SIMs (unusual but handle gracefully)
                config_type = "multi_sim"
                warnings.append(f"Unusual configuration: {present_sims} SIMs detected")
                recommendations.append("System designed for 1-2 SIMs - additional SIMs will be ignored")
                
                # Use best 2 SIMs
                best_sims = self._select_best_sims(detected_sims, 2)
                for slot in list(detected_sims.keys()):
                    if slot not in [sim.slot for sim in best_sims]:
                        detected_sims[slot].status = SIMStatus.STANDBY
            
            # Validate SIM quality
            quality_issues = self._validate_sim_quality(detected_sims)
            if quality_issues:
                warnings.extend(quality_issues)
            
            return {
                "success": True,
                "config_type": config_type,
                "total_slots": total_slots,
                "present_sims": present_sims,
                "active_sim": self.active_sim,
                "single_sim_mode": self.single_sim_mode,
                "warnings": warnings,
                "recommendations": recommendations,
                "sim_details": {
                    slot: {
                        "status": sim.status.value,
                        "carrier": sim.carrier,
                        "signal_strength": sim.signal_strength,
                        "rsrp": sim.rsrp
                    }
                    for slot, sim in detected_sims.items()
                }
            }
            
        except Exception as e:
            self._log(f"Error handling SIM configuration: {str(e)}", "ERROR")
            return self._enter_fallback_mode("configuration_error", [str(e)], ["Contact support"])
    
    def _select_primary_sim(self, sims: Dict[int, SIMCard]) -> Optional[SIMCard]:
        """Select primary SIM based on signal quality and carrier preference"""
        try:
            available_sims = [sim for sim in sims.values() if sim.status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]]
            
            if not available_sims:
                return None
            
            # Score SIMs based on signal quality
            scored_sims = []
            for sim in available_sims:
                score = 0
                
                # Signal strength scoring (0-100)
                if sim.rsrp:
                    if sim.rsrp > -80:
                        score += 100
                    elif sim.rsrp > -90:
                        score += 80
                    elif sim.rsrp > -100:
                        score += 60
                    elif sim.rsrp > -110:
                        score += 40
                    else:
                        score += 20
                
                # Carrier preference (Verizon > AT&T > T-Mobile > Others)
                carrier_scores = {
                    "verizon": 30,
                    "at&t": 25,
                    "t-mobile": 20,
                    "att": 25
                }
                
                if sim.carrier:
                    carrier_lower = sim.carrier.lower()
                    for carrier, bonus in carrier_scores.items():
                        if carrier in carrier_lower:
                            score += bonus
                            break
                
                # Network type preference (5G > LTE > 3G > 2G)
                if sim.network_type:
                    net_type = sim.network_type.upper()
                    if "5G" in net_type:
                        score += 20
                    elif "LTE" in net_type:
                        score += 15
                    elif "3G" in net_type:
                        score += 10
                    elif "2G" in net_type:
                        score += 5
                
                scored_sims.append((sim, score))
            
            # Return highest scoring SIM
            scored_sims.sort(key=lambda x: x[1], reverse=True)
            primary_sim = scored_sims[0][0]
            
            self._log(f"Selected primary SIM: Slot {primary_sim.slot} (score: {scored_sims[0][1]})")
            return primary_sim
            
        except Exception as e:
            self._log(f"Error selecting primary SIM: {str(e)}", "ERROR")
            return available_sims[0] if available_sims else None
    
    def _select_best_sims(self, sims: Dict[int, SIMCard], count: int) -> List[SIMCard]:
        """Select best N SIMs from available options"""
        available_sims = [sim for sim in sims.values() if sim.status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]]
        
        # Use same scoring logic as primary selection
        scored_sims = []
        for sim in available_sims:
            score = 0
            if sim.rsrp and sim.rsrp > self.signal_threshold_rsrp:
                score = max(0, sim.rsrp + 120)  # Convert dBm to positive score
            scored_sims.append((sim, score))
        
        # Return top N SIMs
        scored_sims.sort(key=lambda x: x[1], reverse=True)
        return [sim for sim, score in scored_sims[:count]]
    
    def _validate_sim_quality(self, sims: Dict[int, SIMCard]) -> List[str]:
        """Validate SIM signal quality and return issues"""
        issues = []
        
        for sim in sims.values():
            if sim.status not in [SIMStatus.PRESENT, SIMStatus.ACTIVE]:
                continue
            
            # Check signal strength
            if sim.rsrp and sim.rsrp < self.signal_threshold_rsrp:
                issues.append(f"Slot {sim.slot}: Poor signal strength ({sim.rsrp} dBm)")
            
            # Check carrier identification
            if not sim.carrier:
                issues.append(f"Slot {sim.slot}: Carrier not identified")
            
            # Check network registration
            if not sim.network_type:
                issues.append(f"Slot {sim.slot}: No network connection")
            
            # Check roaming status
            if sim.roaming:
                issues.append(f"Slot {sim.slot}: Roaming active - may incur charges")
        
        return issues
    
    def _enter_fallback_mode(self, reason: str, warnings: List[str], recommendations: List[str]) -> Dict[str, Any]:
        """Enter fallback mode for SIM configuration issues"""
        self._log(f"Entering fallback mode: {reason}", "WARNING")
        
        # Set system state
        try:
            set_state("sim_fallback_mode", True)
            set_state("sim_fallback_reason", reason)
        except:
            pass  # State manager may not be available
        
        return {
            "success": False,
            "fallback_mode": True,
            "reason": reason,
            "warnings": warnings,
            "recommendations": recommendations,
            "requires_intervention": True
        }
    
    def handle_hot_swap(self, old_config: Dict[int, SIMCard], new_config: Dict[int, SIMCard]) -> bool:
        """Handle SIM hot-swap scenarios"""
        try:
            if not self.hot_swap_enabled:
                return False
            
            changes = []
            
            # Detect insertions
            for slot, new_sim in new_config.items():
                if slot not in old_config or old_config[slot].status == SIMStatus.ABSENT:
                    if new_sim.status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]:
                        changes.append(f"SIM inserted in slot {slot}")
                        self._log(f"Hot-swap: SIM inserted in slot {slot}")
            
            # Detect removals
            for slot, old_sim in old_config.items():
                if slot not in new_config or new_config[slot].status == SIMStatus.ABSENT:
                    if old_sim.status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]:
                        changes.append(f"SIM removed from slot {slot}")
                        self._log(f"Hot-swap: SIM removed from slot {slot}")
                        
                        # Handle active SIM removal
                        if slot == self.active_sim:
                            self._handle_active_sim_removal(new_config)
            
            if changes:
                self._log(f"Hot-swap detected: {'; '.join(changes)}")
                # Trigger reconfiguration
                self.detect_sim_configuration()
                return True
            
            return False
            
        except Exception as e:
            self._log(f"Error handling hot-swap: {str(e)}", "ERROR")
            return False
    
    def _handle_active_sim_removal(self, remaining_sims: Dict[int, SIMCard]) -> None:
        """Handle removal of currently active SIM"""
        try:
            self._log("Active SIM removed - selecting new primary", "WARNING")
            
            # Find alternative SIM
            available_sims = [sim for sim in remaining_sims.values() 
                            if sim.status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]]
            
            if available_sims:
                new_primary = self._select_primary_sim(remaining_sims)
                if new_primary:
                    old_active = self.active_sim
                    self.active_sim = new_primary.slot
                    self._log(f"Switched from slot {old_active} to slot {new_primary.slot}")
                else:
                    self.active_sim = None
                    self._log("No suitable replacement SIM found", "ERROR")
            else:
                self.active_sim = None
                self.single_sim_mode = False
                self._log("No SIMs available - entering emergency mode", "ERROR")
                
                # Trigger emergency procedures
                if self.error_handler:
                    self.error_handler.handle_error(
                        SimSelectorError("All SIMs removed", ErrorSeverity.CRITICAL, "sim_removal"),
                        context="hot_swap"
                    )
                    
        except Exception as e:
            self._log(f"Error handling active SIM removal: {str(e)}", "ERROR")
    
    def start_monitoring(self) -> bool:
        """Start SIM monitoring thread"""
        try:
            if self.monitoring_enabled:
                return True
            
            self.monitoring_enabled = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            self._log("SIM monitoring started")
            return True
            
        except Exception as e:
            self._log(f"Error starting SIM monitoring: {str(e)}", "ERROR")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop SIM monitoring thread"""
        try:
            self.monitoring_enabled = False
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            self._log("SIM monitoring stopped")
            return True
            
        except Exception as e:
            self._log(f"Error stopping SIM monitoring: {str(e)}", "ERROR")
            return False
    
    def _monitoring_loop(self):
        """SIM monitoring loop"""
        while self.monitoring_enabled:
            try:
                old_config = self.sim_cards.copy()
                self.detect_sim_configuration()
                
                # Check for hot-swap
                if old_config:
                    self.handle_hot_swap(old_config, self.sim_cards)
                
                time.sleep(self.hot_swap_check_interval)
                
            except Exception as e:
                self._log(f"Error in SIM monitoring loop: {str(e)}", "ERROR")
                time.sleep(5)  # Shorter sleep on error
    
    def _sims_changed(self, old_sims: Dict[int, SIMCard], new_sims: Dict[int, SIMCard]) -> bool:
        """Check if SIM configuration has changed"""
        if len(old_sims) != len(new_sims):
            return True
        
        for slot, new_sim in new_sims.items():
            if slot not in old_sims:
                return True
            
            old_sim = old_sims[slot]
            if (old_sim.status != new_sim.status or 
                old_sim.iccid != new_sim.iccid or
                old_sim.carrier != new_sim.carrier):
                return True
        
        return False
    
    def add_sim_change_callback(self, callback):
        """Add callback for SIM configuration changes"""
        self.sim_change_callbacks.append(callback)
    
    def _notify_sim_change(self):
        """Notify callbacks of SIM configuration changes"""
        for callback in self.sim_change_callbacks:
            try:
                callback(self.sim_cards)
            except Exception as e:
                self._log(f"Error in SIM change callback: {str(e)}", "ERROR")
    
    def get_sim_status(self) -> Dict[str, Any]:
        """Get comprehensive SIM status"""
        return {
            "sim_cards": {
                slot: {
                    "status": sim.status.value,
                    "carrier": sim.carrier,
                    "iccid": sim.iccid,
                    "rsrp": sim.rsrp,
                    "signal_strength": sim.signal_strength,
                    "network_type": sim.network_type,
                    "roaming": sim.roaming,
                    "error_count": sim.error_count,
                    "last_error": sim.last_error
                }
                for slot, sim in self.sim_cards.items()
            },
            "active_sim": self.active_sim,
            "single_sim_mode": self.single_sim_mode,
            "monitoring_enabled": self.monitoring_enabled,
            "last_scan_time": self.last_scan_time,
            "scan_count": self.scan_count,
            "detection_failures": self.detection_failures,
            "hot_swap_enabled": self.hot_swap_enabled
        }
    
    def force_sim_rescan(self) -> Dict[str, Any]:
        """Force immediate SIM rescan"""
        self._log("Forcing SIM rescan...")
        return self.detect_sim_configuration()
    
    def set_active_sim(self, slot: int) -> bool:
        """Manually set active SIM slot"""
        try:
            if slot in self.sim_cards and self.sim_cards[slot].status in [SIMStatus.PRESENT, SIMStatus.ACTIVE]:
                old_active = self.active_sim
                self.active_sim = slot
                self._log(f"Active SIM changed from slot {old_active} to slot {slot}")
                return True
            else:
                self._log(f"Cannot set slot {slot} as active - SIM not available", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Error setting active SIM: {str(e)}", "ERROR")
            return False


# Global SIM manager instance
_sim_manager = None

def get_sim_manager(client=None):
    """Get or create SIM manager instance"""
    global _sim_manager
    if _sim_manager is None:
        _sim_manager = SIMManager(client)
    return _sim_manager

def detect_sim_configuration(client=None) -> Dict[str, Any]:
    """Detect SIM configuration"""
    sim_manager = get_sim_manager(client)
    return sim_manager.detect_sim_configuration()

def get_sim_status(client=None) -> Dict[str, Any]:
    """Get SIM status"""
    sim_manager = get_sim_manager(client)
    return sim_manager.get_sim_status() 