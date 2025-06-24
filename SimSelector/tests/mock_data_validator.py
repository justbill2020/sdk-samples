#!/usr/bin/env python3
"""
Mock Data Validator for SimSelector Testing
==========================================
This tool validates that mock test scenarios accurately represent real Cradlepoint hardware.
"""

import json
import sys
import os
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mock_framework import MockScenarios


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    message: str
    field: str
    expected: Any = None
    actual: Any = None


class MockDataValidator:
    """Validates mock data against real-world constraints."""
    
    # Real carrier MCC/MNC combinations (US carriers)
    VALID_CARRIERS = {
        '310030': 'Centennial/Comcast',
        '310120': 'Sprint', 
        '310170': 'T-Mobile',
        '310260': 'T-Mobile',
        '310410': 'AT&T',
        '310480': 'Verizon',
        '311480': 'Verizon',
        '311580': 'US Cellular',
        '311882': 'T-Mobile Wholesale',
        '313100': 'FirstNet (AT&T)',
        # Canadian carriers for roaming tests
        '302220': 'Telus',
        '302720': 'Rogers'
    }
    
    # Valid RF bands for different technologies
    VALID_RF_BANDS = {
        '5G': ['B28', 'B2', 'B71', 'B260', 'B261'],  # mmWave and sub-6
        'LTE': ['B2', 'B4', 'B5', 'B7', 'B12', 'B13', 'B14', 'B71']
    }
    
    # RSRP value ranges (dBm)
    RSRP_RANGES = {
        'excellent': (-50, -70),
        'good': (-70, -90),
        'weak': (-90, -105),
        'bad': (-105, -120)
    }
    
    # Speed ranges by technology (Mbps)
    SPEED_RANGES = {
        '5G': {'download': (10, 1000), 'upload': (1, 150)},
        'LTE': {'download': (1, 150), 'upload': (0.5, 50)}
    }

    def __init__(self):
        self.results: List[ValidationResult] = []
    
    def validate_scenario(self, scenario_name: str, scenario_data: Dict) -> List[ValidationResult]:
        """Validate a complete test scenario."""
        self.results = []
        
        print(f"🔍 Validating Scenario: {scenario_name}")
        print("=" * 50)
        
        # Basic structure validation
        self._validate_scenario_structure(scenario_data)
        
        # Validate each SIM
        for sim_uid, sim_data in scenario_data.items():
            print(f"\n📱 Validating {sim_uid}:")
            self._validate_sim_data(sim_uid, sim_data)
        
        # Cross-SIM validation
        self._validate_cross_sim_consistency(scenario_data)
        
        return self.results
    
    def _validate_scenario_structure(self, scenario_data: Dict):
        """Validate basic scenario structure."""
        if not scenario_data:
            self._add_result('ERROR', 'scenario_structure', 
                           "Scenario data is empty")
            return
        
        if len(scenario_data) < 2:
            self._add_result('WARNING', 'scenario_structure',
                           f"Only {len(scenario_data)} SIM(s) - SimSelector requires minimum 2 SIMs",
                           expected="≥ 2 SIMs", actual=f"{len(scenario_data)} SIMs")
        
        # Check SIM naming convention
        for sim_uid in scenario_data.keys():
            if not sim_uid.startswith('mdm-'):
                self._add_result('ERROR', 'sim_naming',
                               f"Invalid SIM UID format: {sim_uid}",
                               expected="mdm-*", actual=sim_uid)
    
    def _validate_sim_data(self, sim_uid: str, sim_data: Dict):
        """Validate individual SIM data."""
        # Required fields
        required_fields = ['info', 'config', 'diagnostics', 'status']
        for field in required_fields:
            if field not in sim_data:
                self._add_result('ERROR', f'{sim_uid}.{field}',
                               f"Missing required field: {field}")
                continue
        
        # Validate info section
        if 'info' in sim_data:
            self._validate_sim_info(sim_uid, sim_data['info'])
        
        # Validate diagnostics
        if 'diagnostics' in sim_data:
            self._validate_sim_diagnostics(sim_uid, sim_data['diagnostics'])
        
        # Validate status
        if 'status' in sim_data:
            self._validate_sim_status(sim_uid, sim_data['status'])
        
        # Validate expected speeds
        self._validate_expected_speeds(sim_uid, sim_data)
    
    def _validate_sim_info(self, sim_uid: str, info: Dict):
        """Validate SIM info section."""
        required_info = ['port', 'sim', 'tech', 'iface']
        for field in required_info:
            if field not in info:
                self._add_result('ERROR', f'{sim_uid}.info.{field}',
                               f"Missing info field: {field}")
        
        # Validate technology
        if 'tech' in info:
            tech = info['tech']
            if tech not in ['5G', 'LTE', 'lte/3g']:
                self._add_result('WARNING', f'{sim_uid}.info.tech',
                               f"Unusual technology: {tech}",
                               expected="5G, LTE, or lte/3g", actual=tech)
        
        # Validate port naming
        if 'port' in info:
            port = info['port']
            if not re.match(r'MODEM\d+', port):
                self._add_result('WARNING', f'{sim_uid}.info.port',
                               f"Non-standard port name: {port}",
                               expected="MODEM1, MODEM2, etc.", actual=port)
        
        # Validate interface naming
        if 'iface' in info:
            iface = info['iface']
            if not re.match(r'wwan\d+', iface):
                self._add_result('WARNING', f'{sim_uid}.info.iface',
                               f"Non-standard interface name: {iface}",
                               expected="wwan0, wwan1, etc.", actual=iface)
    
    def _validate_sim_diagnostics(self, sim_uid: str, diagnostics: Dict):
        """Validate SIM diagnostics section."""
        required_diagnostics = ['RSRP', 'PRD', 'HOMECARRID', 'RFBAND']
        for field in required_diagnostics:
            if field not in diagnostics:
                self._add_result('ERROR', f'{sim_uid}.diagnostics.{field}',
                               f"Missing diagnostics field: {field}")
        
        # Validate RSRP
        if 'RSRP' in diagnostics:
            rsrp = diagnostics['RSRP']
            if not isinstance(rsrp, (int, float)):
                self._add_result('ERROR', f'{sim_uid}.diagnostics.RSRP',
                               f"RSRP must be numeric: {rsrp}")
            elif rsrp > -30 or rsrp < -140:
                self._add_result('WARNING', f'{sim_uid}.diagnostics.RSRP',
                               f"RSRP value outside realistic range: {rsrp} dBm",
                               expected="-30 to -140 dBm", actual=f"{rsrp} dBm")
        
        # Validate carrier
        if 'HOMECARRID' in diagnostics:
            carrier_id = diagnostics['HOMECARRID']
            if carrier_id not in self.VALID_CARRIERS:
                self._add_result('WARNING', f'{sim_uid}.diagnostics.HOMECARRID',
                               f"Unknown carrier MCC/MNC: {carrier_id}")
            else:
                carrier_name = self.VALID_CARRIERS[carrier_id]
                if 'PRD' in diagnostics and carrier_name not in diagnostics['PRD']:
                    self._add_result('WARNING', f'{sim_uid}.diagnostics',
                                   f"Carrier mismatch: PRD='{diagnostics['PRD']}' vs HOMECARRID='{carrier_id}' ({carrier_name})")
        
        # Validate RF Band
        if 'RFBAND' in diagnostics and 'tech' in diagnostics:
            tech = diagnostics.get('tech', 'LTE')  # Default to LTE if not specified
            rf_band = diagnostics['RFBAND']
            
            valid_bands = self.VALID_RF_BANDS.get(tech, [])
            if rf_band not in valid_bands and tech in self.VALID_RF_BANDS:
                self._add_result('WARNING', f'{sim_uid}.diagnostics.RFBAND',
                               f"RF Band {rf_band} unusual for {tech}",
                               expected=f"Common {tech} bands: {valid_bands}",
                               actual=rf_band)
    
    def _validate_sim_status(self, sim_uid: str, status: Dict):
        """Validate SIM status section."""
        if 'connection_state' in status:
            conn_state = status['connection_state']
            valid_states = ['connected', 'disconnected', 'connecting', 'idle']
            if conn_state not in valid_states:
                self._add_result('WARNING', f'{sim_uid}.status.connection_state',
                               f"Unusual connection state: {conn_state}",
                               expected=valid_states, actual=conn_state)
        
        # Validate error_text consistency
        if 'error_text' in status:
            error_text = status['error_text']
            conn_state = status.get('connection_state', '')
            
            if error_text and conn_state == 'connected':
                self._add_result('WARNING', f'{sim_uid}.status',
                               "Error text present but connection state is 'connected'")
            elif not error_text and conn_state == 'disconnected':
                self._add_result('INFO', f'{sim_uid}.status',
                               "Disconnected state without error text - consider adding reason")
    
    def _validate_expected_speeds(self, sim_uid: str, sim_data: Dict):
        """Validate expected speed values."""
        tech = sim_data.get('info', {}).get('tech', 'LTE')
        expected_dl = sim_data.get('expected_download', 0)
        expected_ul = sim_data.get('expected_upload', 0)
        
        if tech in self.SPEED_RANGES:
            dl_range = self.SPEED_RANGES[tech]['download']
            ul_range = self.SPEED_RANGES[tech]['upload']
            
            if not (dl_range[0] <= expected_dl <= dl_range[1]):
                self._add_result('WARNING', f'{sim_uid}.expected_download',
                               f"Expected download speed outside realistic {tech} range",
                               expected=f"{dl_range[0]}-{dl_range[1]} Mbps",
                               actual=f"{expected_dl} Mbps")
            
            if not (ul_range[0] <= expected_ul <= ul_range[1]):
                self._add_result('WARNING', f'{sim_uid}.expected_upload',
                               f"Expected upload speed outside realistic {tech} range",
                               expected=f"{ul_range[0]}-{ul_range[1]} Mbps",
                               actual=f"{expected_ul} Mbps")
        
        # Validate upload/download ratio
        if expected_dl > 0 and expected_ul > 0:
            ratio = expected_ul / expected_dl
            if ratio > 0.5:  # Upload rarely exceeds 50% of download
                self._add_result('WARNING', f'{sim_uid}.speed_ratio',
                               f"Upload/Download ratio unusually high: {ratio:.2f}",
                               expected="< 0.5", actual=f"{ratio:.2f}")
    
    def _validate_cross_sim_consistency(self, scenario_data: Dict):
        """Validate consistency across SIMs in scenario."""
        sims = list(scenario_data.values())
        
        # Check for duplicate interfaces
        interfaces = [sim.get('info', {}).get('iface') for sim in sims]
        interface_counts = {}
        for iface in interfaces:
            if iface:
                interface_counts[iface] = interface_counts.get(iface, 0) + 1
        
        for iface, count in interface_counts.items():
            if count > 1:
                self._add_result('ERROR', 'cross_sim.interfaces',
                               f"Duplicate interface {iface} used by {count} SIMs")
        
        # Check for reasonable speed distribution
        speeds = [(sim.get('expected_download', 0), sim.get('expected_upload', 0)) 
                 for sim in sims]
        downloads = [s[0] for s in speeds if s[0] > 0]
        
        if len(downloads) > 1:
            max_dl = max(downloads)
            min_dl = min(downloads)
            if max_dl > 0 and min_dl / max_dl > 0.9:  # All speeds within 10%
                self._add_result('INFO', 'cross_sim.speed_distribution',
                               "All SIMs have very similar speeds - consider more variation for realistic testing")
    
    def _add_result(self, severity: str, field: str, message: str, 
                   expected: Any = None, actual: Any = None):
        """Add a validation result."""
        result = ValidationResult(
            is_valid=(severity != 'ERROR'),
            severity=severity,
            field=field,
            message=message,
            expected=expected,
            actual=actual
        )
        self.results.append(result)
        
        # Print result immediately
        icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}[severity]
        print(f"  {icon} {severity}: {message}")
        if expected and actual:
            print(f"     Expected: {expected}")
            print(f"     Actual: {actual}")
    
    def generate_report(self) -> str:
        """Generate a validation report."""
        errors = [r for r in self.results if r.severity == 'ERROR']
        warnings = [r for r in self.results if r.severity == 'WARNING']
        infos = [r for r in self.results if r.severity == 'INFO']
        
        report = f"""
📊 Mock Data Validation Report
==============================
Total Issues: {len(self.results)}
❌ Errors: {len(errors)}
⚠️ Warnings: {len(warnings)}
ℹ️ Info: {len(infos)}

"""
        
        if errors:
            report += "🚨 ERRORS (Must Fix):\n"
            for error in errors:
                report += f"  - {error.field}: {error.message}\n"
            report += "\n"
        
        if warnings:
            report += "⚠️ WARNINGS (Should Review):\n"
            for warning in warnings:
                report += f"  - {warning.field}: {warning.message}\n"
            report += "\n"
        
        if not errors and not warnings:
            report += "✅ All validations passed! Mock data appears realistic.\n"
        
        return report


