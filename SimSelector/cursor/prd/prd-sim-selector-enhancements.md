# PRD: SimSelector Staging & Enhanced Selection

## 1. Introduction/Overview

This document outlines the requirements for enhancing the `SimSelector` SDK application. The goal is to create a more robust and automated tool for field technicians to ensure optimal SIM card selection and antenna placement during device installation.

The core improvement is a two-phase process:
1.  **Phase 1 (Validation/Staging):** An initial, automated check to validate SIM activity and signal quality, providing immediate feedback for antenna adjustments.
2.  **Phase 2 (Performance/Run):** A full performance test that automatically runs after validation to select and prioritize the best-performing SIM for the device.

This new workflow will be based on the existing `SimSelector.py` script, adding stability and more intelligent decision-making.

## 2. Goals

*   To automate the SIM validation process during new device installations.
*   To provide clear, actionable feedback to technicians regarding signal quality and potential antenna issues.
*   To implement a more sophisticated logic for selecting the "best" SIM, considering download speed, upload speed, and signal strength.
*   To create a seamless, two-phase workflow that transitions automatically from initial validation to final performance testing.
*   To reduce installation errors and ensure devices are deployed with the most reliable cellular connection from the start.

## 3. User Stories

*   **As a field technician,** I want to power on a new device and have it automatically test the installed SIMs so that I can immediately see if they are active and have a good signal.
*   **As a field technician,** I want the device to clearly report "Check Antenna" if the signal is very poor, so I know to reposition the antenna or check the connections before leaving the site.
*   **As an automated system,** I want to transition from the initial SIM validation to a full speed test on the next reboot, so that the final selection process requires no manual intervention.
*   **As a network administrator,** I want the device to intelligently choose the best SIM based on a combination of download, upload, and signal metrics, ensuring the most performant and reliable connection is prioritized.

## 4. Functional Requirements

### Phase 1: Validation/Staging

1.  **Trigger:** The validation phase shall run automatically on the device's first boot after a factory reset or initial configuration. This can be determined by device uptime (e.g., < 5 minutes).
2.  **SIM Status Check:** The script must iterate through all installed SIMs and verify their status.
3.  **Connectivity & Signal Test:** For each active SIM, the script will:
    *   Attempt to establish a basic connection.
    *   Measure the signal strength (RSRP).
4.  **Signal Quality Classification:** The script must classify the signal strength based on the following RSRP thresholds:
    *   **Good:** RSRP > -90 dBm
    *   **Weak:** RSRP between -90 dBm and -105 dBm
    *   **Bad:** RSRP < -105 dBm
5.  **Feedback Reporting:** The script must write the validation results to the NCM device description field (`/config/system/desc`).
    *   The format should be clear and concise, e.g., `Staging - SIM1: Active, Good Signal | SIM2: Active, Bad Signal (Check Antenna)`.
    *   If a SIM is inactive, it should be reported, e.g., `Staging - SIM1: Inactive | SIM2: Active, Weak Signal`.
6.  **State Persistence:** The script must record that the validation phase has been completed successfully. This could be a persisted value or a specific state written to a file on the device.

### Phase 2: Performance Run

1.  **Trigger:** The performance run shall execute automatically on the next reboot *after* the validation phase has been successfully completed. The script must check the persisted state from Phase 1 to ensure it does not re-run validation.
2.  **Full Performance Tests:** The script will perform the following tests on each validated, active SIM:
    *   Ookla speed test to measure TCP download speed.
    *   Ookla speed test to measure TCP upload speed.
    *   Record final RSRP value.
3.  **SIM Prioritization Logic:** The script must sort and prioritize the SIMs according to the following hierarchical logic:
    1.  **Primary Sort:** Highest download speed.
    2.  **Secondary Sort (Tie-Breaker):** If the top download speeds are within a 10% variance of each other, the one with the highest upload speed is ranked higher.
    3.  **Tertiary Sort (Tie-Breaker):** If upload speeds are also within a 10% variance, the one with the best RSRP (higher value, e.g., -85 dBm is better than -95 dBm) is ranked higher.
4.  **Final Configuration:** The script will re-prioritize the WAN rules in the device configuration to match the sorted list from the previous step. The highest-ranked SIM will have the highest priority.
5.  **Final Reporting:** The script must update the NCM device description field with the final results, e.g., `SimSelector Complete - SIM2: DL:85/UL:12/RSRP:-88 | SIM1: DL:82/UL:15/RSRP:-95`.

## 5. Non-Goals (Out of Scope)

*   This version will not include a local web server/UI for technicians. Feedback will be exclusively through the NCM device description field.
*   The script will not continuously monitor SIM performance after the initial selection. It is a "run-once" tool for installation.
*   The script will not handle scenarios with more than two SIMs.

## 6. Technical Considerations

*   The solution should be built upon the existing `SimSelector.py` script.
*   Care must be taken to properly suspend and resume NCM control to avoid configuration conflicts, as is done in the current script.
*   The method for persisting the "validation complete" state must be reliable and survive reboots. Using a non-volatile storage path is required.

## 7. Success Metrics

*   Reduction in support calls related to poor signal or incorrect SIM selection for new installations.
*   Positive feedback from field technicians on the clarity and usefulness of the staging feedback.
*   Consistent and reliable prioritization of the objectively best-performing SIM card at installation time.

## 8. Open Questions

*   Should the script clear the "validation complete" state if a SIM card's ICCID changes, forcing a re-validation? (To be considered for a future version). 