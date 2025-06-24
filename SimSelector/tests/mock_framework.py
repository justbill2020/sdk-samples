"""
Mock Framework for SimSelector Testing
=====================================
This module provides comprehensive mocking for testing SimSelector without real Cradlepoint hardware.
"""

import json
import time
import random
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, Optional, List
import sys
import os


class MockEventingCSClient:
    """Mock implementation of EventingCSClient for testing."""
    
    def __init__(self, name='SimSelector'):
        self.name = name
        self.logs = []
        self.alerts = []
        self.config_data = {
            '/config/wan/rules2': [],
            '/config/system/desc': '',
            '/config/system/asset_id': '',
            '/config/system/snmp/persisted_config': '',
            '/config/wan/dual_sim_disable_mask': '',
            '/config/wan/rem_dual_sim_disable_mask': '',
            '/config/wan/custom_apns': []
        }
        self.status_data = {
            '/status/wan/connection_state': 'connected',
            '/status/ecm/state': 'connected', 
            '/status/ecm/sync': 'ready',
            '/status/system/uptime': 120,  # 2 minutes
            '/status/wan/devices': {}
        }
        self.control_data = {}
        self.wan_devices = {}  # Add this attribute
        self.scenario_data = {}  # Add this attribute
        
        # Set up default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup realistic default router data."""
        # Simulate 2 SIM cards with different carriers
        self.status_data['/status/wan/devices'] = {
            'mdm-a1b2c3d4': {
                'info': {
                    'port': 'MODEM1',
                    'sim': 'SIM1',
                    'tech': '5G',
                    'iface': 'wwan0'
                },
                'config': {
                    '_id_': 'rule_001',
                    'priority': 1.0
                },
                'diagnostics': {
                    'RSRP': -85,
                    'PRD': 'Verizon',
                    'HOMECARRID': '311480',
                    'RFBAND': 'B2'
                },
                'status': {
                    'connection_state': 'connected',
                    'error_text': ''
                }
            },
            'mdm-e5f6g7h8': {
                'info': {
                    'port': 'MODEM2', 
                    'sim': 'SIM1',
                    'tech': 'LTE',
                    'iface': 'wwan1'
                },
                'config': {
                    '_id_': 'rule_002',
                    'priority': 1.1
                },
                'diagnostics': {
                    'RSRP': -95,
                    'PRD': 'T-Mobile',
                    'HOMECARRID': '310260',
                    'RFBAND': 'B4'
                },
                'status': {
                    'connection_state': 'connected',
                    'error_text': ''
                }
            }
        }
        
        self.config_data = {
            '/config/wan/rules2': [
                {
                    '_id_': 'rule_001',
                    'priority': 1.0,
                    'trigger_name': 'MODEM1 SIM1',
                    'trigger_string': 'type|is|mdm%sim|is|SIM1%port|is|MODEM1',
                    'disabled': False
                },
                {
                    '_id_': 'rule_002', 
                    'priority': 1.1,
                    'trigger_name': 'MODEM2 SIM1',
                    'trigger_string': 'type|is|mdm%sim|is|SIM1%port|is|MODEM2',
                    'disabled': False
                }
            ],
            '/config/system/desc': '',
            '/config/system/snmp/persisted_config': '',
            '/config/system/asset_id': '',
            '/config/wan/custom_apns': [],
            '/config/wan/dual_sim_disable_mask': '',
            '/config/wan/rem_dual_sim_disable_mask': ''
        }
    
    def get(self, path: str) -> Any:
        """Mock GET request to router API."""
        self.log(f"GET {path}")
        
        # Normalize path to always have leading slash
        normalized_path = path if path.startswith('/') else '/' + path
        
        # Handle status queries
        if normalized_path.startswith('/status'):
            return self._get_status_data(normalized_path)
        
        # Handle config queries
        if normalized_path.startswith('/config'):
            return self._get_config_data(normalized_path)
        
        return None
    
    def put(self, path: str, data: Any) -> Any:
        """Mock PUT request to router API."""
        self.log(f"PUT {path} = {data}")
        
        if path.startswith('/config'):
            self._set_config_data(path, data)
        elif path.startswith('/control'):
            self._handle_control(path, data)
        
        return True
    
    def post(self, path: str, data: Any) -> Dict[str, Any]:
        """Mock POST request to router API."""
        self.log(f"POST {path} = {data}")
        
        if path == '/config/wan/rules2/':
            # Simulate creating new WAN rule
            new_index = len(self.config_data['/config/wan/rules2'])
            new_rule = dict(data)
            new_rule['_id_'] = f'rule_{new_index:03d}'
            self.config_data['/config/wan/rules2'].append(new_rule)
            return {"data": new_index}
        
        return {"data": 0}
    
    def delete(self, path: str) -> Any:
        """Mock DELETE request to router API."""
        self.log(f"DELETE {path}")
        # For testing, just log the delete operation
        return True
    
    def log(self, message: str):
        """Mock logging function."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {self.name}: {message}"
        self.logs.append(log_entry)
        print(log_entry)  # Also print for real-time feedback
    
    def alert(self, message: str):
        """Mock alert function."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        alert_entry = f"[{timestamp}] ALERT - {self.name}: {message}"
        self.alerts.append(alert_entry)
        print(f"🚨 {alert_entry}")
    
    def _get_status_data(self, path: str) -> Any:
        """Get status data from mock."""
        # Handle direct path queries first
        if path in self.status_data:
            return self.status_data[path]
        
        # Handle specific device queries
        if '/status/wan/devices/' in path and '/diagnostics' in path:
            device_id = path.split('/')[4]
            if device_id in self.status_data['/status/wan/devices']:
                return self.status_data['/status/wan/devices'][device_id]['diagnostics']
        
        if '/status/wan/devices/' in path and '/status/connection_state' in path:
            device_id = path.split('/')[4]
            if device_id in self.status_data['/status/wan/devices']:
                return self.status_data['/status/wan/devices'][device_id]['status']['connection_state']
        
        if '/status/wan/devices/' in path and '/info/iface' in path:
            device_id = path.split('/')[4]
            if device_id in self.status_data['/status/wan/devices']:
                return self.status_data['/status/wan/devices'][device_id]['info']['iface']
        
        if '/status/wan/devices/' in path and '/config/' in path:
            device_id = path.split('/')[4]
            config_key = path.split('/')[-1]
            if device_id in self.status_data['/status/wan/devices']:
                return self.status_data['/status/wan/devices'][device_id]['config'].get(config_key)
        
        # Handle paths that might not have leading slash
        normalized_path = path if path.startswith('/') else '/' + path
        return self.status_data.get(normalized_path)
    
    def _get_config_data(self, path: str) -> Any:
        """Get config data from mock."""
        # Handle direct path queries first
        if path in self.config_data:
            return self.config_data[path]
        
        # Handle specific rule queries
        if '/config/wan/rules2/' in path and path != '/config/wan/rules2':
            parts = path.split('/')
            if len(parts) >= 5:
                rule_index_or_id = parts[4]
                
                # Find rule by index or ID
                rules = self.config_data['/config/wan/rules2']
                rule = None
                
                if rule_index_or_id.isdigit():
                    index = int(rule_index_or_id)
                    if 0 <= index < len(rules):
                        rule = rules[index]
                else:
                    rule = next((r for r in rules if r['_id_'] == rule_index_or_id), None)
                
                if rule and len(parts) > 5:
                    # Return specific field
                    field = parts[5]
                    return rule.get(field)
                
                return rule
        
        # Handle paths that might not have leading slash
        normalized_path = path if path.startswith('/') else '/' + path
        return self.config_data.get(normalized_path)
    
    def _set_config_data(self, path: str, data: Any):
        """Set config data in mock."""
        if '/config/wan/rules2/' in path and path != '/config/wan/rules2':
            parts = path.split('/')
            if len(parts) >= 5:
                rule_id = parts[4]
                
                # Find and update rule
                rules = self.config_data['/config/wan/rules2']
                for rule in rules:
                    if rule['_id_'] == rule_id:
                        if len(parts) > 5:
                            # Update specific field
                            field = parts[5]
                            rule[field] = data
                        else:
                            # Update entire rule
                            rule.update(data)
                        break
        else:
            self.config_data[path] = data
    
    def _handle_control(self, path: str, data: Any):
        """Handle control operations."""
        if path == '/control/ecm':
            if data.get('start'):
                self.status_data['/status/ecm/state'] = 'connected'
                self.status_data['/status/ecm/sync'] = 'ready'
            elif data.get('stop'):
                self.status_data['/status/ecm/state'] = 'stopped'


