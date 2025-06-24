"""
A helper module to handle reading/writing the script's state 
(e.g., "validation complete").
"""
import json
import os

STATE_FILE = '/data/simselector_state.json'

def set_state(state_name: str, value: any):
    """
    Writes a key-value pair to the persistent state file.
    """
    data = {}
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        
        # Read existing data if file exists
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                # Handle empty file case
                content = f.read()
                if content:
                    data = json.loads(content)
    except (IOError, json.JSONDecodeError) as e:
        # For a real device, you'd use a proper logger.
        # This print is a placeholder for development.
        print(f"Could not read state file, starting fresh: {e}")
        data = {}

    # Update data and write back to file
    data[state_name] = value
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Could not write to state file: {e}")

def get_state(state_name: str) -> any:
    """
    Reads the state file and returns the value for the given state_name.
    Returns None if the file or key does not exist.
    """
    if not os.path.exists(STATE_FILE):
        return None
    
    try:
        with open(STATE_FILE, 'r') as f:
            content = f.read()
            if not content:
                return None
            data = json.loads(content)
            return data.get(state_name)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Could not read state file: {e}")
        return None 