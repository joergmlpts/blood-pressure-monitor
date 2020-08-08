#!/usr/bin/env python3

import asyncio, datetime, sys
from bleak import discover, BleakClient # install with 'pip install bleak'


########################################################
#                 Platform-specific Code               #
########################################################

if sys.platform == 'linux':
    import dbus
    # This Linux-specific function returns all the Bluetooth
    # devices that have been paired with this computer.
    def paired_bluetooth_devices():
        BUS_NAME          = "org.bluez"
        DEVICE_INTERFACE  = BUS_NAME + ".Device1"
        bus = dbus.SystemBus()
        try:
            object = bus.get_object(BUS_NAME, "/")
        except Exception as error:
            return
        manager = dbus.Interface(object, "org.freedesktop.DBus.ObjectManager")
        paired_devices = set()
        for path, ifaces in manager.GetManagedObjects().items():
            device = ifaces.get(DEVICE_INTERFACE)
            if device and device['Paired']:
                paired_devices.add(device['Address'].lower())
        return paired_devices

elif sys.platform == 'win32':
    import winreg
    class WindowsBluetooth():
        def subKeys(self, key, size):
            for i in range(size):
                subkey = winreg.EnumKey(key, i)
                yield subkey
        def isPaired(self, key, size):
            has_IRK = has_LTK = False
            for i in range(size):
                subvalue = winreg.EnumValue(key, i)
                if subvalue[0] == 'IRK':
                    has_IRK = True
                elif subvalue[0] == 'LTK':
                    has_LTK = True
            return has_IRK and has_LTK
        def traverseRegistryTree(self, hkey, keypath):
            with winreg.OpenKey(hkey, keypath, 0, winreg.KEY_READ) as key:
                no_subkeys, no_values, _ = winreg.QueryInfoKey(key)
                if no_values >= 2:
                    if self.isPaired(key, no_values):
                        return True
                if no_subkeys:
                    keypath += '\\'
                    for subkey in self.subKeys(key, no_subkeys):
                        if self.traverseRegistryTree(hkey, keypath + subkey):
                            self.paired_devices.add(':'.join([subkey[i:i+2]
                                    for i in range(0, len(subkey), 2)]).lower())
        def __init__(self):
            self.paired_devices = set()
            self.traverseRegistryTree(winreg.HKEY_LOCAL_MACHINE,
                                      r'SYSTEM\CurrentControlSet\Services'
                                       '\BTHPORT\Parameters\Keys')
    # This Windows-specific function returns all the Bluetooth
    # devices that have been paired with this computer.
    def paired_bluetooth_devices():
        try:
            return WindowsBluetooth().paired_devices
        except:
            pass

else:
    # This default function returns None.
    def paired_bluetooth_devices():
        return None


########################################################
#                      Bluetooth LE                    #
########################################################

# Device Discovery: this class communicates with all available Bluetooth LE
# devices, identifies the Blood Pressure Monitor and downloads its data.
class Discovery:

    def __init__(self, bpm, patient_id_cb):
        self.bpm = bpm
        self.patient_id_cb = patient_id_cb
        self.found_device = None
        bpm.loop.run_until_complete(self.run())

    async def run(self):
        self.devices = await discover()

        # restrict to only devices that have been paired with this computer
        paired_devices = paired_bluetooth_devices()
        self.devices = [d for d in self.devices if paired_devices is None
                                   or d.address.lower() in paired_devices]

        # concurrently test all these devices for being the
        # Blood Pressure Monitor we are looking for
        if self.devices:
            self.bpm.prnt(self.message("Contacting %d device%s: " %
                                       (len(self.devices),
                                        "" if len(self.devices)==1 else "s")))
        else:
            self.bpm.prnt("Bluetooth Blood Presssure Monitor not found, "
                          "no paired Bluetooth LE devices detected.")
            return
        tasks = [asyncio.ensure_future(self.isbpm(d.address,d.name))
                 for d in self.devices]
        try:
            await asyncio.gather(*tasks)
        except:
            pass
        if not self.found_device:
            self.bpm.prnt(self.message("Bluetooth Blood Presssure Monitor "
                                       "not found, %d device%s queried: " %
                                       (len(self.devices), "" if len(self.
                                        devices)==1 else "s")))

    # append list of device addresses to mesg
    def message(self, mesg, exclude_addr = None):
        return mesg + ', '.join([d.address for d in self.devices
                                 if d.address != exclude_addr]) + '.'

    async def isbpm(self, mac_addr, name):
        try:
            if self.found_device:
                return # another coroutine has already found it
            async with BleakClient(mac_addr,
                                   loop=self.bpm.loop) as client:
                if self.found_device:
                    return # another coroutine has already found it
                services = await client.get_services()
                if (services.get_service(self.bpm.SERVICE_UUID) and
                    services.get_characteristic(self.bpm.
                                                NOTIFY_CHARACTERISTIC_UUID) and
                    services.get_characteristic(self.bpm.
                                                WRTCMD_CHARACTERISTIC_UUID)):
                    if not self.found_device:
                        self.found_device = mac_addr
                    else: # more than 1 Blood Pressure Monitor ?!
                        return
                    # communicate with Blood Pressure Monitor
                    self.bpm.prnt('Found Bluetooth Blood Pressure Monitor: '
                                  'address %s, name %s.' % (mac_addr, name))
                    await self.bpm.run_client(client, self.patient_id_cb)
                    if len(self.devices) > 1:
                        self.bpm.prnt(self.message("Blood Pressure Monitor com"
                                      "munication done, waiting for %d other "
                                      "Bluetooth LE device%s to disconnect: " %
                                      (len(self.devices) - 1,
                                       "" if len(self.devices)==2 else "s"),
                                      self.found_device))
        except Exception as e:
            # don't report for other devices than the Blood Pressure Monitor
            if self.found_device == mac_addr:
                self.bpm.prnt('Exception: ' + str(e))


