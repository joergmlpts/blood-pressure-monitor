
# Microlife Bluetooth and USB Blood Pressure Monitors with Linux, macOS and Windows 10

This repository provides Python code to download measurements via Bluetooth from Microlife's blood pressure monitor BP3GY1-2N which is [sold at Costco stores](https://www.costco.com/microlife-bluetooth-upper-arm-blood-pressure-monitor-with-irregular-heartbeat-detection.product.100519769.html). USB devices, in particular Microlife model BP3GX1-5X, purchased at Costco in February 2015, are also supported.

This code has been developed on Ubuntu 18.04 Linux. It updates the date and time and patient id of the blood pressure monitor and downloads the blood pressure monitor's id and measurements. It inserts the id and measurements into a database.

A version with a GUI - `bpm_gui.py` - is provided as well. It lists blood pressure and pulse data from the database in a table and plots them. It allows to download data from the blood pressure monitor. It looks like this:

![GUI](/images/gui.png)

## Bluetooth Usage

Bluetooth communication of the blood pressure monitor is activated by pressing Start for 8 seconds. When Bluetooth is activated, the Bluetooth logo flashes and the display shows its MAC address. Bluetooth communication of the blood pressure monitor needs to be activated in order for it to be found by this and any other software. Before this code is called for the first time, the operating system's Bluetooth tool should be used to pair the blood pressure monitor with the computer .

## Other Blood Pressure Monitors with Bluetooth

This code has been written for BP3GY1-2N, a Bluetooth blood pressure monitor by Microlife that is sold exclusively at Costco. There is a good chance that virtually identical products are sold under other names. This tool looks for a Bluetooth device with service UUID `0000fff0-0000-1000-8000-00805f9b34fb`. If such a Bluetooth device is found it will be accepted, the device name `BP3GY1-2N` does not need to match.

## Dependencies

This code has been written in Python3. For Bluetooth communication it relies on package `bleak`. USB communication is based on `hid`. The GUI additionally needs `PyQt5` and `matplotlib`. All necessary packages can be installed on Ubuntu Linux with these two commands:
```
sudo apt install python3-pyqt5 python3-matplotlib python3-pip libhidapi-libusb0
sudo pip3 install bleak hid
```

## macOS and Windows

