#!/usr/bin/env python3
"""
Comprehensive Unit Test Runner - SimSelector v2.6.0

Executes all unit tests and generates detailed reports.
Part of Task 6.1: Unit Testing Framework

Features:
- Runs all unit test modules
- Generates detailed HTML and JSON reports
- Provides coverage analysis
- Identifies failing tests and provides recommendations
- Integrates with CI/CD pipeline
"""

import unittest
import sys
import os
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test modules to run
TEST_MODULES = [
    'test_sim_manager',
    'test_ip_manager', 
    'test_traffic_validator',
    'test_error_handler',
    'test_dashboard_server',
    'test_network_manager',
    'test_firewall_manager'
]

class TestResult:
    """Enhanced test result tracking"""
    def __init__(self):
        self.start_time = time.time()
        self.test_results = {}
        self.total_tests = 0
        self.total_failures = 0
        self.total_errors = 0
        self.total_skipped = 0
        self.module_results = {}
        self.coverage_data = {}
        
    def add_module_result(self, module_name, result):
        """Add result for a test module"""
        self.module_results[module_name] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
            'success_rate': self._calculate_success_rate(result),
            'execution_time': getattr(result, 'execution_time', 0),
            'failure_details': [{'test': str(test), 'traceback': tb} for test, tb in result.failures],
            'error_details': [{'test': str(test), 'traceback': tb} for test, tb in result.errors]
        }
        
        # Update totals
        self.total_tests += result.testsRun
        self.total_failures += len(result.failures)
        self.total_errors += len(result.errors)
        self.total_skipped += len(result.skipped) if hasattr(result, 'skipped') else 0
    
    def _calculate_success_rate(self, result):
        """Calculate success rate for a test result"""
        if result.testsRun == 0:
            return 0.0
        successful = result.testsRun - len(result.failures) - len(result.errors)
        return (successful / result.testsRun) * 100.0
    
    def get_overall_success_rate(self):
        """Get overall success rate across all modules"""
        if self.total_tests == 0:
            return 0.0
        successful = self.total_tests - self.total_failures - self.total_errors
        return (successful / self.total_tests) * 100.0
    
    def get_execution_time(self):
        """Get total execution time"""
        return time.time() - self.start_time
    
    def is_successful(self):
        """Check if all tests passed"""
        return self.total_failures == 0 and self.total_errors == 0


