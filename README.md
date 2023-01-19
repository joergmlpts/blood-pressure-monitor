
# Microlife Bluetooth and USB Blood Pressure Monitors for Linux, MacOS and Windows

This repository provides Python code to download readings via Bluetooth from the Microlife BP3GY1-2N blood pressure monitor [sold at Costco stores](https://www.costco.com/microlife-bluetooth-upper-arm-blood-pressure-monitor-with-irregular-heartbeat-detection.product.100519769.html). USB devices, specifically the Microlife model BP3GX1-5X, purchased at Costco in February 2015, are also supported.

This code was developed on Ubuntu 18.04 Linux. It updates the date and time and patient UD of the blood pressure monitor and downloads the blood pressure monitor's ID and readings. It inserts the ID and readings into a database.

A GUI version - `bpm_gui.py` - is also provided. It lists blood pressure and pulse data from the database in a table and plots them. It allows to download data from the blood pressure monitor. It looks like this:

![GUI](/images/gui.png)

## Bluetooth Usage

Bluetooth communication of the blood pressure monitor is activated by pressing and holding Start for 8 seconds. When Bluetooth is activated, the Bluetooth logo flashes and the display shows its MAC address. The Bluetooth communication of the blood pressure monitor must be activated in order for it to be found by this and any other software. Before calling this code for the first time, use the operating system's Bluetooth tool to pair the blood pressure monitor with the computer.

## Other Blood Pressure Monitors with Bluetooth

This code was written for BP3GY1-2N, a Microlife Bluetooth blood pressure monitor by Microlife sold exclusively at Costco. There is a good chance that nearly identical products are sold under other names. This tool searches for a Bluetooth device with service UUID `0000fff0-0000-1000-8000-00805f9b34fb`. If such a Bluetooth device is found it will be accepted, the device name `BP3GY1-2N` does not have to match.

## Dependencies

This code has been written in Python 3. For Bluetooth communication it relies on the `bleak` package. USB communication relies on `hid`. The GUI also needs `PyQt5` and `matplotlib`. All necessary packages can be installed on Ubuntu Linux with these two commands:

```
sudo apt install python3-pyqt5 python3-matplotlib python3-pip libhidapi-libusb0
sudo pip3 install bleak hid
```

## MacOS and Windows

The Bluetooth code has recently been rewritten to use the [`bleak`](https://github.com/hbldh/bleak) package for Bluetooth LE. The USB code requires the `hid` package. Thanks to `bleak's` and `hid's` availability on Linux, Windows and MacOS, this code should work on all three platforms.

The packages `bleak` and `hid` as well as `PyQt5` and `matplotlib` for the GUI, can be installed with the following command
```
pip install bleak hid matplotlib PyQt5
```
where `pip3` should be used instead of `pip` when appropriate to avoid accidentally installing Python 2 packages.

USB communication is based on the [`hid`](https://pypi.org/project/hid/) package. The Python module `hid` requires the native library `hidapi` to be installed. Please follow [these instructions](https://pypi.org/project/hid/) to install `hidapi`.

  * This code has been developed on Ubuntu **Linux** 18.04 and it works fine on Linux.
  * This code now works fine on **Windows** as well. The recent ports to `bleak` and `hid` enabled these tools to run on WIndows 10 as well.
  * No feedback for **MacOS** has been received yet.

## GUI

After installing Python 3 and its dependencies, this tool can be started by clicking on `bpm_gui.py`.

The graphical user interface allows to add, edit and delete patient records. It allows to import data written by Microlife's tools. It also communicates with the blood pressure monitor via Bluetooth LE and USB and downloads readings. It also sets the date and time and assigns patient IDs of the blood pressure monitor.

## Data import

In addition to downloading readings from the blood pressure monitor, data can also be imported from Microlife software.

The Microlife software on Windows allows you to export blood pressure readings to `.csv` files. These files can be imported into our database.

On Android, the Microlife Connect app stores blood pressure readings in a sqlite database. When the phone is connected to a computer, this database can be copied to the computer from file `sdcard/DBMLBPA6`. This tool allows you to import the app's database into our database.

The `import_examples` directory contains a `.csv` file and a database from an Android phone as example data.

## Database

This code uses a sqlite database. This database is located in `~/.local/share/bpm/bpm.db` and can be accessed directly:

```
sqlite3 ~/.local/share/bpm/bpm.db
.dump
.quit
```
On Windows, the database is located at `\Users\USERNAME\AppData\Local\BPM\bpm.db`.

## Command-line utilities

If the GUI is not desired, the command-line utilities `bpm_bt.py` and `bpm_usb.py` can be used instead. These tools have identical functionality and are based on Bluetooth and USB respectively. We only describe `bpm_bt.py` here.

After blood pressure readings have been taken, they can be downloaded using the command-line tool `bpm_bt.py`. Again, Bluetooth must be activated by pressing and holding Start for 8 seconds. When the Bluetooth logo flashes and the display changes to its MAC address, the blood pressure monitor is ready to connect via Bluetooth. `bpm_bt.py` will find it and connect to it. It look like this:
```
Contacting 3 devices: DA:9A:85:00:A3:52, 51:13:01:D5:02:C4, 7F:FB:7A:6A:CE:46.
Found Bluetooth Blood Pressure Monitor: address DA:9A:85:00:A3:52, name BP3GY1-2N.
2020-05-16 16:29  sys 130 mmHg, dia 81 mmHg, pulse 90 /min
2020-05-17 10:43  sys 133 mmHg, dia 84 mmHg, pulse 58 /min
2020-05-19 19:26  sys 125 mmHg, dia 80 mmHg, pulse 81 /min
2020-05-26 20:53  sys 124 mmHg, dia 79 mmHg, pulse 77 /min
2020-05-27 20:59  sys 126 mmHg, dia 79 mmHg, pulse 71 /min
2020-05-28 10:07  sys 128 mmHg, dia 79 mmHg, pulse 67 /min
2020-05-28 16:37  sys 126 mmHg, dia 80 mmHg, pulse 72 /min
Blood Pressure Monitor communication done, waiting for 2 other Bluetooth LE devices to disconnect: 51:13:01:D5:02:C4, 7F:FB:7A:6A:CE:46.
Downloaded 7 readings, added 3 to database /home/user/.local/share/bpm/bpm.db.
```

The first line
```
Contacting 3 device: DA:9A:85:00:A3:52, 51:13:01:D5:02:C4, 7F:FB:7A:6A:CE:46.
```
lists one or more Bluetooth LE devices that were found during the discovery phase. This software will communicate with all of them in order to find the blood pressure monitor.

The line
```
Found Bluetooth Blood Pressure Monitor: address DA:9A:85:00:A3:52, name BP3GY1-2N.
```
indicates that the device's Bluetooth LE service and characteristics have matched those of the blood pressure monitor. This message is immediately followed by a data download from the blood pressure monitor.

The blood pressure readings are self-explanatory and the last line
```
Downloaded 7 readings, added 3 in database /home/user/.local/share/bpm/bpm.db.
```
indicates that only 3 of the 7 readings were added to the database. This happens when 4 of the 7 readings are already in the database from previous runs of the utitility.

## Command-line arguments

The utilities `bpm_bt.py` and `bpm_usb.py` are usually called without arguments. Without arguments they download blood pressure readings and add them to the database, the most common usage scenario. Multiple command-line arguments are supported.

The `--id` option is available to store a patient ID in the blood pressure monitor. This option is required when there is no patient ID stored in the monitor, for example when it is first used. The `--id` option can also be used to assign a new patient id to the blood pressure monitor.

Another option is `--import_csv` which is followed by a filename. The Microlife software on Windows allows blood pressure readings to be exported to `.csv` files. This option can be used to import thus data into our database.

On Android, the Microlife Connect app stores blood pressure readings in a sqlite database. When the phone is connected to a computer, this database can be copied from the `sdcard/DBMLBPA6` file to the computer. This `--import_db` option allows you to import the app's database into our database.

## Acknowledgements 

The Microlife Connect app on Android communicates via Bluetooth LE and writes extensive debug log files in the `sdcard/Downloads` directory. These logs contain all the data that is passed back and forth between the app and the blood pressure monitor. The Bluetooth communication code is based on the traffic seen in these debug logs.

For USB, [phako](https://github.com/phako/BPM) documented and implemented the communication of a Microlife blood pressure monitor. That has been extremely helpful. Another implementation is from [frankyn](https://github.com/frankyn/BPADataDownloader).
