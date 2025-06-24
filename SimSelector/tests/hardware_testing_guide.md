# SimSelector Hardware Testing Guide

**Safe & Systematic Testing on Real Cradlepoint Hardware**

## 🎯 Overview

This guide provides a systematic approach to validate SimSelector 2.5.9 on actual Cradlepoint hardware after comprehensive mock testing. It includes staging procedures, monitoring tools, and safety protocols to ensure reliable deployment.

## ⚠️ Prerequisites

### Hardware Requirements
- **Cradlepoint Router**: Any NCOS-compatible device (IBR1700, IBR900, etc.)
- **SIM Cards**: Minimum 2 active SIMs with data plans
- **Antennas**: Properly connected cellular antennas
- **Network**: Stable management network connection

### Software Requirements
- **NCM Access**: Active NetCloud Manager account with device access
- **SSH/Console**: Direct device access for troubleshooting
- **Monitoring Tools**: Log collection and analysis capability

### Pre-Testing Validation
```bash
# Run all mock tests first
python tests/test_runner.py all

# Validate mock data accuracy
python tests/mock_data_validator.py --all
```

## 🔧 Staged Testing Approach

### Stage 1: Lab Environment Testing
**Goal**: Validate basic functionality in controlled environment

#### Setup
1. **Controlled Network**: Test in lab with known good connectivity
2. **Backup Configuration**: Save current router configuration
3. **Monitoring**: Set up continuous log monitoring
4. **SIM Cards**: Use test SIMs with adequate data allowances

#### Test Procedure
```bash
# 1. Deploy application to test device
# Upload SimSelector package via NCM

# 2. Enable detailed logging
# Router CLI: config system logging level debug

# 3. Monitor initial boot cycle
# NCM: Monitor > Logs > Application Logs

# 4. Trigger validation phase manually
# NCM: Set device description to "start"

# 5. Monitor validation results
# Look for staging feedback in description field
```

#### Expected Results
- ✅ SIM detection within 30 seconds
- ✅ Staging feedback appears in description field
- ✅ Signal quality classification accurate
- ✅ No application crashes or timeouts

### Stage 2: Signal Quality Validation
**Goal**: Verify signal strength measurements and classifications

#### Test Matrix
| Test Case | RSRP Range | Expected Classification | Test Method |
|-----------|------------|------------------------|-------------|
| Excellent Signal | -50 to -70 dBm | Good Signal | Close to tower |
| Good Signal | -70 to -90 dBm | Good Signal | Normal distance |
| Weak Signal | -90 to -105 dBm | Weak Signal | Far from tower |
| Bad Signal | < -105 dBm | Bad Signal (Check Antenna) | Antenna disconnected |

#### Validation Commands
```bash
# Check actual RSRP values via CLI
status cellular module mdm-sim1 diagnostics

# Compare with SimSelector classification
# Check device description field for staging results
```

### Stage 3: Speed Test Validation
**Goal**: Verify Ookla speed test integration and accuracy

#### Pre-Test Checks
- ✅ Internet connectivity on each SIM
- ✅ Adequate data allowances (>1GB per SIM)
- ✅ Speedtest.net accessibility
- ✅ No data throttling or carrier restrictions

#### Speed Test Monitoring
```bash
# Monitor speed test progress
tail -f /var/log/application.log | grep SimSelector

# Check for timeout errors
grep "timeout" /var/log/application.log

# Verify speed test results
# Compare with manual speed tests using speedtest-cli
```

#### Validation Criteria
- **Download Speeds**: Within 20% of manual speed tests
- **Upload Speeds**: Within 30% of manual speed tests (more variable)
- **Test Duration**: Complete within 5 minutes per SIM
- **No Timeouts**: All tests should complete successfully

### Stage 4: Performance Phase Testing
**Goal**: Validate comprehensive testing and SIM prioritization

#### Test Scenarios
1. **Normal Performance**: All SIMs meet minimum thresholds
2. **Below Minimums**: Some SIMs below 5G/LTE thresholds
3. **Mixed Technologies**: 5G and LTE SIMs together
4. **Similar Speeds**: Test tie-breaking logic

