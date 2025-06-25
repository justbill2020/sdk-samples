# SimSelector Changelog

All notable changes to the SimSelector project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - v2.6.0

### Added - Architecture Foundation ✅ COMPLETE
- **Phase Enumeration System:** STAGING(0), INSTALL(1), DEPLOYED(2) with comprehensive validation
- **Secure State Transitions:** PhaseTransitionManager with validation matrix and rollback capabilities
- **Encrypted State Storage:** AES encryption for sensitive data (dashboard tokens, API keys, credentials)
- **Access Control Matrix:** Phase-specific dashboard and network permissions with security enforcement
- **Comprehensive Documentation:** Phase behaviors, security considerations, and transition flows

### Added - Planned Features (In Development)
- **Tech Dashboard:** Web-based dashboard for technician access during staging and installation
- **Real-Time RSRP Display:** Live signal strength monitoring for SIM optimization
- **Embedded HTTP Server:** Local web server for dashboard access (port 8080)
- **Dynamic Firewall Management:** Automatic rule creation/removal for dashboard access
- **NCM Remote Connect Compatibility:** Dashboard accessible via NCM remote connect

### Security Enhancements ✅ COMPLETE
- **Device-Based Encryption:** PBKDF2 key derivation using hardware characteristics
- **Automatic Data Protection:** Sensitive keys automatically encrypted at rest
- **Production Security:** Dashboard access disabled in DEPLOYED phase
- **Secure Transitions:** Phase transition validation prevents unauthorized access
- **Backward Compatibility:** Maintains existing state_manager API

### Infrastructure ✅ COMPLETE
- **Dependencies:** Added cryptography>=3.4.8 for secure encryption
- **State Management:** SecureStateManager class with encryption/decryption
- **Development Support:** Auto-detection of production vs development environments
- **Error Handling:** Comprehensive exception handling and recovery mechanisms

### Changed
- **Version:** Updated to SimSelector 2.6.0 for three-phase architecture
- **Phase Structure:** Expanded from Validation/Performance to Staging/Install/Deployed phases
- **State Storage:** Enhanced with encryption for sensitive data
- **Documentation:** Complete phase architecture and security documentation

### Breaking Changes
- **Phase Enumeration:** New three-phase system requires state migration
- **Dependencies:** Requires cryptography library for secure state storage
- **Network Requirements:** New firewall rules and HTTP server dependencies (planned)

## [2.5.9] - 2024-06-24

### Added
- **Two-Phase Operation:** Validation phase followed by Performance phase
- **Advanced SIM Sorting:** Intelligent tie-breaking with 10% variance logic
- **Enhanced Manual Controls:** Support for 'start', 'force', and 'reset' commands
- **Signal Quality Classification:** Good/Weak/Bad signal categorization based on RSRP
- **State Persistence:** Reliable state management across reboots
- **Comprehensive Testing Framework:** 12 mock test scenarios with hardware simulation
- **Security Enhancements:** Credential protection and security remediation
- **Complete Documentation:** README.md, testing guides, and troubleshooting

### Changed
- **Sorting Algorithm:** Primary by download speed, secondary by upload, tertiary by RSRP
- **Manual Triggers:** Enhanced manual test function with multiple command support
- **Error Handling:** Improved speedtest initialization and connectivity checks
- **Feedback System:** Enhanced staging feedback with signal quality indicators

### Fixed
- **Speedtest Initialization:** Better error handling for connectivity issues
- **State Transitions:** Reliable phase management across device reboots
- **Security Issues:** Removed credential exposure and implemented proper .gitignore

### Technical Improvements
- **Unit Tests:** 8 comprehensive test cases covering core functionality
- **Mock Framework:** Complete hardware simulation for development testing
- **Code Quality:** Enhanced error handling and logging throughout
- **SDK Updates:** Updated core SDK components (cp.py, csclient.py)

## [2.5.8] - Previous Version

### Features
- Basic SIM selection and prioritization
- Ookla speed testing
- WAN rule management
- Single-phase operation

---

## Version History Summary

| Version | Release Date | Major Features |
|---------|--------------|----------------|
| **2.6.0** | *Planned* | Tech Dashboard, Three-Phase Workflow |
| **2.5.9** | 2024-06-24 | Two-Phase Operation, Advanced Sorting, Testing Framework |
| **2.5.8** | *Previous* | Basic SIM Selection and Speed Testing |

## Development Guidelines

### Version Numbering
- **Major (X.0.0):** Breaking changes, significant architecture changes
- **Minor (X.Y.0):** New features, backwards compatible
- **Patch (X.Y.Z):** Bug fixes, minor improvements

### Changelog Guidelines
- Document all user-facing changes
- Include breaking changes section for major updates
- Provide migration guidance when necessary
- Link to relevant PRDs and documentation

### Branch Strategy
- **main:** Production-ready releases
- **dev-X.Y.Z:** Feature development branches
- **hotfix-X.Y.Z:** Critical bug fixes

---

*For detailed technical specifications, see the PRD documents in `/cursor/prd/` directory.* 