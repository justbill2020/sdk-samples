"""
Mock State Manager for SimSelector Testing
==========================================
This mock replaces the real state_manager.py during testing.
"""

# In-memory state storage for testing
_test_state = {}


def get_state(key: str, default=None):
    """Get state value for testing."""
    value = _test_state.get(key, default)
    print(f"[MOCK STATE] GET {key} = {value}")
    return value


def set_state(key: str, value):
    """Set state value for testing."""
    _test_state[key] = value
    print(f"[MOCK STATE] SET {key} = {value}")


def clear_state():
    """Clear all state for testing."""
    global _test_state
    _test_state = {}
    print("[MOCK STATE] CLEARED ALL STATE")


def get_all_state():
    """Get all state for debugging."""
    return _test_state.copy() 