#### Monitoring Points
```bash
# Watch for phase transitions
grep "phase" /var/log/application.log

# Monitor SIM prioritization
grep "Prioritizing SIMs" /var/log/application.log

# Check WAN rule configuration
status wan rules2
```

### Stage 5: Field Testing
**Goal**: Validate in real deployment conditions

#### Deployment Conditions
- **Remote Locations**: Test with varying signal conditions
- **Multiple Carriers**: Use SIMs from different operators
- **Production Traffic**: Monitor with real user traffic
- **Extended Duration**: Run for multiple days

#### Safety Protocols
1. **Rollback Plan**: Keep original configuration backup
2. **Remote Access**: Ensure out-of-band management access
3. **Monitoring**: Continuous health monitoring
4. **Support Contact**: 24/7 support availability during testing

## 📊 Testing Tools & Scripts

### Real-Time Monitoring Script
```bash
#!/bin/bash
# monitor_simselector.sh - Real-time SimSelector monitoring

echo "🔍 SimSelector Hardware Testing Monitor"
echo "======================================"

while true; do
    echo -n "$(date '+%H:%M:%S') - "
    
    # Check application status
    if pgrep -f SimSelector > /dev/null; then
        echo -n "✅ Running - "
    else
        echo -n "❌ Stopped - "
    fi
    
    # Check current phase
    PHASE=$(grep "Current phase:" /var/log/application.log | tail -1 | cut -d: -f3 | tr -d ' ')
    echo -n "Phase: ${PHASE:-Unknown} - "
    
    # Check description field
    DESC=$(cat /config/system/desc 2>/dev/null)
    echo "Desc: ${DESC:0:50}..."
    
    sleep 30
done
```

### Performance Comparison Tool
```python
#!/usr/bin/env python3
# compare_speeds.py - Compare SimSelector vs manual speed tests

import subprocess
import json
import time

def manual_speed_test(interface):
    """Run manual speed test on specific interface."""
    try:
        cmd = f"speedtest-cli --interface {interface} --json"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Manual speed test failed: {e}")
        return None

def get_simselector_results():
    """Extract SimSelector results from logs."""
    try:
        with open('/var/log/application.log', 'r') as f:
            lines = f.readlines()
        
        # Find most recent results
        for line in reversed(lines):
            if 'DL:' in line and 'UL:' in line:
                return parse_simselector_line(line)
        return None
    except Exception as e:
        print(f"Failed to get SimSelector results: {e}")
        return None

def compare_results():
    """Compare SimSelector vs manual results."""
    print("🔬 Speed Test Comparison")
    print("========================")
    
    # Get interface list
    interfaces = ['wwan0', 'wwan1']  # Adjust as needed
    
    for iface in interfaces:
        print(f"\n📡 Testing {iface}:")
        
        # Manual test
        manual = manual_speed_test(iface)
        if manual:
            manual_dl = manual['download'] / 1_000_000  # Convert to Mbps
            manual_ul = manual['upload'] / 1_000_000
            print(f"  Manual: ↓{manual_dl:.1f} Mbps ↑{manual_ul:.1f} Mbps")
        
        # SimSelector results would be extracted from logs
        # This is a simplified version
        
if __name__ == "__main__":
    compare_results()
```

## 🚨 Safety & Recovery Procedures

### Automatic Rollback
```bash
#!/bin/bash
# rollback_simselector.sh - Emergency rollback script

echo "🚨 SimSelector Emergency Rollback"
echo "================================="

# Stop SimSelector
echo "Stopping SimSelector..."
killall -9 python3 2>/dev/null

# Clear description field
echo "Clearing description field..."
echo "" > /config/system/desc

# Restore WAN rules backup
if [ -f /tmp/wan_rules_backup.json ]; then
    echo "Restoring WAN rules..."
    cp /tmp/wan_rules_backup.json /config/wan/rules2.json
fi

# Restart networking
echo "Restarting network services..."
systemctl restart networking

echo "✅ Rollback complete"
```

