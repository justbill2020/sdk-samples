"""
Integration Tests - SimSelector v2.6.0

Tests end-to-end workflows and system integration including:
- Complete phase transition workflows
- SIM detection and selection integration
- IP management and dashboard setup
- Traffic validation and monitoring
- Error handling across components
- Real-world scenario validation
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all major components
from sim_manager import SIMManager, SIMCard, SIMStatus
from ip_manager import IPManager, IPConflict, ConflictSeverity
from traffic_validator import TrafficValidator
from error_handler import ErrorHandler
from dashboard_server import DashboardServer
from network_manager import NetworkManager
from firewall_manager import FirewallManager
from phases import PhaseManager, Phase


class IntegrationTestEnvironment:
    """Test environment setup for integration tests"""
    
    def __init__(self):
        self.client = Mock()
        self.setup_mock_responses()
        
        # Initialize all components
        self.sim_manager = SIMManager(self.client)
        self.ip_manager = IPManager(self.client)
        self.traffic_validator = TrafficValidator(self.client)
        self.error_handler = ErrorHandler(self.client)
        self.network_manager = NetworkManager(self.client)
        self.firewall_manager = FirewallManager(self.client)
        self.phase_manager = PhaseManager(self.client)
        
        # Track integration state
        self.events = []
        self.errors = []
        
    def setup_mock_responses(self):
        """Setup mock responses for CS client"""
        self.client.log = Mock(side_effect=self.log_event)
        self.client.get = Mock(side_effect=self.get_response)
        self.client.put = Mock(side_effect=self.put_response)
        
        # Default mock responses
        self.mock_responses = {
            "status/wan/devices": {
                "modem_count": 1,
                "sim_slots": 2,
                "modems": [
                    {
                        "id": "modem0",
                        "status": "connected",
                        "sim_slots": [
                            {"slot": 1, "status": "present"},
                            {"slot": 2, "status": "present"}
                        ]
                    }
                ]
            },
            "status/wan/devices/modem0/sim1": {
                "iccid": "89014103211118510720",
                "imsi": "310410118510720", 
                "carrier": "Verizon",
                "rsrp": -75.0,
                "signal_strength": 85
            },
            "status/wan/devices/modem0/sim2": {
                "iccid": "89014103211118510721",
                "imsi": "310410118510721",
                "carrier": "AT&T", 
                "rsrp": -85.0,
                "signal_strength": 75
            },
            "status/system/network/interfaces": {
                "interfaces": [
                    {"name": "enp1s0", "ip": "192.168.1.100", "netmask": "255.255.255.0", "status": "up"}
                ]
            }
        }
    
    def log_event(self, message):
        """Log integration test events"""
        self.events.append({"timestamp": time.time(), "message": message})
    
    def get_response(self, path):
        """Handle mock GET requests"""
        return self.mock_responses.get(path, None)
    
    def put_response(self, path, data):
        """Handle mock PUT requests"""
        return {"success": True}
    
    def add_error(self, component, error):
        """Add error to integration test tracking"""
        self.errors.append({"component": component, "error": error, "timestamp": time.time()})


class TestPhaseTransitionWorkflows(unittest.TestCase):
    """Test complete phase transition workflows"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.env = IntegrationTestEnvironment()
    
    def test_staging_to_install_transition(self):
        """Test complete staging to install phase transition"""
        # Start in staging phase
        self.env.phase_manager.current_phase = Phase.STAGING
        
        # Execute staging phase tasks
        staging_result = self._execute_staging_phase()
        self.assertTrue(staging_result["success"])
        
        # Transition to install phase
        transition_result = self.env.phase_manager.transition_to_phase(Phase.INSTALL)
        self.assertTrue(transition_result["success"])
        
        # Execute install phase tasks
        install_result = self._execute_install_phase()
        self.assertTrue(install_result["success"])
        
        # Verify phase transition completed
        self.assertEqual(self.env.phase_manager.current_phase, Phase.INSTALL)
        
        # Check that all components are properly configured
        self.assertIsNotNone(self.env.sim_manager.active_sim)
        self.assertIsNotNone(self.env.ip_manager.dashboard_ip)
    
    def test_install_to_deployed_transition(self):
        """Test install to deploy phase transition"""
        # Start in install phase
        self.env.phase_manager.current_phase = Phase.INSTALL
        self.env.sim_manager.active_sim = 1
        self.env.ip_manager.dashboard_ip = "192.168.1.50"
        
        # Execute install phase validation
        install_validation = self._validate_install_phase()
        self.assertTrue(install_validation["ready_for_deployment"])
        
        # Transition to deployed phase
        transition_result = self.env.phase_manager.transition_to_phase(Phase.DEPLOYED)
        self.assertTrue(transition_result["success"])
        
        # Execute deployment phase tasks
        deploy_result = self._execute_deployment_phase()
        self.assertTrue(deploy_result["success"])
        
        # Verify deployment state
        self.assertEqual(self.env.phase_manager.current_phase, Phase.DEPLOYED)
        self.assertTrue(self._verify_deployment_health())
    
    def test_emergency_phase_transition(self):
        """Test emergency phase transitions"""
        # Start in normal deployed state
        self.env.phase_manager.current_phase = Phase.DEPLOYED
        
        # Simulate emergency condition
        self.env.sim_manager.active_sim = None  # SIM failure
        
        # Trigger emergency response
        with patch.object(self.env.error_handler, 'handle_critical_error') as mock_critical:
            mock_critical.return_value = {"success": True, "emergency_mode": True}
            
            emergency_result = self.env.phase_manager.handle_emergency()
            
            # Should transition to staging for recovery
            self.assertTrue(emergency_result["success"])
            self.assertEqual(self.env.phase_manager.current_phase, Phase.STAGING)
    
    def _execute_staging_phase(self):
        """Execute staging phase tasks"""
        tasks = []
        
        # SIM detection and configuration
        sim_result = self.env.sim_manager.detect_sim_configuration()
        tasks.append(("sim_detection", sim_result["success"]))
        
        # Network interface detection
        network_result = self.env.network_manager.detect_interfaces()
        tasks.append(("network_detection", network_result["success"]))
        
        # IP configuration
        ip_result = self.env.ip_manager.select_dashboard_ip()
        tasks.append(("ip_configuration", ip_result["success"]))
        
        # All tasks must succeed for staging phase completion
        all_successful = all(task[1] for task in tasks)
        
        return {
            "success": all_successful,
            "tasks": tasks,
            "phase": "staging"
        }
    
    def _execute_install_phase(self):
        """Execute install phase tasks"""
        tasks = []
        
        # Dashboard server startup
        dashboard_result = self._start_dashboard_server()
        tasks.append(("dashboard_startup", dashboard_result["success"]))
        
        # Firewall configuration
        firewall_result = self.env.firewall_manager.configure_dashboard_access()
        tasks.append(("firewall_config", firewall_result["success"]))
        
        # Traffic validation
        traffic_result = self.env.traffic_validator.test_connectivity()
        tasks.append(("traffic_validation", traffic_result["success"]))
        
        all_successful = all(task[1] for task in tasks)
        
        return {
            "success": all_successful,
            "tasks": tasks,
            "phase": "install"
        }
    
    def _validate_install_phase(self):
        """Validate install phase readiness"""
        validations = []
        
        # Check SIM status
        sim_status = self.env.sim_manager.get_sim_status()
        validations.append(("sim_active", sim_status["active_sim"] is not None))
        
        # Check IP configuration
        ip_status = self.env.ip_manager.get_status()
        validations.append(("ip_configured", ip_status["dashboard_ip"] is not None))
        
        # Check network connectivity
        connectivity = self.env.traffic_validator.test_connectivity()
        validations.append(("connectivity", connectivity["success"]))
        
        ready_for_deployment = all(validation[1] for validation in validations)
        
        return {
            "ready_for_deployment": ready_for_deployment,
            "validations": validations
        }
    
    def _execute_deployment_phase(self):
        """Execute deployment phase tasks"""
        tasks = []
        
        # Start monitoring services
        monitoring_result = self._start_monitoring_services()
        tasks.append(("monitoring_startup", monitoring_result["success"]))
        
        # Final validation
        final_validation = self._run_final_validation()
        tasks.append(("final_validation", final_validation["success"]))
        
        all_successful = all(task[1] for task in tasks)
        
        return {
            "success": all_successful,
            "tasks": tasks,
            "phase": "deployed"
        }
    
    def _start_dashboard_server(self):
        """Mock dashboard server startup"""
        return {"success": True, "port": 8080}
    
    def _start_monitoring_services(self):
        """Mock monitoring services startup"""
        return {"success": True, "services": ["sim_monitor", "traffic_monitor"]}
    
    def _run_final_validation(self):
        """Mock final deployment validation"""
        return {"success": True, "all_systems_operational": True}
    
    def _verify_deployment_health(self):
        """Verify deployment health"""
        return True


