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
    todo: differentiate between 5G and LTE speeds
    todo: if there's less than a 10% variance of dl use upload then best RSRP value
    todo: create a logging webhook in powerautomate to track progress
    todo: create a local webpage for techs 
"""

from csclient import EventingCSClient
from speedtest import Speedtest
import time
import re
import datetime


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
    MIN_DOWNLOAD_SPD = {'5G':30.0,'LTE':10.0} # Mbps
    MIN_UPLOAD_SPD = {'5G':2.0,'LTE':1.0}  # Mbps
    SCHEDULE = 0  # Run SimSelector every {SCHEDULE} minutes. 0 = Only run on boot.
    NUM_ACTIVE_SIMS = 1  # Number of fastest (download) SIMs to keep active.  0 = all; do not disable SIMs
    ONLY_RUN_ONCE = False  # True means do not run if SimSelector has been run on this device before.

    APP_NAME = "SimSelector 2.5.0"

    STATUS_DEVS_PATH = '/status/wan/devices'
    CFG_RULES2_PATH = '/config/wan/rules2'
    CTRL_WAN_DEVS_PATH = '/control/wan/devices'
    API_URL = 'https://www.cradlepointecm.com/api/v2'
    CONNECTION_STATE_TIMEOUT = 7 * 60  # 7 Min
    NETPERF_TIMEOUT = 5 * 60  # 5 Min
    low_speed = False
    sims = {}
    wan_devs = {}
    rules_map = {}
    isRunning = False

    ADV_APN = {"custom_apns": 
            [ 
                {"carrier": "310030", "apn": "11200.mcs"},
                {"carrier": "310170", "apn": "ComcastMES5G"},
                {"carrier": "310030", "apn": "contingent.net"},
                {"carrier": "311882", "apn": "iot.tmowholesale.static"},
                {"carrier": "311882", "apn": "iot.tmowholesale"},
                {"carrier": "311480", "apn": "mw01.vzwstatic"},
                {"carrier": "311480", "apn": "we01.vzwstatic"}
            ]
        }

    APN_LIST = {
        'att': [
            {
                'match': '/diagnostics/ICCID',
                'regex':'/(?>^.{4})(?:.{3})?170/gm',
                'env': 'pod1',
                'apn':'ComcastMES5G'
            },
            {
                'match': '/diagnostics/ICCID',
                'regex':'/(?>^.{4})(?:.{3})?030/gm',
                'env': 'pod11/19',
                'apn':'11200.mcs'
            }
        ],
        'vzw': [
            {
                'match': '/diagnostics/CARRID',
                'regex':'Verizon',
                'env': 'Thingspace',
                'apn': 'mw01.vzwstatic'
            }
        ],
        'tmo': [
                {
                'match':'/diagnostics/CARRID',
                'regex':'T-Mobile',
                'env': 'Netcracker Wholesale',
                'apn':'iot.tmowholesale.static'
                }
        ]
    }
    def __init__(self):
        self.client = EventingCSClient('SimSelector')
        self.speedtest = Speedtest()

    def check_if_run_before(self, raise_err = True):
        """Check if SimSelector has been run before and return boolean."""

        if self.ONLY_RUN_ONCE:
            if self.client.get('config/system/snmp/persisted_config') == f'{self.APP_NAME}':
                self.client.log(
                    f'{self.APP_NAME} has been run before!')
                if test_only:
                    raise RunBefore(
                        f'ERROR - {self.APP_NAME} has been run before!')
                else:
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
        if cp.get('/config/wan/dual_sim_disable_mask') != '':
            self.send_update('Resetting Dual Sim Mask')
            cp.put("/config/wan/dual_sim_disable_mask","")
        if cp.get('/config/wan/rem_dual_sim_disable_mask') != '':
            self.send_update('Resetting Remote Dual Sim Mask')
            cp.put("/config/wan/rem_dual_sim_disable_mask","")
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
                    isNone = self.sims[dev_UID]["rule_id"] == None
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
                                    config = {'priority':1.1,'trigger_name':'','trigger_string':''}
                                else:
                                    if not isNone:
                                        self.client.log(f'Detatching Duplicate Rules')
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
                    self.client.log(f'Exception: {e}')
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
            self.client.log(f'Waiting for {self.port_sim(sim)} to connect.  Current State={conn_state}. timeout in {self.CONNECTION_STATE_TIMEOUT-timeout_counter}')
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

    def do_speedtest(self, sim):
        """Run Ookla speedtests and return TCP down and TCP up in Mbps."""
        servers = []
        self.speedtest.get_servers(servers)
        self.speedtest.get_best_server()
        self.client.log(f'Running TCP Download test on {sim}...')
        self.speedtest.download()
        self.client.log(f'Running TCP Upload test on {sim}...')
        self.speedtest.upload(pre_allocate=False)
        down = self.speedtest.results.download / 1000 / 1000
        up = self.speedtest.results.upload / 1000 / 1000
        self.client.log(f'Speedtest complete for {sim}.')
        if up != None and down != None:
            return down, up
        else:
            return self.do_speedtest(sim)

    def send_update (self,message):

        cp.log(f'{self.APP_NAME}: {message}')
        cp.alert(f'{self.APP_NAME}: {message}')
        cp.put('config/system/desc', f'{self.APP_NAME}: {message}'[:1023])
    
    def clear_apn(self,sims):
        for sim in sims:
            item = cp.get(f'/config/wan/rules2/{sim}')
            if "manual_apn" in item.get("modem",{}) or "apn_mode" in item.get("modem",{}):
                if item['modem'].get("manual_apn", "") == "":
                    cp.delete(f'/config/wan/rules2/{sim}/modem/apn_mode')
                    cp.delete(f'/config/wan/rules2/{sim}/modem/manual_apn')
                    if "modem" in cp.get(f'/config/wan/rules2/{sim}') and cp.get(f'/config/wan/rules2/{sim}/modem') == {}:
                        cp.delete(f'/config/wan/rules2/{sim}/modem')
                    self.send_update(f'APN Mode Updated on Rule Id: {item["_id_"]}. Group configuration might require updates.')
                elif item['modem'].get("manual_apn", "") != "":
                    cp.put(f'/config/wan/rules2/{sim}/modem/manual_apn',"")
                    self.send_update(f'Manual APN has been cleared on Rule Id: {item["_id_"]}. Group configuration might require updates.')

    def check_manual(self):
        dev_manual = []
        rules = cp.get('/config/wan/rules2')
        for item in rules:
            if "manual_apn" in item.get("modem", {}):
                dev_manual.append(item["_id_"])
            elif "apn_mode" in item.get("modem",{}):
                if item["modem"].get("apn_mode", "") == "manual":
                    dev_manual.append(item["_id_"])
        return dev_manual

    def update_custom(self,new_customs):
        cp.put('/config/wan/custom_apns',new_customs)
        self.send_update('Custom APNs were updated')

    def check_custom(self):
        dev_apns = cp.get('/config/wan/custom_apns') or {}
        if dev_apns == {}:
            try:
                cp.put('/config/wan/custom_apns',self.ADV_APN.get('custom_apns',{}))    
                return
            except:
                pass
        new_apns = dev_apns + [item for item in self.ADV_APN.get('custom_apns',{}) if item not in dev_apns]
        dirty_flag = len(new_apns) != len(dev_apns) + len(self.ADV_APN.get('custom_apns',{})) and new_apns != dev_apns
        return new_apns, dirty_flag

    def check_apn(self):
        new_customs, isDirty = self.check_custom(self)  
        if isDirty:
            self.update_custom(self, new_customs)
        found_manuals = self.check_manual(self)
        if len(found_manuals) > 0:
            self.clear_apn(self, found_manuals)
        


    def test_sim(self, device):
        """Get diagnostics, run speedtests, and verify minimums."""
        try:
            if self.modem_state(device, 'connected'):

                # Get diagnostics and log it
                diagnostics = self.client.get(f'{self.STATUS_DEVS_PATH}/{device}/diagnostics')
                self.sims[device]['diagnostics'] = diagnostics
                self.client.log(
                    f'Modem Diagnostics: {self.port_sim(device)} RSRP:{diagnostics.get("RSRP")}')

                # Do speedtest and log results
                self.sims[device]['download'], self.sims[device]['upload'] = self.do_speedtest(device)
                self.client.log(
                    f'Speedtest Results: {self.port_sim(device)} TCP Download: '
                    f'{self.sims[device]["download"]}Mbps TCP Upload: {self.sims[device]["upload"]}Mbps')

                # Verify minimum speeds
                #  if device is 5G use 5G speeds if not use LTE speeds
                if self.sims[device].get('download', 0.0) > self.MIN_DOWNLOAD_SPD and \
                        self.sims[device].get('upload', 0.0) > self.MIN_UPLOAD_SPD:
                    return True
                else:  # Did not meet minimums
                    self.client.log(f'{self.port_sim(device)} Failed to meet minimums! MIN_DOWNLOAD_SPD: {self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD: {self.MIN_UPLOAD_SPD}')
                    self.sims[device]['low-speed'] = True
                    return True
        except Timeout:
            message = f'Timed out running speedtest on {self.port_sim(device)}'
            self.client.log(message)
            self.client.alert(message)
            self.sims[device]['download'] = self.sims[device]['upload'] = 0.0
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
            self.client.log(e)
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
            self.client.log(f'New priority for {uid} = {new_priority}')
            self.client.put(f'config/wan/rules2/{rule_id}/priority', new_priority)
        return

    def set_all_rule_states (self, disable_val = False):
        wan_rules = cp.get('config/wan/rules2')
        for i, uid in enumerate(wan_rules):
            cp.put(f'config/wan/rules2/{i}/disabled', disable_val)
        time.sleep(5)

    def get_port(self, items, search):
        if items.get(search, None) is not None:
            return items[search].get('port', None)            
        return search
            

    def run(self):
        """Start of Main Application."""
        self.isRunning = True
        self.client.log(
            f'{self.APP_NAME} Starting... MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD} '
            f'SCHEDULE:{self.SCHEDULE} NUM_ACTIVE_SIMS:{self.NUM_ACTIVE_SIMS} ONLY_RUN_ONCE:{self.ONLY_RUN_ONCE}')

        self.check_if_run_before()

        self.wait_for_ncm_sync()

        # Get info from router
        product_name = self.client.get("/status/product_info/product_name")
        system_id = self.client.get("/config/system/system_id")
        router_id = self.client.get('status/ecm/client_id')

        # Send startup alert
        message = f'{self.APP_NAME} Starting! {system_id} - {product_name} - Router ID: {router_id}'
        self.client.log(f'Sending alert to NCM: {message}')
        self.client.alert(message)

        self.create_unique_WAN_profiles()

        # Pause for 3 seconds to allow NCM Alert to be sent before suspending NCM
        time.sleep(10)
        self.NCM_suspend()

        success = False  # SimSelector Success Status - Becomes True when a SIM meets minimum speeds
        self.low_speed = False
        # Test the connected SIM first
        primary_device = self.client.get('status/wan/primary_device')
        if 'mdm-' in primary_device:  # make sure its a modem
            if self.test_sim(primary_device):
                rule_id = self.client.get(f'status/wan/devices/{primary_device}/config/_id_')
                self.rules_map[rule_id] = {"uid": primary_device, "port": self.sims[primary_device]['port']}
                success = True

        # Disable all wan rules
        self.set_all_rule_states(True)

        # test remaining SIMs
        for sim in self.sims:
            if not self.sims[sim].get('download'):
                rule_id = self.client.get(f'status/wan/devices/{sim}/config/_id_')
                if rule_id is not None:
                    self.client.put(f'config/wan/rules2/{rule_id}/disabled', False)
                else:
                    self.set_all_rule_states(False)
                    self.run()
                    break
                if self.test_sim(sim):
                    rule_id = self.client.get(f'status/wan/devices/{sim}/config/_id_')
                    self.rules_map[rule_id] = {"uid": sim, "port": self.sims[sim]['port']}
                    success = True
                self.client.put(f'config/wan/rules2/{rule_id}/disabled', True)

        # Prioritizes SIMs based on download speed
        sorted_results = sorted(self.sims, key=lambda x: (self.sims[x]['upload'], self.sims[x]['download']) if self.sims[x]['low-speed'] else (self.sims[x]['download'], self.sims[x]['upload']), reverse=True)

        # Configure WAN Profiles
        self.client.log(f'Prioritizing SIMs: {sorted_results}')
        self.prioritize_rules(sorted_results)

        # Enable highest priority wan rules for each port
        wan_rules = self.client.get('config/wan/rules2')
        sorted_wan_rules = sorted(wan_rules, key=lambda x: x['priority'], reverse=False)
        selected_ports = []
        for i, uid in enumerate(sorted_wan_rules):
            sim_items = self.rules_map
            rule_id = uid.get('_id_')
            curr_port = self.get_port(self.rules_map,rule_id)
            disable_val = curr_port not in selected_ports
            if disable_val:
                selected_ports.append(curr_port)
            self.client.put(f'config/wan/rules2/{rule_id}/disabled', not disable_val)
        time.sleep(3)

        # Build results text
        results_text = datetime.datetime.now().strftime('%m/%d/%y %H:%M:%S')  # Start with a timestamp
        if not success:
            results_text += f' FAILED TO MEET MINIMUMS! MIN_DOWNLOAD_SPD:{self.MIN_DOWNLOAD_SPD} MIN_UPLOAD_SPD:{self.MIN_UPLOAD_SPD}'
        for uid in sorted_results:  # Add the results of each SIM with the fields specified:
            results_text = ' | '.join(
                [results_text, self.create_message(uid, 'PRD', 'HOMECARRID', 'RFBAND', 'RSRP', 'download', 'upload')])

        # put results to description field
        self.client.put('config/system/desc', results_text[:1023])

        # Mark as RUN for ONLY_RUN_ONCE flag
        self.client.put('config/system/snmp/persisted_config', f'{self.APP_NAME}')

        # Complete!  Send results.
        message = f"{self.APP_NAME} Complete! {system_id} Results: {results_text}"
        self.wait_for_ncm_sync()
        self.client.log(message)
        self.client.alert(message)
        self.isRunning = False


def manual_test(path, desc, *args):
    """Callback function for triggering manual tests."""
    # if desc is blank and first run, or starts with APP_NAME or contains "start" (case insensitive)
    if "start" in f'{desc.lower()}':
        try:
            devUptime = simselector.client.get('status/system/uptime')
            if not simselector.isRunning and ( devUptime >= 15*60):
                simselector.run()
        except Exception as e:
            simselector.isRunning=False
            simselector.set_all_rule_states(False)
            simselector.client.log(f"Failed with exception={type(e)} err={str(e)}")
            
        finally:
            simselector.client.put('/control/ecm', {'start': 'true'})


if __name__ == '__main__':
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
            SimSelector.check_apn(SimSelector)
            simselector = SimSelector()
            break
        except Exception as err0:
            cp.log('Error getting http://www.speedtest.net/speedtest-config.php - will try again in 5 seconds.')
            time.sleep(5)
            SimSelector.check_apn(SimSelector)


    try:
        # Setup callback for manual testing:
        simselector.client.on('put', '/config/system/desc', manual_test)

        # RUN SIMSELECTOR:
        desc = simselector.client.get('/config/system/desc')
        manual_test(None, desc)

        # Sleep forever / wait for manual tests:
        while True:
            time.sleep(1)
    except Exception as err:
        simselector.client.log(f"Failed with exception={type(err)} err={str(err)}")