The Bluetooth code has recently been rewritten to use package [`bleak`](https://github.com/hbldh/bleak) for Bluetooth LE. The USB code requires package `hid`. Thanks to `bleak's` and `hid's` availability on Linux, Windows 10 and macOS, this code should run on all three platforms.

Packages `bleak` and `hid` as well as `PyQt5` and `matplotlib` for the GUI, can be installed with this command
```
pip install bleak hid matplotlib PyQt5
```
where `pip3` should be called instead of `pip` when appropriate to avoid accidentally installing packages for Python 2.

USB communication is based on package [`hid`](https://pypi.org/project/hid/). The Python module `hid` requires its native library `hidapi` to be installed. Please follow [these instructions](https://pypi.org/project/hid/) to install `hidapi`.

  * This code has been developed on Ubuntu **Linux** 18.04 and it works fine on Linux.
  * This code now works fine on **Windows 10** as well. The recent ports to `bleak` and `hid` enabled these tools to run on WIndows 10 as well.
  * No feedback for **macOS** has been received yet.

Care must be taken when the same computer - or just the same Bluetooth USB dongle - is used with different operating systems. The blood pressure monitor, once paired, does not appear to pair again with the same Bluetooth adapter (to be more precise: with an adapter that has the same mac address but lacks the encryption keys that were negotiated during the pairing). A workaround is to change the adapter's mac address to another one that the blood pressure monitor has not been paired with. Changing the mac address has worked for me with [Linux utility bdaddr](http://www.petrilopia.net/wordpress/wp-content/uploads/bdaddrtar.bz2). A much superior solution is to copy the encryption keys from one operating system to the other. Windows 10 stores them in the registry, and Linux stores them in the file system under directory `/var/lib/bluetooth`. Since the blood pressure monitor cannot easily be paired again, it is a good idea to keep a backup of the encryption keys.

## GUI

After Python3 and the dependencies have been installed, this tool can be started by clicking on `bpm_gui.py`.

The graphical user interface allows to add, edit and delete patient records. It allows to import data written by Microlife's tools. It also communicates via Bluetooth LE and USB with the blood pressure monitor and downloads measurements. Moreover, it sets the date and time and assigns patient ids of the blood pressure monitor.

## Data import

Besides downloading measurements from the blood pressure monitor, data from Microlife software can be imported as well.

The Microlife software on Windows allows to export blood pressure measurements to `.csv` files. These files can be imported into our database.

On Android, the Microlife Connect app stores blood pressure measurements in a sqlite database. When the phone is connected to a computer, that database can be copied from file `sdcard/DBMLBPA6` to the computer. This tool allows to import the app's database into our database.

Directory `import_examples` contains a `.csv` file and a database from an Android phone as example data.

## Database

This code uses a sqlite database. This database is found in `~/.local/share/bpm/bpm.db` and direct access is possible as this:

```
sqlite3 ~/.local/share/bpm/bpm.db
.dump
.quit
```
On Windows, the database is at `\Users\USERNAME\AppData\Local\BPM\bpm.db`.

## Command-line tools

If the GUI is not wanted, the command-line tools `bpm_bt.py` and `bpm_usb.py` can be used instead. These tools have identical functionality and are based on Bluetooth and USB respectively. We only describe `bpm_bt.py` here.

After blood pressure measurements have been taken, they can be downloaded with the command-line tool `bpm_bt.py`. Again, Bluetooth needs to be activated by pressing  Start for 8 seconds. When the Bluetooth logo flashes and the display changes to its MAC address, the blood pressure monitor is ready to connect via Bluetooth. `bpm_bt.py` will find it and connect to it. The run should look like this:
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
Downloaded 7 measurements, inserted 3 into database /home/user/.local/share/bpm/bpm.db.
```

The first line
```
Contacting 3 device: DA:9A:85:00:A3:52, 51:13:01:D5:02:C4, 7F:FB:7A:6A:CE:46.
```
lists one or more Bluetooth LE devices that were found during the discovery phase. This software is going to communicate with all of them in order to find the blood pressure monitor.

The line
```
Found Bluetooth Blood Pressure Monitor: address DA:9A:85:00:A3:52, name BP3GY1-2N.
```
indicates that the device's Bluetooth LE service and characteristics have matched the ones of the blood pressure monitor. This message is immediately followed by data download from the blood pressure monitor.

The blood pressure measurements are self-explanatory and the final line
```
Downloaded 7 measurements, inserted 3 into database /home/user/.local/share/bpm/bpm.db.
```
indicates that of the 7 measurements only 3 were inserted into the database. This happens when from previous runs of the tool, 4 of the 7 measurements are already in the database.

## Command-line arguments

The tools `bpm_bt.py` and `bpm_usb.py` are commonly called without arguments. Without arguments they download blood pressure measurements and insert them into the database, the most common usage scenario. Several command-line arguments are supported.

Option `--id` is available to store a patient id in the blood pressure monitor. This option is required when no patient id is stored in the monitor, e.g. upon the first use. Option `--id` can also be used to assign a new patient id to the blood pressure monitor.

Another option is `--import_csv` which is followed by a file name. The Microlife software on Windows allows to export blood pressure measurements to `.csv` files. This option can be used to import that data into the database.

On Android, the Microlife Connect app stores blood pressure measurements in a sqlite database. When the phone is connected to a computer, that database can be copied from file `sdcard/DBMLBPA6` to the computer. This tool's option `--import_db` allows to import the app's database into our database.

## Acknowledgements 

The Microlife Connect app on Android communicates via Bluetooth LE and writes extensive debug logfiles under directory `sdcard/Downloads`. These logs include all the data that pass back and forth between the app and the blood pressure monitor. The Bluetooth communication code is based on the traffic seen in these debug logs.

For USB, [phako](https://github.com/phako/BPM) has documented and implemented the communication of a Microlife blood pressure monitor. That was extremely helpful. Another implementation is [frankyn's](https://github.com/frankyn/BPADataDownloader).
