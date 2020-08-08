#!/usr/bin/env python3

import ctypes, datetime, sys

import hid    # if missing, install python module with `pip install hid'
# don't forget to install hidapi libray as well:
#  on Ubuntu install library with 'sudo apt install libhidapi-libusb0'
#  instructions for other platforms: https://pypi.org/project/hid/#description

class USB_IO:
    VENDOR  = 0x04B4
    PRODUCT = 0x5500

    def __init__(self):
        self.device = None
        try:
            self.device = hid.Device(self.VENDOR, self.PRODUCT)
        except Exception as e:
            if str(e) == 'unable to open device':
                raise Exception('Microlife Blood Pressure Monitor '
                                'not found on USB ports.')
            else:
                raise e

    def close(self):
        if self.device:
            self.device.close()
            self.device = None

    def read(self):
        data = bytearray()
        BUFFER_SIZE = 8
        TIMEOUT = 100 # 0.1 secs
        while True:
            buf = self.device.read(BUFFER_SIZE, TIMEOUT)
            if not buf:
                break
            data.extend(buf[1:(buf[0]&15)+1])
        return data

    def write(self, data):
        assert len(data) <= 7
        if sys.platform == 'win32':
            raw = ctypes.create_string_buffer(len(data)+2)
            raw[0] = 0
            raw[1] = len(data)
            raw[2:] = data
            assert self.device.write(raw) == 9
        else:
            raw = ctypes.create_string_buffer(len(data)+1)
            raw[0] = len(data)
            raw[1:] = data
            assert self.device.write(raw) == len(raw)

