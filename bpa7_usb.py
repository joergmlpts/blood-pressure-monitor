#!/usr/bin/env python3
import glob
import os
import sys
import time
import argparse
from datetime import datetime
from typing import List, Tuple, Optional
from dataclasses import dataclass
import pickle
import serial
import getpass

import bpm_db


VENDOR_ID = '04b4'
PRODUCT_ID = '5500'
BAUDRATE = 9600
MAX_RECORDS = 99 # Tonometer keeps only 99 last measurements

@dataclass(frozen=True)
class Header:
    num_records: int       
    device_serial_marker: str       

    @classmethod
    def from_raw_record(cls, record: bytes | str) -> "Header":
        """Factory method to parse a clean, synchronized 32-byte header record."""
        # Convert to string if bytes were passed (decode as ascii/latin-1)
        if isinstance(record, bytes):
            record = record.decode('ascii', errors='ignore')
            
        if len(record) < 32:
            raise ValueError(f"Record length is too small ({len(record)} < 32)")

        # 1. Parsing 
        num_rec = int(record[0:4], 16)
        serial_no = record[8:24].strip()

        # 2. Return a new object of the class
        return cls(
            num_records=num_rec,
            device_serial_marker=serial_no
        )

@dataclass(frozen=True)
class Measurement:
    timestamp: str       # Formatted date: 'YYYY-MM-DD HH:MM'
    diastolic: int       # Diastolic pressure
    systolic: int        # Systolic pressure
    pulse: int           # Pulse

    @classmethod
    def from_raw_record(cls, record: bytes | str) -> "Measurement":
        """Factory method to parse a raw 32-byte measurement record."""
        # Convert to string if bytes were passed (decode as ascii/latin-1)
        if isinstance(record, bytes):
            record = record.decode('ascii', errors='ignore')
        if len(record) < 32:
            raise ValueError(f"Record text is too short ({len(record)} < 32)")

        # 1. Parse date and time
        date_str = record[0:10]
        dt = datetime.strptime(date_str, '%y%m%d%H%M')
        formatted_date = dt.strftime('%Y-%m-%d %H:%M')

        # 2. Extract metrics from HEX substrings
        pulse_val = int(record[16:19], 16)
        dia_val   = int(record[19:22], 16) // 4 # Here we shift out 2 leftmost bits, that we do not use in this code
        sys_val   = int(record[22:24], 16)

#        flag_m_val = int(record[10], 16)
#        is_mam = "Yes" if (flag_m_val & 2) else "No"

#        print()
#        print(record)
#        print(record[0:10],record[16:19],record[19:22],record[22:24],record[19],"MAM:",int(record[10],16)&0x002)
#        print(pulse_val,dia_val,sys_val)

        # 3. Return a new class instance
        return cls(
            timestamp=formatted_date,
            diastolic=dia_val,
            systolic=sys_val,
            pulse=pulse_val
        )

