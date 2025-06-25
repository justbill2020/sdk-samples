"""
Unit Tests for Traffic Validator - SimSelector v2.6.0

Tests all traffic validation functionality including:
- Traffic analysis and monitoring
- Bandwidth validation
- Network connectivity testing
- Speed test execution
- Quality of Service (QoS) monitoring
- Real-time traffic metrics
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_validator import (
    TrafficValidator, TrafficMetrics, NetworkTest, TestResult,
    get_traffic_validator, validate_network_connectivity, run_speed_test
)


class MockCSClient:
    """Mock CS client for testing"""
    def __init__(self):
        self.logs = []
        self.get_responses = {}
        self.put_calls = []
    
    def log(self, message):
        self.logs.append(message)
        print(f"MockClient: {message}")
    
    def get(self, path):
        return self.get_responses.get(path, None)
    
    def put(self, path, data):
        self.put_calls.append({"path": path, "data": data})
        return {"success": True}
    
    def set_response(self, path, response):
        self.get_responses[path] = response


class TestTrafficValidator(unittest.TestCase):
    """Test cases for Traffic Validator functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        self.client = MockCSClient()
        self.validator = TrafficValidator(self.client)
        
        # Reset global instance for clean testing
        import traffic_validator
        traffic_validator._traffic_validator = None
    
    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self.validator, 'monitoring_enabled') and self.validator.monitoring_enabled:
            self.validator.stop_monitoring()
    
    def test_traffic_validator_initialization(self):
        """Test traffic validator initialization"""
        self.assertIsNotNone(self.validator)
        self.assertEqual(self.validator.client, self.client)
        self.assertFalse(self.validator.monitoring_enabled)
        self.assertEqual(self.validator.test_results, [])
        self.assertIsNone(self.validator.current_metrics)
    
    def test_traffic_metrics_dataclass(self):
        """Test traffic metrics data structure"""
        metrics = TrafficMetrics(
            timestamp=1234567890,
            interface="enp1s0",
            bytes_sent=1048576,
            bytes_received=2097152,
            packets_sent=1000,
            packets_received=1500,
            download_speed=25.5,
            upload_speed=5.2,
            latency=45.0,
            packet_loss=0.1
        )
        
        self.assertEqual(metrics.interface, "enp1s0")
        self.assertEqual(metrics.bytes_sent, 1048576)
        self.assertEqual(metrics.download_speed, 25.5)
        self.assertEqual(metrics.latency, 45.0)
        self.assertEqual(metrics.packet_loss, 0.1)
    
    def test_network_connectivity_basic(self):
        """Test basic network connectivity testing"""
        # Mock successful ping responses
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="PING 8.8.8.8: 56 data bytes\n64 bytes from 8.8.8.8: icmp_seq=1 time=25.1 ms\n",
                stderr=""
            )
            
            result = self.validator.test_connectivity()
            
            self.assertTrue(result["success"])
            self.assertIn("latency", result)
            self.assertGreater(result["latency"], 0)
    
    def test_network_connectivity_failure(self):
        """Test network connectivity test failure"""
        # Mock failed ping responses
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="ping: cannot resolve 8.8.8.8: Unknown host"
            )
            
            result = self.validator.test_connectivity()
            
            self.assertFalse(result["success"])
            self.assertIn("error", result)
    
    def test_speed_test_execution(self):
        """Test speed test execution"""
        # Mock speedtest command
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"download": {"bandwidth": 26214400}, "upload": {"bandwidth": 5242880}, "ping": {"latency": 45.2}}',
                stderr=""
            )
            
            result = self.validator.run_speed_test()
            
            self.assertTrue(result["success"])
            self.assertIn("download_speed", result)
            self.assertIn("upload_speed", result)
            self.assertIn("latency", result)
            self.assertGreater(result["download_speed"], 0)
    
    def test_speed_test_with_server_selection(self):
        """Test speed test with specific server selection"""
        # Mock speedtest with server selection
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"download": {"bandwidth": 31457280}, "upload": {"bandwidth": 6291456}, "ping": {"latency": 32.1}}',
                stderr=""
            )
            
            result = self.validator.run_speed_test(server_id="12345")
            
            self.assertTrue(result["success"])
            self.assertGreater(result["download_speed"], 25)  # Should be faster with specific server
    
    def test_traffic_monitoring_start_stop(self):
        """Test traffic monitoring thread management"""
        # Mock network interface data
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [
                {"name": "enp1s0", "bytes_sent": 1048576, "bytes_received": 2097152, "status": "up"}
            ]
        })
        
        # Start monitoring
        result = self.validator.start_monitoring()
        self.assertTrue(result)
        self.assertTrue(self.validator.monitoring_enabled)
        
        # Stop monitoring
        result = self.validator.stop_monitoring()
        self.assertTrue(result)
        self.assertFalse(self.validator.monitoring_enabled)
    
    def test_traffic_metrics_collection(self):
        """Test traffic metrics collection"""
        # Mock network statistics
        self.client.set_response("status/system/network/statistics", {
            "interfaces": {
                "enp1s0": {
                    "bytes_sent": 10485760,
                    "bytes_received": 20971520,
                    "packets_sent": 10000,
                    "packets_received": 15000,
                    "errors": 0,
                    "dropped": 0
                }
            }
        })
        
        metrics = self.validator.collect_traffic_metrics()
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.interface, "enp1s0")
        self.assertEqual(metrics.bytes_sent, 10485760)
        self.assertEqual(metrics.packets_received, 15000)
        self.assertEqual(metrics.errors, 0)
    
    def test_bandwidth_validation_sufficient(self):
        """Test bandwidth validation with sufficient bandwidth"""
        # Mock high bandwidth results
        test_result = {
            "success": True,
            "download_speed": 50.0,  # 50 Mbps
            "upload_speed": 10.0,    # 10 Mbps
            "latency": 25.0
        }
        
        validation = self.validator.validate_bandwidth(
            test_result, 
            min_download=25.0, 
            min_upload=5.0
        )
        
        self.assertTrue(validation["sufficient"])
        self.assertGreater(validation["download_margin"], 0)
        self.assertGreater(validation["upload_margin"], 0)
    
    def test_bandwidth_validation_insufficient(self):
        """Test bandwidth validation with insufficient bandwidth"""
        # Mock low bandwidth results
        test_result = {
            "success": True,
            "download_speed": 15.0,  # 15 Mbps (below 25 Mbps requirement)
            "upload_speed": 3.0,     # 3 Mbps (below 5 Mbps requirement)
            "latency": 75.0
        }
        
        validation = self.validator.validate_bandwidth(
            test_result,
            min_download=25.0,
            min_upload=5.0
        )
        
        self.assertFalse(validation["sufficient"])
        self.assertLess(validation["download_margin"], 0)
        self.assertLess(validation["upload_margin"], 0)
        self.assertIn("recommendations", validation)
    
    def test_quality_of_service_monitoring(self):
        """Test QoS monitoring and analysis"""
        # Mock QoS data
        self.client.set_response("status/system/network/qos", {
            "interfaces": {
                "enp1s0": {
                    "priority_queues": [
                        {"priority": "high", "packets": 1000, "bytes": 1048576, "drops": 0},
                        {"priority": "normal", "packets": 5000, "bytes": 5242880, "drops": 2},
                        {"priority": "low", "packets": 2000, "bytes": 2097152, "drops": 5}
                    ]
                }
            }
        })
        
        qos_status = self.validator.monitor_qos()
        
        self.assertIn("interfaces", qos_status)
        self.assertIn("enp1s0", qos_status["interfaces"])
        self.assertEqual(len(qos_status["interfaces"]["enp1s0"]["queues"]), 3)
        self.assertIn("total_drops", qos_status)
    
    def test_network_test_comprehensive(self):
        """Test comprehensive network testing"""
        # Mock all network test components
        with patch.object(self.validator, 'test_connectivity') as mock_conn, \
             patch.object(self.validator, 'run_speed_test') as mock_speed, \
             patch.object(self.validator, 'monitor_qos') as mock_qos:
            
            mock_conn.return_value = {"success": True, "latency": 25.0}
            mock_speed.return_value = {"success": True, "download_speed": 50.0, "upload_speed": 10.0}
            mock_qos.return_value = {"total_drops": 0, "interfaces": {}}
            
            result = self.validator.run_comprehensive_test()
            
            self.assertTrue(result["success"])
            self.assertIn("connectivity", result)
            self.assertIn("speed_test", result)
            self.assertIn("qos_status", result)
            self.assertIn("overall_score", result)
    
    def test_network_test_failure_scenarios(self):
        """Test network test failure handling"""
        # Mock failed connectivity
        with patch.object(self.validator, 'test_connectivity') as mock_conn:
            mock_conn.return_value = {"success": False, "error": "Network unreachable"}
            
            result = self.validator.run_comprehensive_test()
            
            self.assertFalse(result["success"])
            self.assertIn("connectivity_failed", result["reason"])
    
    def test_latency_analysis(self):
        """Test latency analysis and categorization"""
        # Test excellent latency
        analysis = self.validator.analyze_latency(15.0)
        self.assertEqual(analysis["category"], "excellent")
        self.assertGreater(analysis["score"], 90)
        
        # Test poor latency
        analysis = self.validator.analyze_latency(150.0)
        self.assertEqual(analysis["category"], "poor")
        self.assertLess(analysis["score"], 50)
    
    def test_packet_loss_detection(self):
        """Test packet loss detection and reporting"""
        # Mock ping with packet loss
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="10 packets transmitted, 8 received, 20% packet loss",
                stderr=""
            )
            
            result = self.validator.test_packet_loss()
            
            self.assertIn("packet_loss", result)
            self.assertEqual(result["packet_loss"], 20.0)
            self.assertFalse(result["acceptable"])  # 20% loss is not acceptable
    
    def test_traffic_analysis_patterns(self):
        """Test traffic pattern analysis"""
        # Create mock traffic data over time
        traffic_data = [
            {"timestamp": 1000, "bytes_sent": 1000000, "bytes_received": 2000000},
            {"timestamp": 1001, "bytes_sent": 1500000, "bytes_received": 2500000},
            {"timestamp": 1002, "bytes_sent": 2000000, "bytes_received": 3000000}
        ]
        
        analysis = self.validator.analyze_traffic_patterns(traffic_data)
        
        self.assertIn("trend", analysis)
        self.assertIn("average_throughput", analysis)
        self.assertIn("peak_usage", analysis)
        self.assertEqual(analysis["trend"], "increasing")
    
    def test_interface_monitoring(self):
        """Test network interface monitoring"""
        # Mock interface statistics
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [
                {
                    "name": "enp1s0",
                    "status": "up",
                    "bytes_sent": 10000000,
                    "bytes_received": 20000000,
                    "speed": "1000 Mbps",
                    "duplex": "full"
                }
            ]
        })
        
        interfaces = self.validator.monitor_interfaces()
        
        self.assertIn("enp1s0", interfaces)
        self.assertEqual(interfaces["enp1s0"]["status"], "up")
        self.assertEqual(interfaces["enp1s0"]["speed"], "1000 Mbps")
    
    def test_dns_resolution_test(self):
        """Test DNS resolution testing"""
        # Mock DNS resolution
        with patch('socket.gethostbyname') as mock_dns:
            mock_dns.return_value = "8.8.8.8"
            
            result = self.validator.test_dns_resolution()
            
            self.assertTrue(result["success"])
            self.assertIn("resolution_time", result)
            self.assertIn("servers_tested", result)
    
    def test_wan_failover_testing(self):
        """Test WAN failover capabilities"""
        # Mock multiple WAN interfaces
        self.client.set_response("status/wan/devices", {
            "devices": [
                {"id": "wan1", "status": "connected", "priority": 1},
                {"id": "wan2", "status": "standby", "priority": 2}
            ]
        })
        
        failover_status = self.validator.test_wan_failover()
        
        self.assertIn("primary_wan", failover_status)
        self.assertIn("backup_wan", failover_status)
        self.assertIn("failover_capable", failover_status)
    
    def test_traffic_validator_status(self):
        """Test traffic validator status reporting"""
        # Add some test data
        self.validator.monitoring_enabled = True
        self.validator.test_results = [
            {"timestamp": 1000, "test_type": "speed", "result": "success"}
        ]
        
        status = self.validator.get_status()
        
        self.assertIn("monitoring_enabled", status)
        self.assertIn("test_count", status)
        self.assertIn("last_test", status)
        self.assertTrue(status["monitoring_enabled"])
        self.assertEqual(status["test_count"], 1)
    
    def test_bandwidth_trending(self):
        """Test bandwidth trending analysis"""
        # Mock historical speed test data
        historical_data = [
            {"timestamp": 1000, "download_speed": 25.0, "upload_speed": 5.0},
            {"timestamp": 1001, "download_speed": 30.0, "upload_speed": 6.0},
            {"timestamp": 1002, "download_speed": 35.0, "upload_speed": 7.0}
        ]
        
        trend = self.validator.analyze_bandwidth_trend(historical_data)
        
        self.assertIn("download_trend", trend)
        self.assertIn("upload_trend", trend)
        self.assertEqual(trend["download_trend"], "improving")
        self.assertEqual(trend["upload_trend"], "improving")
    
    def test_network_topology_discovery(self):
        """Test network topology discovery"""
        # Mock traceroute results
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1  192.168.1.1  1.234 ms\n2  10.0.0.1  15.678 ms\n3  8.8.8.8  25.123 ms",
                stderr=""
            )
            
            topology = self.validator.discover_network_topology()
            
            self.assertIn("hops", topology)
            self.assertGreater(len(topology["hops"]), 0)
            self.assertIn("total_hops", topology)


