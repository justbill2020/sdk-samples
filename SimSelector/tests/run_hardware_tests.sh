#!/bin/bash

# SimSelector Local Hardware Test Runner
# Runs SimSelector tests locally while connecting to real hardware via SDK

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SDK_SETTINGS="../sdk_settings.ini"
TEST_TYPE="all"
REPORT_FILE="hardware_test_report.md"
RESULTS_FILE="hardware_test_results.json"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "SimSelector Local Hardware Test Runner"
    echo "====================================="
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -s, --sdk-settings FILE    Path to SDK settings file (default: ../sdk_settings.ini)"
    echo "  -t, --test TYPE           Test type: signal|validation|performance|full|all (default: all)"
    echo "  -r, --report FILE         Report output file (default: hardware_test_report.md)"
    echo "  -j, --json FILE           JSON results file (default: hardware_test_results.json)"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Test Types:"
    echo "  signal      - Test signal quality detection only"
    echo "  validation  - Test validation phase (SIM detection, signal classification)"
    echo "  performance - Test performance phase (speed tests, prioritization)"
    echo "  full        - Test complete cycle (validation + performance)"
    echo "  all         - Run all individual tests"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests with defaults"
    echo "  $0 -t signal                         # Run only signal quality test"
    echo "  $0 -t full -s /path/to/sdk_settings.ini  # Run full cycle with custom settings"
    echo "  $0 -t validation -r my_report.md     # Run validation test with custom report name"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--sdk-settings)
            SDK_SETTINGS="$2"
            shift 2
            ;;
        -t|--test)
            TEST_TYPE="$2"
            shift 2
            ;;
        -r|--report)
            REPORT_FILE="$2"
            shift 2
            ;;
        -j|--json)
            RESULTS_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate test type
case $TEST_TYPE in
    signal|validation|performance|full|all)
        ;;
    *)
        print_error "Invalid test type: $TEST_TYPE"
        show_usage
        exit 1
        ;;
esac

# Check if SDK settings file exists
if [[ ! -f "$SDK_SETTINGS" ]]; then
    print_error "SDK settings file not found: $SDK_SETTINGS"
    print_warning "Please create sdk_settings.ini with your device configuration"
    echo ""
    echo "Example sdk_settings.ini:"
    echo "[csclient]"
    echo "router_id = your_router_id"
    echo "username = your_username"
    echo "password = your_password"
    echo "# ... other settings"
    exit 1
fi

# Check if Python script exists
PYTHON_SCRIPT="local_hardware_test.py"
if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    print_error "Python test script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Print test configuration
print_status "Starting SimSelector Local Hardware Tests"
echo "=========================================="
echo "SDK Settings: $SDK_SETTINGS"
echo "Test Type: $TEST_TYPE"
echo "Report File: $REPORT_FILE"
echo "Results File: $RESULTS_FILE"
echo ""

# Check Python dependencies
print_status "Checking Python dependencies..."
python3 -c "import paramiko, requests, yaml" 2>/dev/null || {
    print_warning "Some Python dependencies may be missing"
    print_status "Installing required packages..."
    pip3 install paramiko requests pyyaml
}

# Run the test
print_status "Running hardware tests..."
echo ""

# Execute the Python test script
if python3 "$PYTHON_SCRIPT" \
    --sdk-settings "$SDK_SETTINGS" \
    --test "$TEST_TYPE" \
    --report "$REPORT_FILE" \
    --results "$RESULTS_FILE"; then
    
    print_success "Hardware tests completed successfully!"
    echo ""
    
    # Show results summary
    if [[ -f "$REPORT_FILE" ]]; then
        print_status "Test Report Summary:"
        echo "===================="
        grep -E "^- (Total Tests|Passed|Failed|Errors|Timeouts):" "$REPORT_FILE" || true
        echo ""
        print_status "Full report available at: $REPORT_FILE"
    fi
    
    if [[ -f "$RESULTS_FILE" ]]; then
        print_status "Detailed results saved to: $RESULTS_FILE"
    fi
    
else
    print_error "Hardware tests failed!"
    exit 1
fi

# Optional: Open report in browser/editor
if command -v open >/dev/null 2>&1; then
    # macOS
    read -p "Open report in default application? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "$REPORT_FILE"
    fi
elif command -v xdg-open >/dev/null 2>&1; then
    # Linux
    read -p "Open report in default application? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        xdg-open "$REPORT_FILE"
    fi
fi

print_success "All done! 🎉" 