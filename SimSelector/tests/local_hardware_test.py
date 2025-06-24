#!/usr/bin/env python3
"""
Local Hardware Testing for SimSelector
=====================================
Runs SimSelector locally while connecting to real Cradlepoint hardware
via SDK API using sdk_settings.ini configuration.
"""

import os
import sys
import time
import json
import subprocess
import configparser
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging

# Add parent directory to path for SimSelector imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('local_hardware_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class HardwareTestResult:
    """Result of a hardware test run."""
    test_name: str
    status: str  # PASS, FAIL, ERROR, TIMEOUT
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    sim_results: Dict[str, Any] = None
    final_description: str = ""
    logs: List[str] = None
    error_message: str = ""
    
    def __post_init__(self):
        if self.sim_results is None:
            self.sim_results = {}
        if self.logs is None:
            self.logs = []


class LocalHardwareTester:
    """Local testing framework for SimSelector with real hardware."""
    
    def __init__(self, sdk_settings_path: str = "sdk_settings.ini"):
        self.sdk_settings_path = sdk_settings_path
        self.device_config = {}
        self.test_results: List[HardwareTestResult] = []
        
        # Load SDK settings
        self._load_sdk_settings()
    
    def _load_sdk_settings(self):
        """Load and validate SDK settings."""
        if not os.path.exists(self.sdk_settings_path):
            raise FileNotFoundError(f"SDK settings file not found: {self.sdk_settings_path}")
        
        config = configparser.ConfigParser()
        config.read(self.sdk_settings_path)
        
        # Extract device configuration
        if 'csclient' in config:
            self.device_config = dict(config['csclient'])
            logger.info(f"Loaded SDK settings for device: {self.device_config.get('router_id', 'Unknown')}")
        else:
            raise ValueError("Invalid SDK settings file - missing [csclient] section")
    
    def run_validation_test(self, timeout: int = 300) -> HardwareTestResult:
        """Run validation phase test on real hardware."""
        result = HardwareTestResult(
            test_name="validation_phase",
            status="RUNNING",
            start_time=datetime.now()
        )
        
        logger.info("🔍 Starting Validation Phase Test on Real Hardware")
        
        try:
            # Create a test version of SimSelector that only runs validation
            test_script = self._create_validation_test_script()
            
            # Run the test script
            process = subprocess.Popen(
                [sys.executable, test_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Monitor execution with timeout
            start_time = time.time()
            output_lines = []
            
            while process.poll() is None:
                if time.time() - start_time > timeout:
                    process.terminate()
                    result.status = "TIMEOUT"
                    result.error_message = f"Test timed out after {timeout} seconds"
                    break
                
                # Read output line by line
                try:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        logger.info(f"📱 {line.strip()}")
                except:
                    pass
                
                time.sleep(1)
            
            if result.status != "TIMEOUT":
                # Get final output
                stdout, stderr = process.communicate()
                if stdout:
                    output_lines.extend(stdout.strip().split('\n'))
                
                result.logs = output_lines
                
                # Parse results
                if process.returncode == 0:
                    result.status = "PASS"
                    result = self._parse_validation_results(result, output_lines)
                else:
                    result.status = "FAIL"
                    result.error_message = stderr if stderr else "Process failed with non-zero exit code"
        
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            logger.error(f"Validation test error: {e}")
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            self.test_results.append(result)
            
            # Cleanup test script
            if 'test_script' in locals():
                try:
                    os.remove(test_script)
                except:
                    pass
        
        return result
    
    def run_performance_test(self, timeout: int = 900) -> HardwareTestResult:
        """Run performance phase test on real hardware."""
        result = HardwareTestResult(
            test_name="performance_phase",
            status="RUNNING",
            start_time=datetime.now()
        )
        
        logger.info("🚀 Starting Performance Phase Test on Real Hardware")
        
        try:
            # Create a test version of SimSelector that runs full performance testing
            test_script = self._create_performance_test_script()
            
            # Run the test script
            process = subprocess.Popen(
                [sys.executable, test_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Monitor execution with timeout
            start_time = time.time()
            output_lines = []
            
            while process.poll() is None:
                if time.time() - start_time > timeout:
                    process.terminate()
                    result.status = "TIMEOUT"
                    result.error_message = f"Test timed out after {timeout} seconds"
                    break
                
                # Read output line by line
                try:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        logger.info(f"📊 {line.strip()}")
                except:
                    pass
                
                time.sleep(1)
            
            if result.status != "TIMEOUT":
                # Get final output
                stdout, stderr = process.communicate()
                if stdout:
                    output_lines.extend(stdout.strip().split('\n'))
                
                result.logs = output_lines
                
                # Parse results
                if process.returncode == 0:
                    result.status = "PASS"
                    result = self._parse_performance_results(result, output_lines)
                else:
                    result.status = "FAIL"
                    result.error_message = stderr if stderr else "Process failed with non-zero exit code"
        
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            logger.error(f"Performance test error: {e}")
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            self.test_results.append(result)
            
            # Cleanup test script
            if 'test_script' in locals():
                try:
                    os.remove(test_script)
                except:
                    pass
        
        return result
    
    def run_full_cycle_test(self, timeout: int = 1200) -> HardwareTestResult:
        """Run complete SimSelector cycle test."""
        result = HardwareTestResult(
            test_name="full_cycle",
            status="RUNNING",
            start_time=datetime.now()
        )
        
        logger.info("🔄 Starting Full Cycle Test on Real Hardware")
        
        try:
            # Create a test version that runs the complete cycle
            test_script = self._create_full_cycle_test_script()
            
            # Run the test script
            process = subprocess.Popen(
                [sys.executable, test_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Monitor execution with timeout
            start_time = time.time()
            output_lines = []
            
            while process.poll() is None:
                if time.time() - start_time > timeout:
                    process.terminate()
                    result.status = "TIMEOUT"
                    result.error_message = f"Test timed out after {timeout} seconds"
                    break
                
                # Read output line by line
                try:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        logger.info(f"🔄 {line.strip()}")
                except:
                    pass
                
                time.sleep(1)
            
            if result.status != "TIMEOUT":
                # Get final output
                stdout, stderr = process.communicate()
                if stdout:
                    output_lines.extend(stdout.strip().split('\n'))
                
                result.logs = output_lines
                
                # Parse results
                if process.returncode == 0:
                    result.status = "PASS"
                    result = self._parse_full_cycle_results(result, output_lines)
                else:
                    result.status = "FAIL"
                    result.error_message = stderr if stderr else "Process failed with non-zero exit code"
        
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            logger.error(f"Full cycle test error: {e}")
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            self.test_results.append(result)
            
            # Cleanup test script
            if 'test_script' in locals():
                try:
                    os.remove(test_script)
                except:
                    pass
        
        return result
    
    def run_signal_quality_test(self) -> HardwareTestResult:
        """Test signal quality detection and classification."""
        result = HardwareTestResult(
            test_name="signal_quality",
            status="RUNNING",
            start_time=datetime.now()
        )
        
        logger.info("📶 Starting Signal Quality Test on Real Hardware")
        
        try:
            # Create a test script that only checks signal quality
            test_script = self._create_signal_test_script()
            
            # Run the test script
            process = subprocess.run(
                [sys.executable, test_script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            result.logs = process.stdout.split('\n') if process.stdout else []
            
            if process.returncode == 0:
                result.status = "PASS"
                result = self._parse_signal_results(result, result.logs)
            else:
                result.status = "FAIL"
                result.error_message = process.stderr if process.stderr else "Signal test failed"
        
        except subprocess.TimeoutExpired:
            result.status = "TIMEOUT"
            result.error_message = "Signal quality test timed out"
        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            self.test_results.append(result)
            
            # Cleanup test script
            if 'test_script' in locals():
                try:
                    os.remove(test_script)
                except:
                    pass
        
        return result
    
    def _create_validation_test_script(self) -> str:
        """Create a temporary test script for validation phase."""
        script_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SimSelector import run_validation_phase, SimSelector
import state_manager

try:
    # Initialize SimSelector
    global simselector
    simselector = SimSelector()
    
    print("🔍 Starting Validation Phase Test")
    print("=" * 50)
    
    # Reset state to validation
    state_manager.set_state('phase', 'validation')
    
    # Run validation phase
    run_validation_phase()
    
    print("✅ Validation phase completed successfully")
    
except Exception as e:
    print(f"❌ Validation phase failed: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        
        script_path = "temp_validation_test.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path
    
    def _create_performance_test_script(self) -> str:
        """Create a temporary test script for performance phase."""
        script_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SimSelector import run_performance_phase, SimSelector
import state_manager

try:
    # Initialize SimSelector
    global simselector
    simselector = SimSelector()
    
    print("🚀 Starting Performance Phase Test")
    print("=" * 50)
    
    # Set state to performance (assuming validation already done)
    state_manager.set_state('phase', 'performance')
    
    # Run performance phase
    run_performance_phase()
    
    print("✅ Performance phase completed successfully")
    
except Exception as e:
    print(f"❌ Performance phase failed: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        
        script_path = "temp_performance_test.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path
    
    def _create_full_cycle_test_script(self) -> str:
        """Create a temporary test script for full cycle."""
        script_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SimSelector import run_validation_phase, run_performance_phase, SimSelector
import state_manager

try:
    # Initialize SimSelector
    global simselector
    simselector = SimSelector()
    
    print("🔄 Starting Full Cycle Test")
    print("=" * 50)
    
    # Reset state and run complete cycle
    state_manager.set_state('phase', 'validation')
    
    print("Phase 1: Validation")
    run_validation_phase()
    print("✅ Validation phase completed")
    
    print("\\nPhase 2: Performance")
    run_performance_phase()
    print("✅ Performance phase completed")
    
    print("\\n🎉 Full cycle completed successfully!")
    
except Exception as e:
    print(f"❌ Full cycle failed: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        
        script_path = "temp_full_cycle_test.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path
    
    def _create_signal_test_script(self) -> str:
        """Create a temporary test script for signal quality testing."""
        script_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SimSelector import SimSelector

try:
    # Initialize SimSelector
    simselector = SimSelector()
    
    print("📶 Starting Signal Quality Test")
    print("=" * 50)
    
    # Find SIMs
    simselector.find_sims()
    
    # Test signal quality on each SIM
    for sim_uid, sim_data in simselector.sims.items():
        print(f"\\n📱 Testing {{sim_uid}}:")
        
        # Get diagnostics
        diagnostics = simselector.client.get(f'{{simselector.STATUS_DEVS_PATH}}/{{sim_uid}}/diagnostics')
        if diagnostics:
            rsrp = diagnostics.get('RSRP')
            carrier = diagnostics.get('HOMECARRID', 'Unknown')
            tech = sim_data.get('info', {{}}).get('tech', 'Unknown')
            
            # Classify signal
            signal_quality = simselector.classify_signal(rsrp)
            
            print(f"  RSRP: {{rsrp}} dBm")
            print(f"  Quality: {{signal_quality}}")
            print(f"  Carrier: {{carrier}}")
            print(f"  Technology: {{tech}}")
        else:
            print(f"  ❌ No diagnostics available")
    
    print("\\n✅ Signal quality test completed")
    
except Exception as e:
    print(f"❌ Signal quality test failed: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        
        script_path = "temp_signal_test.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        return script_path
    
    def _parse_validation_results(self, result: HardwareTestResult, logs: List[str]) -> HardwareTestResult:
        """Parse validation phase results from logs."""
        for log in logs:
            if "Staging -" in log:
                result.final_description = log
                # Parse SIM information from staging results
                parts = log.split(" | ")
                for part in parts[1:]:  # Skip "Staging -" part
                    if ":" in part:
                        sim_info = part.split(":")
                        if len(sim_info) >= 2:
                            sim_name = sim_info[0].strip()
                            status_quality = sim_info[1].strip()
                            result.sim_results[sim_name] = status_quality
        
        return result
    
    def _parse_performance_results(self, result: HardwareTestResult, logs: List[str]) -> HardwareTestResult:
        """Parse performance phase results from logs."""
        for log in logs:
            if "DL:" in log and "UL:" in log:
                result.final_description = log
                # Parse speed test results
                if "FAILED TO MEET MINIMUMS" in log:
                    result.sim_results['minimums_met'] = False
                else:
                    result.sim_results['minimums_met'] = True
                
                # Count SIMs tested
                dl_count = log.count("DL:")
                result.sim_results['sims_tested'] = dl_count
        
        return result
    
    def _parse_full_cycle_results(self, result: HardwareTestResult, logs: List[str]) -> HardwareTestResult:
        """Parse full cycle results from logs."""
        result = self._parse_validation_results(result, logs)
        result = self._parse_performance_results(result, logs)
        
        # Check if both phases completed
        validation_complete = any("Validation phase completed" in log for log in logs)
        performance_complete = any("Performance phase completed" in log for log in logs)
        
        result.sim_results['validation_completed'] = validation_complete
        result.sim_results['performance_completed'] = performance_complete
        result.sim_results['full_cycle_completed'] = validation_complete and performance_complete
        
        return result
    
    def _parse_signal_results(self, result: HardwareTestResult, logs: List[str]) -> HardwareTestResult:
        """Parse signal quality results from logs."""
        current_sim = None
        
        for log in logs:
            if "Testing mdm-sim" in log:
                current_sim = log.split("Testing ")[1].replace(":", "")
                result.sim_results[current_sim] = {}
            elif current_sim and "RSRP:" in log:
                rsrp_value = log.split("RSRP: ")[1].split(" dBm")[0]
                result.sim_results[current_sim]['rsrp'] = rsrp_value
            elif current_sim and "Quality:" in log:
                quality = log.split("Quality: ")[1]
                result.sim_results[current_sim]['quality'] = quality
            elif current_sim and "Carrier:" in log:
                carrier = log.split("Carrier: ")[1]
                result.sim_results[current_sim]['carrier'] = carrier
            elif current_sim and "Technology:" in log:
                tech = log.split("Technology: ")[1]
                result.sim_results[current_sim]['technology'] = tech
        
        return result
    
    def run_all_tests(self) -> List[HardwareTestResult]:
        """Run all available hardware tests."""
        logger.info("🧪 Starting Complete Hardware Test Suite")
        
        tests = [
            ("Signal Quality", lambda: self.run_signal_quality_test()),
            ("Validation Phase", lambda: self.run_validation_test()),
            ("Performance Phase", lambda: self.run_performance_test()),
            ("Full Cycle", lambda: self.run_full_cycle_test()),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\\n{'='*60}")
            logger.info(f"🔬 Running: {test_name}")
            logger.info(f"{'='*60}")
            
            try:
                result = test_func()
                status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "🚨", "TIMEOUT": "⏰"}
                logger.info(f"{status_emoji.get(result.status, '❓')} {test_name}: {result.status} ({result.duration:.1f}s)")
            except Exception as e:
                logger.error(f"❌ {test_name} failed with exception: {e}")
        
        return self.test_results
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report."""
        if not self.test_results:
            return "No test results available"
        
        report_lines = [
            "# SimSelector Local Hardware Test Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Device: {self.device_config.get('router_id', 'Unknown')}",
            "",
            "## Summary",
            f"- Total Tests: {len(self.test_results)}",
            f"- Passed: {len([r for r in self.test_results if r.status == 'PASS'])}",
            f"- Failed: {len([r for r in self.test_results if r.status == 'FAIL'])}",
            f"- Errors: {len([r for r in self.test_results if r.status == 'ERROR'])}",
            f"- Timeouts: {len([r for r in self.test_results if r.status == 'TIMEOUT'])}",
            ""
        ]
        
        # Individual test results
        for result in self.test_results:
            status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "🚨", "TIMEOUT": "⏰"}
            report_lines.extend([
                f"## {status_emoji.get(result.status, '❓')} {result.test_name.replace('_', ' ').title()}",
                f"- Status: {result.status}",
                f"- Duration: {result.duration:.1f}s" if result.duration else "- Duration: N/A",
            ])
            
            if result.error_message:
                report_lines.append(f"- Error: {result.error_message}")
            
            if result.final_description:
                report_lines.append(f"- Final Result: {result.final_description}")
            
            if result.sim_results:
                report_lines.append("- SIM Results:")
                for key, value in result.sim_results.items():
                    report_lines.append(f"  - {key}: {value}")
            
            report_lines.append("")
        
        return "\\n".join(report_lines)
    
    def save_results(self, filename: str = "hardware_test_results.json"):
        """Save test results to JSON file."""
        results_data = []
        for result in self.test_results:
            result_dict = {
                'test_name': result.test_name,
                'status': result.status,
                'start_time': result.start_time.isoformat(),
                'end_time': result.end_time.isoformat() if result.end_time else None,
                'duration': result.duration,
                'sim_results': result.sim_results,
                'final_description': result.final_description,
                'error_message': result.error_message,
                'logs': result.logs
            }
            results_data.append(result_dict)
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        logger.info(f"Results saved to {filename}")


def main():
    """Main entry point for local hardware testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SimSelector Local Hardware Testing')
    parser.add_argument('--sdk-settings', default='../sdk_settings.ini', 
                       help='Path to SDK settings file')
    parser.add_argument('--test', choices=['signal', 'validation', 'performance', 'full', 'all'],
                       default='all', help='Specific test to run')
    parser.add_argument('--report', default='hardware_test_report.md',
                       help='Report output file')
    parser.add_argument('--results', default='hardware_test_results.json',
                       help='JSON results file')
    
    args = parser.parse_args()
    
    try:
        # Create tester instance
        tester = LocalHardwareTester(args.sdk_settings)
        
        # Run specified test(s)
        if args.test == 'signal':
            tester.run_signal_quality_test()
        elif args.test == 'validation':
            tester.run_validation_test()
        elif args.test == 'performance':
            tester.run_performance_test()
        elif args.test == 'full':
            tester.run_full_cycle_test()
        else:  # all
            tester.run_all_tests()
        
        # Generate and save report
        report = tester.generate_report()
        with open(args.report, 'w') as f:
            f.write(report)
        
        tester.save_results(args.results)
        
        # Print summary
        total_tests = len(tester.test_results)
        passed_tests = len([r for r in tester.test_results if r.status == 'PASS'])
        
        print(f"\\n🏁 Local Hardware Testing Complete!")
        print(f"📊 Results: {passed_tests}/{total_tests} passed")
        print(f"📝 Report: {args.report}")
        print(f"💾 Data: {args.results}")
        
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 