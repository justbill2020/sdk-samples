# SimSelector 2.5.9

**Intelligent SIM Card Performance Testing and Prioritization for Cradlepoint Routers**

## 🎯 Overview

SimSelector is a sophisticated Cradlepoint SDK application that automatically detects, tests, and prioritizes multiple SIM cards based on real-world performance metrics. The application uses a two-phase approach to ensure optimal cellular connectivity by running comprehensive speed tests and intelligently organizing WAN profiles for maximum performance.

## 🚀 Key Features

- **Dual-Phase Operation**: Quick validation followed by comprehensive performance testing
- **Multi-SIM Support**: Handles 2-4 SIM cards across different modems
- **Intelligent Prioritization**: Advanced sorting logic with tie-breaking algorithms
- **Technology Awareness**: Different thresholds for 5G vs LTE connections
- **Signal Quality Assessment**: RSRP-based signal strength classification
- **Automatic APN Management**: Custom APN testing for carrier optimization
- **Comprehensive Logging**: Detailed progress tracking and result reporting
- **NCM Integration**: Results synchronized to NetCloud Manager

## 📋 System Requirements

- **NCOS Devices**: All Cradlepoint routers with NCOS
- **Minimum SIMs**: 2 SIM cards required for operation
- **Network**: Internet connectivity for Ookla speed tests
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

## 🔄 Two-Phase Operation

### Phase 1: Validation/Staging
**Triggers**: Device boot (within first 5 minutes)
- Detects available SIM cards
- Creates unique WAN profiles for each SIM
- Performs quick connection validation
- Measures signal strength (RSRP)
- Provides immediate feedback on SIM status
- **Output**: "Staging - MODEM1 SIM1: Active, Good Signal | MODEM2 SIM1: Active, Weak Signal (Check Antenna)"

### Phase 2: Performance/Run
**Triggers**: Subsequent boots or manual trigger
- Runs comprehensive Ookla speed tests
- Applies advanced sorting algorithms
- Prioritizes SIMs by performance
- Configures WAN rule priorities
- Generates detailed results report

## 🧮 Advanced Sorting Logic

SimSelector uses sophisticated tie-breaking algorithms:

1. **Primary Sort**: TCP Download Speed (highest first)
2. **Secondary Sort**: TCP Upload Speed (if downloads within 10%)
3. **Tertiary Sort**: Signal Strength (RSRP - higher is better)
4. **Low-Speed Priority**: For SIMs below minimums, prioritize by upload speed

## 📊 Signal Quality Classification

| RSRP Range | Classification | Action |
|------------|----------------|---------|
| > -90 dBm | Good Signal | Normal operation |
| -90 to -105 dBm | Weak Signal | Warning in staging |
| < -105 dBm | Bad Signal | "Check Antenna" message |

## 🛠️ Installation & Deployment

1. **Upload Application**: Deploy to Cradlepoint router via NCM
2. **Configure Settings**: Adjust thresholds in `SimSelector.py` if needed
3. **Initial Boot**: Application runs validation phase automatically
4. **Monitor Results**: Check NCM device description field for status

## 🎮 Manual Control

Control SimSelector through the device description field in NCM:

| Command | Action |
|---------|---------|
| `start` | Run current phase (within 5-minute boot window) |
| `force` | Override uptime check and run current phase |
| `reset` | Reset to validation phase, restart device to begin |
| Clear field | Cancel pending operations |

## 🧪 Testing Framework

SimSelector includes a comprehensive mock testing system requiring no hardware:

### Quick Tests
```bash
python tests/test_runner.py good          # Good signal scenario
python tests/test_runner.py weak          # Weak signal scenario  
python tests/test_runner.py failed        # Failed connection scenario
```

### Advanced Tests
```bash
python tests/test_runner.py triple        # 3 SIM mixed performance
python tests/test_runner.py quad          # 4 SIM all carriers
python tests/test_runner.py highspeed     # Ultra-high 5G speeds
python tests/test_runner.py allweak       # All SIMs weak signals
python tests/test_runner.py tiebreaker    # Tie-breaking logic test
```

