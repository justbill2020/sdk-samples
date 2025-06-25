# SimSelector 2.6.0

**Enterprise-Grade SIM Card Performance Testing and Prioritization with Three-Phase Workflow**

## 🎯 Overview

SimSelector v2.6.0 is a comprehensive Cradlepoint SDK application that provides intelligent SIM card management through a sophisticated three-phase workflow. The application combines automated SIM detection, performance testing, and security-aware deployment phases to ensure optimal cellular connectivity in warehouse, field installation, and production environments.

## 🚀 Key Features

### Three-Phase Workflow Architecture
- **STAGING Phase**: Warehouse validation with basic SIM connectivity testing
- **INSTALL Phase**: Field installation with full performance testing and technician dashboard
- **DEPLOYED Phase**: Production operation with security lockdown and remote management

### Advanced Management Systems
- **SIM Manager**: Multi-SIM detection, switching, and carrier identification
- **IP Manager**: DHCP reservations, conflict resolution, and network scanning
- **Traffic Validator**: Comprehensive bandwidth testing and QoS monitoring
- **Security Manager**: Phase-based access control and firewall management
- **Dashboard Server**: Real-time web interface with technician tools
- **Error Handler**: Intelligent error recovery and suppression systems

### Enterprise Security Features
- **Phase-Based Access Control**: Automatic dashboard lockdown in production
- **Firewall Integration**: Dynamic port management per phase
- **State Encryption**: Secure state persistence with validation
- **Audit Logging**: Comprehensive operation tracking

## 📋 System Requirements

- **NCOS Devices**: All Cradlepoint routers with NCOS 7.0+
- **Minimum SIMs**: 2 SIM cards required for operation
- **Memory**: 256MB RAM minimum (512MB recommended)
- **Storage**: 50MB free space for application and logs
- **Network**: Internet connectivity for speed tests and NCM sync
- **NCM**: NetCloud Manager for result synchronization

## ⚙️ Configuration Options

Configure the following variables in `SimSelector.py`:

### Performance Thresholds
```python
MIN_DOWNLOAD_SPD = {'5G': 30.0, 'lte/3g': 10.0}  # Mbps minimum download speeds
MIN_UPLOAD_SPD = {'5G': 2.0, 'lte/3g': 1.0}      # Mbps minimum upload speeds
```

### Operational Settings
```python
SCHEDULE = 0                # Minutes between runs (0 = boot only)
NUM_ACTIVE_SIMS = 1        # Number of fastest SIMs to keep active
ONLY_RUN_ONCE = False      # Prevent multiple runs on same device
```

### Timeout Settings
```python
CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 minutes connection timeout
NETPERF_TIMEOUT = 5 * 60          # 5 minutes speed test timeout
```

## 🔄 Three-Phase Workflow

### Phase 0: STAGING (Warehouse)
**Purpose**: Basic SIM validation for warehouse staging
- **Trigger**: First boot after SDK installation
- **Duration**: Until device power-off (indefinite)
- **Access**: LAN dashboard enabled (port 8080 open)
- **Testing**: Basic connectivity validation only
- **Behavior**: Validates both SIMs have functional connections
- **Dashboard**: Active on all LAN interfaces with basic status
- **Exit**: Device power-off, then reboot triggers INSTALL phase

**Staging Output Example**:
```
STAGING - MODEM1 SIM1: Verizon Active, Good Signal (-75 dBm) | MODEM2 SIM1: T-Mobile Active, Weak Signal (-95 dBm) - Check Antenna
```

### Phase 1: INSTALL (Field Installation)
**Purpose**: Full testing and technician dashboard access
- **Trigger**: First boot after STAGING phase completion
- **Duration**: Until installation completion (~15-30 minutes)
- **Access**: LAN dashboard enabled with full technician tools
- **Testing**: Complete speed tests and performance validation
- **Behavior**: Full SimSelector validation and prioritization
- **Dashboard**: Real-time RSRP, progress tracking, help system
- **Exit**: Successful SIM prioritization, auto-transition to DEPLOYED

**Install Dashboard Features**:
- Real-time signal strength monitoring
- Speed test progress with live results
- Network topology discovery
- Troubleshooting guides and help system
- Manual override controls for technicians

### Phase 2: DEPLOYED (Production)
**Purpose**: Normal production operation with security lockdown
- **Trigger**: Automatic after INSTALL completion
- **Duration**: Indefinite (production state)
- **Access**: LAN dashboard DISABLED (port 8080 closed)
- **Testing**: Manual trigger only via NCM description field
- **Behavior**: Standard operation with existing manual triggers
- **Dashboard**: NCM remote connect access only
- **Exit**: Manual reset to INSTALL for maintenance/troubleshooting