class Microlife_USB(USB_IO):

    MAX_RETRY        = 15 # for garbage input or checksum mismatches
    MAX_CMD_WRITE    = 7
    ID_LENGTH        = 11

    FIRST_RECORD     = 32
    RECORD_LENGTH    = 32

    CMD_CYCLES       = 0x22
    CMD_SET_ID       = 0x23
    CMD_GET_ID       = 0x24
    CMD_GET_DATETIME = 0x26
    CMD_SET_DATETIME = 0x27

    # opens the serial interface
    def __init__(self, update_id = None, prnt = None):
        super().__init__()
        self.patient_id = None    # patient id stored in device
        self.blood_pressure_measurements = [] # (date_time, sys, dia, pulse)
        self.prnt = prnt
        self.in_gui = True
        if not prnt:
            self.prnt = lambda s : print(s)
            self.in_gui = False
        self.update_id = update_id

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    # returns a string
    def get_patient_id(self):
        return self.patient_id

    # returns a list of quadruples (date-time, sys, dia, pulse)
    def get_measurements(self):
        return self.blood_pressure_measurements

    # invokes USB communication
    def usb_communication(self, patient_id_cb):
        self.prnt('Starting USB communication with Blood Pressure Monitor.')
        self.set_date_time()

        patient_id = self.get_patient_id();
        if self.update_id is None:
            self.patient_id, update = patient_id_cb(patient_id)
        else:
            update = True
            self.patient_id = self.update_id
        if update:
            self.set_id(self.patient_id)
            self.get_data()
        elif self.patient_id:
            self.get_data()

    # Converts byte-array to string, called for patient id's.
    def user_name(self, bytes):
        id = ''.join([chr(b) for b in bytes if b >= ord(' ') and b < 128])
        return id.strip()

    # sends command, waits for response, verifies checksum, returns response
    def send_command(self, cmd, arg = None):
        command_bytes = [0x12, 0x16, 0x18, cmd]
        retries = 0
        while retries < self.MAX_RETRY:
            retries += 1

            self.write(command_bytes)
            response = self.read()

            if arg is not None: # set id or date/time
                if len(response) != 1 or response[0] != 6:
                    continue
                arg = [ord(d) for d in bytearray(arg).hex()]
                cksum = bytearray([sum(arg) % 256]).hex()
                arg.append(ord(cksum[0]))
                arg.append(ord(cksum[1]))
                while len(arg):
                    self.write(arg[:self.MAX_CMD_WRITE]
                               if len(arg) > self.MAX_CMD_WRITE else arg)
                    arg = arg[self.MAX_CMD_WRITE:] if len(arg) > \
                                                      self.MAX_CMD_WRITE else []
                return self.read()

            # check for unexpected response
            if len(response) <= 3 or response[0] != 6:
                continue

            # verify checksum
            cksum = sum(response[1:len(response)-2]) % 256
            if '%2.2X' % cksum == response[-2:].decode():
                return response[1:-2] # strip first byte and checksum
            self.prnt('checksum mismatch: computed %s, expected %s.' %
                      ('%2.2X' % cksum, response[-2:].decode()),
                      file=sys.stderr)

    # returns 0 .. 15, raises exception if out of range
    def decode_hexdigit(self, byte):
        if byte >= ord('0') and byte <= ord('9'):
            return byte - ord('0')
        elif byte >= ord('A') and byte <= ord('F'):
            return byte - ord('A') + 10
        elif byte >= ord('a') and byte <= ord('f'):
            return byte - ord('a') + 10
        raise Exception("not a hex digit")

    # returns number coded as hex string
    def decode_hexnum(self, bytes):
        word = 0
        for b in bytes:
            word *= 16
            word += self.decode_hexdigit(b)
        return word

    # decodes string represented as bytes of hex-digits
    def get_id(self, data):
        id = ''
        try:
            for i in range(0, len(data), 2):
                ch = self.decode_hexnum(data[i:i+2])
                if ch < ord(' ') or ch > ord('~') or not chr(ch).isalnum():
                    break
                id += chr(ch)
        finally:
            return id

    # returns patient id
    def get_patient_id(self):
        response = self.send_command(self.CMD_GET_ID)
        return self.get_id(response[0:2*self.ID_LENGTH])

    # sets patient_id of blood pressure monitor
    def set_id(self, id):
        if len(id) > self.ID_LENGTH:
            id = id[:self.ID_LENGTH]
        arg = [0] * 32
        arg[1] = arg[3] = 1
        for i in range(len(id)):
            arg[i+4] = ord(id[i])
        self.send_command(self.CMD_SET_ID, arg)

    # returns datetime object
    def get_date_time(self):
        response = self.send_command(self.CMD_GET_DATETIME)
        return datetime.datetime.strptime(response[:14].decode(),
                                          '%m%d%Y%H%M%S')

    # turns 12 into 0x12
    def dec_to_hex(self, i):
        return 16 * (i // 10) + (i % 10)

    # sets date and time
    def set_date_time(self):
        arg = [0] * 40
        dt = datetime.datetime.now()
        arg[0] = self.dec_to_hex(dt.month)
        arg[1] = self.dec_to_hex(dt.day)
        arg[2] = self.dec_to_hex(dt.year // 100)
        arg[3] = self.dec_to_hex(dt.year % 100)
        arg[4] = self.dec_to_hex(dt.hour)
        arg[5] = self.dec_to_hex(dt.minute)
        arg[6] = self.dec_to_hex(dt.second)
        self.send_command(self.CMD_SET_DATETIME, arg)

    # download blood pressure measurements
    def get_data(self):
        response = self.send_command(self.CMD_CYCLES)

        # number of cycles in 4 hex digits
        number_of_cycles = self.decode_hexnum(response[:4])

        # patient id
        user = self.get_id(response[8:self.FIRST_RECORD])

        for offset in range(self.FIRST_RECORD,
                            self.FIRST_RECORD +
                            number_of_cycles * self.RECORD_LENGTH,
                            self.RECORD_LENGTH):
            record = response[offset:offset+self.RECORD_LENGTH]

            try:
                dt = datetime.datetime.strptime(record[0:10].decode(),
                                                '%y%m%d%H%M')
            except ValueError:
                continue

            # this 32-bit word contains systolic pressure, diastolic pressure,
            # and pulse in 10 bits each
            word = self.decode_hexnum(record[16:24])

            measurement = ('%d-%2.2d-%2.2d %2.2d:%2.2d' % (dt.year, dt.month,
                           dt.day, dt.hour, dt.minute), word & 1023,
                           (word >> 10) & 1023, (word >> 20) & 1023)

            if not self.in_gui:
                self.prnt('%s  sys %d mmHg, dia %d mmHg, pulse %d /min' %
                          measurement)

            self.blood_pressure_measurements.append(measurement)


if __name__ == '__main__':

    import bpm_db

    args = bpm_db.parse_commandline()

    try:
        with Microlife_USB(args.id) as bpm:

            if args.id:
                print('desired_id', args.id)

            bpm.usb_communication(bpm_db.patient_id_callback)

            if bpm.get_patient_id() and bpm.get_measurements():
                bpm_db.insert_measurements(bpm.get_patient_id(),
                                           bpm.get_measurements())

    except Exception as e:
        print('Error:', str(e), file=sys.stderr)

