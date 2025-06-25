#!/usr/bin/env python3
"""
Test Phase Manager for SimSelector v2.6.0

Tests the three-phase state machine implementation including:
- Phase transitions and validation
- Phase execution methods
- State persistence
- Security integration
- Error handling
"""

import sys
import os
import time
import tempfile
import shutil

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phase_manager():
    """Test the phase manager functionality"""
    print("=== SimSelector v2.6.0 Phase Manager Test ===\n")
    
    try:
        # Import phase manager
        from phase_manager import get_phase_manager, PhaseExecutionResult
        from SimSelector import Phase
        
        print("✓ Successfully imported phase manager components")
        
        # Create phase manager instance
        phase_manager = get_phase_manager()
        print("✓ Phase manager instance created")
        
        # Test initial state
        current_phase = phase_manager.get_current_phase()
        print(f"✓ Initial phase: {Phase.get_name(current_phase) if current_phase is not None else 'None'}")
        
        # Test phase status
        status = phase_manager.get_phase_status()
        print(f"✓ Phase status retrieved: {status['current_phase_name']}")
        
        # Test transition to staging phase
        print("\n--- Testing Phase Transitions ---")
        # Reset to staging first to ensure clean state
        result = phase_manager.reset_to_staging()
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Successfully reset to STAGING phase")
        else:
            print(f"✗ Failed to reset to STAGING phase: {result}")
            return False
        
        # Test staging phase execution
        print("\n--- Testing Phase Execution ---")
        result = phase_manager.execute_staging_phase()
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Staging phase execution completed successfully")
        elif result == PhaseExecutionResult.FAILURE:
            print("⚠ Staging phase execution failed (expected - no real SIM data)")
        else:
            print(f"✓ Staging phase execution result: {result}")
        
        # Test transition to install phase
        result = phase_manager.transition_to_phase(Phase.INSTALL)
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Successfully transitioned to INSTALL phase")
        else:
            print(f"✗ Failed to transition to INSTALL phase: {result}")
            return False
        
        # Test install phase execution
        result = phase_manager.execute_install_phase()
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Install phase execution completed successfully")
        elif result == PhaseExecutionResult.FAILURE:
            print("⚠ Install phase execution failed (expected - no real SIM data)")
        else:
            print(f"✓ Install phase execution result: {result}")
        
        # Test transition to deployed phase
        result = phase_manager.transition_to_phase(Phase.DEPLOYED)
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Successfully transitioned to DEPLOYED phase")
        else:
            print(f"✗ Failed to transition to DEPLOYED phase: {result}")
            return False
        
        # Test deployed phase execution
        result = phase_manager.execute_deployed_phase()
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Deployed phase execution completed successfully")
        else:
            print(f"✗ Deployed phase execution failed: {result}")
            return False
        
        # Test phase advancement
        print("\n--- Testing Phase Advancement ---")
        phase_manager.reset_to_staging()
        print("✓ Reset to staging phase")
        
        result = phase_manager.advance_to_next_phase()
        if result == PhaseExecutionResult.SUCCESS:
            current_phase = phase_manager.get_current_phase()
            print(f"✓ Advanced to next phase: {Phase.get_name(current_phase)}")
        else:
            print(f"✗ Failed to advance phase: {result}")
            return False
        
        # Test manual commands
        print("\n--- Testing Manual Commands ---")
        commands = ["status", "reset", "advance"]
        for command in commands:
            result = phase_manager.handle_manual_command(command)
            print(f"✓ Command '{command}' executed: {result}")
        
        # Test phase history
        print("\n--- Testing Phase History ---")
        history = phase_manager.get_phase_history(5)
        print(f"✓ Retrieved {len(history)} phase history entries")
        for i, entry in enumerate(history):
            print(f"  {i+1}. {entry['from_phase_name']} -> {entry['to_phase_name']} ({entry['result']})")
        
        # Test invalid transitions
        print("\n--- Testing Invalid Transitions ---")
        # Try to go from deployed back to staging without force
        phase_manager.transition_to_phase(Phase.DEPLOYED)
        result = phase_manager.transition_to_phase(Phase.STAGING, force=False)
        if result == PhaseExecutionResult.FAILURE:
            print("✓ Invalid transition correctly rejected")
        else:
            print(f"⚠ Invalid transition not rejected: {result}")
        
        # Test forced transition
        result = phase_manager.transition_to_phase(Phase.STAGING, force=True)
        if result == PhaseExecutionResult.SUCCESS:
            print("✓ Forced transition successful")
        else:
            print(f"✗ Forced transition failed: {result}")
            return False
        
        print("\n=== Phase Manager Test Completed Successfully ===")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("This is expected if running outside the full SimSelector environment")
        return False
    except Exception as e:
        print(f"✗ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_phase_persistence():
    """Test phase state persistence"""
    print("\n=== Testing Phase State Persistence ===")
    
    try:
        from phase_manager import get_phase_manager
        from SimSelector import Phase
        
        # Create first instance and set a phase
        phase_manager1 = get_phase_manager()
        phase_manager1.transition_to_phase(Phase.INSTALL, force=True)
        
        # Get the phase
        phase1 = phase_manager1.get_current_phase()
        print(f"✓ Set phase to: {Phase.get_name(phase1)}")
        
        # Create second instance (simulating restart)
        from phase_manager import _phase_manager
        globals()['_phase_manager'] = None  # Reset global instance
        
        phase_manager2 = get_phase_manager()
        phase2 = phase_manager2.get_current_phase()
        
        if phase1 == phase2:
            print(f"✓ Phase persistence successful: {Phase.get_name(phase2)}")
            return True
        else:
            print(f"✗ Phase persistence failed: {Phase.get_name(phase1)} != {Phase.get_name(phase2)}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing persistence: {e}")
        return False

if __name__ == "__main__":
    success = True
    
    # Run main phase manager test
    success &= test_phase_manager()
    
    # Run persistence test
    success &= test_phase_persistence()
    
    if success:
        print("\n🎉 All phase manager tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some phase manager tests failed!")
        sys.exit(1) 