## 🛡️ Security & Access Control

### Access Control Matrix

| Phase    | LAN Dashboard | NCM Dashboard | SIM Testing | Firewall Port 8080 |
|----------|---------------|---------------|-------------|-------------------|
| STAGING  | ✅ Enabled    | ✅ Enabled    | Basic Only  | 🟢 Open          |
| INSTALL  | ✅ Enabled    | ✅ Enabled    | Full Tests  | 🟢 Open          |
| DEPLOYED | ❌ Disabled   | ✅ Enabled    | Manual Only | 🔒 Closed        |

### Security Features
- **Automatic Lockdown**: Dashboard access disabled in production
- **State Encryption**: Sensitive configuration data encrypted at rest
- **Phase Validation**: Prevents unauthorized phase transitions
- **Audit Trail**: Complete logging of all security-related events

## 🧮 Advanced Performance Testing

### Multi-Layer Testing Approach
1. **Connectivity Testing**: Basic ping and DNS resolution
2. **Speed Testing**: Ookla-based download/upload measurements
3. **QoS Analysis**: Traffic pattern analysis and optimization
4. **Latency Assessment**: Round-trip time and jitter measurement
5. **Signal Quality**: RSRP/RSRQ monitoring and classification

### Intelligent Sorting Algorithm
1. **Primary Sort**: TCP Download Speed (highest first)
2. **Secondary Sort**: TCP Upload Speed (if downloads within 10%)
3. **Tertiary Sort**: Signal Strength (RSRP - higher is better)
4. **Tie-Breaking**: Advanced multi-factor analysis for optimal selection

## 📊 Signal Quality Classification

| RSRP Range | Classification | Dashboard Status | Recommended Action |
|------------|----------------|------------------|-------------------|
| > -90 dBm | Excellent | 🟢 Good Signal | Normal operation |
| -90 to -100 dBm | Good | 🟡 Fair Signal | Monitor performance |
| -100 to -110 dBm | Fair | 🟠 Weak Signal | Check antenna position |
| < -110 dBm | Poor | 🔴 Bad Signal | Replace/reposition antenna |

## 🛠️ Installation & Deployment

### Standard Deployment
1. **Package Upload**: Deploy SimSelector_v2.6.0.tar.gz via NCM
2. **Initial Boot**: Device automatically enters STAGING phase
3. **Warehouse Validation**: Verify SIM connectivity in staging
4. **Field Installation**: Reboot triggers INSTALL phase with full testing
5. **Production Deployment**: Automatic transition to DEPLOYED phase

### Development/Testing Deployment
1. **Local Development**: Use `sdk_settings.ini` for API authentication
2. **Debug Mode**: Run with `--debug` flag for verbose logging
3. **Phase Override**: Use `--phase=install` for specific phase testing
4. **Mock Testing**: Comprehensive test suite with hardware simulation

## 🎮 Manual Control Commands

Control SimSelector through the device description field in NCM:

| Command | Phase | Action |
|---------|-------|---------|
| `start` | Any | Run current phase operations |
| `force` | Any | Override safety checks and run current phase |
| `reset` | Any | Reset to INSTALL phase (requires device restart) |
| `staging` | Any | Force return to STAGING phase |
| Clear field | Any | Cancel pending operations |

### Advanced Commands
| Command | Description |
|---------|-------------|
| `debug` | Enable verbose logging for troubleshooting |
| `status` | Display current phase and system status |
| `test-sim-1` | Test specific SIM slot manually |
| `dashboard-enable` | Temporarily enable dashboard in DEPLOYED phase |

## 🧪 Comprehensive Testing Framework

SimSelector v2.6.0 includes a robust testing system with **130 unit tests** achieving **100% success rate**.

### Test Categories
- **SIM Manager Tests**: 25 tests covering detection, switching, hot-swap
- **IP Manager Tests**: 31 tests for DHCP, conflicts, network scanning
- **Traffic Validator Tests**: 34 tests for bandwidth, QoS, latency
- **Error Handler Tests**: 25 tests for recovery, suppression, logging
- **Dashboard Server Tests**: 9 tests for web interface and API
- **Firewall Manager Tests**: 6 tests for security and access control

### Running Tests
```bash
# Full test suite
cd tests && python run_unit_tests.py

# Specific module testing
python run_unit_tests.py --module sim_manager

# Verbose output with detailed logging
python run_unit_tests.py --verbose

# Generate HTML test reports
python run_unit_tests.py --report
```

