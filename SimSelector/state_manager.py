"""
A helper module to handle reading/writing the script's state 
(e.g., "validation complete") with secure encryption for sensitive data.
SimSelector v2.6.0 - Enhanced with encryption and security features.
"""
import json
import os
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import tempfile

# Use /data for production, temp directory for development
if os.path.exists('/data') and os.access('/data', os.W_OK):
    STATE_FILE = '/data/simselector_state.json'
    DEVICE_ID_FILE = '/data/device_id'
else:
    # Development mode - use temporary directory
    temp_dir = os.path.join(tempfile.gettempdir(), 'simselector')
    STATE_FILE = os.path.join(temp_dir, 'simselector_state.json')
    DEVICE_ID_FILE = os.path.join(temp_dir, 'device_id')

# Define which state keys contain sensitive data that should be encrypted
SENSITIVE_KEYS = {
    'dashboard_access_token',
    'api_keys', 
    'auth_credentials',
    'device_secrets',
    'installation_tokens'
}

class SecureStateManager:
    """Enhanced state manager with encryption for sensitive data"""
    
    def __init__(self):
        self._encryption_key = None
        self._device_id = None
    
    def _get_device_id(self):
        """Get or create a unique device identifier"""
        if self._device_id:
            return self._device_id
            
        try:
            # Try to read existing device ID
            if os.path.exists(DEVICE_ID_FILE):
                with open(DEVICE_ID_FILE, 'r') as f:
                    self._device_id = f.read().strip()
                    return self._device_id
        except IOError:
            pass
        
        # Generate new device ID based on hardware characteristics
        try:
            # Use MAC address and hostname for device fingerprinting
            import uuid
            import socket
            
            mac = uuid.getnode()
            hostname = socket.gethostname()
            device_string = f"{mac}-{hostname}-simselector"
            
            # Create hash of device characteristics
            device_hash = hashlib.sha256(device_string.encode()).hexdigest()[:16]
            self._device_id = f"ss-{device_hash}"
            
            # Save device ID for future use
            os.makedirs(os.path.dirname(DEVICE_ID_FILE), exist_ok=True)
            with open(DEVICE_ID_FILE, 'w') as f:
                f.write(self._device_id)
                
            return self._device_id
            
        except Exception as e:
            # Fallback to timestamp-based ID
            import time
            fallback_id = f"ss-fallback-{int(time.time())}"
            self._device_id = fallback_id
            return self._device_id
    
    def _get_encryption_key(self):
        """Generate or retrieve encryption key based on device characteristics"""
        if self._encryption_key:
            return self._encryption_key
        
        device_id = self._get_device_id()
        
        # Use device ID as password for key derivation
        password = device_id.encode()
        
        # Use a fixed salt for consistency (in production, consider dynamic salt)
        salt = b'simselector_v2.6.0_salt'
        
        # Derive encryption key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self._encryption_key = key
        return self._encryption_key
    
    def _encrypt_data(self, data):
        """Encrypt sensitive data"""
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            
            # Convert data to JSON string then encrypt
            json_data = json.dumps(data)
            encrypted_data = fernet.encrypt(json_data.encode())
            
            # Return base64 encoded encrypted data
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            print(f"Encryption failed: {e}")
            # Return None to indicate encryption failure
            return None
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt sensitive data"""
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            
            # Decode base64 then decrypt
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            
            # Convert back to original data structure
            json_data = decrypted_bytes.decode()
            return json.loads(json_data)
            
        except Exception as e:
            print(f"Decryption failed: {e}")
            # Return None to indicate decryption failure
            return None
    
    def _is_sensitive_key(self, state_name):
        """Check if a state key contains sensitive data"""
        return state_name in SENSITIVE_KEYS
    
    def set_state(self, state_name: str, value: any, force_encrypt: bool = False):
        """
        Writes a key-value pair to the persistent state file.
        Automatically encrypts sensitive data.
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
            print(f"Could not read state file, starting fresh: {e}")
            data = {}

        # Determine if data should be encrypted
        should_encrypt = force_encrypt or self._is_sensitive_key(state_name)
        
        if should_encrypt:
            # Encrypt sensitive data
            encrypted_value = self._encrypt_data(value)
            if encrypted_value is not None:
                data[state_name] = {
                    '_encrypted': True,
                    '_data': encrypted_value,
                    '_version': '2.6.0'
                }
            else:
                print(f"Failed to encrypt sensitive data for key: {state_name}")
                return False
        else:
            # Store non-sensitive data as plain text
            data[state_name] = value

        # Write back to file
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except IOError as e:
            print(f"Could not write to state file: {e}")
            return False
    
    def get_state(self, state_name: str) -> any:
        """
        Reads the state file and returns the value for the given state_name.
        Automatically decrypts sensitive data.
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
                
                if state_name not in data:
                    return None
                
                value = data[state_name]
                
                # Check if data is encrypted
                if isinstance(value, dict) and value.get('_encrypted'):
                    # Decrypt the data
                    decrypted_value = self._decrypt_data(value['_data'])
                    return decrypted_value
                else:
                    # Return plain text data
                    return value
                    
        except (IOError, json.JSONDecodeError) as e:
            print(f"Could not read state file: {e}")
            return None
    
    def clear_sensitive_data(self):
        """Clear all sensitive data from state storage"""
        if not os.path.exists(STATE_FILE):
            return True
        
        try:
            with open(STATE_FILE, 'r') as f:
                content = f.read()
                if not content:
                    return True
                data = json.loads(content)
            
            # Remove sensitive keys
            keys_to_remove = []
            for key in data.keys():
                if self._is_sensitive_key(key):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del data[key]
            
            # Write cleaned data back
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            
            return True
            
        except (IOError, json.JSONDecodeError) as e:
            print(f"Could not clear sensitive data: {e}")
            return False
    
    def get_device_info(self):
        """Get device information for debugging (non-sensitive)"""
        return {
            'device_id': self._get_device_id(),
            'state_file': STATE_FILE,
            'has_encryption_key': self._encryption_key is not None,
            'sensitive_keys': list(SENSITIVE_KEYS)
        }


# Create global instance for backward compatibility
_secure_state_manager = SecureStateManager()

# Backward compatible functions
def set_state(state_name: str, value: any):
    """Backward compatible state setter"""
    return _secure_state_manager.set_state(state_name, value)

def get_state(state_name: str) -> any:
    """Backward compatible state getter"""
    return _secure_state_manager.get_state(state_name)

# New secure functions
def set_secure_state(state_name: str, value: any):
    """Set state with forced encryption"""
    return _secure_state_manager.set_state(state_name, value, force_encrypt=True)

def clear_sensitive_data():
    """Clear all sensitive data"""
    return _secure_state_manager.clear_sensitive_data()

def get_device_info():
    """Get device information for debugging"""
    return _secure_state_manager.get_device_info() 