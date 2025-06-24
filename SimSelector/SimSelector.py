""" SimSelector is a Cradlepoint SDK Application used to choose the best SIM on install.
The application detects SIMs, and ensures (clones) they have unique WAN profiles for prioritization.
Then the app collects diagnostics and runs Ookla speedtests on each SIM.
Then the app prioritizes the SIMs WAN Profiles by TCP download speed.
Results are written to the log, set as the description field, and sent as a custom alert.
The app can be manually triggered again by clearing out the description field in NCM."""

"""
    todo: only 1 sim found time out notify for next steps
    todone: will not run on blank description unless it's the first time running
    todone: min up and down enforcement
    todone: differentiate between 5G and LTE speeds
    todo: if there's less than a 10% variance of dl use upload then best RSRP value
    todo: create a logging webhook in powerautomate to track progress
    todo: create a local webpage for techs
"""

import configparser
import datetime
import os
import sys
import time
import state_manager
from csclient import EventingCSClient
from speedtest import Speedtest


class SimSelectorException(Exception):
    """General SimSelector Exception."""
    pass


class Timeout(SimSelectorException):
    """Timeout Exception."""
    pass


class OneModem(SimSelectorException):
    """Only One Modem Found Exception."""
    pass


class RunBefore(SimSelectorException):
    """SimSelector has already been run before Exception."""
    pass