class MockSpeedtest:
    """Mock implementation of Speedtest for testing."""
    
    def __init__(self):
        self.results = Mock()
        self.servers = []
        self.best_server = None
        
    def get_servers(self, servers_list: List = None):
        """Mock get_servers method."""
        self.servers = [
            {'id': '12345', 'name': 'Test Server 1', 'country': 'US'},
            {'id': '67890', 'name': 'Test Server 2', 'country': 'US'}
        ]
        if servers_list is not None:
            servers_list.extend(self.servers)
    
    def get_best_server(self):
        """Mock get_best_server method."""
        self.best_server = self.servers[0] if self.servers else None
        return self.best_server
    
    def download(self) -> float:
        """Mock download speed test - returns speed in bits per second."""
        # Simulate realistic 5G/LTE speeds (convert Mbps to bps)
        download_mbps = random.uniform(20, 100)  # 20-100 Mbps
        download_bps = download_mbps * 1_000_000  # Convert to bits per second
        self.results.download = download_bps
        time.sleep(0.1)  # Simulate test time
        return download_bps
    
    def upload(self, pre_allocate: bool = True) -> float:
        """Mock upload speed test - returns speed in bits per second."""
        # Simulate realistic upload speeds (usually lower than download)
        upload_mbps = random.uniform(5, 30)  # 5-30 Mbps  
        upload_bps = upload_mbps * 1_000_000  # Convert to bits per second
        self.results.upload = upload_bps
        time.sleep(0.1)  # Simulate test time
        return upload_bps


