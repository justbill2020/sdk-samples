import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from SimSelector import SimSelector

class MockClient:
    def __init__(self):
        self.config_data = {'/config/wan/custom_apns': []}
        self.put_calls = []
    def get(self, path):
        if path == '/config/wan/custom_apns':
            return self.config_data['/config/wan/custom_apns']
        return None
    def put(self, path, data):
        self.put_calls.append((path, data))
        self.config_data[path] = data
        return True
    def log(self, msg):
        print(f"LOG: {msg}")
    def alert(self, msg):
        print(f"ALERT: {msg}")


def test_check_apn_adds_missing():
    simselector = SimSelector()
    simselector.client = MockClient()
    simselector.ADV_APN = {
        "custom_apns": [
            {"carrier": "310030", "apn": "11200.mcs"},
            {"carrier": "310030", "apn": "38335.mcs"},
            {"carrier": "310170", "apn": "ComcastMES5G"},
            {"carrier": "310030", "apn": "contingent.net"},
            {"carrier": "311882", "apn": "iot.tmowholesale.static"},
            {"carrier": "311480", "apn": "mw01.vzwstatic"},
            {"carrier": "311480", "apn": "we01.vzwstatic"}
        ]
    }
    # Start with only one APN present
    simselector.client.config_data['/config/wan/custom_apns'] = [
        {"carrier": "310030", "apn": "11200.mcs"}
    ]
    simselector.check_apn()
    updated_apns = simselector.client.config_data['/config/wan/custom_apns']
    required_apns = simselector.ADV_APN['custom_apns']
    for apn in required_apns:
        assert apn in updated_apns, f"Missing APN: {apn}"
    print("✅ test_check_apn_adds_missing passed.")


def test_check_apn_no_duplicates():
    simselector = SimSelector()
    simselector.client = MockClient()
    simselector.ADV_APN = {
        "custom_apns": [
            {"carrier": "310030", "apn": "11200.mcs"},
            {"carrier": "310170", "apn": "ComcastMES5G"}
        ]
    }
    # Start with all APNs present
    simselector.client.config_data['/config/wan/custom_apns'] = [
        {"carrier": "310030", "apn": "11200.mcs"},
        {"carrier": "310170", "apn": "ComcastMES5G"}
    ]
    simselector.check_apn()
    updated_apns = simselector.client.config_data['/config/wan/custom_apns']
    assert len(updated_apns) == 2, "Should not add duplicates"
    print("✅ test_check_apn_no_duplicates passed.")

if __name__ == "__main__":
    test_check_apn_adds_missing()
    test_check_apn_no_duplicates()