class TestTrafficValidatorUtilityFunctions(unittest.TestCase):
    """Test utility functions for traffic validator"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset global instance
        import traffic_validator
        traffic_validator._traffic_validator = None
    
    def test_get_traffic_validator_singleton(self):
        """Test traffic validator singleton pattern"""
        client = MockCSClient()
        
        # First call creates instance
        validator1 = get_traffic_validator(client)
        self.assertIsNotNone(validator1)
        
        # Second call returns same instance
        validator2 = get_traffic_validator()
        self.assertIs(validator1, validator2)
    
    def test_validate_network_connectivity_function(self):
        """Test validate_network_connectivity utility function"""
        client = MockCSClient()
        
        # Mock successful validation
        with patch('traffic_validator.get_traffic_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_validator.test_connectivity.return_value = {"success": True, "latency": 25.0}
            mock_get_validator.return_value = mock_validator
            
            result = validate_network_connectivity(client)
            
            self.assertTrue(result["success"])
            mock_validator.test_connectivity.assert_called_once()
    
    def test_run_speed_test_function(self):
        """Test run_speed_test utility function"""
        client = MockCSClient()
        
        # Mock speed test execution
        with patch('traffic_validator.get_traffic_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_validator.run_speed_test.return_value = {"success": True, "download_speed": 50.0}
            mock_get_validator.return_value = mock_validator
            
            result = run_speed_test(client)
            
            self.assertTrue(result["success"])
            mock_validator.run_speed_test.assert_called_once()


class TestTrafficValidatorEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = MockCSClient()
        self.validator = TrafficValidator(self.client)
        
        # Reset global instance
        import traffic_validator
        traffic_validator._traffic_validator = None
    
    def test_network_api_unavailable(self):
        """Test operation when network API is unavailable"""
        # No network data available
        self.client.set_response("status/system/network/interfaces", None)
        
        metrics = self.validator.collect_traffic_metrics()
        
        # Should return None or empty metrics
        self.assertIsNone(metrics)
    
    def test_speedtest_command_not_found(self):
        """Test handling when speedtest command is not available"""
        # Mock command not found
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("speedtest-cli not found")
            
            result = self.validator.run_speed_test()
            
            self.assertFalse(result["success"])
            self.assertIn("command not found", result["error"].lower())
    
    def test_malformed_speedtest_output(self):
        """Test handling of malformed speedtest output"""
        # Mock malformed JSON output
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Invalid JSON output",
                stderr=""
            )
            
            result = self.validator.run_speed_test()
            
            self.assertFalse(result["success"])
            self.assertIn("parse", result["error"].lower())
    
    def test_network_interface_down(self):
        """Test handling of network interface failures"""
        # Mock interface down
        self.client.set_response("status/system/network/interfaces", {
            "interfaces": [
                {"name": "enp1s0", "status": "down", "error": "Interface down"}
            ]
        })
        
        interfaces = self.validator.monitor_interfaces()
        
        self.assertIn("enp1s0", interfaces)
        self.assertEqual(interfaces["enp1s0"]["status"], "down")
    
    def test_high_latency_scenarios(self):
        """Test handling of extremely high latency"""
        # Mock very high latency
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="64 bytes from 8.8.8.8: icmp_seq=1 time=1500.0 ms",
                stderr=""
            )
            
            result = self.validator.test_connectivity()
            
            self.assertTrue(result["success"])
            self.assertGreater(result["latency"], 1000)
            self.assertIn("warning", result)
    
    def test_no_internet_connection(self):
        """Test handling of no internet connection"""
        # Mock no internet connection
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=2,
                stdout="",
                stderr="ping: sendto: Network is unreachable"
            )
            
            result = self.validator.test_connectivity()
            
            self.assertFalse(result["success"])
            self.assertIn("unreachable", result["error"].lower())
    
    def test_concurrent_test_execution(self):
        """Test concurrent test execution"""
        # Mock multiple tests running simultaneously
        with patch.object(self.validator, 'test_connectivity') as mock_test:
            mock_test.return_value = {"success": True, "latency": 25.0}
            
            # Run multiple tests concurrently
            results = []
            for i in range(3):
                result = self.validator.run_comprehensive_test()
                results.append(result)
            
            # All should succeed
            for result in results:
                self.assertTrue(result["success"])
    
    def test_traffic_validator_without_client(self):
        """Test traffic validator operation without CS client"""
        validator = TrafficValidator(client=None)
        
        # Should use mock/fallback behavior
        result = validator.monitor_interfaces()
        
        # Should not crash
        self.assertIsInstance(result, dict)
    
    def test_memory_usage_monitoring(self):
        """Test memory usage during long-running tests"""
        # Mock long-running monitoring
        self.validator.start_monitoring()
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Should not consume excessive memory
        status = self.validator.get_status()
        self.assertIn("monitoring_enabled", status)
        
        # Clean up
        self.validator.stop_monitoring()


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Traffic Validator Test Results")
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