# Hardware Testing Guide - SimSelector v2.6.0

This guide provides comprehensive procedures for testing SimSelector on real Cradlepoint hardware devices.

## Table of Contents

1. [Testing Prerequisites](#testing-prerequisites)
2. [Test Environment Setup](#test-environment-setup)
3. [Hardware Configuration Tests](#hardware-configuration-tests)
4. [SIM Card Testing](#sim-card-testing)
5. [Network Configuration Testing](#network-configuration-testing)
6. [Performance Testing](#performance-testing)
7. [Security Testing](#security-testing)
8. [Failover and Recovery Testing](#failover-and-recovery-testing)
9. [Integration Testing](#integration-testing)
10. [Troubleshooting Guide](#troubleshooting-guide)

## Testing Prerequisites

### Required Hardware
- Cradlepoint router with cellular modem (IBR1700, IBR900, AER series)
- Minimum 2 SIM cards from different carriers (recommended: Verizon, AT&T, T-Mobile)
- Ethernet cable for management access
- Computer for testing and monitoring
- Network connectivity for internet access

### Software Requirements
- NetCloud Manager access
- SSH client (Terminal, PuTTY, etc.)
- Web browser for dashboard access
- Speed test applications (speedtest-cli, iperf3)
- Network monitoring tools

### SIM Card Requirements
- Active cellular data plans
- Different carriers for redundancy testing
- Known ICCID/IMSI information
- PIN codes (if applicable)

## Test Environment Setup

### 1. Initial Router Configuration

```bash
# SSH into router
ssh admin@192.168.1.1

# Verify router model and firmware
status system model
status system firmware

# Check cellular modem status
status wan devices
```

### 2. Install SimSelector

```bash
# Upload SimSelector package
scp SimSelector.tar.gz admin@192.168.1.1:/var/lib/application/

# Install via NetCloud or local interface
# Enable application in router configuration
```

### 3. Baseline Network Testing

```bash
# Test initial connectivity
ping -c 5 8.8.8.8

# Run baseline speed test
speedtest-cli --simple

# Check interface status
status system network interfaces
```

## Hardware Configuration Tests

### Test HC-001: Router Hardware Detection
**Objective**: Verify SimSelector correctly detects router hardware

```bash
# Start SimSelector with verbose logging
python3 SimSelector.py --verbose --log-level DEBUG

# Expected: Correct detection of:
# - Router model
# - Cellular modem type
# - Number of SIM slots
# - Available network interfaces
```

**Success Criteria**:
- ✅ Router model correctly identified
- ✅ Cellular modem detected and accessible
- ✅ All SIM slots enumerated
- ✅ Network interfaces discovered

### Test HC-002: SIM Slot Detection
**Objective**: Verify detection of all available SIM slots

```bash
# Check SIM slot status
python3 -c "from sim_manager import get_sim_manager; print(get_sim_manager().detect_sim_configuration())"
```

**Success Criteria**:
- ✅ All physical SIM slots detected
- ✅ SIM presence/absence correctly reported
- ✅ SIM slot numbering matches hardware

### Test HC-003: Temperature Monitoring
**Objective**: Verify thermal monitoring functionality

```bash
# Monitor modem temperature
watch -n 5 "status wan devices | grep temperature"

# Run SimSelector thermal monitoring
python3 -c "from hardware_monitor import get_temperature_status; print(get_temperature_status())"
```

**Success Criteria**:
- ✅ Temperature readings within normal range (20-70°C)
- ✅ Temperature monitoring alerts functional
- ✅ Thermal shutdown protection works

## SIM Card Testing

### Test SC-001: Single SIM Configuration
**Objective**: Test SimSelector with single SIM

**Setup**:
1. Insert one SIM card in slot 1
2. Leave slot 2 empty
3. Start SimSelector

```bash
# Run single SIM test
python3 SimSelector.py --test-mode single-sim
```

**Expected Behavior**:
- ✅ Single SIM detected and activated
- ✅ Single SIM mode enabled
- ✅ Dashboard accessible on cellular network
- ✅ Performance monitoring active

### Test SC-002: Dual SIM Configuration
**Objective**: Test SimSelector with dual SIM setup

**Setup**:
1. Insert SIM cards in both slots
2. Use different carriers if possible
3. Start SimSelector

```bash
# Run dual SIM test
python3 SimSelector.py --test-mode dual-sim
```

**Expected Behavior**:
- ✅ Both SIMs detected
- ✅ Primary SIM selected based on signal quality
- ✅ Secondary SIM available for failover
- ✅ Carrier preference logic applied

### Test SC-003: SIM Hot-Swap Testing
**Objective**: Verify hot-swap detection and handling

**Procedure**:
1. Start with SIM in slot 1 active
2. Remove SIM from slot 1 while system running
3. Insert SIM in slot 2
4. Monitor system response

```bash
# Monitor SIM changes
tail -f /var/log/SimSelector.log | grep -i "hot-swap\|sim.*change"
```

**Expected Behavior**:
- ✅ SIM removal detected within 30 seconds
- ✅ System switches to available SIM
- ✅ No service interruption
- ✅ Hot-swap events logged

### Test SC-004: Signal Quality Assessment
**Objective**: Test signal quality evaluation

**Procedure**:
1. Move router to different locations
2. Monitor RSRP values
3. Verify signal quality calculations

```bash
# Check signal quality
python3 -c "from sim_manager import get_sim_manager; print(get_sim_manager().get_signal_quality())"
```

**Success Criteria**:
- ✅ RSRP values accurately reported
- ✅ Signal bars calculation correct
- ✅ Poor signal warnings triggered
- ✅ Carrier switching on poor signal

## Network Configuration Testing

### Test NC-001: IP Address Management
**Objective**: Test dashboard IP selection and conflict resolution

```bash
# Test IP configuration
python3 -c "from ip_manager import get_ip_manager; print(get_ip_manager().select_dashboard_ip())"

# Check for IP conflicts
nmap -sn 192.168.1.0/24
```

**Success Criteria**:
- ✅ Dashboard IP automatically selected
- ✅ No IP conflicts detected
- ✅ IP accessible from local network
- ✅ DHCP reservation created

### Test NC-002: Firewall Configuration
**Objective**: Verify firewall rules properly configured

```bash
# Check firewall rules
iptables -L -n | grep SimSelector

# Test dashboard access
curl -I http://192.168.1.50:8080
```

**Success Criteria**:
- ✅ Dashboard port accessible
- ✅ Management ports secured
- ✅ Firewall rules properly applied
- ✅ Security policies enforced

### Test NC-003: Network Interface Monitoring
**Objective**: Test network interface detection and monitoring

```bash
# Monitor network interfaces
python3 -c "from network_manager import get_network_manager; print(get_network_manager().get_interfaces())"
```

**Success Criteria**:
- ✅ All interfaces detected
- ✅ Interface status accurate
- ✅ Traffic statistics collected
- ✅ Interface changes detected

## Performance Testing

### Test PT-001: Speed Test Validation
**Objective**: Verify speed test accuracy and reliability

**Procedure**:
1. Run multiple speed tests
2. Compare with external tools
3. Test on different carriers

```bash
# SimSelector speed test
python3 -c "from traffic_validator import run_speed_test; print(run_speed_test())"

# External validation
speedtest-cli --simple
iperf3 -c iperf.scottlinux.com
```

**Success Criteria**:
- ✅ Speed test results within 10% of external tools
- ✅ Consistent results across multiple runs
- ✅ Tests complete within 60 seconds
- ✅ Results properly logged

### Test PT-002: Carrier Performance Comparison
**Objective**: Test performance comparison between carriers

**Test Matrix**:
| Carrier | Technology | Expected Speed | Test Location |
|---------|------------|----------------|---------------|
| Verizon | 5G/LTE     | >25 Mbps       | Location A    |
| AT&T    | LTE        | >15 Mbps       | Location A    |
| T-Mobile| 5G/LTE     | >30 Mbps       | Location A    |

```bash
# Automated carrier testing
python3 tests/carrier_performance_test.py --all-carriers --location "Test Lab"
```

### Test PT-003: Load Testing
**Objective**: Test system performance under load

```bash
# Generate traffic load
iperf3 -c test-server.com -t 300 -P 10

# Monitor system performance
python3 -c "from system_monitor import get_system_stats; print(get_system_stats())"
```

**Success Criteria**:
- ✅ System stable under load
- ✅ Dashboard responsive during testing
- ✅ SIM switching functional under load
- ✅ No memory leaks detected

## Security Testing

### Test ST-001: Authentication Testing
**Objective**: Verify dashboard authentication

```bash
# Test unauthenticated access
curl http://192.168.1.50:8080/admin

# Test with credentials
curl -u admin:password http://192.168.1.50:8080/admin
```

**Success Criteria**:
- ✅ Unauthenticated access blocked
- ✅ Valid credentials accepted
- ✅ Session management working
- ✅ Password security enforced

### Test ST-002: Network Security
**Objective**: Test network security controls

```bash
# Port scan
nmap -sS 192.168.1.50

# Vulnerability scan
nmap --script vuln 192.168.1.50
```

**Success Criteria**:
- ✅ Only required ports open
- ✅ No vulnerable services exposed
- ✅ TLS/SSL properly configured
- ✅ Security headers present

### Test ST-003: Data Protection
**Objective**: Verify sensitive data protection

**Checks**:
- ✅ SIM details not exposed in logs
- ✅ Credentials properly encrypted
- ✅ API endpoints secured
- ✅ Error messages don't leak info

## Failover and Recovery Testing

### Test FR-001: SIM Failover Testing
**Objective**: Test automatic SIM failover

**Procedure**:
1. Start with primary SIM active
2. Simulate primary SIM failure
3. Monitor failover process
4. Restore primary SIM

```bash
# Simulate SIM failure
python3 -c "from sim_manager import get_sim_manager; get_sim_manager().simulate_sim_failure(1)"

# Monitor failover
tail -f /var/log/SimSelector.log | grep -i failover
```

**Success Criteria**:
- ✅ Failover triggered within 60 seconds
- ✅ Secondary SIM activated
- ✅ Service continuity maintained
- ✅ Automatic recovery on primary restore

### Test FR-002: Network Recovery Testing
**Objective**: Test recovery from network failures

**Procedure**:
1. Disconnect ethernet interface
2. Simulate cellular network failure
3. Monitor recovery process

```bash
# Simulate network failure
sudo ifdown eth0

# Monitor recovery
python3 -c "from error_handler import get_error_handler; print(get_error_handler().get_status())"
```

**Success Criteria**:
- ✅ Network failure detected
- ✅ Alternative connectivity attempted
- ✅ Error recovery mechanisms triggered
- ✅ Service restored automatically

### Test FR-003: System Recovery Testing
**Objective**: Test system recovery after crashes

**Procedure**:
1. Simulate application crash
2. Test restart procedures
3. Verify state recovery

```bash
# Test application restart
sudo systemctl restart simselector

# Check recovery status
python3 -c "from state_manager import get_state; print(get_state())"
```

**Success Criteria**:
- ✅ Application restarts automatically
- ✅ Previous state recovered
- ✅ SIM selection maintained
- ✅ Dashboard connectivity restored

## Integration Testing

### Test IT-001: NetCloud Integration
**Objective**: Test integration with NetCloud Manager

**Procedure**:
1. Configure NetCloud monitoring
2. Verify data reporting
3. Test remote management

**Success Criteria**:
- ✅ Device status reported to NetCloud
- ✅ Performance data uploaded
- ✅ Remote configuration possible
- ✅ Alerts properly forwarded

### Test IT-002: Third-Party Integration
**Objective**: Test integration with external systems

```bash
# Test SNMP integration
snmpwalk -v2c -c public 192.168.1.50

# Test syslog integration
logger "SimSelector test message"
```

**Success Criteria**:
- ✅ SNMP data available
- ✅ Syslog messages forwarded
- ✅ API endpoints functional
- ✅ Data formats correct

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: SIM Not Detected
**Symptoms**: SIM card present but not recognized

**Diagnosis**:
```bash
# Check modem status
status wan devices

# Check SIM slot status
python3 -c "from sim_manager import get_sim_manager; print(get_sim_manager().debug_sim_slots())"
```

**Solutions**:
1. Verify SIM card properly seated
2. Check SIM card compatibility
3. Restart cellular modem
4. Check for SIM lock/PIN

#### Issue: Poor Performance
**Symptoms**: Slow speeds or connection drops

**Diagnosis**:
```bash
# Check signal quality
python3 -c "from sim_manager import get_sim_manager; print(get_sim_manager().get_signal_quality())"

# Check network congestion
ping -c 10 8.8.8.8
```

**Solutions**:
1. Improve antenna positioning
2. Switch to different carrier
3. Check for network congestion
4. Update carrier settings

#### Issue: Dashboard Inaccessible
**Symptoms**: Cannot access web dashboard

**Diagnosis**:
```bash
# Check dashboard service
sudo systemctl status simselector

# Check network configuration
python3 -c "from ip_manager import get_ip_manager; print(get_ip_manager().get_status())"
```

**Solutions**:
1. Restart dashboard service
2. Check IP configuration
3. Verify firewall rules
4. Check network connectivity

### Performance Benchmarks

#### Expected Performance Ranges

| Technology | Download Speed | Upload Speed | Latency |
|------------|---------------|--------------|---------|
| 5G mmWave  | 100-1000 Mbps| 50-100 Mbps | <20ms   |
| 5G Sub-6   | 50-200 Mbps  | 10-50 Mbps  | <30ms   |
| LTE Cat 20 | 25-100 Mbps  | 5-25 Mbps   | <50ms   |
| LTE Cat 12 | 10-50 Mbps   | 2-10 Mbps   | <75ms   |

#### Signal Quality Thresholds

| RSRP Range | Quality | Expected Performance |
|------------|---------|---------------------|
| > -70 dBm  | Excellent | Full speed         |
| -70 to -85 | Good     | 80% of max speed   |
| -85 to -100| Fair     | 50% of max speed   |
| -100 to -115| Poor    | 25% of max speed   |
| < -115 dBm | Very Poor| Unreliable         |

### Test Report Template

```markdown
# SimSelector Hardware Test Report

**Test Date**: [Date]
**Tester**: [Name]
**Router Model**: [Model]
**Firmware Version**: [Version]
**SimSelector Version**: v2.6.0

## Test Summary
- Total Tests: [X]
- Passed: [X]
- Failed: [X]
- Success Rate: [X]%

## Hardware Configuration
- SIM Cards: [Number and carriers]
- Signal Strength: [RSRP values]
- Network Environment: [Description]

## Performance Results
- Primary SIM Speed: [Down/Up Mbps]
- Secondary SIM Speed: [Down/Up Mbps]
- Failover Time: [Seconds]
- Dashboard Response: [ms]

## Issues Found
1. [Issue description and resolution]
2. [Issue description and resolution]

## Recommendations
1. [Recommendation]
2. [Recommendation]

## Conclusion
[Overall assessment and deployment readiness]
```

---

**Note**: This testing guide should be executed in a controlled environment before production deployment. All tests should pass before considering the system ready for field deployment. 