def _read(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read().strip().lower()
    except OSError:
        return None

def find_microlife() -> List[str]:
    """Returns a list of found Microlife device paths."""
    result = []
    for tty in sorted(glob.glob('/sys/class/tty/ttyUSB*')):
        # climb from tty to usb_device, look for idVendor
        cur = os.path.realpath(tty)
        usb_dir = None
        while cur and cur != '/':
            cur = os.path.dirname(cur)
            if os.path.exists(os.path.join(cur, 'idVendor')):
                usb_dir = cur
                break
            
        if not usb_dir:
            continue

        vendor = _read(os.path.join(usb_dir, 'idVendor'))
        product = _read(os.path.join(usb_dir, 'idProduct'))
        
        if vendor == VENDOR_ID and product == PRODUCT_ID:
            result.append(os.path.join('/dev', os.path.basename(tty)))
#            result.append('/dev/ttyUSB1')  # for testing only
    return result

def check_port_permissions(port: str) -> bool:
    """Checks if the current user has read and write permissions for the target port."""
    if not os.path.exists(port):
        print(f"Error: Port file '{port}' does not exist.")
        return False

    if not (os.access(port, os.R_OK) and os.access(port, os.W_OK)):
        print(f"\n[Permission Error] You do not have sufficient permissions to access {port}")
        print(f"Run: sudo usermod -aG dialout {getpass.getuser()} (and relog) or sudo chmod a+rw {port}\n")
        return False
    return True

def download_raw_dump(port: str) -> Optional[Tuple[bytes, List[bytes]]]:
    """STAGE 1: Strictly handles serial I/O with explicit ACK (0x06) synchronization."""
    if not check_port_permissions(port):
        return None

    cmd_get_data = bytes([0x12, 0x16, 0x18, 0x22])
    raw_records = []
    synced = False
    raw_header = b""

    try:
        ser = serial.Serial(port, baudrate=BAUDRATE, timeout=2.0, write_timeout=2.0, rtscts=False, dsrdtr=False)
        ser.dtr = False
        ser.rts = False
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        for attempt in range(1, 3):
            try:
                if attempt > 1:
                    print("\n[Attempt 2] Resetting Cypress buffers due to sync failure...")
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    time.sleep(0.5)
                
                print(f"Sending request (attempt {attempt}/2)...")
                ser.write(cmd_get_data)
                ser.flush()
                
                # --- SYNCHRONIZATION PHASE ---
                print("Synchronizing with device stream (looking for ACK 0x06)...")
                ack_found = False
                
                # Allow skipping up to 4 bytes of potential line noise to find the real 0x06 ACK
                for _ in range(4):
                    ack_byte = ser.read(1)
                    if ack_byte == b'\x06':
                        ack_found = True
                        break
                    if ack_byte:
                        print(f" -> Ignored sync byte: {ack_byte.hex().upper()}")

                if not ack_found:
                    print(f"Warning: Attempt {attempt} failed. Device did not respond with ACK (0x06).")
                    continue  # Try next attempt with full buffer reset

                # --- HEADER READING PHASE ---
                # Since ACK is confirmed, the next 32 bytes are GUARANTEED to be the unshifted header
                raw_header = ser.read(32)
                if len(raw_header) < 32:
                    print(f"Warning: Header truncated on attempt {attempt} (read only {len(raw_header)} bytes).")
                    continue

                # Safely extract the expected record count from the guaranteed position
                num_records = int(raw_header[0:4].decode('ascii', errors='ignore'), 16)

                print(f"ACK confirmed! Unshifted header parsed. Expecting {num_records} blocks.")
                if num_records>MAX_RECORDS:
                    print(f"Warning: Header reports {num_records} records to read, it is more than maximum possible {MAX_RECORDS}.")
                    print(f"Looks strange, but trying to read {MAX_RECORDS}.")
                    num_records=MAX_RECORDS
                # --- DATA STREAMING PHASE ---
                raw_records.clear()
                for i in range(num_records):
                    record_chunk = ser.read(32)
                    if len(record_chunk) < 32:
                        print(f"Warning: Stream truncated at record {i+1}/{num_records}")
                        break
                    raw_records.append(record_chunk)

                synced = True
                break

            except Exception as e:
                print(f"Error during acquisition attempt {attempt}: {e}")
                
    except serial.SerialException as e:
        print(f"Error opening port {port}: {e}")
        return None

    if synced:
        return raw_header, raw_records
    else:
        print("\nError: Critical protocol synchronization failure (No valid ACK found).")
        return None


def parse_raw_dump(raw_header: bytes, raw_records: List[bytes]) -> Tuple[str, List[Measurement]]:
    """STAGE 2: Pure data processor. Parses raw bytes into high-level dataclasses."""
    header_obj = Header.from_raw_record(raw_header)
    measurements = []

    for i, raw_record in enumerate(raw_records):
        try:
            measurement = Measurement.from_raw_record(raw_record)
            measurements.append(measurement)
        except ValueError as parse_err:
            print(f"Warning: Skipping corrupt record block at index {i}: {parse_err}")
            continue

    return header_obj.device_serial_marker, measurements


def main():

    parser = argparse.ArgumentParser(description="Reading data from Microlife BP A7.")
    parser.add_argument('port', nargs='?', default=None, help='Target serial port path.')
    parser.add_argument('--save-dump', type=str, metavar='FILE', help='Save downloaded raw binary dump to a file.')
    parser.add_argument('--load-dump', type=str, metavar='FILE', help='Load and parse raw binary dump from a file, bypassing serial port.')
    args = parser.parse_args()
        
    # --- STAGE 1: Acquire raw bytes (From File or From Serial) ---
    if args.load_dump:
        print(f"Loading raw binary dump from file: {args.load_dump}")
        try:
            with open(args.load_dump, 'rb') as f:
                raw_header, raw_records = pickle.load(f)
            print("Dump successfully loaded from disk.")
        except Exception as e:
            print(f"Failed to load dump file: {e}")
            sys.exit(1)
    else:
        device_port = args.port
        if not device_port:
            ports = find_microlife()
            if not ports:
                print("No Microlife devices discovered.")
                sys.exit(1)
            if len(ports) > 1:
                print(f"Multiple devices found: {', '.join(ports)}. Please specify one.")
                sys.exit(1)
            device_port = ports[0]

        print(f"Connecting to port: {device_port}")
        dump_data = download_raw_dump(device_port)
        if not dump_data:
            print("Data acquisition failed.")
            os._exit(1)

        raw_header, raw_records = dump_data
        if len(raw_records)==0:
            print("Device reports 0 records. No data to load.")
            os._exit(0)
            
        
        # Optional block: Save dump to disk if requested by the user
        if args.save_dump:
            print(f"Saving acquired binary dump to file: {args.save_dump}")
            try:
                with open(args.save_dump, 'wb') as f:
                    pickle.dump((raw_header, raw_records), f)
                print("Dump successfully written.")
            except Exception as e:
                print(f"Warning: Failed to save dump file: {e}")
                

    total_bytes = len(raw_header) + sum(len(r) for r in raw_records)
    print(f"Processing raw data block ({total_bytes} bytes)...")

    # --- STAGE 2: Parse raw bytes ---
    try:
        patient_id, measurements = parse_raw_dump(raw_header, raw_records)
    except Exception as parse_fault:
        print(f"Critical error during metrics parsing: {parse_fault}")
        os._exit(1)

    # --- STAGE 3: Database insertion ---
    db_payload = [(m.timestamp, m.systolic, m.diastolic, m.pulse) for m in measurements]
    bpm_db.insert_measurements(patient_id, db_payload)
    print("Database updated successfully. Forcing exit...")
    os._exit(0)




if __name__ == '__main__':
    main()
