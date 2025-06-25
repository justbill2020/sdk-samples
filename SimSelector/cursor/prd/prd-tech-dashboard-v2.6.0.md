# PRD: SimSelector Tech Dashboard & Three-Phase Enhancement

## 1. Introduction/Overview

This document outlines the requirements for enhancing SimSelector to v2.6.0 with a comprehensive three-phase workflow and integrated tech dashboard. The goal is to create a streamlined device lifecycle from warehouse staging through field installation to production deployment, with appropriate dashboard access for technicians at each phase.

The core enhancement introduces a **Tech Dashboard** accessible during staging and installation phases, providing real-time visibility into device status, SIM performance, and installation progress. This dashboard will significantly improve the installation experience for field technicians and reduce support overhead.

## 2. Goals

- **Streamline Device Lifecycle:** Implement a clear three-phase workflow (Staging → Install → Deployed)
- **Improve Field Installation Experience:** Provide technicians with real-time dashboard access during installation
- **Reduce Support Calls:** Give techs immediate visibility into device status and SIM performance
- **Maintain Security:** Ensure dashboard access is properly controlled and disabled in production
- **Business Continuity:** Implement robust error handling to prevent device failures during critical installations

## 3. User Stories

### **Warehouse/Staging Technician:**
- **As a staging technician,** I want to power on a pre-configured device and immediately see both SIMs are functional, so I can confirm the device is ready for shipment without technical expertise.
- **As a staging technician,** I want a clear dashboard showing "SIM1: Verizon - Connected - APN: vzwinternet - IP: 10.x.x.x" so I can verify connectivity before shipping.
- **As a staging technician,** I want the device to remain in staging mode until I power it off, so I can perform multiple validation checks if needed.

### **Field Installation Technician:**
- **As a field technician,** I want to connect to a local dashboard during installation to see real-time SIM performance and signal strength, so I can optimize antenna placement.
- **As a field technician,** I want to view live RSRP data for both SIMs during installation, so I can ensure optimal signal quality before completing the installation.
- **As a field technician,** I want access to SimSelector help documentation on the dashboard, so I can troubleshoot issues without calling support.
- **As a field technician,** I want to see the current phase status and progress, so I know when the installation process is complete.

### **Test & Turn-Up Team:**
- **As a test & turn-up team member,** I want to access the tech dashboard via NCM remote connect, so I can assist with remote troubleshooting during installation.
- **As a test & turn-up team member,** I want to manage device configuration through standard NCM tools while the tech dashboard provides real-time status, so I can coordinate effectively with field technicians.

### **Network Administrator:**
- **As a network administrator,** I want the dashboard to be automatically disabled in production deployment, so the device maintains security in operational environments.
- **As a network administrator,** I want the dashboard accessible via NCM remote connect even in deployed phase, so I can perform maintenance when needed.

## 4. Functional Requirements

### **Phase Management:**

1. **Staging Phase (Warehouse):**
   - Device boots into staging phase on first power-on after SDK installation
   - Validates both SIMs have functional connections (exception: single-SIM modems)
   - Displays clear status: "SIM1: [Carrier] - Connected - APN: [apn] - IP: [address]"
   - Remains in staging phase until device is powered off
   - Dashboard accessible via LAN (wired/wireless)

2. **Install Phase (Field Installation):**
   - Triggered automatically on first boot after staging phase completion
   - Runs full SimSelector validation and performance testing
   - Tech dashboard remains active throughout installation process
   - Displays real-time RSRP data, phase progress, and SIM performance
   - Transitions to deployed phase upon completion

3. **Deployed Phase (Production):**
   - Dashboard disabled for local LAN access
   - Dashboard remains accessible via NCM remote connect only
   - Standard SimSelector operation with existing manual triggers
   - Can only return to install phase via device reset

### **Tech Dashboard Features:**

4. **Real-Time Data Display:**
   - Live RSRP values for all detected SIMs
   - Current phase status and progress indicators
   - Router log stream (filtered for relevant events)
   - Custom APNs currently configured
   - Online/offline status indicators

5. **Device Information:**
   - Device model, firmware version, uptime
   - Current WAN connection status and signal strengths
   - Network interface information and IP addresses
   - SIM carrier identification and connection details

6. **Documentation & Help:**
   - Integrated SimSelector help documentation
   - Phase-specific guidance and troubleshooting tips
   - Contact information for support escalation

### **Network Configuration:**

