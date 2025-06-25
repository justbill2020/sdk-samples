#!/usr/bin/env python3
"""
SimSelector v2.6.0 Test Runner

Provides consistent test execution with individual test control, comprehensive testing,
and detailed reporting. Supports running specific tests, test suites, or full system validation.

Usage Examples:
    # Run all tests with coverage
    python tests/test_runner.py --all --coverage
    
    # Run specific test suite
    python tests/test_runner.py --suite dashboard
    python tests/test_runner.py --suite security
    python tests/test_runner.py --suite integration
    
    # Run individual test
    python tests/test_runner.py --test test_dashboard_server.py::TestDashboardServer::test_server_lifecycle
    
    # Run with specific scenarios
    python tests/test_runner.py --scenario phase_transitions
    python tests/test_runner.py --scenario security_validation
    
    # Generate detailed report
    python tests/test_runner.py --all --report --output-dir ./test_reports
    
    # Quick smoke test
    python tests/test_runner.py --smoke
"""

import os
import sys
import argparse
import subprocess
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import unittest
import importlib.util

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestRunner:
    """Comprehensive test runner for SimSelector v2.6.0"""
    
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(__file__))
        self.tests_dir = os.path.join(self.project_root, 'tests')
        self.results = {}
        self.start_time = None
        self.end_time = None
        
        # Test suites configuration
        self.test_suites = {
            'unit': [
                'test_phase_manager.py',
                'test_security_manager.py',
                'test_firewall_manager.py',
                'test_dashboard_server.py'
            ],
            'integration': [
                'test_comprehensive_system.py'
            ],
            'dashboard': [
                'test_dashboard_server.py'
            ],
            'security': [
                'test_security_manager.py'
            ],
            'phase': [
                'test_phase_manager.py'
            ],
            'firewall': [
                'test_firewall_manager.py'
            ]
        }
        
        # Test scenarios configuration
        self.test_scenarios = {
            'smoke': {
                'description': 'Quick smoke tests to verify basic functionality',
                'tests': [
                    'test_phase_manager.py::TestPhaseManager::test_phase_initialization',
                    'test_security_manager.py::TestSecurityManager::test_security_initialization',
                    'test_dashboard_server.py::TestDashboardServer::test_server_lifecycle'
                ]
            },
            'phase_transitions': {
                'description': 'Complete phase transition workflow testing',
                'tests': [
                    'test_phase_manager.py::TestPhaseManager::test_phase_transitions',
                    'test_phase_manager.py::TestPhaseManager::test_transition_validation',
                    'test_comprehensive_system.py::TestSystemIntegration::test_phase_transitions'
                ]
            },
            'security_validation': {
                'description': 'Comprehensive security framework testing',
                'tests': [
                    'test_security_manager.py::TestSecurityManager::test_ip_validation',
                    'test_security_manager.py::TestSecurityManager::test_phase_access_control',
                    'test_security_manager.py::TestSecurityManager::test_request_validation',
                    'test_comprehensive_system.py::TestSystemIntegration::test_security_integration'
                ]
            },
            'dashboard_functionality': {
                'description': 'Dashboard server functionality and integration',
                'tests': [
                    'test_dashboard_server.py::TestDashboardServer::test_server_lifecycle',
                    'test_dashboard_server.py::TestDashboardServer::test_api_endpoints',
                    'test_dashboard_server.py::TestDashboardServer::test_template_rendering',
                    'test_dashboard_server.py::TestDashboardServer::test_static_file_serving'
                ]
            },
            'error_handling': {
                'description': 'Error handling and recovery testing',
                'tests': [
                    'test_dashboard_server.py::TestDashboardServer::test_error_handling',
                    'test_comprehensive_system.py::TestSystemIntegration::test_error_handling_integration'
                ]
            },
            'performance': {
                'description': 'Performance and reliability testing',
                'tests': [
                    'test_dashboard_server.py::TestDashboardServer::test_concurrent_requests',
                    'test_comprehensive_system.py::TestSystemIntegration::test_performance_benchmarks',
                    'test_comprehensive_system.py::TestSystemIntegration::test_concurrent_operations'
                ]
            }
        }
    
    def run_tests(self, args) -> bool:
        """Run tests based on provided arguments"""
        self.start_time = time.time()
        
        try:
            if args.all:
                return self._run_all_tests(args)
            elif args.suite:
                return self._run_test_suite(args.suite, args)
            elif args.test:
                return self._run_specific_test(args.test, args)
            elif args.scenario:
                return self._run_test_scenario(args.scenario, args)
            elif args.smoke:
                return self._run_test_scenario('smoke', args)
            else:
                print("No test selection specified. Use --help for options.")
                return False
        
        finally:
            self.end_time = time.time()
            if args.report:
                self._generate_report(args)
    
    def _run_all_tests(self, args) -> bool:
        """Run all available tests"""
        print("Running all SimSelector v2.6.0 tests...")
        print("=" * 60)
        
        success = True
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        # Run all test suites
        for suite_name, test_files in self.test_suites.items():
            print(f"\n📋 Running {suite_name.upper()} test suite...")
            
            suite_success = self._run_test_suite(suite_name, args, verbose=False)
            if not suite_success:
                success = False
            
            # Count results
            if suite_name in self.results:
                suite_results = self.results[suite_name]
                total_tests += suite_results.get('total', 0)
                passed_tests += suite_results.get('passed', 0)
                failed_tests += suite_results.get('failed', 0)
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 ALL TESTS SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        print(f"Duration: {self.end_time - self.start_time:.2f}s")
        
        return success
    
    def _run_test_suite(self, suite_name: str, args, verbose: bool = True) -> bool:
        """Run a specific test suite"""
        if suite_name not in self.test_suites:
            print(f"❌ Unknown test suite: {suite_name}")
            print(f"Available suites: {', '.join(self.test_suites.keys())}")
            return False
        
        if verbose:
            print(f"Running {suite_name.upper()} test suite...")
            print("-" * 40)
        
        test_files = self.test_suites[suite_name]
        suite_success = True
        suite_results = {'total': 0, 'passed': 0, 'failed': 0, 'tests': []}
        
        for test_file in test_files:
            test_path = os.path.join(self.tests_dir, test_file)
            if not os.path.exists(test_path):
                print(f"⚠️  Test file not found: {test_file}")
                continue
            
            print(f"🧪 Running {test_file}...")
            
            # Build pytest command
            cmd = self._build_pytest_command(test_path, args)
            
            # Run test
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            
            # Parse results
            test_result = self._parse_test_output(result, test_file)
            suite_results['tests'].append(test_result)
            suite_results['total'] += test_result.get('total', 0)
            suite_results['passed'] += test_result.get('passed', 0)
            suite_results['failed'] += test_result.get('failed', 0)
            
            if result.returncode != 0:
                suite_success = False
                print(f"❌ {test_file} failed")
                if verbose and args.verbose:
                    print(f"Error output:\n{result.stderr}")
            else:
                print(f"✅ {test_file} passed")
        
        self.results[suite_name] = suite_results
        
        if verbose:
            print(f"\n📊 {suite_name.upper()} Suite Results:")
            print(f"Total: {suite_results['total']}, Passed: {suite_results['passed']}, Failed: {suite_results['failed']}")
        
        return suite_success
    
    def _run_specific_test(self, test_spec: str, args) -> bool:
        """Run a specific test"""
        print(f"Running specific test: {test_spec}")
        print("-" * 40)
        
        # Parse test specification
        if '::' in test_spec:
            test_file, test_method = test_spec.split('::', 1)
        else:
            test_file = test_spec
            test_method = None
        
        test_path = os.path.join(self.tests_dir, test_file)
        if not os.path.exists(test_path):
            print(f"❌ Test file not found: {test_file}")
            return False
        
        # Build pytest command
        if test_method:
            cmd = self._build_pytest_command(f"{test_path}::{test_method}", args)
        else:
            cmd = self._build_pytest_command(test_path, args)
        
        # Run test
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        # Parse and display results
        test_result = self._parse_test_output(result, test_spec)
        self.results['specific'] = test_result
        
        if result.returncode == 0:
            print(f"✅ Test passed: {test_spec}")
            return True
        else:
            print(f"❌ Test failed: {test_spec}")
            if args.verbose:
                print(f"Output:\n{result.stdout}")
                print(f"Error:\n{result.stderr}")
            return False
    
    def _run_test_scenario(self, scenario_name: str, args) -> bool:
        """Run a specific test scenario"""
        if scenario_name not in self.test_scenarios:
            print(f"❌ Unknown test scenario: {scenario_name}")
            print(f"Available scenarios: {', '.join(self.test_scenarios.keys())}")
            return False
        
        scenario = self.test_scenarios[scenario_name]
        print(f"Running {scenario_name.upper()} scenario...")
        print(f"Description: {scenario['description']}")
        print("-" * 60)
        
        scenario_success = True
        scenario_results = {'total': 0, 'passed': 0, 'failed': 0, 'tests': []}
        
        for test_spec in scenario['tests']:
            print(f"🧪 Running {test_spec}...")
            
            # Parse test specification
            if '::' in test_spec:
                test_file, test_method = test_spec.split('::', 1)
            else:
                test_file = test_spec
                test_method = None
            
            test_path = os.path.join(self.tests_dir, test_file)
            if not os.path.exists(test_path):
                print(f"⚠️  Test file not found: {test_file}")
                continue
            
            # Build pytest command
            if test_method:
                cmd = self._build_pytest_command(f"{test_path}::{test_method}", args)
            else:
                cmd = self._build_pytest_command(test_path, args)
            
            # Run test
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            
            # Parse results
            test_result = self._parse_test_output(result, test_spec)
            scenario_results['tests'].append(test_result)
            scenario_results['total'] += test_result.get('total', 0)
            scenario_results['passed'] += test_result.get('passed', 0)
            scenario_results['failed'] += test_result.get('failed', 0)
            
            if result.returncode != 0:
                scenario_success = False
                print(f"❌ {test_spec} failed")
            else:
                print(f"✅ {test_spec} passed")
        
        self.results[scenario_name] = scenario_results
        
        print(f"\n📊 {scenario_name.upper()} Scenario Results:")
        print(f"Total: {scenario_results['total']}, Passed: {scenario_results['passed']}, Failed: {scenario_results['failed']}")
        
        return scenario_success
    
    def _build_pytest_command(self, test_path: str, args) -> List[str]:
        """Build pytest command with appropriate options"""
        cmd = ['python', '-m', 'pytest', test_path]
        
        # Add verbosity
        if args.verbose:
            cmd.append('-v')
        else:
            cmd.append('-q')
        
        # Add coverage if requested
        if args.coverage:
            cmd.extend([
                '--cov=.',
                '--cov-report=term-missing',
                '--cov-report=html:htmlcov'
            ])
        
        # Add other pytest options
        cmd.extend([
            '--tb=short',  # Short traceback format
            '--strict-markers',  # Strict marker checking
            '-ra'  # Show all test results
        ])
        
        return cmd
    
    def _parse_test_output(self, result: subprocess.CompletedProcess, test_name: str) -> Dict[str, Any]:
        """Parse pytest output to extract test results"""
        output = result.stdout
        
        test_result = {
            'name': test_name,
            'success': result.returncode == 0,
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'duration': 0.0,
            'output': output,
            'errors': result.stderr
        }
        
        # Parse pytest output for detailed results
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line and 'failed' in line:
                # Parse summary line like "5 passed, 2 failed in 1.23s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        test_result['passed'] = int(parts[i-1])
                    elif part == 'failed':
                        test_result['failed'] = int(parts[i-1])
                    elif part == 'skipped':
                        test_result['skipped'] = int(parts[i-1])
                    elif part == 'in' and i+1 < len(parts) and 's' in parts[i+1]:
                        duration_str = parts[i+1].replace('s', '')
                        try:
                            test_result['duration'] = float(duration_str)
                        except ValueError:
                            pass
        
        test_result['total'] = test_result['passed'] + test_result['failed'] + test_result['skipped']
        
        return test_result
    
    def _generate_report(self, args):
        """Generate detailed test report"""
        if not args.output_dir:
            args.output_dir = os.path.join(self.project_root, 'test_reports')
        
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Generate JSON report
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'duration': self.end_time - self.start_time if self.end_time and self.start_time else 0,
            'results': self.results,
            'summary': self._generate_summary()
        }
        
        json_report_path = os.path.join(args.output_dir, 'test_report.json')
        with open(json_report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        # Generate HTML report
        html_report_path = os.path.join(args.output_dir, 'test_report.html')
        self._generate_html_report(report_data, html_report_path)
        
        print(f"\n📄 Test reports generated:")
        print(f"   JSON: {json_report_path}")
        print(f"   HTML: {html_report_path}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test results summary"""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for suite_results in self.results.values():
            if isinstance(suite_results, dict):
                total_tests += suite_results.get('total', 0)
                total_passed += suite_results.get('passed', 0)
                total_failed += suite_results.get('failed', 0)
                total_skipped += suite_results.get('skipped', 0)
        
        return {
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_skipped': total_skipped,
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0
        }
    
    def _generate_html_report(self, report_data: Dict[str, Any], output_path: str):
        """Generate HTML test report"""
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimSelector v2.6.0 Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric h3 {{ margin: 0 0 10px 0; color: #333; }}
        .metric .value {{ font-size: 2em; font-weight: bold; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .skipped {{ color: #ffc107; }}
        .results {{ margin-top: 30px; }}
        .suite {{ margin-bottom: 30px; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; }}
        .suite h3 {{ margin: 0 0 15px 0; color: #495057; }}
        .test {{ padding: 10px; margin: 5px 0; border-radius: 4px; }}
        .test.passed {{ background: #d4edda; border-left: 4px solid #28a745; }}
        .test.failed {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SimSelector v2.6.0 Test Report</h1>
            <p>Generated on {report_data['timestamp']}</p>
            <p>Duration: {report_data['duration']:.2f} seconds</p>
        </div>
        
        <div class="summary">
            <div class="metric">
                <h3>Total Tests</h3>
                <div class="value">{report_data['summary']['total_tests']}</div>
            </div>
            <div class="metric">
                <h3>Passed</h3>
                <div class="value passed">{report_data['summary']['total_passed']}</div>
            </div>
            <div class="metric">
                <h3>Failed</h3>
                <div class="value failed">{report_data['summary']['total_failed']}</div>
            </div>
            <div class="metric">
                <h3>Success Rate</h3>
                <div class="value">{report_data['summary']['success_rate']:.1f}%</div>
            </div>
        </div>
        
        <div class="results">
            <h2>Detailed Results</h2>
"""
        
        # Add detailed results for each suite
        for suite_name, suite_results in report_data['results'].items():
            if isinstance(suite_results, dict) and 'tests' in suite_results:
                html_content += f"""
            <div class="suite">
                <h3>{suite_name.upper()} Suite</h3>
                <p>Total: {suite_results['total']}, Passed: {suite_results['passed']}, Failed: {suite_results['failed']}</p>
"""
                for test in suite_results['tests']:
                    status_class = 'passed' if test['success'] else 'failed'
                    html_content += f"""
                <div class="test {status_class}">
                    <strong>{test['name']}</strong> - {test['total']} tests, {test['duration']:.2f}s
                </div>
"""
                html_content += "</div>"
        
        html_content += """
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html_content)


def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(
        description='SimSelector v2.6.0 Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Test selection options
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--suite', choices=list(TestRunner().test_suites.keys()), help='Run specific test suite')
    parser.add_argument('--test', help='Run specific test (e.g., test_file.py::TestClass::test_method)')
    parser.add_argument('--scenario', choices=list(TestRunner().test_scenarios.keys()), help='Run test scenario')
    parser.add_argument('--smoke', action='store_true', help='Run smoke tests')
    
    # Output options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--report', action='store_true', help='Generate detailed test report')
    parser.add_argument('--output-dir', help='Output directory for reports')
    
    # Information options
    parser.add_argument('--list-suites', action='store_true', help='List available test suites')
    parser.add_argument('--list-scenarios', action='store_true', help='List available test scenarios')
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Handle information requests
    if args.list_suites:
        print("Available test suites:")
        for suite_name, test_files in runner.test_suites.items():
            print(f"  {suite_name}: {', '.join(test_files)}")
        return
    
    if args.list_scenarios:
        print("Available test scenarios:")
        for scenario_name, scenario_data in runner.test_scenarios.items():
            print(f"  {scenario_name}: {scenario_data['description']}")
        return
    
    # Run tests
    success = runner.run_tests(args)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 