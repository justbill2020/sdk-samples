#!/usr/bin/env python3
"""
SimSelector Test Runner - Comprehensive testing for SimSelector 2.5.9

This test runner provides comprehensive mock testing of the SimSelector application
without requiring actual Cradlepoint hardware. It includes multiple test scenarios
covering various real-world situations including:

- Basic dual SIM scenarios (good signals, weak signal, failed connection)
- Multi-SIM scenarios (triple and quad SIM configurations)
- Edge cases (all weak signals, all failed connections, tie-breaker logic)
- Performance scenarios (ultra-high 5G speeds)
- Carrier/network scenarios (APN testing, roaming, MVNO carriers)

Usage:
    python test_runner.py [scenario]
    
    Available scenarios:
    - all: Run all test scenarios
    - good, weak, failed: Basic dual SIM scenarios
    - triple, quad: Multi-SIM scenarios  
    - allweak, allfailed: Edge case scenarios
    - highspeed, tiebreaker: Performance scenarios
    - apn, roaming, mvno: Carrier/network scenarios
    - interactive: Interactive testing mode
"""

import sys
import os
import argparse
from unittest.mock import patch

# Add the SimSelector directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mock_framework import TestHarness, MockScenarios


def run_all_scenarios():
    """Run all predefined test scenarios."""
    harness = TestHarness()
    
    print("🚀 SimSelector 2.5.9 Comprehensive Testing Suite")
    print("=" * 60)
    print("Testing with full mocking - no hardware required!")
    print()
    
    # Define all test scenarios
    scenarios = [
        ("Dual SIM - Good Signals", MockScenarios.dual_sim_good_signals()),
        ("Dual SIM - One Weak Signal", MockScenarios.dual_sim_one_weak()),
        ("Dual SIM - One Failed Connection", MockScenarios.dual_sim_one_failed()),
        ("Triple SIM - Mixed Performance", MockScenarios.triple_sim_mixed_performance()),
        ("Quad SIM - All Major Carriers", MockScenarios.quad_sim_all_carriers()),
        ("All Weak Signals - Minimum Speed Test", MockScenarios.all_weak_signals()),
        ("All Failed Connections - Error Handling", MockScenarios.all_failed_connections()),
        ("High Speed 5G - Ultra Performance", MockScenarios.high_speed_5g_scenario()),
        ("Edge Case - Tie Breaker Logic", MockScenarios.edge_case_tie_breaker()),
        ("Carrier Specific - APN Testing", MockScenarios.carrier_specific_apn_test()),
        ("International Roaming", MockScenarios.international_roaming()),
        ("MVNO Carriers", MockScenarios.mvno_carriers()),
    ]
    
    results = {}
    
    for scenario_name, scenario_data in scenarios:
        try:
            harness.run_test_scenario(scenario_name, scenario_data)
            results[scenario_name] = "✅ PASSED"
        except Exception as e:
            results[scenario_name] = f"❌ FAILED: {str(e)}"
        
        print("\n" + "="*60 + "\n")
    
    # Print final summary
    print("🏁 Final Test Results Summary:")
    print("=" * 40)
    for scenario, result in results.items():
        print(f"{result} - {scenario}")
    
    # Overall result
    passed = sum(1 for r in results.values() if "PASSED" in r)
    total = len(results)
    
    print(f"\n📊 Overall: {passed}/{total} scenarios passed")
    
    if passed == total:
        print("🎉 All tests passed! SimSelector 2.5.9 is ready for deployment!")
        return True
    else:
        print("⚠️  Some tests failed. Please review and fix issues before deployment.")
        return False


def run_single_scenario(scenario_name: str):
    """Run a single test scenario."""
    harness = TestHarness()
    
    scenarios = {
        "good": ("Dual SIM - Good Signals", MockScenarios.dual_sim_good_signals()),
        "weak": ("Dual SIM - One Weak Signal", MockScenarios.dual_sim_one_weak()),
        "failed": ("Dual SIM - One Failed Connection", MockScenarios.dual_sim_one_failed()),
        "triple": ("Triple SIM - Mixed Performance", MockScenarios.triple_sim_mixed_performance()),
        "quad": ("Quad SIM - All Major Carriers", MockScenarios.quad_sim_all_carriers()),
        "allweak": ("All Weak Signals - Minimum Speed Test", MockScenarios.all_weak_signals()),
        "allfailed": ("All Failed Connections - Error Handling", MockScenarios.all_failed_connections()),
        "highspeed": ("High Speed 5G - Ultra Performance", MockScenarios.high_speed_5g_scenario()),
        "tiebreaker": ("Edge Case - Tie Breaker Logic", MockScenarios.edge_case_tie_breaker()),
        "apn": ("Carrier Specific - APN Testing", MockScenarios.carrier_specific_apn_test()),
        "roaming": ("International Roaming", MockScenarios.international_roaming()),
        "mvno": ("MVNO Carriers", MockScenarios.mvno_carriers()),
    }
    
    if scenario_name not in scenarios:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available scenarios: {', '.join(scenarios.keys())}")
        return False
    
    name, data = scenarios[scenario_name]
    harness.run_test_scenario(name, data)
    return True