### Comprehensive Testing
```bash
python tests/test_runner.py all           # Run all 12 scenarios
python tests/test_runner.py interactive   # Interactive test mode
```

## 📈 Expected Results Format

SimSelector generates timestamped results in the device description field:

```
06/24/25 16:13:07 | Verizon 311480 B2 RSRP:-75 DL:95.2Mbps UL:28.4Mbps | T-Mobile 310260 B71 RSRP:-80 DL:110.1Mbps UL:32.7Mbps
```

**Format Components**:
- Timestamp
- Carrier Name and MCC/MNC
- RF Band
- Signal Strength (RSRP)  
- Download/Upload Speeds

## ⚠️ Known Issues & Limitations

### Technical Limitations
- **Minimum 2 SIMs Required**: Will not run with only 1 SIM detected
- **Uptime Restriction**: Validation phase only runs within first 5 minutes of boot
- **NCM Dependency**: Results require NCM connection for synchronization
- **Speed Test Accuracy**: Results depend on network conditions and server selection

### Common Issues

#### Issue: "Only 1 SIM found"
**Cause**: Second SIM not detected or has NOSIM error
**Solution**: 
- Verify SIM card is properly inserted
- Check SIM card activation status
- Wait 30 seconds and restart application

#### Issue: "Uptime is over 5 minutes"
**Cause**: Trying to run validation phase after boot window
**Solutions**:
- Restart device to reset uptime
- Use `force` command to override
- Use `reset` command to restart from validation

#### Issue: Speed tests timing out
**Cause**: Poor cellular connectivity or server issues
**Solutions**:
- Check signal strength and antenna connections
- Verify SIM card data plans are active
- Try alternative APNs (automatic in app)

#### Issue: NCM sync failures
**Cause**: NetCloud Manager connectivity issues
**Solutions**:
- Check internet connectivity
- Verify NCM credentials
- Wait for automatic reconnection

### Performance Considerations
- **Memory Usage**: Speed tests consume ~50MB RAM during operation
- **Data Consumption**: Each speed test uses ~200MB data per SIM
- **Processing Time**: Complete run takes 15-30 minutes depending on SIM count
- **NCM Bandwidth**: Results upload requires active NCM connection

## 🔧 Troubleshooting

### Debug Information
Check router logs for detailed operation information:
```
Monitor > Logs > Application Logs > SimSelector
```

### State Management
SimSelector maintains state between phases:
- **Validation State**: Stored until performance phase runs
- **Performance State**: Marked complete when finished
- **Reset State**: Use `reset` command to clear and restart

### Manual Recovery
If SimSelector gets stuck:
1. Clear device description field
2. Use `reset` command
3. Restart device  
4. Monitor validation phase output

## 📝 Development & Customization

### File Structure
```
SimSelector/
├── SimSelector.py          # Main application
├── csclient.py            # Cradlepoint SDK client
├── speedtest.py           # Ookla speed test library
├── state_manager.py       # State persistence
├── package.ini            # Application metadata
├── tests/                 # Comprehensive test suite
│   ├── mock_framework.py  # Mock testing framework
│   ├── test_runner.py     # Test execution script
│   └── mock_state_manager.py # Mock state management
└── README.md              # This documentation
```

### Customization Options
- **Carrier-Specific APNs**: Modify `ADV_APN` dictionary
- **Speed Thresholds**: Adjust `MIN_DOWNLOAD_SPD` and `MIN_UPLOAD_SPD`
- **Timeout Values**: Customize connection and test timeouts
- **Result Format**: Modify `create_message()` function

## 📞 Support & Contact

For technical support or feature requests:
- Review logs in NCM Application Logs
- Test with mock framework before hardware deployment
- Check signal quality and antenna connections
- Verify SIM card activation and data plans

## 📄 License

This application is part of the Cradlepoint SDK samples and follows the same licensing terms.

---

**SimSelector 2.5.9** - Intelligent SIM Performance Optimization for Cradlepoint Routers 