### Mock Testing Scenarios
```bash
# Hardware simulation tests
python tests/test_runner.py good          # Good signal scenario
python tests/test_runner.py weak          # Weak signal scenario  
python tests/test_runner.py failed        # Failed connection scenario
python tests/test_runner.py triple        # 3 SIM mixed performance
python tests/test_runner.py quad          # 4 SIM all carriers
python tests/test_runner.py all           # Run all scenarios
```

## 📈 Expected Results Format

SimSelector generates comprehensive timestamped results:

### STAGING Phase Results
```
STAGING - 06/25/25 12:15:30 | MODEM1 SIM1: Verizon Active, Good Signal (-75 dBm) | MODEM2 SIM1: T-Mobile Active, Fair Signal (-95 dBm)
```

### INSTALL Phase Results
```
INSTALL - 06/25/25 12:45:17 | Verizon 311480 B2 RSRP:-75 DL:95.2Mbps UL:28.4Mbps | T-Mobile 310260 B71 RSRP:-80 DL:110.1Mbps UL:32.7Mbps | Priority: Verizon(1) T-Mobile(2)
```

### Dashboard Interface
- **Real-time Metrics**: Live RSRP, speed test progress, network status
- **Historical Data**: Performance trends and connectivity history
- **Interactive Controls**: Manual testing, phase management, troubleshooting
- **Help System**: Integrated guides and diagnostic tools

## 🏗️ Architecture Overview

### Core Components
```
SimSelector v2.6.0/
├── SimSelector.py          # Main application with three-phase logic
├── phase_manager.py        # Phase transition and state management
├── sim_manager.py          # SIM detection, switching, carrier ID
├── ip_manager.py           # DHCP, IP conflicts, network scanning
├── traffic_validator.py    # Speed tests, QoS, bandwidth analysis
├── security_manager.py     # Access control and firewall management
├── dashboard_server.py     # Web interface and technician tools
├── dashboard_api.py        # REST API for dashboard communication
├── error_handler.py        # Error recovery and intelligent suppression
├── network_manager.py      # Network topology and connectivity
├── firewall_manager.py     # Security policies and port management
└── state_manager.py        # Persistent state with encryption
```

### Web Interface
```
static/                     # Dashboard assets
├── css/
│   ├── dashboard.css       # Main dashboard styling
│   └── responsive.css      # Mobile-responsive design
└── js/
    ├── dashboard.js        # Interactive dashboard functionality
    └── notifications.js    # Real-time update system

templates/
└── dashboard.html          # Main dashboard template
```

### Testing Infrastructure
```
tests/                      # Comprehensive test suite (130 tests)
├── run_unit_tests.py       # Main test runner with reporting
├── test_sim_manager.py     # SIM management testing (25 tests)
├── test_ip_manager.py      # IP management testing (31 tests)
├── test_traffic_validator.py # Traffic testing (34 tests)
├── test_error_handler.py   # Error handling testing (25 tests)
├── test_dashboard_server.py # Dashboard testing (9 tests)
├── test_firewall_manager.py # Security testing (6 tests)
└── mock_framework.py       # Hardware simulation framework
```

## ⚠️ Known Issues & Limitations

### Technical Limitations
- **Minimum 2 SIMs Required**: Will not run with only 1 SIM detected
- **Phase Transition Rules**: Cannot skip phases or transition arbitrarily
- **Dashboard Security**: LAN access automatically disabled in DEPLOYED phase
- **NCM Dependency**: Results require NCM connection for synchronization
- **Speed Test Accuracy**: Results depend on network conditions and server selection

### Common Issues & Solutions

#### Issue: "Phase transition validation failed"
**Cause**: Attempting invalid phase transition
**Solutions**:
- Use `reset` command to return to valid state
- Check phase requirements in logs
- Restart device to reset phase state

#### Issue: "Dashboard not accessible"
**Cause**: Device in DEPLOYED phase with security lockdown
**Solutions**:
- Use `dashboard-enable` command for temporary access
- Use `reset` command to return to INSTALL phase
- Access via NCM remote connect

#### Issue: "Only 1 SIM found - insufficient for testing"
**Cause**: Second SIM not detected or has NOSIM error
**Solutions**:
- Verify SIM card is properly inserted and activated
- Check SIM card activation status with carrier
- Wait 30 seconds and restart application
- Review antenna connections

#### Issue: Speed tests timing out
**Cause**: Poor cellular connectivity or server issues
**Solutions**:
- Check signal strength and antenna connections
- Verify SIM card data plans are active and have sufficient data
- Try alternative APNs (automatic in app)
- Check for carrier-specific APN requirements

#### Issue: NCM sync failures
**Cause**: NetCloud Manager connectivity issues
**Solutions**:
- Check internet connectivity on management interface
- Verify NCM credentials and device registration
- Wait for automatic reconnection (up to 5 minutes)
- Check firewall rules for NCM communication