def interactive_test():
    """Run interactive testing mode."""
    print("🔧 SimSelector Interactive Test Mode")
    print("=" * 40)
    
    harness = TestHarness()
    
    while True:
        print("\nAvailable commands:")
        print("📊 Basic Scenarios:")
        print("  1. run all - Run all test scenarios")
        print("  2. run good - Test with good signals")
        print("  3. run weak - Test with one weak signal")
        print("  4. run failed - Test with one failed connection")
        
        print("\n🔄 Multi-SIM Scenarios:")
        print("  5. run triple - Triple SIM mixed performance")
        print("  6. run quad - Quad SIM all major carriers")
        
        print("\n⚠️ Edge Case Scenarios:")
        print("  7. run allweak - All SIMs have weak signals")
        print("  8. run allfailed - All SIMs fail to connect")
        print("  9. run tiebreaker - Similar speeds (tie-breaker logic)")
        
        print("\n🚀 Performance Scenarios:")
        print("  10. run highspeed - Ultra-high 5G speeds")
        
        print("\n🌐 Carrier/Network Scenarios:")
        print("  11. run apn - Carrier-specific APN testing")
        print("  12. run roaming - International roaming")
        print("  13. run mvno - MVNO carrier testing")
        
        print("\n🛠️ Other Options:")
        print("  14. custom - Create custom scenario")
        print("  15. exit - Exit test mode")
        
        choice = input("\nEnter command: ").strip().lower()
        
        if choice == "exit":
            break
        elif choice == "run all":
            run_all_scenarios()
        elif choice.startswith("run "):
            scenario = choice.split(" ", 1)[1]
            run_single_scenario(scenario)
        elif choice == "custom":
            create_custom_scenario(harness)
        else:
            print("❌ Invalid command. Please try again.")


def create_custom_scenario(harness: TestHarness):
    """Create and run a custom test scenario."""
    print("\n🛠️  Custom Scenario Builder")
    print("-" * 30)
    
    # Get number of SIMs
    try:
        num_sims = int(input("Number of SIMs (1-4): "))
        if num_sims < 1 or num_sims > 4:
            print("❌ Please enter 1-4 SIMs")
            return
    except ValueError:
        print("❌ Invalid number")
        return
    
    scenario_data = {}
    
    for i in range(num_sims):
        print(f"\n📱 Configuring SIM {i+1}:")
        
        # Get basic info
        port = input(f"  Port (e.g., MODEM{i+1}): ") or f"MODEM{i+1}"
        sim = input(f"  SIM slot (e.g., SIM1): ") or "SIM1"
        tech = input(f"  Technology (5G/LTE): ") or "LTE"
        carrier = input(f"  Carrier (e.g., Verizon): ") or "Unknown"
        
        # Get signal strength
        try:
            rsrp = int(input(f"  RSRP signal strength (-50 to -120): ") or "-85")
            if rsrp > -50 or rsrp < -120:
                print("  ⚠️  Unusual RSRP value, using -85")
                rsrp = -85
        except ValueError:
            rsrp = -85
        
        # Get expected speeds
        try:
            download = float(input(f"  Expected download speed (Mbps): ") or "50.0")
            upload = float(input(f"  Expected upload speed (Mbps): ") or "15.0")
        except ValueError:
            download, upload = 50.0, 15.0
        
        # Connection status
        connected = input(f"  Connected? (y/n): ").lower().startswith('y')
        
        sim_id = f"mdm-sim{i+1}"
        scenario_data[sim_id] = {
            'info': {'port': port, 'sim': sim, 'tech': tech, 'iface': f'wwan{i}'},
            'config': {'_id_': f'rule_{i+1:03d}', 'priority': 1.0 + i * 0.1},
            'diagnostics': {'RSRP': rsrp, 'PRD': carrier, 'HOMECARRID': '000000', 'RFBAND': 'B1'},
            'status': {
                'connection_state': 'connected' if connected else 'disconnected',
                'error_text': '' if connected else 'TIMEOUT'
            },
            'expected_download': download,
            'expected_upload': upload
        }
    
    # Run the custom scenario
    scenario_name = input("\nScenario name: ") or "Custom Test"
    harness.run_test_scenario(scenario_name, scenario_data)


