Application Name
================
SimSelector


Application Version
===================
2.5.9

NCOS Devices Supported
======================
ALL Cradlepoint routers with NCOS


External Requirements
=====================
- Minimum 2 SIM cards installed
- Active cellular data plans
- Internet connectivity for speed tests
- NetCloud Manager (NCM) connection for result synchronization


Application Purpose
===================
SimSelector is an intelligent SIM card performance testing and prioritization application
for Cradlepoint routers. It automatically detects multiple SIM cards, performs comprehensive
speed tests, and optimally prioritizes WAN profiles based on real-world performance metrics.

KEY FEATURES:
• Two-Phase Operation: Quick validation followed by comprehensive performance testing
• Multi-SIM Support: Handles 2-4 SIM cards across different modems  
• Intelligent Prioritization: Advanced sorting with tie-breaking algorithms
• Technology Awareness: Different thresholds for 5G (30 Mbps) vs LTE (10 Mbps)
• Signal Quality Assessment: RSRP-based signal strength classification
• Automatic APN Management: Tests custom APNs for carrier optimization
• Comprehensive Testing Framework: 12 mock test scenarios requiring no hardware

CONFIGURATION OPTIONS:
======================

Performance Thresholds (configurable in SimSelector.py):
• MIN_DOWNLOAD_SPD = {'5G': 30.0, 'lte/3g': 10.0}  # Mbps minimum download speeds
• MIN_UPLOAD_SPD = {'5G': 2.0, 'lte/3g': 1.0}      # Mbps minimum upload speeds

Operational Settings:
• SCHEDULE = 0                # Minutes between runs (0 = boot only)
• NUM_ACTIVE_SIMS = 1        # Number of fastest SIMs to keep active
• ONLY_RUN_ONCE = False      # Prevent multiple runs on same device

Timeout Settings:
• CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 minutes connection timeout
• NETPERF_TIMEOUT = 5 * 60          # 5 minutes speed test timeout

TWO-PHASE OPERATION:
===================

Phase 1: Validation/Staging (Runs on device boot within first 5 minutes)
• Detects available SIM cards (minimum 2 required)
• Creates unique WAN profiles for each SIM if needed
• Performs quick connection validation
• Measures signal strength (RSRP values)
• Provides immediate feedback on SIM status and signal quality
• Example Output: "Staging - MODEM1 SIM1: Active, Good Signal | MODEM2 SIM1: Active, Weak Signal (Check Antenna)"

Phase 2: Performance/Run (Runs on subsequent boots or manual trigger)
• Runs comprehensive Ookla speed tests on each SIM
• Applies advanced sorting algorithms with tie-breaking logic
• Prioritizes SIMs by download speed, upload speed, then signal strength
• Configures WAN rule priorities based on performance
• Generates detailed timestamped results report

SIGNAL QUALITY CLASSIFICATION:
=============================
> -90 dBm     = Good Signal (normal operation)
-90 to -105   = Weak Signal (warning in staging feedback)
< -105 dBm    = Bad Signal ("Check Antenna" message)

MANUAL CONTROL COMMANDS:
=======================
Control SimSelector through the device description field in NCM:

"start"  = Run current phase (must be within 5-minute boot window for validation)
"force"  = Override uptime check and run current phase immediately
"reset"  = Reset to validation phase (restart device to begin fresh)
Clear field = Cancel any pending operations

TESTING FRAMEWORK:
=================
SimSelector includes comprehensive mock testing requiring no hardware:

Quick Tests:
python tests/test_runner.py good          # Good signal scenario
python tests/test_runner.py weak          # Weak signal scenario  
python tests/test_runner.py failed        # Failed connection scenario

Advanced Tests:
python tests/test_runner.py triple        # 3 SIM mixed performance
python tests/test_runner.py quad          # 4 SIM all carriers
python tests/test_runner.py highspeed     # Ultra-high 5G speeds
python tests/test_runner.py allweak       # All SIMs weak signals
python tests/test_runner.py tiebreaker    # Tie-breaking logic test