### Performance Considerations
- **Memory Usage**: Peak ~150MB RAM during full speed testing
- **Data Consumption**: ~200MB per SIM for comprehensive testing
- **Processing Time**: 15-30 minutes for complete INSTALL phase
- **Dashboard Resources**: ~10MB RAM for web interface
- **State Storage**: ~5MB for persistent configuration and logs

## 🔧 Advanced Troubleshooting

### Debug Information Access
```bash
# Application logs
Monitor > Logs > Application Logs > SimSelector

# System logs with debug info
tail -f /var/log/messages | grep SimSelector

# Phase state information
cat /var/mnt/sdk/SimSelector/state.json

# Dashboard access logs
cat /var/mnt/sdk/SimSelector/dashboard.log
```

### State Management
SimSelector maintains persistent state across phases:
- **Phase State**: Current phase and transition history
- **SIM Configuration**: Detected SIMs and performance data
- **Security State**: Access permissions and firewall rules
- **Test Results**: Historical performance and connectivity data

### Manual Recovery Procedures
If SimSelector encounters critical errors:

1. **Safe Recovery**:
   ```bash
   # Clear description field in NCM
   # Use 'reset' command
   # Monitor phase transition in logs
   ```

2. **Full Reset**:
   ```bash
   # Stop application
   # Clear state files: rm /var/mnt/sdk/SimSelector/state.json
   # Restart device
   # Application will restart in STAGING phase
   ```

3. **Emergency Access**:
   ```bash
   # Use NCM remote connect for dashboard access
   # Enable debug logging: 'debug' command
   # Force phase transition: 'force' command
   ```

## 📊 Performance Metrics & Monitoring

### Real-Time Metrics
- **Signal Strength**: RSRP/RSRQ monitoring with trend analysis
- **Speed Performance**: Download/upload with historical comparison
- **Connection Quality**: Latency, jitter, packet loss measurement
- **System Resources**: Memory usage, CPU utilization, storage
- **Network Topology**: Interface status, routing table, DNS resolution

### Reporting & Analytics
- **HTML Test Reports**: Comprehensive test results with graphs
- **JSON Data Export**: Machine-readable performance data
- **NCM Integration**: Automatic result synchronization
- **Trend Analysis**: Performance degradation detection
- **Alert Generation**: Proactive issue notification

## 🔄 Development & Customization

### Local Development Setup
1. **SDK Configuration**: Create `sdk_settings.ini` with device credentials
2. **Environment Setup**: Install requirements with `pip install -r requirements.txt`
3. **Debug Mode**: Run with `python SimSelector.py --debug --phase=install`
4. **API Testing**: Use HTTP API calls for remote debugging

### Customization Options
- **Carrier-Specific APNs**: Modify `ADV_APN` dictionary in SimSelector.py
- **Speed Thresholds**: Adjust performance minimums per technology
- **Dashboard Themes**: Customize CSS in `static/css/` directory
- **Test Scenarios**: Add custom test cases in `tests/` directory
- **Alert Templates**: Modify message formats in `create_message()` function

### API Integration
```python
# Example API usage for custom integrations
from csclient import CSClient
client = CSClient("SimSelector")

# Get current SIM status
sim_status = client.get('/status/wan/devices')

# Trigger manual test
client.put('/config/system/desc', 'start')

# Check phase state
phase_data = client.get('/control/wan/devices')
```

## 📞 Support & Maintenance

### Technical Support Resources
- **Comprehensive Logs**: All operations logged with timestamps
- **Test Framework**: 130 unit tests for validation
- **Mock Hardware**: Complete simulation for testing without hardware
- **Debug Dashboard**: Real-time system monitoring and diagnostics

### Maintenance Procedures
- **Regular Testing**: Run test suite after any configuration changes
- **State Backup**: Periodic backup of phase and configuration state
- **Performance Monitoring**: Track speed test results over time
- **Security Audits**: Regular review of access permissions and firewall rules

### Version Control & Updates
- **Semantic Versioning**: Major.Minor.Patch version scheme
- **Backward Compatibility**: State migration for version upgrades
- **Rollback Capability**: Safe downgrade procedures if needed
- **Change Documentation**: Comprehensive CHANGELOG.md maintenance

## 📄 License & Legal

This application is part of the Cradlepoint SDK samples and follows the same licensing terms. SimSelector v2.6.0 includes additional enterprise features and security enhancements for production deployment scenarios.

---

**SimSelector 2.6.0** - Enterprise-Grade SIM Performance Optimization with Three-Phase Workflow
*Warehouse Staging • Field Installation • Production Deployment*

**🎉 100% Test Success Rate - Production Ready** 