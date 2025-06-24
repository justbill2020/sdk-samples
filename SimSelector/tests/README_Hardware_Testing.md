# SimSelector Automated Hardware Testing

## 🎯 Overview

This automated testing framework allows you to test SimSelector functionality on **real Cradlepoint hardware** while running the tests **locally on your development machine**. The tests communicate with your actual router via the SDK API using your `sdk_settings.ini` configuration.

## ✨ Key Benefits

- **🏠 Local Execution**: Run tests from your development machine
- **📡 Real Hardware**: Test against actual Cradlepoint routers with real SIMs
- **🔄 No Deployment**: No need to upload/install on the router
- **📊 Comprehensive**: Tests all phases of SimSelector operation
- **📝 Detailed Reports**: Generate markdown reports and JSON data
- **⚡ Fast Iteration**: Quick test cycles during development

## 🔧 Setup

### Prerequisites

1. **SDK Settings File**: You need a properly configured `sdk_settings.ini` file
2. **Network Access**: Your machine must be able to reach the target router
3. **Python Dependencies**: The framework will auto-install required packages

### SDK Settings Configuration

Create or verify your `sdk_settings.ini` file:

```ini
[csclient]
router_id = your_router_id_here
username = your_username
password = your_password
# Additional SDK settings as needed
```

## 🚀 Quick Start

### Run All Tests
```bash
# Run complete test suite
./tests/run_hardware_tests.sh

# Or specify custom SDK settings
./tests/run_hardware_tests.sh -s /path/to/your/sdk_settings.ini
```

### Run Specific Tests
```bash
# Test only signal quality detection
./tests/run_hardware_tests.sh -t signal

# Test validation phase only
./tests/run_hardware_tests.sh -t validation

# Test performance phase only  
./tests/run_hardware_tests.sh -t performance

# Test complete cycle (validation + performance)
./tests/run_hardware_tests.sh -t full
```

### Custom Output Files
```bash
# Specify custom report and results files
./tests/run_hardware_tests.sh -r my_test_report.md -j my_results.json
```

## 📋 Available Tests

### 1. **Signal Quality Test** (`signal`)
- **Duration**: ~1 minute
- **Purpose**: Test signal strength detection and classification
- **Validates**:
  - SIM detection
  - RSRP measurement accuracy
  - Signal quality classification (Good/Weak/Bad)
  - Carrier identification
  - Technology detection (5G/LTE)

### 2. **Validation Phase Test** (`validation`)
- **Duration**: ~5 minutes
- **Purpose**: Test the validation/staging phase
- **Validates**:
  - SIM detection and enumeration
  - Signal quality assessment
  - Staging feedback generation
  - State management (validation → performance)
  - WAN rule creation

### 3. **Performance Phase Test** (`performance`)
- **Duration**: ~15 minutes
- **Purpose**: Test speed testing and prioritization
- **Validates**:
  - Ookla speed test execution
  - Download/upload speed measurement
  - Minimum speed enforcement
  - SIM prioritization logic
  - WAN rule configuration
  - Final results generation

### 4. **Full Cycle Test** (`full`)
- **Duration**: ~20 minutes
- **Purpose**: Test complete SimSelector workflow
- **Validates**:
  - End-to-end operation
  - Phase transitions
  - Complete state management
  - Final prioritization results

### 5. **All Tests** (`all`)
- **Duration**: ~25 minutes
- **Purpose**: Run all individual tests sequentially
- **Provides**: Comprehensive validation of all functionality

## 📊 Test Results

### Report Format

The framework generates two types of output:

1. **Markdown Report** (`hardware_test_report.md`)
   - Human-readable summary
   - Test status and duration
   - SIM results and signal quality
   - Error messages and diagnostics

2. **JSON Results** (`hardware_test_results.json`)
   - Machine-readable data
   - Complete test logs
   - Detailed SIM information
   - Programmatic analysis

### Sample Report

```markdown
# SimSelector Local Hardware Test Report
Generated: 2024-06-24 16:45:30
Device: CP123456789

## Summary
- Total Tests: 4
- Passed: 4
- Failed: 0
- Errors: 0
- Timeouts: 0

## ✅ Signal Quality
- Status: PASS
- Duration: 45.2s
- SIM Results:
  - mdm-sim1: RSRP: -82 dBm, Quality: Good, Carrier: 311480, Technology: 5G
  - mdm-sim2: RSRP: -95 dBm, Quality: Weak, Carrier: 310260, Technology: LTE

## ✅ Validation Phase
- Status: PASS
- Duration: 287.5s
- Final Result: Staging - MODEM1 SIM1: Active, Good Signal | MODEM2 SIM1: Active, Weak Signal
```

## 🔍 Interpreting Results

### Test Status Meanings