### Health Check Script
```bash
#!/bin/bash
# health_check.sh - Automated health monitoring

check_connectivity() {
    ping -c 3 8.8.8.8 > /dev/null 2>&1
    return $?
}

check_application() {
    pgrep -f SimSelector > /dev/null
    return $?
}

check_memory() {
    MEM_USAGE=$(ps aux | grep SimSelector | awk '{sum+=$6} END {print sum/1024}')
    if (( $(echo "$MEM_USAGE > 100" | bc -l) )); then
        return 1
    fi
    return 0
}

# Main health check
echo "🏥 SimSelector Health Check"
echo "============================"

HEALTHY=true

if ! check_connectivity; then
    echo "❌ No internet connectivity"
    HEALTHY=false
fi

if ! check_application; then
    echo "❌ SimSelector not running"
    HEALTHY=false
fi

if ! check_memory; then
    echo "⚠️ High memory usage detected"
fi

if [ "$HEALTHY" = true ]; then
    echo "✅ All systems healthy"
    exit 0
else
    echo "🚨 Health check failed - manual intervention required"
    exit 1
fi
```

## 📋 Testing Checklist

### Pre-Deployment
- [ ] Mock tests all pass (12/12 scenarios)
- [ ] Mock data validation clean
- [ ] Hardware requirements verified
- [ ] Backup configuration saved
- [ ] Test SIMs activated with data
- [ ] Monitoring tools configured

### Validation Phase Testing
- [ ] SIM detection successful
- [ ] Signal strength accurate
- [ ] Staging feedback correct
- [ ] No application crashes
- [ ] State management working

### Performance Phase Testing
- [ ] Speed tests complete
- [ ] Results within expected ranges
- [ ] SIM prioritization correct
- [ ] WAN rule configuration valid
- [ ] Final results accurate

### Production Deployment
- [ ] Field testing successful
- [ ] Extended duration stable
- [ ] Performance meets requirements
- [ ] Support procedures documented
- [ ] Rollback tested and ready

## 🔍 Common Issues & Solutions

### Issue: SIM Detection Failures
**Symptoms**: "Only 1 SIM found" errors
**Diagnosis**:
```bash
status cellular modules
status wan devices
```
**Solutions**:
- Check SIM card seating
- Verify carrier activation
- Check for NOSIM errors
- Wait 60 seconds for detection

### Issue: Speed Test Timeouts
**Symptoms**: "Error accessing speedtest config page"
**Diagnosis**:
```bash
ping -I wwan0 www.speedtest.net
nslookup speedtest.net
```
**Solutions**:
- Check internet connectivity per SIM
- Verify DNS resolution
- Test manual speedtest-cli
- Check carrier APN settings

### Issue: Incorrect Signal Classification
**Symptoms**: Signal quality doesn't match staging feedback
**Diagnosis**:
```bash
status cellular module mdm-sim1 diagnostics | grep RSRP
```
**Solutions**:
- Verify antenna connections
- Check for RF interference
- Compare with carrier signal maps
- Validate RSRP measurement methodology

### Issue: Performance Inconsistencies
**Symptoms**: Results vary significantly between runs
**Diagnosis**:
- Check network load and time of day
- Monitor carrier throttling
- Verify data plan status
- Check for background traffic

**Solutions**:
- Run tests during off-peak hours
- Use dedicated test APNs if available
- Monitor concurrent device usage
- Implement result averaging

## 📞 Support & Escalation

### Level 1: Local Troubleshooting
- Check logs: `/var/log/application.log`
- Verify connectivity: `ping`, `traceroute`
- Monitor resources: `top`, `free`, `df`
- Test manually: `speedtest-cli`

### Level 2: Remote Diagnosis
- Enable debug logging
- Collect full system logs
- Run diagnostic scripts
- Compare with mock test results

### Level 3: Development Support
- Provide detailed reproduction steps
- Include log files and configuration
- Document environmental conditions
- Share performance comparison data

---

**Remember**: Always test thoroughly in lab before production deployment. When in doubt, roll back to known good configuration. 