7. **LAN Access Control:**
   - Dashboard accessible from any LAN interface during staging/install phases
   - Automatic firewall rule management for dashboard access
   - Implicit denial of local access during deployed phase
   - NCM remote connect compatibility maintained in all phases

8. **Security & Access:**
   - View-only dashboard access (no authentication required in v2.6.0)
   - Dashboard automatically disabled in production deployment
   - Robust error handling to prevent business-critical device failures
   - Secure firewall rule management

### **Data Persistence:**

9. **State Management:**
   - Enhanced state persistence using SDK save data functionality
   - Phase transition logging and timestamps
   - Installation progress tracking
   - Access key generation and storage (prepared for v2.6.2)

## 5. Non-Goals (Out of Scope)

- **Authentication/Login:** Dashboard login functionality deferred to v2.6.2
- **Tech Access Control:** Granular permissions and access codes deferred to v2.6.2
- **Remote Configuration:** Dashboard-based device configuration (use NCM instead)
- **Multi-Device Management:** Dashboard focuses on single device installation
- **Historical Analytics:** Long-term performance tracking (focus on real-time data)

## 6. Technical Considerations

### **Integration Requirements:**
- **Existing SimSelector Integration:** Dashboard must display current validation/performance phase progress
- **NCM Compatibility:** Ensure dashboard works with NCM remote connect feature
- **SDK Save Data:** Utilize SDK save data functionality for state persistence
- **Firewall Management:** Automatic rule creation/removal for dashboard access

### **Network Configuration Changes:**
- **HTTP Server:** Embedded web server for dashboard (port 8080 recommended)
- **Firewall Rules:** Dynamic rules for LAN access during staging/install phases
- **Interface Binding:** Dashboard accessible on all LAN interfaces
- **Remote Connect:** Compatible with NCM HTTP remote connect feature

### **Performance Requirements:**
- **Real-Time Updates:** RSRP data refresh every 5-10 seconds
- **Responsive Design:** Dashboard accessible from mobile devices and tablets
- **Low Resource Usage:** Minimal impact on device performance during critical phases
- **Fault Tolerance:** Dashboard failures must not impact SimSelector core functionality

## 7. Success Metrics

- **Reduced Installation Time:** 25% reduction in average field installation time
- **Decreased Support Calls:** 40% reduction in installation-related support tickets
- **Improved First-Time Success Rate:** 95% of installations complete without escalation
- **Tech Satisfaction:** Positive feedback from field technicians on dashboard usability
- **Zero Critical Failures:** No business-critical device failures due to dashboard functionality

## 8. Implementation Phases

### **v2.6.0 - Core Dashboard (Current PRD):**
- Three-phase workflow implementation
- Basic tech dashboard with real-time data
- LAN access control and NCM compatibility
- View-only access (no authentication)

### **v2.6.1 - Enhanced Features:**
- Advanced troubleshooting tools
- Enhanced documentation and help system
- Performance optimizations

### **v2.6.2 - Authentication & Security:**
- Access key authentication system
- Granular permission controls
- Enhanced security features

## 9. Open Questions

1. **Dashboard Port Configuration:** Should the HTTP port be configurable or fixed at 8080?
2. **Log Filtering:** What specific log events should be displayed vs. filtered out?
3. **Mobile Responsiveness:** What screen sizes should be prioritized for dashboard design?
4. **Staging Timeout:** Should staging phase have an automatic timeout, or remain active indefinitely?
5. **Error Recovery:** What specific error conditions require automatic phase transitions?

## 10. Change Log Preparation

**Major Changes from v2.5.9:**
- **Phase Structure:** Two-phase (Validation → Performance) expanded to three-phase (Staging → Install → Deployed)
- **Network Services:** Added embedded HTTP server for tech dashboard
- **Access Control:** Dynamic firewall rule management
- **State Management:** Enhanced state persistence with phase tracking
- **User Interface:** New web-based dashboard for technician access

**Breaking Changes:**
- Phase enumeration updated (requires state migration)
- New network configuration requirements
- Additional SDK dependencies for HTTP server

**Documentation Updates Required:**
- Installation procedures for three-phase workflow
- Network configuration requirements
- Troubleshooting guides for dashboard access
- Field technician training materials

---

**Target Implementation:** SimSelector v2.6.0  
**Priority:** High - Business Critical Feature  
**Estimated Complexity:** Large (3-4 week development cycle)  
**Dependencies:** Enhanced state management, HTTP server integration, firewall management 