- **✅ PASS**: Test completed successfully with expected results
- **❌ FAIL**: Test completed but results indicate failure
- **🚨 ERROR**: Test encountered an exception or error
- **⏰ TIMEOUT**: Test exceeded maximum allowed duration

### Common Result Patterns

#### Successful Validation
```
Final Result: Staging - MODEM1 SIM1: Active, Good Signal | MODEM2 SIM1: Active, Good Signal
```

#### Signal Quality Issues
```
Final Result: Staging - MODEM1 SIM1: Active, Good Signal | MODEM2 SIM1: Active, Bad Signal (Check Antenna)
```

#### Performance Results
```
Final Result: 06/24/24 16:45:30 | Verizon 311480 B2 -82 DL:125.50Mbps UL:45.20Mbps | T-Mobile 310260 B71 -95 DL:87.30Mbps UL:32.10Mbps
```

## 🐛 Troubleshooting

### Common Issues

#### 1. SDK Settings Not Found
```
[ERROR] SDK settings file not found: ../sdk_settings.ini
```
**Solution**: Create or specify the correct path to your SDK settings file.

#### 2. Connection Failed
```
[ERROR] Failed to connect to device
```
**Solutions**:
- Verify router is online and accessible
- Check network connectivity
- Validate credentials in SDK settings
- Ensure router API is enabled

#### 3. SIM Detection Issues
```
[ERROR] Expected 2 SIMs, found 1
```
**Solutions**:
- Verify SIM cards are properly seated
- Check SIM activation status
- Wait 60 seconds for SIM detection
- Check for NOSIM errors in router logs

#### 4. Speed Test Timeouts
```
[TIMEOUT] Performance phase timeout after 900 seconds
```
**Solutions**:
- Check internet connectivity on each SIM
- Verify adequate data allowances
- Test during off-peak hours
- Check for carrier throttling

#### 5. Python Dependencies
```
[WARNING] Some Python dependencies may be missing
```
**Solution**: The framework will auto-install required packages, or manually install:
```bash
pip3 install paramiko requests pyyaml
```

### Debug Mode

For detailed debugging, run the Python script directly:

```bash
cd tests
python3 local_hardware_test.py --sdk-settings ../sdk_settings.ini --test signal
```

## 🔄 Integration with Development Workflow

### Pre-Deployment Testing
```bash
# Before deploying to production
./tests/run_hardware_tests.sh -t full

# Verify all tests pass before deployment
```

### Continuous Integration
```bash
# Add to CI/CD pipeline
./tests/run_hardware_tests.sh -t validation -r ci_report.md
```

### Regression Testing
```bash
# After code changes, run specific tests
./tests/run_hardware_tests.sh -t performance
```

## 📈 Performance Benchmarks

### Expected Test Durations

| Test Type | Duration | Network Calls | SIM Operations |
|-----------|----------|---------------|----------------|
| Signal | 30-60s | ~10 | SIM detection |
| Validation | 3-5 min | ~50 | Connection tests |
| Performance | 10-15 min | ~100 | Speed tests |
| Full Cycle | 15-20 min | ~150 | Complete workflow |

### Resource Usage

- **CPU**: Low (mostly waiting for network operations)
- **Memory**: <100MB (Python process)
- **Network**: Moderate (API calls + speed tests)
- **Router Impact**: Minimal (normal API usage)

## 🔒 Security Considerations

### Credentials
- SDK settings file contains sensitive credentials
- Ensure file permissions are restrictive (`chmod 600`)
- Don't commit SDK settings to version control
- Use environment variables for CI/CD

### Network Security
- Tests communicate over existing SDK channels
- No additional ports or protocols required
- Router firewall rules apply normally

## 🚀 Advanced Usage

### Programmatic Access

```python
from tests.local_hardware_test import LocalHardwareTester

# Create tester instance
tester = LocalHardwareTester("path/to/sdk_settings.ini")

# Run specific test
result = tester.run_signal_quality_test()

# Access results
print(f"Test status: {result.status}")
print(f"SIM results: {result.sim_results}")
```

### Custom Test Scripts

You can create custom test scripts by extending the framework:

```python
# Custom test script
def my_custom_test(self, device, result):
    # Your custom test logic here
    pass

# Add to test suite
tester.test_suite['my_test'] = my_custom_test
```

## 📞 Support

### Getting Help

1. **Check Logs**: Review `local_hardware_test.log` for detailed information
2. **Validate Setup**: Ensure SDK settings and network connectivity
3. **Compare with Mock Tests**: Run mock tests first to isolate issues
4. **Router Logs**: Check router application logs for additional context

### Reporting Issues

When reporting issues, include:
- Test command used
- Complete error output
- SDK settings (redacted credentials)
- Router model and firmware version
- Network configuration details

---

**Happy Testing!** 🎉

This automated framework makes hardware testing as easy as running mock tests, giving you confidence in your SimSelector deployment before it goes to production. 