class SimSelector(object):
    """Main Application."""
    MIN_DOWNLOAD_SPD = {'5G': 30.0, 'lte/3g': 10.0}  # Mbps - need to confirm tech response for w1850
    MIN_UPLOAD_SPD = {'5G': 2.0, 'lte/3g': 1.0}  # Mbps -  need to confirm tech response for w1850
    SCHEDULE = 0  # Run SimSelector every {SCHEDULE} minutes. 0 = Only run on boot.
    NUM_ACTIVE_SIMS = 1  # Number of fastest (download) SIMs to keep active.  0 = all; do not disable SIMs
    ONLY_RUN_ONCE = False  # True means do not run if SimSelector has been run on this device before.

    APP_NAME = "SimSelector 2.5.9"

    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    API_URL = 'https://www.cradlepointecm.com/api/v2'
    CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 Min
    NETPERF_TIMEOUT = 5 * 60  # 5 Min
    sims = {}
    wan_devs = {}
    rules_map = {}
    isRunning = False
    staging = False
    pending_updates = []

    ADV_APN = {"custom_apns": [
                   {"carrier": "310030", "apn": "11200.mcs"},
                   {"carrier": "310170", "apn": "ComcastMES5G"},
                   {"carrier": "310030", "apn": "contingent.net"},
                   {"carrier": "311882", "apn": "iot.tmowholesale.static"},
                   {"carrier": "311480", "apn": "mw01.vzwstatic"},
                   {"carrier": "311480", "apn": "we01.vzwstatic"}
               ]}

    def __init__(self):
        global DYN_APP_NAME
        self.client = EventingCSClient('SimSelector')
        
        # Initialize speedtest with proper error handling
        try:
            # Ensure we have internet connectivity before initializing speedtest
            self._wait_for_internet_connectivity()
            self.speedtest = Speedtest()
            self.client.log("Speedtest library initialized successfully")
        except Exception as e:
            self.client.log(f"Warning: Speedtest initialization failed: {e}")
            self.client.log("Will retry speedtest initialization when needed")
            self.speedtest = None
        
        DYN_APP_NAME = get_app_version()
        self.APP_NAME = DYN_APP_NAME

    def _wait_for_internet_connectivity(self, timeout=60):
        """Wait for internet connectivity before initializing speedtest."""
        import socket
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to connect to Ookla's speedtest server
                socket.create_connection(("www.speedtest.net", 80), timeout=5)
                self.client.log("Internet connectivity confirmed for speedtest")
                return True
            except (socket.error, OSError):
                self.client.log("Waiting for internet connectivity...")
                time.sleep(2)
        
        raise Exception("Internet connectivity timeout - cannot initialize speedtest")

    def _ensure_speedtest_ready(self):
        """Ensure speedtest is initialized and ready for use."""
        if self.speedtest is None:
            try:
                self._wait_for_internet_connectivity()
                self.speedtest = Speedtest()
                self.client.log("Speedtest library initialized on demand")
            except Exception as e:
                self.client.log(f"Failed to initialize speedtest: {e}")
                raise Exception(f"Speedtest unavailable: {e}")
        return self.speedtest

    def check_if_run_before(self, raise_err=True):
        """Check if SimSelector has been run before and return boolean."""

        if self.ONLY_RUN_ONCE:
            if self.client.get('config/system/snmp/persisted_config') == f'{self.APP_NAME}':
                self.client.log(f'{self.APP_NAME} has been run before!')
                # if test_only:  # This variable is undefined, commenting out
                #     raise RunBefore(f'ERROR - {self.APP_NAME} has been run before!')
                # else:
                return True
        return False

    def wait_for_ncm_sync(self):
        """Blocking call to wait until WAN is connected, and NCM is connected and synced."""
        # WAN connection_state
        if self.client.get('status/wan/connection_state') != 'connected':
            self.client.log('Waiting until WAN is connected...')
        timeout_count = self.CONNECTION_STATE_TIMEOUT
        while self.client.get('/status/wan/connection_state') != 'connected':
            timeout_count -= 2
            if not timeout_count:
                raise Timeout('WAN not connecting')
            time.sleep(2)

        # ECM State
        if self.client.get('status/ecm/state') != 'connected':
            self.client.log('Waiting until NCM is connected...')
            self.client.put('/control/ecm', {'start': True})
        timeout_count = self.CONNECTION_STATE_TIMEOUT
        while self.client.get('/status/ecm/state') != 'connected':
            timeout_count -= 2
            if not timeout_count:
                raise Timeout('NCM not connecting')
            time.sleep(2)

        # ECM Sync
        if self.client.get('status/ecm/sync') != 'ready':
            self.client.log('Waiting until NCM is synced...')
            self.client.put('/control/ecm', {'start': True})
        timeout_count = self.CONNECTION_STATE_TIMEOUT
        while self.client.get('/status/ecm/sync') != 'ready':
            self.client.put('/control/ecm', {'start': True})
            timeout_count -= 2
            if not timeout_count:
                raise Timeout('NCM not syncing')
            time.sleep(2)
        return

    def NCM_suspend(self):
        """Blocking call to wait until NCM synced, then stopped."""
        self.client.log('Stopping NCM')
        timeout_count = 500
        while not 'ready' == self.client.get('/status/ecm/sync'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM sync not ready')
            time.sleep(2)
        self.client.put('/control/ecm', {'stop': True})
        timeout_count = 500
        while not 'stopped' == self.client.get('/status/ecm/state'):
            timeout_count -= 1
            if not timeout_count:
                raise Timeout('NCM not stopping')
            time.sleep(2)

    def find_sims(self):
        """Detects all available SIMs in router and stores in self.sims."""
        timeout = 0
        while True:
            sims = {}
            wan_devs = self.client.get(self.STATUS_DEVS_PATH) or {}
            for uid, status in wan_devs.items():
                if uid.startswith('mdm-'):
                    error_text = status.get('status', {}).get('error_text', '')
                    if error_text:
                        if 'NOSIM' in error_text:
                            continue
                    sims[uid] = status
            num_sims = len(sims)
            if not num_sims:
                self.client.log('No SIMs found at all yet')
                self.reset_dsdm()
            if num_sims < 2:
                self.client.log('Only 1 SIM found!')
                self.reset_dsdm()
            if timeout >= 10:
                self.send_update('Timeout: Did not find 2 or more SIMs')
                self.reset_dsdm()
                raise Timeout('Did not find 2 or more SIMs')
            if num_sims >= 2:
                break
            time.sleep(10)
            timeout += 1

        self.client.log(f'Found SIMs: {sims.keys()}')
        self.sims = sims
        self.wan_devs = wan_devs
        return True

    def reset_dsdm(self):
        int_dsdm = self.client.get('/config/wan/dual_sim_disable_mask')
        rem_dsdm = self.client.get('/config/wan/rem_dual_sim_disable_mask')
        if int_dsdm is not None and int_dsdm != '':
            self.send_update('Resetting Dual Sim Mask')
            self.client.put("/config/wan/dual_sim_disable_mask", "")
        if rem_dsdm is not None and rem_dsdm != '':
            self.send_update('Resetting Remote Dual Sim Mask')
            self.client.put("/config/wan/rem_dual_sim_disable_mask", "")
        time.sleep(5)

    def create_unique_WAN_profiles(self):
        """Ensures that each modem has a unique WAN profile (rule) for prioritization."""
        repeat = True
        while repeat:
            self.find_sims()
            for dev_UID, dev_status in self.sims.items():
                try:
                    self.sims[dev_UID]["rule_id"] = dev_status.get('config', {}).get('_id_')
                    self.sims[dev_UID]["priority"] = float(dev_status.get('config', {}).get('priority'))
                    self.sims[dev_UID]["port"] = dev_status.get('info', {}).get('port')
                    self.sims[dev_UID]["sim"] = dev_status.get('info', {}).get('sim')
                    i = 0.1
                    found_self = False
                    isNone = self.sims[dev_UID]["rule_id"] is None
                    repeat = False
                    for dev, stat in self.sims.items():
                        if stat.get('config', {}).get('_id_') == self.sims[dev_UID]["rule_id"]:
                            if not found_self and not isNone:
                                found_self = True
                            else:  # Two SIMs using same WAN profile
                                config = self.client.get(
                                    f'config/wan/rules2/'
                                    f'{self.sims[dev_UID]["rule_id"]}')
                                if not config:
                                    config = {'priority': 1.1, 'trigger_name': '', 'trigger_string': ''}
                                else:
                                    if not isNone:
                                        self.client.log('Detatching Duplicate Rules')
                                        config.pop('_id_')
                                config['priority'] += i
                                i += 0.1
                                config['trigger_name'] = f'{stat["info"]["port"]} {stat["info"]["sim"]}'
                                config['trigger_string'] = \
                                    f'type|is|mdm%sim|is|{stat["info"]["sim"]}%port|is|{stat["info"]["port"]}'
                                self.client.log(f'NEW WAN RULE: {config}')
                                rule_index = self.client.post('config/wan/rules2/', config)["data"]
                                new_id = self.client.get(f'config/wan/rules2/{rule_index}/_id_')
                                self.sims[dev_UID]["config"]["_id_"] = new_id
                                repeat = True
                except Exception as e:
                    self.client.log(f'Exception: {e} trace: {sys.exc_info}')
                    continue

    def modem_state(self, sim, state):
        """Blocking call that will wait until a given state is shown as the modem's status."""
        timeout_counter = 0
        sleep_seconds = 0
        conn_path = '%s/%s/status/connection_state' % (self.STATUS_DEVS_PATH, sim)
        self.client.log(f'Connecting {self.port_sim(sim)}')
        while True:
            sleep_seconds += 5
            conn_state = self.client.get(conn_path)
            self.client.log(f'Waiting for {self.port_sim(sim)} to connect.  '
                            f'Current State={conn_state}. timeout in {self.CONNECTION_STATE_TIMEOUT-timeout_counter}')
            if conn_state == state:
                break
            if timeout_counter > self.CONNECTION_STATE_TIMEOUT:
                self.client.log(f'Timeout waiting on {self.port_sim(sim)}. Testing Alternate APNs')
                self.update_custom(sim)
                raise Timeout(conn_path)
            time.sleep(min(sleep_seconds, 45))
            timeout_counter += sleep_seconds
        self.client.log(f'{self.port_sim(sim)} connected.')
        return True

    def iface(self, sim):
        """Return iface value for sim."""
        iface = self.client.get('%s/%s/info/iface' % (self.STATUS_DEVS_PATH, sim))
        return iface

    def port_sim(self, sim):
        """Return port value for sim."""
        return f'{self.sims[sim]["info"]["port"]} {self.sims[sim]["info"]["sim"]}'

    def do_speedtest(self, sim, staging):
        """Run Ookla speedtests and return TCP down and TCP up in Mbps."""
        servers = []
        self._ensure_speedtest_ready().get_servers(servers)
        self._ensure_speedtest_ready().get_best_server()
        self.client.log(f'Running TCP Download test on {sim}...')
        self._ensure_speedtest_ready().download()
        self.client.log(f'Running TCP Upload test on {sim}...')
        self._ensure_speedtest_ready().upload(pre_allocate=False)
        down = self._ensure_speedtest_ready().results.download / 1000 / 1000
        up = self._ensure_speedtest_ready().results.upload / 1000 / 1000
        self.client.log(f'Speedtest complete for {sim}.')
        if up is not None and down is not None:
            return down, up
        else:
            return self.do_speedtest(sim)
    
    def send_update(self, message, level=7):
        """
        Sends an update to the log, as an alert, and to the description field.
        Caches messages if NCM is not connected, and flushes them when reconnected.
        level is a bitmask: 1=log, 2=alert, 4=description
        """
        if self.client.get('status/ecm/state') == 'connected':
            if self.pending_updates:
                self.client.log(f"Flushing {len(self.pending_updates)} cached messages.")
                # Process from oldest to newest to maintain order
                for update in reversed(self.pending_updates):
                    if update['level'] & 1:
                        self.client.log(f'[OFFLINE] {self.APP_NAME}: {update["message"]}')
                    if update['level'] & 2:
                        self.client.alert(f'[OFFLINE] {self.APP_NAME}: {update["message"]}')
                    if update['level'] & 4:
                        self.client.put('/config/system/desc', f'[OFFLINE] {self.APP_NAME}: {update["message"]}'[:1023])
                self.pending_updates = []

            if level & 1:
                self.client.log(f'{self.APP_NAME}: {message}')
            if level & 2:
                self.client.alert(f'{self.APP_NAME}: {message}')
            if level & 4:
                self.client.put('/config/system/desc', f'{self.APP_NAME}: {message}'[:1023])
        else:
            self.client.log(f"ECM not connected. Caching update: {message}")
            current_time = datetime.datetime.now()
            time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            self.pending_updates.insert(0, {"level": level, "message": f"{time_str}:: {message}"})

    def clear_apn(self, sims):
        for sim in sims:
            item = self.client.get(f'/config/wan/rules2/{sim}')
            if "manual_apn" in item.get("modem", {}) or "apn_mode" in item.get("modem", {}):
                if item['modem'].get("manual_apn", "") == "":
                    self.client.delete(f'/config/wan/rules2/{sim}/modem/apn_mode')
                    self.client.delete(f'/config/wan/rules2/{sim}/modem/manual_apn')
                    if ("modem" in self.client.get(f'/config/wan/rules2/{sim}') and 
                            self.client.get(f'/config/wan/rules2/{sim}/modem') == {}):
                        self.client.delete(f'/config/wan/rules2/{sim}/modem')
                    self.send_update(f'APN Mode Updated on Rule Id: {item["_id_"]}. '
                                     f'Group configuration might require updates.')
                elif item['modem'].get("manual_apn", "") != "":
                    self.client.put(f'/config/wan/rules2/{sim}/modem/manual_apn', "")
                    self.send_update(f'Manual APN has been cleared on Rule Id: {item["_id_"]}. '
                                     f'Group configuration might require updates.')

    def check_manual(self):
        dev_manual = []
        rules = self.client.get('/config/wan/rules2')
        for item in rules:
            if "manual_apn" in item.get("modem", {}):
                dev_manual.append(item["_id_"])
            elif "apn_mode" in item.get("modem", {}):
                if item["modem"].get("apn_mode", "") == "manual":
                    dev_manual.append(item["_id_"])
        return dev_manual

    def update_custom(self, new_customs):
        self.client.put('/config/wan/custom_apns', new_customs)
        self.send_update('Custom APNs were updated')

    def check_custom(self):
        dev_apns = self.client.get('/config/wan/custom_apns') or {}
        if dev_apns == {}:
            try:
                self.client.put('/config/wan/custom_apns', self.ADV_APN.get('custom_apns', {}))
                return
            except Exception:
                pass
        new_apns = dev_apns + [item for item in self.ADV_APN.get('custom_apns', {}) if item not in dev_apns]
        dirty_flag = len(new_apns) != len(dev_apns) + len(self.ADV_APN.get('custom_apns', {})) and new_apns != dev_apns
        return new_apns, dirty_flag

    def check_apn(self):
        new_customs, isDirty = self.check_custom()
        if isDirty:
            self.update_custom(new_customs)
        found_manuals = self.check_manual()
        if len(found_manuals) > 0:
            self.clear_apn(found_manuals)
        

    def test_sim(self, device, staging=False):
        """Get diagnostics, run speedtests, and verify minimums."""
        try:
            if self.modem_state(device, 'connected'):
                self.sims[device]['OK'] = True
                # Get diagnostics and log it
                diagnostics = self.client.get(f'{self.STATUS_DEVS_PATH}/{device}/diagnostics')
                self.sims[device]['diagnostics'] = diagnostics
                self.send_update(
                    f'Modem Diagnostics: {self.port_sim(device)} RSRP:{diagnostics.get("RSRP")}', 1)

                # Do speedtest and log results
                if not staging:
                    self.sims[device]['download'], self.sims[device]['upload'] = self.do_speedtest(device)
                    self.send_update(
                        f'Speedtest Results: {self.port_sim(device)} TCP Download: '
                        f'{self.sims[device]["download"]}Mbps TCP Upload: {self.sims[device]["upload"]}Mbps', 1)

                tech = self.sims[device]['info'].get('tech', "LTE")
                # Verify minimum speeds
                #  if device is 5G use 5G speeds if not use LTE speeds
                if self.sims[device].get('download', 0.0) > self.MIN_DOWNLOAD_SPD.get(tech, 10) and \
                        self.sims[device].get('upload', 0.0) > self.MIN_UPLOAD_SPD.get(tech, 1):
                    self.sims[device]['low-speed'] = False
                    return True
                elif not staging:  # Did not meet minimums
                    self.send_update(f'{self.port_sim(device)} Failed to meet minimums! '
                                     f'MIN_DOWNLOAD_SPD: {self.MIN_DOWNLOAD_SPD} '
                                     f'MIN_UPLOAD_SPD: {self.MIN_UPLOAD_SPD}', 1)
                    self.sims[device]['low-speed'] = True
                    return True

        except Timeout:
            message = f'Timed out running speedtest on {self.port_sim(device)}'
            self.send_update(message, 7)
            self.sims[device]['download'] = self.sims[device]['upload'] = 0.0
            self.sims[device]['OK'] = False
            return False

    def create_message(self, uid, *args):
        """Create text results message for log, alert, and description."""
        message = ''
        try:
            for arg in args:
                if arg == 'download':
                    message = "DL:{:.2f}Mbps".format(self.sims[uid]['download']) if not message else ' '.join(
                        [message, "DL:{:.2f}Mbps".format(self.sims[uid]['download'])])
                elif arg == 'upload':
                    message = "UL:{:.2f}Mbps".format(self.sims[uid]['upload']) if not message else ' '.join(
                        [message, "UL:{:.2f}Mbps".format(self.sims[uid]['upload'])])
                elif arg in ['PRD', 'HOMECARRID', 'RFBAND']:  # Do not include labels for these fields
                    message = "{}".format(self.sims[uid]['diagnostics'].get(arg)) if not message else ' '.join(
                        [message, "{}".format(self.sims[uid]['diagnostics'].get(arg))])
                else:  # Include field labels (e.g. "RSRP:-82")
                    message = "{}:{}".format(arg, self.sims[uid]['diagnostics'].get(arg)) if not message else ' '.join(
                        [message, "{}:{}".format(arg, self.sims[uid]['diagnostics'].get(arg))])
        except Exception as e:
            self.send_update({"e": e, "info": sys.exc_info}, 1)
        return message

    def prioritize_rules(self, sim_list):
        """Re-prioritize WAN rules by TCP download speed."""
        lowest_priority = 100
        for uid in sim_list:
            priority = self.client.get(f'status/wan/devices/{uid}/config/priority')
            if priority < lowest_priority:
                lowest_priority = priority
        for i, uid in enumerate(sim_list):
            rule_id = self.client.get(f'status/wan/devices/{uid}/config/_id_')
            new_priority = lowest_priority + i * .1
            self.send_update(f'New priority for {uid} = {new_priority}', 1)
            self.client.put(f'config/wan/rules2/{rule_id}/priority', new_priority)
        return

    def set_all_rule_states(self, disable_val=False):
        wan_rules = self.client.get('config/wan/rules2')
        for i, uid in enumerate(wan_rules):
            self.client.put(f'config/wan/rules2/{i}/disabled', disable_val)
        time.sleep(5)

    def get_port(self, items, search):
        """Return port value for the given search key from items dict."""
        if items.get(search, None) is not None:
            return items[search].get('port', None)            
        return search

    def classify_signal(self, rsrp):
        """Classifies RSRP value as Good, Weak, or Bad."""
        if rsrp is None:
            return "Unknown"
        if rsrp > -90:
            return "Good"
        if -105 <= rsrp <= -90:
            return "Weak"
        return "Bad"

    def run(self):
        """Start of Main Application."""
        pass  # This is now deprecated and replaced by the two-phase workflow


def manual_test(path, desc, *args):
    """Callback function for triggering manual tests."""
    # if desc is blank and first run, or starts with APP_NAME or contains "start" (case insensitive)
    simselector.client.put('/config/system/asset_id', f'{SimSelector.APP_NAME} Enabled')
    if desc is None:
        return
    
    desc_lower = desc.lower()
    
    # Handle reset command - restart from validation phase
    if "reset" in desc_lower:
        try:
            state_manager.set_state('phase', 'validation')
            simselector.send_update("State reset to validation phase. Restart device to begin fresh validation.", 7)
            return
        except Exception as e:
            simselector.send_update(f"Failed to reset state: {type(e)} err={str(e)}", 7)
            return
    
    # Handle force or start commands
    if "start" in desc_lower or "force" in desc_lower:
        try:
            devUptime = simselector.client.get('status/system/uptime')
            
            # Force command bypasses uptime check and runs current phase
            if "force" in desc_lower:
                phase = state_manager.get_state('phase') or 'validation'
                simselector.client.log(f"Force command received. Running {phase} phase...")
                
                if phase == 'validation':
                    run_validation_phase()
                elif phase == 'performance':
                    run_performance_phase()
                else:
                    simselector.send_update("SimSelector has already completed. Use 'reset' to restart.", 7)
                    
            elif not simselector.isRunning and devUptime <= 5*60:
                # Normal start command within uptime window
                phase = state_manager.get_state('phase') or 'validation'
                simselector.client.log(f"Start command received. Running {phase} phase...")
                
                if phase == 'validation':
                    run_validation_phase()
                elif phase == 'performance':
                    run_performance_phase()
                else:
                    simselector.send_update("SimSelector has already completed.", 7)
            else:
                simselector.send_update("Uptime is over 5 minutes, Restart router to run script, "
                                        "Clear this description field to cancel, or use 'force' to override.")
        except Exception as e:
            # traceback.print_stack()
            simselector.isRunning = False
            simselector.set_all_rule_states(False)
            simselector.send_update(f"Failed with exception={type(e)} err={str(e)}", 7)

        finally:
            simselector.client.put('/control/ecm', {'start': 'true'})
            # simselector.send_update('Updating all pending messages', 0)


@staticmethod
def get_app_version(create_new_uuid=False):
    """Get app version from package.ini file."""
    global g_app_uuid
    global g_app_name
    global g_app_version

    g_app_name = "SimSelector"

    uuid_key = 'uuid'
    # app_key = "app_name"  # Unused variable
    major_key = "version_major"
    minor_key = "version_minor"
    patch_key = "version_patch"

    app_config_file = os.path.join(g_app_name, 'package.ini')
    config = configparser.ConfigParser()
    config.read(app_config_file)
    if g_app_name in config:
        if uuid_key in config[g_app_name]:
            g_app_uuid = config[g_app_name][uuid_key]
            g_app_version = f"v{config[g_app_name][major_key]}.{config[g_app_name][minor_key]}." \
                            f"{config[g_app_name][patch_key]}"
            return f"{g_app_name} {g_app_version}"
        else:
            print('ERROR: The uuid key does not exist in {}'.format(app_config_file))
    else:
        print('ERROR: The APP_NAME section does not exist in {}'.format(app_config_file))

def find_string_in_text(text, strings, index=0):
    # Base case: If index reaches the length of the strings array, return False
    if index == len(strings):
        return False
    
    # Check if the current string in the array is in the text
    if strings[index] in text:
        return True
    
    # Recurse to the next string in the array
    return find_string_in_text(text, strings, index + 1)

def run_validation_phase():
    """
    Phase 1: Validates SIMs and checks signal strength.
    """
    global simselector
    simselector.client.log("Executing Validation/Staging Phase...")

    # Check uptime. Only run validation within the first 5 minutes.
    uptime = simselector.client.get('status/system/uptime')
    if uptime > 5 * 60:
        simselector.client.log("Device uptime is greater than 5 minutes. Skipping validation phase.")
        return

    simselector.create_unique_WAN_profiles()
    time.sleep(10)
    simselector.NCM_suspend()

    # Disable all wan rules so we can test them one by one
    simselector.set_all_rule_states(True)

    for sim in simselector.sims:
        rule_id = simselector.sims[sim].get("rule_id")
        if rule_id:
            # Enable this rule to test the SIM
            simselector.client.put(f'config/wan/rules2/{rule_id}/disabled', False)
            time.sleep(2)  # allow change to apply

            # test_sim in staging mode checks for connection and gets diagnostics
            if simselector.test_sim(sim, staging=True):
                # Classify and store signal quality
                diagnostics = simselector.sims[sim].get('diagnostics', {})
                rsrp = diagnostics.get('RSRP')
                signal_quality = simselector.classify_signal(rsrp)
                simselector.sims[sim]['signal_quality'] = signal_quality
                simselector.client.log(f"SIM {sim}: RSRP={rsrp}, Quality={signal_quality}")

            # Disable rule again to isolate the next test
            simselector.client.put(f'config/wan/rules2/{rule_id}/disabled', True)
        else:
            simselector.client.log(f"Could not find rule_id for {sim} during validation.")

    # Build the feedback string
    feedback_parts = []
    # Sort by port and then sim for consistent ordering
    sorted_sim_uids = sorted(simselector.sims.keys(),
                             key=lambda k: simselector.sims[k]['info']['port'] + simselector.sims[k]['info']['sim'])

    for sim_uid in sorted_sim_uids:
        sim_data = simselector.sims[sim_uid]
        port_name = simselector.port_sim(sim_uid)  # e.g. "MODEM1 SIM1"

        status = "Active" if sim_data.get('OK') else "Inactive"
        quality = sim_data.get('signal_quality', 'Unknown')
        
        part = f"{port_name}: {status}, {quality} Signal"
        if quality == "Bad":
            part += " (Check Antenna)"
        
        feedback_parts.append(part)
    
    feedback_string = "Staging - " + " | ".join(feedback_parts)
    simselector.client.log(f"Validation feedback string: {feedback_string}")
    simselector.send_update(feedback_string, level=7)
    
    # Set state to performance for the next boot
    state_manager.set_state('phase', 'performance')
    simselector.client.log("Validation phase complete. Set state to 'performance'.")

def run_performance_phase():
    """
    Phase 2: Runs speed tests and prioritizes SIMs.
    """
    global simselector
    simselector.client.log("Executing Performance/Run Phase...")
    
    # Most of the logic from the original `run` method goes here.
    # We can assume NCM is already suspended from the validation phase.

    success = False  # SimSelector Success Status

    # test remaining SIMs
    for sim in simselector.sims:
        if not simselector.sims[sim].get('OK'):
            rule_id = simselector.client.get(f'status/wan/devices/{sim}/config/_id_')
            if rule_id is not None:
                simselector.client.put(f'config/wan/rules2/{rule_id}/disabled', False)
            else:
                simselector.set_all_rule_states(False)
                # This indicates a problem, should probably restart the whole process.
                # For now, we'll log it and let it fail.
                simselector.client.log(f"ERROR: No rule_id for {sim}, cannot test.")
                continue

            if simselector.test_sim(sim, staging=False):
                success = True
            simselector.client.put(f'config/wan/rules2/{rule_id}/disabled', True)

    # Prioritizes SIMs based on advanced sorting logic from PRD
    def advanced_sort_key(sim_uid):
        sim_data = simselector.sims[sim_uid]
        download = sim_data.get('download', 0.0)
        upload = sim_data.get('upload', 0.0)
        rsrp = sim_data.get('diagnostics', {}).get('RSRP', -999)
        
        # If low-speed, prioritize by upload then download
        if sim_data.get('low-speed'):
            return (upload, download, rsrp)
        else:
            # Normal priority: download first, then upload, then RSRP
            return (download, upload, rsrp)
    
    sorted_results = sorted(simselector.sims.keys(), key=advanced_sort_key, reverse=True)
    
    # Apply advanced tie-breaking logic from PRD
    if len(sorted_results) > 1:
        # Check for 10% variance in download speeds among top performers
        top_sim = sorted_results[0]
        top_download = simselector.sims[top_sim].get('download', 0.0)
        
        # Group SIMs with download speeds within 10% of the top
        similar_download_sims = []
        for sim_uid in sorted_results:
            sim_download = simselector.sims[sim_uid].get('download', 0.0)
            if top_download == 0 or abs(sim_download - top_download) / top_download <= 0.1:
                similar_download_sims.append(sim_uid)
            else:
                break  # Since it's sorted, we can break here
        
        if len(similar_download_sims) > 1:
            # Apply secondary sort by upload speed
            top_upload = max(simselector.sims[sim].get('upload', 0.0) for sim in similar_download_sims)
            similar_upload_sims = []
            
            for sim_uid in similar_download_sims:
                sim_upload = simselector.sims[sim_uid].get('upload', 0.0)
                if top_upload == 0 or abs(sim_upload - top_upload) / top_upload <= 0.1:
                    similar_upload_sims.append(sim_uid)
            
            if len(similar_upload_sims) > 1:
                # Apply tertiary sort by RSRP (higher is better)
                similar_upload_sims.sort(key=lambda x: simselector.sims[x].get('diagnostics', {}).get('RSRP', -999), reverse=True)
                # Replace the beginning of sorted_results with the RSRP-sorted similar sims
                sorted_results = similar_upload_sims + [sim for sim in sorted_results if sim not in similar_upload_sims]
            else:
                # Replace the beginning of sorted_results with upload-sorted similar sims
                similar_download_sims.sort(key=lambda x: simselector.sims[x].get('upload', 0.0), reverse=True)
                sorted_results = similar_download_sims + [sim for sim in sorted_results if sim not in similar_download_sims]

    # Configure WAN Profiles
    simselector.send_update(f'Prioritizing SIMs: {sorted_results}', 7)
    simselector.prioritize_rules(sorted_results)

    # Enable highest priority wan rules for each port
    wan_rules = simselector.client.get('config/wan/rules2')
    sorted_wan_rules = sorted(wan_rules, key=lambda x: x['priority'], reverse=False)
    selected_ports = []
    for uid in sorted_wan_rules:
        rule_id = uid.get('_id_')
        curr_port = simselector.get_port(simselector.rules_map, rule_id)
        disable_val = curr_port not in selected_ports
        if disable_val:
            selected_ports.append(curr_port)
        simselector.client.put(f'config/wan/rules2/{rule_id}/disabled', not disable_val)
    time.sleep(3)

    # Build results text
    results_text = datetime.datetime.now().strftime('%m/%d/%y %H:%M:%S')  # Start with a timestamp
    if not success:
        results_text += f' FAILED TO MEET MINIMUMS! MIN_DOWNLOAD_SPD:{simselector.MIN_DOWNLOAD_SPD} ' \
                       f'MIN_UPLOAD_SPD:{simselector.MIN_UPLOAD_SPD}'
    for uid in sorted_results:  # Add the results of each SIM with the fields specified:
        results_text = ' | '.join([results_text,
                                   simselector.create_message(uid, 'PRD', 'HOMECARRID', 'RFBAND', 'RSRP',
                                                              'download', 'upload')])

    # put results to description field
    simselector.send_update(results_text[:1023], 7)

    # Mark as Complete
    state_manager.set_state('phase', 'complete')
    simselector.client.log("Performance phase complete. Set state to 'complete'.")

    # Resume NCM
    simselector.wait_for_ncm_sync()


# Keep track of global instances that the script logic relies on.
cp = None
simselector = None

def main():
    """Main execution block."""
    global cp, simselector
    cp = EventingCSClient('SimSelector')
    
    cp.log('Starting...')
    to = 100
    
    while not cp.get('status/wan/connection_state') == 'connected':
        time.sleep(1)
        to = to-1
        if to <= 0:
            SimSelector.set_all_rule_states(SimSelector, False)
            to = 100


    
    while True:
        try:
            simselector = SimSelector()
            break
        except Exception as err0:
            EventingCSClient('SimSelector').log('Error accessing speedtest config page - will try again in 5 seconds.')
            time.sleep(5)

    # Main phase logic
    phase = state_manager.get_state('phase') or 'validation'
    cp.log(f"Current phase: {phase}")

    if phase == 'validation':
        run_validation_phase()
    elif phase == 'performance':
        run_performance_phase()
    else: # phase == 'complete'
        cp.log('SimSelector has already completed.')

    cp.log("SimSelector script finished.")


if __name__ == '__main__':
    main()