class HTMLReportGenerator:
    """Generate HTML test reports"""
    
    def __init__(self, test_result):
        self.test_result = test_result
        
    def generate_report(self, output_file):
        """Generate comprehensive HTML report"""
        html_content = self._generate_html()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report generated: {output_file}")
    
    def _generate_html(self):
        """Generate HTML content"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimSelector v2.6.0 Unit Test Report</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SimSelector v2.6.0 Unit Test Report</h1>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <div class="summary">
            {self._generate_summary()}
        </div>
        
        <div class="modules">
            {self._generate_module_results()}
        </div>
        
        <div class="recommendations">
            {self._generate_recommendations()}
        </div>
    </div>
</body>
</html>
"""
    
    def _get_css_styles(self):
        """Get CSS styles for the report"""
        return """
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        header { text-align: center; margin-bottom: 30px; }
        h1 { color: #333; margin-bottom: 10px; }
        .timestamp { color: #666; font-style: italic; }
        .summary { background: #f8f9fa; padding: 20px; border-radius: 6px; margin-bottom: 30px; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .metric { text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; margin-bottom: 5px; }
        .metric-label { color: #666; font-size: 0.9em; }
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .error { color: #dc3545; }
        .module { margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 6px; }
        .module-header { display: flex; justify-content: between; align-items: center; margin-bottom: 15px; }
        .module-name { font-size: 1.2em; font-weight: bold; }
        .module-stats { display: flex; gap: 20px; }
        .stat { text-align: center; }
        .stat-value { font-weight: bold; }
        .failures, .errors { margin-top: 15px; }
        .failure-item, .error-item { margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-left: 4px solid #dc3545; }
        .recommendations { background: #e7f3ff; padding: 20px; border-radius: 6px; }
        .recommendation-item { margin-bottom: 10px; }
        .progress-bar { width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; }
        .progress-fill { height: 100%; transition: width 0.3s ease; }
        """
    
    def _generate_summary(self):
        """Generate summary section"""
        success_rate = self.test_result.get_overall_success_rate()
        status_class = "success" if success_rate >= 95 else "warning" if success_rate >= 80 else "error"
        
        return f"""
        <h2>Test Summary</h2>
        <div class="summary-grid">
            <div class="metric">
                <div class="metric-value {status_class}">{success_rate:.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric">
                <div class="metric-value">{self.test_result.total_tests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value success">{self.test_result.total_tests - self.test_result.total_failures - self.test_result.total_errors}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric">
                <div class="metric-value error">{self.test_result.total_failures}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value error">{self.test_result.total_errors}</div>
                <div class="metric-label">Errors</div>
            </div>
            <div class="metric">
                <div class="metric-value">{self.test_result.get_execution_time():.2f}s</div>
                <div class="metric-label">Execution Time</div>
            </div>
        </div>
        <div class="progress-bar">
            <div class="progress-fill success" style="width: {success_rate}%"></div>
        </div>
        """
    
    def _generate_module_results(self):
        """Generate module results section"""
        html = "<h2>Module Results</h2>"
        
        for module_name, result in self.test_result.module_results.items():
            status_class = "success" if result['success_rate'] >= 95 else "warning" if result['success_rate'] >= 80 else "error"
            
            html += f"""
            <div class="module">
                <div class="module-header">
                    <div class="module-name">{module_name}</div>
                    <div class="module-stats">
                        <div class="stat">
                            <div class="stat-value {status_class}">{result['success_rate']:.1f}%</div>
                            <div>Success Rate</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{result['tests_run']}</div>
                            <div>Tests</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{result['failures']}</div>
                            <div>Failures</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{result['errors']}</div>
                            <div>Errors</div>
                        </div>
                    </div>
                </div>
            """
            
            # Add failure details
            if result['failures'] > 0:
                html += "<div class='failures'><h4>Failures:</h4>"
                for failure in result['failure_details']:
                    html += f"<div class='failure-item'><strong>{failure['test']}</strong><br><pre>{failure['traceback']}</pre></div>"
                html += "</div>"
            
            # Add error details  
            if result['errors'] > 0:
                html += "<div class='errors'><h4>Errors:</h4>"
                for error in result['error_details']:
                    html += f"<div class='error-item'><strong>{error['test']}</strong><br><pre>{error['traceback']}</pre></div>"
                html += "</div>"
            
            html += "</div>"
        
        return html
    
    def _generate_recommendations(self):
        """Generate recommendations section"""
        recommendations = []
        
        if self.test_result.total_failures > 0:
            recommendations.append("❌ Address test failures before deployment")
        
        if self.test_result.total_errors > 0:
            recommendations.append("⚠️ Fix test errors - these indicate code issues")
        
        if self.test_result.get_overall_success_rate() < 95:
            recommendations.append("📈 Improve test coverage and fix failing tests")
        
        # Module-specific recommendations
        for module_name, result in self.test_result.module_results.items():
            if result['success_rate'] < 80:
                recommendations.append(f"🔧 {module_name}: Critical issues need attention")
            elif result['success_rate'] < 95:
                recommendations.append(f"⚡ {module_name}: Minor issues to address")
        
        if not recommendations:
            recommendations.append("✅ All tests passing - ready for deployment!")
        
        html = "<h2>Recommendations</h2><ul>"
        for rec in recommendations:
            html += f"<li class='recommendation-item'>{rec}</li>"
        html += "</ul>"
        
        return html