# APN validation tests
class MockClient:
    def __init__(self):
        self.config_data = {'/config/wan/custom_apns': []}
        self.put_calls = []
    def get(self, path):
        if path == '/config/wan/custom_apns':
            return self.config_data['/config/wan/custom_apns']
        return None
    def put(self, path, data):
        self.put_calls.append((path, data))
        self.config_data[path] = data
        return True
    def log(self, msg):
        print(f"LOG: {msg}")
    def alert(self, msg):
        print(f"ALERT: {msg}")

def test_check_apn_adds_missing():
    from SimSelector import SimSelector
    simselector = SimSelector()
    simselector.client = MockClient()
    simselector.ADV_APN = {
        "custom_apns": [
            {"carrier": "310030", "apn": "11200.mcs"},
            {"carrier": "310170", "apn": "ComcastMES5G"},
            {"carrier": "310030", "apn": "contingent.net"},
            {"carrier": "311882", "apn": "iot.tmowholesale.static"},
            {"carrier": "311480", "apn": "mw01.vzwstatic"},
            {"carrier": "311480", "apn": "we01.vzwstatic"}
        ]
    }
    simselector.client.config_data['/config/wan/custom_apns'] = [
        {"carrier": "310030", "apn": "11200.mcs"}
    ]
    simselector.check_apn()
    updated_apns = simselector.client.config_data['/config/wan/custom_apns']
    required_apns = simselector.ADV_APN['custom_apns']
    for apn in required_apns:
        assert apn in updated_apns, f"Missing APN: {apn}"
    print("✅ test_check_apn_adds_missing passed.")

def test_check_apn_no_duplicates():
    from SimSelector import SimSelector
    simselector = SimSelector()
    simselector.client = MockClient()
    simselector.ADV_APN = {
        "custom_apns": [
            {"carrier": "310030", "apn": "11200.mcs"},
            {"carrier": "310170", "apn": "ComcastMES5G"}
        ]
    }
    simselector.client.config_data['/config/wan/custom_apns'] = [
        {"carrier": "310030", "apn": "11200.mcs"},
        {"carrier": "310170", "apn": "ComcastMES5G"}
    ]
    simselector.check_apn()
    updated_apns = simselector.client.config_data['/config/wan/custom_apns']
    assert len(updated_apns) == 2, "Should not add duplicates"
    print("✅ test_check_apn_no_duplicates passed.")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description='SimSelector Test Runner')
    parser.add_argument('scenario', nargs='?', 
                       help='Test scenario: all, good, weak, failed, triple, quad, allweak, allfailed, highspeed, tiebreaker, apn, roaming, mvno, interactive')
    
    args = parser.parse_args()
    
    # Run APN validation tests before scenarios
    test_check_apn_adds_missing()
    test_check_apn_no_duplicates()
    
    if not args.scenario:
        print("SimSelector Test Runner")
        print("Available scenarios:")
        print("  all       - Run all test scenarios")
        print("  good      - Dual SIM with good signals")
        print("  weak      - Dual SIM with one weak signal")
        print("  failed    - Dual SIM with one failed connection")
        print("  triple    - Triple SIM mixed performance")
        print("  quad      - Quad SIM all major carriers")
        print("  allweak   - All SIMs have weak signals")
        print("  allfailed - All SIMs fail to connect")
        print("  highspeed - Ultra-high 5G speeds")
        print("  tiebreaker- Similar speeds (tie-breaker logic)")
        print("  apn       - Carrier-specific APN testing")
        print("  roaming   - International roaming")
        print("  mvno      - MVNO carrier testing")
        print("  interactive - Interactive mode")
        sys.exit(1)
    
    if args.scenario == "all":
        run_all_scenarios()
    elif args.scenario == "interactive":
        interactive_test()
    else:
        run_single_scenario(args.scenario)


if __name__ == "__main__":
    main()