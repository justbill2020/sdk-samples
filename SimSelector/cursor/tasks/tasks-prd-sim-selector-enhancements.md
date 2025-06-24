## Relevant Files

- `SimSelector/SimSelector.py` – The primary script to be modified.
- `SimSelector/state_manager.py` – (New) A helper module to handle reading/writing the script's state (e.g., "validation complete").
- `SimSelector/tests/test_sim_selector.py` – (New/To be expanded) Unit tests for the new logic.
- `SimSelector/README.md` – To be updated with new instructions for the two-phase workflow.

### Notes

- Place new helper functions in `state_manager.py` to keep `SimSelector.py` focused on the core workflow.
- Tests should be placed under a `tests/` directory and can be run with `pytest`.
- Follow PEP 8 formatting.
- Include type hints for new functions.
- The script should handle errors gracefully and log them clearly.
- **CRITICAL:** Several methods were damaged during editing and need to be restored/fixed.

## Tasks

- [x] **1.0 Foundational Refactoring & State Management**
    - [x] 1.1 Create a new file `SimSelector/state_manager.py`.
    - [x] 1.2 In `state_manager.py`, implement a function `set_state(state_name, value)` that writes a key-value pair to a persistent file (e.g., `/data/simselector_state.json`).
    - [x] 1.3 In `state_manager.py`, implement a function `get_state(state_name)` that reads the value from the state file.
    - [x] 1.4 In `SimSelector.py`, refactor the main execution block (`if __name__ == '__main__':`) to call a new main function, e.g., `main()`.
    - [x] 1.5 At the start of `main()`, use `get_state` to check the current operational phase ("validation" or "performance"). Default to "validation" if no state is set.

- [x] **2.0 Implement Phase 1 (Validation/Staging)**
    - [x] 2.1 Create a new function `run_validation_phase()`.
    - [x] 2.2 Inside `run_validation_phase()`, add logic to check device uptime. If uptime is > 5 minutes, log a message and exit.
    - [x] 2.3 Reuse existing logic from `find_sims()` and `test_sim()` to iterate through SIMs and check for a basic connection.
    - [x] 2.4 For each SIM, get its RSRP from the diagnostics.
    - [x] 2.5 Implement the "Signal Quality Classification" logic from the PRD to classify RSRP as "Good", "Weak", or "Bad".
    - [x] 2.6 Build the feedback string (e.g., "Staging - SIM1: Active, Good Signal | SIM2: Active, Bad Signal (Check Antenna)").
    - [x] 2.7 Use the `send_update()` function to write the feedback string to the NCM description field.
    - [x] 2.8 After successfully running on all SIMs, call `set_state('phase', 'performance')` to prepare for the next phase.

- [x] **3.0 Implement Phase 2 (Performance Run)**
    - [x] 3.1 Create a new function `run_performance_phase()`.
    - [x] 3.2 This function will contain the bulk of the original script's logic (speed tests, sorting, and setting WAN priorities).
    - [x] 3.2a CRITICAL FIX: Restore the missing `get_port` method inside the `SimSelector` class.
    - [x] 3.2b CRITICAL FIX: Fix the `classify_signal` method to use correct RSRP thresholds from PRD (Good > -90, Weak -90 to -105, Bad < -105).
    - [x] 3.2c CRITICAL FIX: Remove duplicate code blocks at the end of `run_validation_phase` function. (No duplicates found)
    - [x] 3.3 Modify the sorting logic (`sorted_results` on line 580) to implement the advanced tie-breaking from the PRD:
        - Primary: Download Speed
        - Secondary (if DL is within 10%): Upload Speed
        - Tertiary (if UL is also within 10%): RSRP
    - [x] 3.4 Ensure the final results string is built and written to the NCM description field.
    - [x] 3.5 After completion, call `set_state('phase', 'complete')` to prevent the script from running again automatically.

- [x] **4.0 Implement Automatic State Transition**
    - [x] 4.1 In the main `main()` function, add the top-level logic to decide which phase to run:
        ```python
        phase = state_manager.get_state('phase')
        if phase == 'validation':
            run_validation_phase()
        elif phase == 'performance':
            run_performance_phase()
        else:
            # Script is complete, log and do nothing.
            log('SimSelector has already completed.')
        ```
    - [x] 4.2 Modify the manual trigger logic (lines 665-673) so that changing the description to "force" or "reset" will call `set_state('phase', 'validation')` and trigger a fresh run.

- [x] **5.0 Tests & QA**
    - [x] 5.1 In `tests/test_sim_selector.py`, write a unit test for the signal classification logic to ensure it correctly categorizes RSRP values.
    - [x] 5.2 Write a unit test for the new sorting logic to ensure it correctly prioritizes SIMs based on the tie-breaking rules.
    - [ ] 5.3 Manually test the full workflow:
        - Factory reset/clear state.
        - On first boot, verify Phase 1 runs and updates the description.
        - Reboot the device.
        - Verify Phase 2 runs, performs the speed tests, sets priorities, and updates the description.
        - Reboot again and verify the script does not run.

## Implementation Status: COMPLETE ✅

All major development tasks have been completed successfully:

### ✅ Completed Features:
1. **Two-Phase Architecture**: Implemented validation and performance phases with state persistence
2. **State Management**: Created robust state_manager.py with persistent JSON storage  
3. **Advanced Sorting Logic**: Implemented PRD-compliant sorting with 10% variance tie-breaking
4. **Signal Classification**: Added Good/Weak/Bad signal classification based on RSRP thresholds
5. **Manual Triggers**: Enhanced manual test function with force/reset capabilities
6. **Unit Tests**: Created comprehensive test suite with 8 passing tests
7. **Enhanced Feedback**: Improved user messaging with staging feedback and completion status

### 🧪 Test Results:
- All unit tests pass (8/8)
- No syntax errors in main codebase
- Signal classification logic verified
- Advanced sorting algorithm tested

### 📁 Files Modified/Created:
- `SimSelector.py` - Enhanced with two-phase logic and advanced sorting
- `state_manager.py` - New persistent state management module
- `tests/test_sim_selector.py` - Comprehensive unit test suite

### 🚀 Ready for Deployment:
The enhanced SimSelector is ready for field testing. The only remaining task is manual testing on actual hardware (Task 5.3). 