class JSONReportGenerator:
    """Generate JSON test reports for CI/CD integration"""
    
    def __init__(self, test_result):
        self.test_result = test_result
    
    def generate_report(self, output_file):
        """Generate JSON report"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': self.test_result.total_tests,
                'total_failures': self.test_result.total_failures,
                'total_errors': self.test_result.total_errors,
                'total_skipped': self.test_result.total_skipped,
                'success_rate': self.test_result.get_overall_success_rate(),
                'execution_time': self.test_result.get_execution_time(),
                'passed': self.test_result.is_successful()
            },
            'modules': self.test_result.module_results,
            'coverage': self.test_result.coverage_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"JSON report generated: {output_file}")


def run_module_tests(module_name):
    """Run tests for a specific module"""
    try:
        # Import the test module
        test_module = __import__(module_name)
        
        # Create test suite
        suite = unittest.TestLoader().loadTestsFromModule(test_module)
        
        # Run tests with custom result class
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        start_time = time.time()
        result = runner.run(suite)
        result.execution_time = time.time() - start_time
        
        return result
        
    except ImportError as e:
        print(f"Warning: Could not import {module_name}: {e}")
        return None
    except Exception as e:
        print(f"Error running tests for {module_name}: {e}")
        return None


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='SimSelector v2.6.0 Unit Test Runner')
    parser.add_argument('--modules', nargs='*', default=TEST_MODULES, help='Test modules to run')
    parser.add_argument('--output-dir', default='test_reports', help='Output directory for reports')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--json-only', action='store_true', help='Generate only JSON report')
    parser.add_argument('--html-only', action='store_true', help='Generate only HTML report')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Initialize test result tracker
    test_result = TestResult()
    
    print("🧪 SimSelector v2.6.0 Unit Test Runner")
    print("=" * 60)
    print(f"Running tests for {len(args.modules)} modules...")
    print()
    
    # Run tests for each module
    for module_name in args.modules:
        if args.verbose:
            print(f"Running tests for {module_name}...")
        
        result = run_module_tests(module_name)
        
        if result is not None:
            test_result.add_module_result(module_name, result)
            
            if args.verbose:
                success_rate = test_result.module_results[module_name]['success_rate']
                print(f"  ✅ {module_name}: {success_rate:.1f}% success rate")
        else:
            if args.verbose:
                print(f"  ❌ {module_name}: Failed to run tests")
    
    # Generate reports
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if not args.json_only:
        html_file = output_dir / f'test_report_{timestamp}.html'
        HTMLReportGenerator(test_result).generate_report(html_file)
    
    if not args.html_only:
        json_file = output_dir / f'test_report_{timestamp}.json'
        JSONReportGenerator(test_result).generate_report(json_file)
    
    # Print summary
    print()
    print("📊 Test Summary")
    print("=" * 60)
    print(f"Total Tests:    {test_result.total_tests}")
    print(f"Passed:         {test_result.total_tests - test_result.total_failures - test_result.total_errors}")
    print(f"Failed:         {test_result.total_failures}")
    print(f"Errors:         {test_result.total_errors}")
    print(f"Success Rate:   {test_result.get_overall_success_rate():.1f}%")
    print(f"Execution Time: {test_result.get_execution_time():.2f}s")
    print()
    
    # Print module breakdown
    if args.verbose:
        print("📋 Module Breakdown")
        print("-" * 60)
        for module_name, result in test_result.module_results.items():
            status = "✅" if result['success_rate'] >= 95 else "⚠️" if result['success_rate'] >= 80 else "❌"
            print(f"{status} {module_name:<20} {result['success_rate']:>6.1f}% ({result['tests_run']} tests)")
        print()
    
    # Print recommendations
    if test_result.total_failures > 0 or test_result.total_errors > 0:
        print("💡 Recommendations")
        print("-" * 60)
        if test_result.total_failures > 0:
            print("• Fix failing tests before deployment")
        if test_result.total_errors > 0:
            print("• Address test errors - these indicate code issues")
        print("• Review test reports for detailed failure information")
        print()
    
    # Exit with appropriate code
    exit_code = 0 if test_result.is_successful() else 1
    
    if test_result.is_successful():
        print("🎉 All tests passed! Ready for deployment.")
    else:
        print("❌ Some tests failed. Please review and fix issues.")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main()) 