Comprehensive Testing:
python tests/test_runner.py all           # Run all 12 scenarios
python tests/test_runner.py interactive   # Interactive test mode

Expected Output
===============
SimSelector performs Ookla speed tests on all detected SIMs and prioritizes by TCP download speed.
It creates unique WAN profiles if needed but does not delete existing profiles.

SimSelector sends NCM alerts when starting, on timeouts, and when completing.
Results are stored in the device description field and synchronized to NCM.

EXAMPLE RESULTS FORMAT:
06/24/25 16:13:07 | Verizon 311480 B2 RSRP:-75 DL:95.2Mbps UL:28.4Mbps | T-Mobile 310260 B71 RSRP:-80 DL:110.1Mbps UL:32.7Mbps

Result Components:
• Timestamp (MM/DD/YY HH:MM:SS)
• Carrier Name and MCC/MNC codes
• RF Band information
• Signal Strength (RSRP in dBm)
• Download/Upload speeds in Mbps

KNOWN ISSUES & LIMITATIONS:
==========================

Technical Limitations:
• Minimum 2 SIMs required - will not run with only 1 SIM detected
• Validation phase only runs within first 5 minutes of device boot
• Results require active NCM connection for synchronization
• Speed test accuracy depends on network conditions and server selection

Common Issues and Solutions:

Issue: "Only 1 SIM found"
Cause: Second SIM not detected or has NOSIM error
Solutions: 
- Verify SIM cards are properly inserted and activated
- Wait 30 seconds for SIM detection and restart application
- Check SIM card status in router diagnostics

Issue: "Uptime is over 5 minutes"  
Cause: Trying to run validation phase after boot window closed
Solutions:
- Restart device to reset uptime counter
- Use "force" command to override uptime restriction
- Use "reset" command to restart from validation phase

Issue: Speed tests timing out
Cause: Poor cellular connectivity or Ookla server issues
Solutions:
- Check signal strength and antenna connections
- Verify SIM data plans are active and have sufficient data
- Application automatically tries alternative APNs on timeout

Issue: NCM synchronization failures
Cause: NetCloud Manager connectivity problems
Solutions:
- Verify internet connectivity and NCM credentials
- Wait for automatic NCM reconnection
- Check ECM status in router diagnostics

Performance Considerations:
• Memory Usage: Speed tests consume approximately 50MB RAM
• Data Consumption: Each complete speed test uses ~200MB data per SIM  
• Processing Time: Complete run takes 15-30 minutes depending on SIM count
• NCM Bandwidth: Results upload requires active NCM connection

TROUBLESHOOTING:
===============

Debug Information:
Check detailed logs: Monitor > Logs > Application Logs > SimSelector

State Management:
SimSelector maintains state between device boots:
- Validation phase sets state to "performance" when complete
- Performance phase sets state to "complete" when finished
- Use "reset" command to clear state and restart from validation

Manual Recovery Process:
If SimSelector appears stuck or unresponsive:
1. Clear the device description field in NCM
2. Issue "reset" command in description field  
3. Restart the device to begin fresh validation
4. Monitor application logs for detailed progress

File Structure:
SimSelector/
├── SimSelector.py          # Main application logic
├── csclient.py            # Cradlepoint SDK client library
├── speedtest.py           # Ookla speed test library
├── state_manager.py       # State persistence between boots
├── package.ini            # Application metadata and version
├── tests/                 # Comprehensive mock testing framework
│   ├── mock_framework.py  # Mock router API and speed tests
│   ├── test_runner.py     # Test execution and scenarios
│   └── mock_state_manager.py # Mock state management for testing
├── README.md              # Comprehensive documentation (Markdown)
└── readme.txt             # This documentation (Plain text)

SUPPORT:
========
For technical support:
1. Review application logs in NCM (Monitor > Logs > Application Logs)
2. Test functionality using the mock framework before hardware deployment
3. Verify signal quality, antenna connections, and SIM activation status
4. Check that SIM data plans are active with sufficient data allowances

This application is part of the Cradlepoint SDK samples.

SimSelector 2.5.9 - Intelligent SIM Performance Optimization for Cradlepoint Routers