class MockScenarios:
    """Pre-defined test scenarios for different SIM configurations."""
    
    @staticmethod
    def dual_sim_good_signals():
        """Scenario: 2 SIMs with good signal strength."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -75, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 85.0,
                'expected_upload': 25.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -85, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 65.0,
                'expected_upload': 20.0
            }
        }
    
    @staticmethod
    def dual_sim_one_weak():
        """Scenario: 2 SIMs, one with weak signal."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -80, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 95.0,
                'expected_upload': 30.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -105, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 15.0,  # Weak signal = slow speed
                'expected_upload': 3.0
            }
        }
    
    @staticmethod
    def dual_sim_one_failed():
        """Scenario: 2 SIMs, one fails to connect."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -85, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 75.0,
                'expected_upload': 22.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -110, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B4'},
                'status': {'connection_state': 'disconnected', 'error_text': 'TIMEOUT'},
                'expected_download': 0.0,  # Failed connection
                'expected_upload': 0.0
            }
        }

    @staticmethod
    def triple_sim_mixed_performance():
        """Scenario: 3 SIMs with different technologies and performance levels."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -70, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B28'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 120.0,  # Excellent 5G
                'expected_upload': 35.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -85, 'PRD': 'AT&T', 'HOMECARRID': '310410', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 45.0,  # Good LTE
                'expected_upload': 12.0
            },
            'mdm-sim3': {
                'info': {'port': 'MODEM3', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan2'},
                'config': {'_id_': 'rule_003', 'priority': 1.2},
                'diagnostics': {'RSRP': -95, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B12'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 25.0,  # Marginal LTE
                'expected_upload': 8.0
            }
        }

    @staticmethod
    def quad_sim_all_carriers():
        """Scenario: 4 SIMs from all major US carriers."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -75, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 95.0,
                'expected_upload': 28.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -80, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B71'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 110.0,  # T-Mobile 5G often faster
                'expected_upload': 32.0
            },
            'mdm-sim3': {
                'info': {'port': 'MODEM3', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan2'},
                'config': {'_id_': 'rule_003', 'priority': 1.2},
                'diagnostics': {'RSRP': -85, 'PRD': 'AT&T', 'HOMECARRID': '310410', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 65.0,
                'expected_upload': 18.0
            },
            'mdm-sim4': {
                'info': {'port': 'MODEM4', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan3'},
                'config': {'_id_': 'rule_004', 'priority': 1.3},
                'diagnostics': {'RSRP': -90, 'PRD': 'US Cellular', 'HOMECARRID': '311580', 'RFBAND': 'B5'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 35.0,
                'expected_upload': 10.0
            }
        }

    @staticmethod
    def all_weak_signals():
        """Scenario: All SIMs have weak signals - tests minimum speed enforcement."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -105, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 8.0,  # Below 5G minimum (30 Mbps)
                'expected_upload': 1.5   # Below 5G minimum (2 Mbps)
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -110, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 5.0,  # Below LTE minimum (10 Mbps)
                'expected_upload': 0.8   # Below LTE minimum (1 Mbps)
            }
        }

    @staticmethod
    def all_failed_connections():
        """Scenario: All SIMs fail to connect - tests error handling."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -120, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'disconnected', 'error_text': 'NO SIGNAL'},
                'expected_download': 0.0,
                'expected_upload': 0.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -115, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B4'},
                'status': {'connection_state': 'disconnected', 'error_text': 'AUTH FAILED'},
                'expected_download': 0.0,
                'expected_upload': 0.0
            }
        }

    @staticmethod
    def high_speed_5g_scenario():
        """Scenario: Ultra-high speed 5G performance testing."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -65, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B260'},  # mmWave
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 850.0,  # Ultra-high 5G speeds
                'expected_upload': 120.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -70, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B261'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 920.0,  # Even faster T-Mobile 5G
                'expected_upload': 135.0
            }
        }

    @staticmethod
    def edge_case_tie_breaker():
        """Scenario: Very similar speeds to test tie-breaker logic."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -75, 'PRD': 'Verizon', 'HOMECARRID': '311480', 'RFBAND': 'B2'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 50.0,  # Within 10% of sim2
                'expected_upload': 15.0     # Within 10% of sim2
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -80, 'PRD': 'T-Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B71'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 52.0,  # Within 10% of sim1
                'expected_upload': 16.0     # Within 10% of sim1
            }
        }

    @staticmethod
    def carrier_specific_apn_test():
        """Scenario: Tests carrier-specific APN handling."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': '5G', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -85, 'PRD': 'FirstNet', 'HOMECARRID': '313100', 'RFBAND': 'B14'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 45.0,
                'expected_upload': 12.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -90, 'PRD': 'Comcast', 'HOMECARRID': '310030', 'RFBAND': 'B4'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 35.0,
                'expected_upload': 8.0
            }
        }

    @staticmethod
    def international_roaming():
        """Scenario: International roaming scenario."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -85, 'PRD': 'Rogers', 'HOMECARRID': '302720', 'RFBAND': 'B4'},  # Canada
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 25.0,  # Roaming speeds often slower
                'expected_upload': 5.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -95, 'PRD': 'Telus', 'HOMECARRID': '302220', 'RFBAND': 'B7'},
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 18.0,
                'expected_upload': 3.0
            }
        }

    @staticmethod
    def mvno_carriers():
        """Scenario: Mobile Virtual Network Operators (MVNOs)."""
        return {
            'mdm-sim1': {
                'info': {'port': 'MODEM1', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan0'},
                'config': {'_id_': 'rule_001', 'priority': 1.0},
                'diagnostics': {'RSRP': -80, 'PRD': 'Visible', 'HOMECARRID': '311480', 'RFBAND': 'B4'},  # Verizon MVNO
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 40.0,  # MVNO typically slower
                'expected_upload': 10.0
            },
            'mdm-sim2': {
                'info': {'port': 'MODEM2', 'sim': 'SIM1', 'tech': 'LTE', 'iface': 'wwan1'},
                'config': {'_id_': 'rule_002', 'priority': 1.1},
                'diagnostics': {'RSRP': -85, 'PRD': 'Mint Mobile', 'HOMECARRID': '310260', 'RFBAND': 'B2'},  # T-Mobile MVNO
                'status': {'connection_state': 'connected', 'error_text': ''},
                'expected_download': 35.0,
                'expected_upload': 8.0
            }
        }


class TestHarness:
    """Main test harness for running SimSelector scenarios."""
    
    def __init__(self):
        self.mock_client = MockEventingCSClient('SimSelector')
        self.mock_speedtest = MockSpeedtest()
        self.original_modules = {}
    
    def setup_mocks(self, scenario_data: Dict):
        """Setup mock objects with scenario-specific data."""
        # Configure mock client with scenario data
        self.mock_client.scenario_data = scenario_data
        self.mock_speedtest.scenario_data = scenario_data
        
        # Set up WAN devices based on scenario
        for sim_uid, sim_data in scenario_data.items():
            self.mock_client.wan_devices[sim_uid] = sim_data
    
    def run_test_scenario(self, scenario_name: str, scenario_data: dict):
        """Execute a complete test scenario with the given SIM configuration."""
        print(f"🧪 Running Test Scenario: {scenario_name}")
        print(f"📋 SIMs to test: {len(scenario_data)}")
        print()
        
        # Set up mock objects with scenario data
        self.setup_mocks(scenario_data)
        
        # Create scenario-specific results
        for sim_uid, sim_data in scenario_data.items():
            diagnostics = sim_data.get('diagnostics', {})
            rsrp = diagnostics.get('RSRP')
            
            # Ensure RSRP is properly classified
            if rsrp is not None:
                if rsrp > -90:
                    signal_quality = "Good"
                elif -105 <= rsrp <= -90:
                    signal_quality = "Weak"
                else:
                    signal_quality = "Bad"
                
                sim_data['signal_quality'] = signal_quality
                print(f"📡 {sim_uid}: RSRP={rsrp} dBm ({signal_quality} Signal)")
        
        print()
        
        # Apply module patches
        self._apply_patches()
        
        try:
            # Import SimSelector after patching
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            import SimSelector
            
            # Set up global instances for SimSelector functions
            SimSelector.simselector = SimSelector.SimSelector()
            SimSelector.simselector.client = self.mock_client
            SimSelector.simselector.speedtest = self.mock_speedtest
            SimSelector.cp = self.mock_client
            
            # Run the validation phase
            print("🔍 Phase 1: Validation/Staging")
            print("-" * 30)
            SimSelector.run_validation_phase()
            print()
            
            # Run the performance phase
            print("🚀 Phase 2: Performance/Run")
            print("-" * 30)
            SimSelector.run_performance_phase()
            print()
            
            # Analysis and results
            print("📊 Test Scenario Analysis:")
            print("-" * 30)
            
            for sim_uid, sim_data in scenario_data.items():
                port_name = f"{sim_data['info']['port']} {sim_data['info']['sim']}"
                diagnostics = sim_data.get('diagnostics', {})
                
                # Expected vs actual results
                expected_dl = sim_data.get('expected_download', 0)
                expected_ul = sim_data.get('expected_upload', 0)
                
                print(f"📱 {port_name}:")
                print(f"   Carrier: {diagnostics.get('PRD', 'Unknown')}")
                print(f"   Technology: {sim_data['info'].get('tech', 'Unknown')}")
                print(f"   Signal: {diagnostics.get('RSRP', 'Unknown')} dBm ({sim_data.get('signal_quality', 'Unknown')})")
                print(f"   Expected Speeds: ↓{expected_dl} Mbps ↑{expected_ul} Mbps")
                
                # Connection status
                status = sim_data.get('status', {})
                conn_state = status.get('connection_state', 'unknown')
                error_text = status.get('error_text', '')
                
                if conn_state == 'connected':
                    print(f"   Status: ✅ Connected")
                else:
                    print(f"   Status: ❌ {conn_state.upper()}" + (f" ({error_text})" if error_text else ""))
                print()
            
            print("✅ Test scenario completed successfully!")
            
        except Exception as e:
            print(f"❌ Test scenario failed with error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        
        finally:
            # Remove patches
            self._remove_patches()
            
            # Clean up module imports
            modules_to_remove = [mod for mod in sys.modules.keys() 
                               if mod.startswith('SimSelector') or mod in ['csclient', 'speedtest', 'state_manager']]
            for mod in modules_to_remove:
                if mod in sys.modules:
                    del sys.modules[mod]
    
    def _apply_patches(self):
        """Apply module patches for testing."""
        import sys
        from unittest.mock import MagicMock
        
        # Store original modules
        self.original_modules = {}
        modules_to_mock = ['csclient', 'speedtest', 'state_manager']
        
        for module_name in modules_to_mock:
            if module_name in sys.modules:
                self.original_modules[module_name] = sys.modules[module_name]
        
        # Import mock state manager functions
        sys.path.insert(0, os.path.dirname(__file__))
        import mock_state_manager
        
        # Mock csclient module
        mock_csclient_module = MagicMock()
        mock_csclient_module.EventingCSClient = lambda name: self.mock_client
        sys.modules['csclient'] = mock_csclient_module
        
        # Mock speedtest module  
        mock_speedtest_module = MagicMock()
        mock_speedtest_module.Speedtest = lambda: self.mock_speedtest
        sys.modules['speedtest'] = mock_speedtest_module
        
        # Mock state_manager module with the imported functions
        mock_state_manager_module = MagicMock()
        mock_state_manager_module.get_state = mock_state_manager.get_state
        mock_state_manager_module.set_state = mock_state_manager.set_state
        sys.modules['state_manager'] = mock_state_manager_module
    
    def _remove_patches(self):
        """Remove module patches and restore originals."""
        # Restore original modules
        if hasattr(self, 'original_modules'):
            for module_name, original_module in self.original_modules.items():
                sys.modules[module_name] = original_module
        
        # Remove mock modules that weren't originally present
        modules_to_clean = ['csclient', 'speedtest', 'state_manager']
        for module_name in modules_to_clean:
            if module_name in sys.modules and (not hasattr(self, 'original_modules') or module_name not in self.original_modules):
                del sys.modules[module_name] 