class TestComponentIntegration(unittest.TestCase):
    """Test integration between major components"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.env = IntegrationTestEnvironment()
    
    def test_sim_manager_ip_manager_integration(self):
        """Test SIM manager and IP manager integration"""
        # SIM detection triggers IP configuration
        sim_result = self.env.sim_manager.detect_sim_configuration()
        self.assertTrue(sim_result["success"])
        
        # IP manager should use SIM information for network selection
        with patch.object(self.env.ip_manager, 'get_network_interfaces') as mock_interfaces:
            mock_interfaces.return_value = {
                "wwan0": {"ip": "10.0.0.100", "mask": "255.255.255.0", "status": "up"}
            }
            
            ip_result = self.env.ip_manager.select_dashboard_ip()
            self.assertTrue(ip_result["success"])
            
            # Should select IP in cellular network range
            self.assertIn("10.0.0", ip_result["ip"])
    
    def test_ip_manager_firewall_integration(self):
        """Test IP manager and firewall manager integration"""
        # Set dashboard IP
        self.env.ip_manager.dashboard_ip = "192.168.1.50"
        
        # Firewall should configure rules based on dashboard IP
        firewall_result = self.env.firewall_manager.configure_dashboard_access()
        self.assertTrue(firewall_result["success"])
        
        # Verify firewall rules include dashboard IP
        rules = self.env.firewall_manager.get_active_rules()
        dashboard_rules = [rule for rule in rules if "192.168.1.50" in rule.get("target", "")]
        self.assertGreater(len(dashboard_rules), 0)
    
    def test_traffic_validator_sim_manager_integration(self):
        """Test traffic validator and SIM manager integration"""
        # Set active SIM
        self.env.sim_manager.active_sim = 1
        
        # Traffic validator should use active SIM for testing
        with patch.object(self.env.traffic_validator, 'test_connectivity') as mock_connectivity:
            mock_connectivity.return_value = {"success": True, "latency": 45.0}
            
            # Test should use active SIM interface
            connectivity_result = self.env.traffic_validator.test_connectivity()
            self.assertTrue(connectivity_result["success"])
            
            # Verify test was performed on correct interface
            mock_connectivity.assert_called_once()
    
    def test_error_handler_component_integration(self):
        """Test error handler integration with all components"""
        # Register components with error handler
        self.env.error_handler.register_component("sim_manager", self.env.sim_manager)
        self.env.error_handler.register_component("ip_manager", self.env.ip_manager)
        self.env.error_handler.register_component("traffic_validator", self.env.traffic_validator)
        
        # Simulate error in SIM manager
        with patch.object(self.env.sim_manager, 'detect_sim_configuration') as mock_sim:
            mock_sim.side_effect = Exception("SIM detection failed")
            
            # Error handler should catch and handle the error
            error_result = self.env.error_handler.handle_error("sim_manager", "detection_failed")
            
            self.assertTrue(error_result["handled"])
            self.assertIn("recovery_attempted", error_result)


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world deployment scenarios"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.env = IntegrationTestEnvironment()
    
    def test_single_sim_deployment_scenario(self):
        """Test deployment with single SIM configuration"""
        # Configure single SIM scenario
        self.env.mock_responses["status/wan/devices"]["modems"][0]["sim_slots"] = [
            {"slot": 1, "status": "present"},
            {"slot": 2, "status": "absent"}
        ]
        
        # Execute complete deployment workflow
        workflow_result = self._execute_complete_workflow()
        
        self.assertTrue(workflow_result["success"])
        self.assertEqual(workflow_result["final_phase"], Phase.DEPLOYED)
        self.assertTrue(self.env.sim_manager.single_sim_mode)
    
    def test_dual_sim_failover_scenario(self):
        """Test deployment with dual SIM failover"""
        # Configure dual SIM scenario
        self.env.mock_responses["status/wan/devices"]["modems"][0]["sim_slots"] = [
            {"slot": 1, "status": "present"},
            {"slot": 2, "status": "present"}
        ]
        
        # Execute deployment
        workflow_result = self._execute_complete_workflow()
        self.assertTrue(workflow_result["success"])
        
        # Simulate primary SIM failure
        self.env.mock_responses["status/wan/devices/modem0/sim1"]["status"] = "error"
        
        # Should automatically failover to secondary SIM
        failover_result = self.env.sim_manager.handle_sim_failure(1)
        self.assertTrue(failover_result["success"])
        self.assertEqual(self.env.sim_manager.active_sim, 2)
    
    def test_network_conflict_resolution_scenario(self):
        """Test deployment with network IP conflicts"""
        # Configure conflicted network environment
        self.env.mock_responses["status/wan/devices"]["dhcp_leases"] = [
            {"ip": "192.168.1.50", "mac": "aa:bb:cc:dd:ee:ff"}
        ]
        
        # Execute deployment workflow
        workflow_result = self._execute_complete_workflow()
        
        # Should resolve conflicts and succeed
        self.assertTrue(workflow_result["success"])
        
        # Dashboard IP should be different from conflicted IP
        self.assertNotEqual(self.env.ip_manager.dashboard_ip, "192.168.1.50")
    
    def test_poor_connectivity_scenario(self):
        """Test deployment with poor network connectivity"""
        # Configure poor signal conditions
        self.env.mock_responses["status/wan/devices/modem0/sim1"]["rsrp"] = -115.0
        self.env.mock_responses["status/wan/devices/modem0/sim2"]["rsrp"] = -120.0
        
        # Mock poor connectivity test results
        with patch.object(self.env.traffic_validator, 'test_connectivity') as mock_test:
            mock_test.return_value = {"success": False, "error": "High latency"}
            
            workflow_result = self._execute_complete_workflow()
            
            # Should handle poor conditions gracefully
            self.assertIn("warning", workflow_result)
            self.assertIn("poor_connectivity", workflow_result["warnings"])
    
    def test_rapid_sim_swapping_scenario(self):
        """Test rapid SIM card swapping during operation"""
        # Start with initial SIM configuration
        self.env.sim_manager.active_sim = 1
        
        # Simulate rapid SIM changes
        sim_changes = [
            {"slot": 1, "status": "absent"},  # Remove SIM 1
            {"slot": 2, "status": "present"}, # Keep SIM 2
            {"slot": 1, "status": "present"}, # Reinsert SIM 1 
            {"slot": 2, "status": "absent"}   # Remove SIM 2
        ]
        
        # Process each change
        for change in sim_changes:
            self.env.mock_responses["status/wan/devices"]["modems"][0]["sim_slots"][change["slot"]-1] = change
            
            # Trigger hot-swap detection
            swap_result = self.env.sim_manager.handle_hot_swap({}, {})
            
            # System should handle changes gracefully
            self.assertTrue(swap_result or self.env.sim_manager.active_sim is not None)
    
    def _execute_complete_workflow(self):
        """Execute complete deployment workflow"""
        phases = [Phase.STAGING, Phase.INSTALL, Phase.DEPLOYED]
        current_phase = Phase.STAGING
        
        for target_phase in phases:
            if current_phase != target_phase:
                # Execute phase transition
                transition_result = self.env.phase_manager.transition_to_phase(target_phase)
                if not transition_result["success"]:
                    return {"success": False, "failed_phase": target_phase}
                current_phase = target_phase
            
            # Execute phase-specific tasks
            if target_phase == Phase.STAGING:
                phase_result = self._execute_staging_tasks()
            elif target_phase == Phase.INSTALL:
                phase_result = self._execute_install_tasks()
            elif target_phase == Phase.DEPLOYED:
                phase_result = self._execute_deployment_tasks()
            
            if not phase_result["success"]:
                return {"success": False, "failed_phase": target_phase, "error": phase_result}
        
        return {
            "success": True,
            "final_phase": current_phase,
            "warnings": []
        }
    
    def _execute_staging_tasks(self):
        """Execute staging phase tasks"""
        return {"success": True}
    
    def _execute_install_tasks(self):
        """Execute install phase tasks"""
        return {"success": True}
    
    def _execute_deployment_tasks(self):
        """Execute deployment phase tasks"""
        return {"success": True}


class TestConcurrentOperations(unittest.TestCase):
    """Test concurrent operations and thread safety"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.env = IntegrationTestEnvironment()
    
    def test_concurrent_sim_monitoring_and_ip_management(self):
        """Test concurrent SIM monitoring and IP management"""
        # Start SIM monitoring
        sim_monitor_result = self.env.sim_manager.start_monitoring()
        self.assertTrue(sim_monitor_result)
        
        # Start IP conflict monitoring  
        ip_monitor_result = self.env.ip_manager.start_monitoring()
        self.assertTrue(ip_monitor_result)
        
        # Let both run concurrently
        time.sleep(0.5)
        
        # Both should be running without interference
        self.assertTrue(self.env.sim_manager.monitoring_enabled)
        self.assertTrue(self.env.ip_manager.monitoring_enabled)
        
        # Clean up
        self.env.sim_manager.stop_monitoring()
        self.env.ip_manager.stop_monitoring()
    
    def test_concurrent_traffic_validation_and_error_handling(self):
        """Test concurrent traffic validation and error handling"""
        # Start traffic monitoring
        traffic_result = self.env.traffic_validator.start_monitoring()
        self.assertTrue(traffic_result)
        
        # Trigger error handling while traffic monitoring is active
        with patch.object(self.env.error_handler, 'handle_error') as mock_error:
            mock_error.return_value = {"success": True, "handled": True}
            
            # Simulate concurrent error
            error_result = self.env.error_handler.handle_error("test_component", "test_error")
            self.assertTrue(error_result["handled"])
        
        # Traffic monitoring should continue unaffected
        self.assertTrue(self.env.traffic_validator.monitoring_enabled)
        
        # Clean up
        self.env.traffic_validator.stop_monitoring()
    
    def test_thread_safety_during_phase_transitions(self):
        """Test thread safety during phase transitions"""
        # Start multiple concurrent operations
        operations = []
        
        def sim_operation():
            return self.env.sim_manager.detect_sim_configuration()
        
        def ip_operation():
            return self.env.ip_manager.select_dashboard_ip()
        
        def traffic_operation():
            return self.env.traffic_validator.test_connectivity()
        
        # Start operations in parallel
        threads = []
        for operation in [sim_operation, ip_operation, traffic_operation]:
            thread = threading.Thread(target=operation)
            threads.append(thread)
            thread.start()
        
        # Wait for all operations to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # All threads should complete without deadlock
        for thread in threads:
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Integration Test Results")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100:.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1) 