def validate_all_scenarios():
    """Validate all predefined mock scenarios."""
    validator = MockDataValidator()
    
    scenarios = [
        ("Dual SIM - Good Signals", MockScenarios.dual_sim_good_signals()),
        ("Dual SIM - One Weak Signal", MockScenarios.dual_sim_one_weak()),
        ("Dual SIM - One Failed Connection", MockScenarios.dual_sim_one_failed()),
        ("Triple SIM - Mixed Performance", MockScenarios.triple_sim_mixed_performance()),
        ("Quad SIM - All Major Carriers", MockScenarios.quad_sim_all_carriers()),
        ("All Weak Signals", MockScenarios.all_weak_signals()),
        ("All Failed Connections", MockScenarios.all_failed_connections()),
        ("High Speed 5G", MockScenarios.high_speed_5g_scenario()),
        ("Edge Case - Tie Breaker", MockScenarios.edge_case_tie_breaker()),
        ("Carrier Specific APN", MockScenarios.carrier_specific_apn_test()),
        ("International Roaming", MockScenarios.international_roaming()),
        ("MVNO Carriers", MockScenarios.mvno_carriers()),
    ]
    
    print("🧪 Validating All Mock Scenarios")
    print("=" * 60)
    
    all_results = []
    for scenario_name, scenario_data in scenarios:
        results = validator.validate_scenario(scenario_name, scenario_data)
        all_results.extend(results)
        print()
    
    # Overall summary
    total_errors = len([r for r in all_results if r.severity == 'ERROR'])
    total_warnings = len([r for r in all_results if r.severity == 'WARNING'])
    
    print("🏁 Overall Validation Summary:")
    print("=" * 40)
    print(f"Scenarios Tested: {len(scenarios)}")
    print(f"Total Errors: {total_errors}")
    print(f"Total Warnings: {total_warnings}")
    
    if total_errors == 0:
        print("✅ All scenarios passed validation!")
    else:
        print("❌ Some scenarios have validation errors that should be fixed.")
    
    return total_errors == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate SimSelector mock data')
    parser.add_argument('--scenario', help='Validate specific scenario')
    parser.add_argument('--all', action='store_true', help='Validate all scenarios')
    
    args = parser.parse_args()
    
    if args.all:
        validate_all_scenarios()
    else:
        print("Usage: python mock_data_validator.py --all")
        print("       python mock_data_validator.py --scenario <scenario_name>") 