class Microlife_BTLE():

    # The Microlife Blood Pressure Monitor with Bluetooth that Costco sells.

    BPM_NAME = "BP3GY1-2N"

    # These are the UUIDs for services and characteristics of that blood
    # pressure monitor. If they are present, we have found it. If they are
    # not present, we will ignore that device.

    SERVICE_UUID = '0000fff0-0000-1000-8000-00805f9b34fb'

    NOTIFY_CHARACTERISTIC_UUID = '0000fff1-0000-1000-8000-00805f9b34fb'
    WRTCMD_CHARACTERISTIC_UUID = '0000fff2-0000-1000-8000-00805f9b34fb'

    # The maximum length of a patient id. For two different users, the blood
    # pressure monitor stores patient ids of up to 20 alphanumeric characters.
    # Software retrieves this patient id to associate the blood pressure
    # measurements with a particular patient.
    MAX_ID_LENGTH = 20

    # These are commands that are sent to the blood pressure monitor via
    # bluetooth. The last number is the checksum, the least significant 8 bits
    # of the sum of all preceding bytes.
    CMD_DISCONNECT       = [77, 255, 0, 2, 4, 82]
    CMD_GET_ID           = [77, 255, 0, 2, 5, 83]
    CMD_GET_MEASUREMENTS = [77, 255, 0, 9, 0, 0, 0, 0, 0, 0, 0, 253, 82]

    def __init__(self, update_id=None, prnt = None):
        self.user = None          # patient 1 or 2 selected in device
        self.patient_id = None    # patient id stored in device
        self.blood_pressure_measurements = [] # (date_time, sys, dia, pulse)
        self.prnt = prnt
        self.in_gui = True
        if not prnt:
            self.prnt = lambda s : print(s)
            self.in_gui = False
        self.update_id = update_id

        self.loop = asyncio.get_event_loop()  # event loop
        self.result_event = asyncio.Event()   # event signals result received
        self.received_value = bytearray()     # data received so far
        self.result = bytearray()             # command result received

    # returns a string
    def get_patient_id(self):
        return self.patient_id

    # returns a list of quadruples (date-time, sys, dia, pulse)
    def get_measurements(self):
        return self.blood_pressure_measurements

    # invokes Bluetooth LE communication
    def bluetooth_communication(self, patient_id_callback):
        self.prnt('Starting discovery, listening on Bluetooth for '
                  'Blood Pressure Monitor.')
        Discovery(self, patient_id_callback)

    # Converts byte-array to string, called for patient id's.
    def user_name(self, bytes):
        id = ''.join([chr(b) for b in bytes if b >= ord(' ') and b < 128])
        return id.strip()

    # The following member functions send commands and process responses.
    # They deal with Bluetooth LE. See https://github.com/hbldh/bleak for
    # more info.

    # run commands for given client
    async def run_client(self, client, patient_id_cb):
        self.client = client
        await client.start_notify(self.NOTIFY_CHARACTERISTIC_UUID,
                                  self.characteristic_notification)
        await self.set_date_and_time()
        patient_id = await self.get_id()
        if self.update_id is None:
            self.patient_id, update = patient_id_cb(patient_id)
        else:
            update = True
            self.patient_id = self.update_id
        if update:
            await self.set_id(self.patient_id)
            await self.get_data()
        elif self.patient_id:
            await self.get_data()
        await client.stop_notify(self.NOTIFY_CHARACTERISTIC_UUID)
        await self.send_command(self.CMD_DISCONNECT, wait_for_response=False)

    # read blood pressure measurements
    async def get_data(self):
        result = await self.send_command(self.CMD_GET_MEASUREMENTS)
        for i in range(38, len(result), 10):
            (sys, dia, pulse, year, month, day, hour, minute) = result[i:i+8]
            year += 2000
            measurement = ('%d-%2.2d-%2.2d %2.2d:%2.2d' %
                           (year, month, day, hour, minute),
                           sys, dia, pulse)
            if not self.in_gui:
                self.prnt('%s  sys %d mmHg, dia %d mmHg, pulse %d /min' %
                          measurement)
            self.blood_pressure_measurements.append(measurement)

    # sets patient id of blood pressure monitor
    async def set_id(self, id):
        set_id_cmd = [77, 255, 0, 24, 6, 253, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 216]
        if len(id) > self.MAX_ID_LENGTH:
            id = id[:self.MAX_ID_LENGTH]
        for i in range(len(id)):
            set_id_cmd[6+i] = ord(id[i])
        set_id_cmd.append(sum(set_id_cmd) % 256) # append checksum
        result = await self.send_command(set_id_cmd)
        assert result == bytearray([129])

    # gets patient id from blood pressure monitor
    async def get_id(self):
        result = await self.send_command(self.CMD_GET_ID)
        self.user = result[1]
        if self.user == 1:
            self.patient_id = self.user_name(result[2:self.MAX_ID_LENGTH+2])
        else:
            self.patient_id = self.user_name(result[23:self.MAX_ID_LENGTH+23])
        return self.patient_id

    # sends current date and time to blood pressure monitor
    async def set_date_and_time(self):
        dt = datetime.datetime.now()
        set_time_cmd = [77, 255, 0, 8, 13, dt.year - 2000, dt.month,
                        dt.day, dt.hour, dt.minute, dt.second]
        set_time_cmd.append(sum(set_time_cmd) % 256) # append checksum
        result = await self.send_command(set_time_cmd)
        assert result == bytearray([129])

    # callback called when pressure monitor has sent data
    def characteristic_notification(self, characteristic, value):
        self.received_value.extend(value)
        assert self.received_value[0:2] == b'M:'
        expected_length = (self.received_value[2] * 256 +
                           self.received_value[3] + 4)
        if len(self.received_value) >= expected_length:
            assert len(self.received_value) == expected_length
            checksum = sum(self.received_value[:-1]) % 256
            assert checksum == self.received_value[-1]
            self.result = self.received_value[4:-1]
            self.received_value = bytearray()
            self.result_event.set() # signals result received

    # splits a command into smaller chunks
    def split_write_cmd(self, cmd):
        MAX_WRITE_LEN = 20  # in a single write command, we can write up to
                            # this many bytes to the blood pressure monitor
        next_cmd = None
        if len(cmd) > MAX_WRITE_LEN:
            next_cmd = cmd[MAX_WRITE_LEN:]
            cmd = cmd[:MAX_WRITE_LEN]
        return cmd, next_cmd

    # send command and return response
    async def send_command(self, cmd, wait_for_response=True):
        TIMEOUT = 60.0 # 1 minute
        self.received_value = self.result = bytearray()
        while cmd:
            cmd, next_cmd = self.split_write_cmd(cmd)
            await self.client.write_gatt_char(self.WRTCMD_CHARACTERISTIC_UUID,
                                              bytearray(cmd))
            cmd = next_cmd
        if wait_for_response:
            try:
                await asyncio.wait_for(self.result_event.wait(), TIMEOUT)
            except asyncio.TimeoutError:
                raise Exception("Notification not received in %d seconds" %
                                TIMEOUT)
            self.result_event.clear()
            return self.result


if __name__ == '__main__':

    import bpm_db

    args = bpm_db.parse_commandline()

    bpm = Microlife_BTLE(args.id)

    if args.id:
        print('desired_id', args.id)

    bpm.bluetooth_communication(bpm_db.patient_id_callback)

    if bpm.get_patient_id() and bpm.get_measurements():
        bpm_db.insert_measurements(bpm.get_patient_id(), bpm.get_measurements())

