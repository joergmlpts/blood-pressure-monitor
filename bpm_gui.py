#!/usr/bin/env python3

import datetime, os, sys
import bpm_db

import_error = ''
try:
    import bpm_bt
    bpm_bt_loaded = True
except ImportError as e:
    import_error = str(e)
    bpm_bt_loaded = False

try:
    import bpm_usb
    bpm_usb_loaded = True
except ImportError as e:
    import_error = str(e)
    bpm_usb_loaded = False

# if missing, install on Ubuntu with 'sudo apt install python3-pyqt5'
from PyQt5.QtCore    import QDate, QDateTime, Qt
from PyQt5.QtGui     import QKeySequence, QColor, QFont, QIntValidator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QAction, QWidget,
                             QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
                             QSizePolicy, QComboBox, QTableWidget, qApp,
                             QTableWidgetItem, QMessageBox, QDialog, QDateEdit,
                             QLineEdit, QFormLayout, QDialogButtonBox,
                             QFileDialog)

# if missing, install on Ubuntu with 'sudo apt install python3-matplotlib'
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


########################################################
#                      Utilities                       #
########################################################

DATETIME_FMT = 'yyyy-MM-dd HH:mm' # date and time stored in database as this
XAXIS_FMT    = 'M/d\nyyyy'        # x-axis is labeled with dates in this format

# return seconds of epoch for start of day
def secs_at_midnight(secs_since_epoch):
    time = QDateTime.fromSecsSinceEpoch(secs_since_epoch).time()
    secs_since_epoch -= 3600 * time.hour()
    secs_since_epoch -= 60 * time.minute()
    secs_since_epoch -= time.second()
    return secs_since_epoch

# combine patient_id with patient name, used by scrollbar
def id_plus_name(id, patient_ids):
    if id:
        if 'name' in patient_ids[id]:
            id += '  ' + patient_ids[id]['name']
        return id
    return ''


########################################################
#                          GUI                         #
########################################################

class MainWindow(QMainWindow):

    def __init__(self, widget, patient_ids, app):
        QMainWindow.__init__(self)
        self.patient_ids = patient_ids
        self.app = app
        self.setWindowTitle("Blood Pressure Log")
        self.setCentralWidget(widget)

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")

        import_csv_action = QAction("Import CSV ...", self)
        import_csv_action.triggered.connect(self.import_csv)

        import_db_action = QAction("Import DB ...", self)
        import_db_action.triggered.connect(self.import_db)

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)

        self.file_menu.addAction(import_csv_action)
        self.file_menu.addAction(import_db_action)
        self.file_menu.addAction(exit_action)

        self.edit_menu = self.menu.addMenu("Edit")

        add_patient_action = QAction("Add Patient ...", self)
        add_patient_action.triggered.connect(self.add_patient)
        del_patient_action = QAction("Delete Patient ...", self)
        del_patient_action.triggered.connect(self.delete_patient)
        edit_patient_action = QAction("Edit Patient Info ...", self)
        edit_patient_action.triggered.connect(self.edit_patient)

        self.edit_menu.addAction(add_patient_action);
        self.edit_menu.addAction(del_patient_action);
        self.edit_menu.addAction(edit_patient_action);

        self.bluetooth_menu = self.menu.addMenu("Bluetooth")
        self.bluetooth_menu.setEnabled(bpm_bt_loaded)

        bluetooth_action = QAction("Receive Readings ...", self)
        bluetooth_action.triggered.connect(self.bluetooth_receive)
        self.bluetooth_menu.addAction(bluetooth_action);

        send_id_action = QAction("Send ID ...", self)
        send_id_action.triggered.connect(self.bluetooth_send_id)
        self.bluetooth_menu.addAction(send_id_action);

        clear_id_action = QAction("Clear ID ...", self)
        clear_id_action.triggered.connect(self.bluetooth_clear_id)
        self.bluetooth_menu.addAction(clear_id_action);

        self.usb_menu = self.menu.addMenu("USB")
        self.usb_menu.setEnabled(bpm_usb_loaded)

        usb_action = QAction("Receive Readings ...", self)
        usb_action.triggered.connect(self.usb_receive)
        self.usb_menu.addAction(usb_action);

        send_id_action = QAction("Send ID ...", self)
        send_id_action.triggered.connect(self.usb_send_id)
        self.usb_menu.addAction(send_id_action);

        clear_id_action = QAction("Clear ID ...", self)
        clear_id_action.triggered.connect(self.usb_clear_id)
        self.usb_menu.addAction(clear_id_action);

        # Status Bar
        self.status = self.statusBar()

        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)
        self.setFixedSize(int(geometry.width() * 0.8),
                          int(geometry.height() * 0.8))

    def set_status_message(self, patient_id = None):
        if patient_id:
            msg = 'Loaded patient "' + patient_id + '"'
            if patient_id in self.patient_ids:
                info = self.patient_ids[patient_id]
                if 'name' in info:
                    msg += ', name ' + info['name']
                if 'age' in info:
                    msg += ', age %d' % info['age']
                if 'gender' in info:
                    msg += ', gender ' + info['gender'].lower()
                msg += '.'
            self.status.showMessage(msg)
        elif import_error:
            self.status.showMessage(import_error)
        elif len(self.patient_ids) == 0:
            self.status.showMessage('No patients in database.')
        elif len(self.patient_ids) == 1:
            self.set_status_message(patient_id=next(iter(self.patient_ids)))
        else:
            self.status.showMessage('Select patient, %d patients in '
                                    'database.' % len(self.patient_ids))

    def show_message(self, msg):
        self.status.showMessage(msg)
        self.app.processEvents()

    def refresh_window(self):
        self.setCentralWidget(BPWidget(self.centralWidget().patient_id,
                                       self.patient_ids))

    def add_patient(self):
        dialog = PatientDialog(PatientDialog.ADD_PATIENT, self.patient_ids)
        info = dialog.run()
        if info:
            bpm_db.insert_patient(info)
            self.patient_ids[info['id']] = info
            self.refresh_window()

    def delete_patient(self):
        if not self.patient_ids:
            self.status.showMessage('Cannot delete patient, no patients yet.')
            return
        dialog = PatientDialog(PatientDialog.DELETE_PATIENT, self.patient_ids)
        info = dialog.run()
        if info:
            bpm_db.delete_patient(info)
            del self.patient_ids[info['id']]
            self.setCentralWidget(BPWidget(self.centralWidget().patient_id if
                                           self.centralWidget().patient_id !=
                                           info['id'] else None,
                                           self.patient_ids))

    def edit_patient(self):
        if not self.patient_ids:
            self.status.showMessage('Cannot edit patient, no patients yet.')
            return
        dialog = PatientDialog(PatientDialog.EDIT_PATIENT, self.patient_ids)
        info = dialog.run()
        if info:
            bpm_db.insert_patient(info)
            self.patient_ids[info['id']] = info
            self.refresh_window()

    def patient_id_callback(self, patient_id):
        # return patient_id, True   replace patient_id in bp monitor and
        #                           add measurements to database
        # return '', True           delete patient_id in bp monitor
        # return patient_id, False  add mesurements to database
        # return '', False          abort and don't update database
        if patient_id:
            if patient_id in self.patient_ids or not self.patient_ids:
                return patient_id, False

            if QMessageBox.question(self, 'New Patient Id',
                                    'Save new Patient Id "%s" to database?'
                                    % patient_id, QMessageBox.Save |
                                    QMessageBox.Cancel) == QMessageBox.Save:
                return patient_id, False

        if QMessageBox.question(self, 'Change Patient Id "%s"' % patient_id
                                if patient_id else "No Patient Id",
                                'Update Patient Id in Blood Pressure Monitor?',
                                QMessageBox.Ok |
                                QMessageBox.Cancel) == QMessageBox.Ok:
            dialog = PatientDialog(PatientDialog.UPDATE_ID if self.patient_ids
                                   else PatientDialog.ADD_PATIENT,
                                   self.patient_ids)
            info = dialog.run()
            self.app.processEvents()
            if info:
                bpm_db.insert_patient(info)
                self.patient_ids[info['id']] = info
                return info['id'], True
        return '', False

    def post_communication(self, bpm, update_id):
        QApplication.restoreOverrideCursor()

        if not update_id is None:
            self.status.showMessage('Patient ID ' +
                                    ('set to "%s".' % update_id if update_id
                                     else 'cleared.'))
        elif bpm.get_patient_id():
            if not bpm.get_patient_id() in self.patient_ids:
                self.show_message('Patient id "%s" received is not in database.'
                                  % bpm.get_patient_id())
                self.patient_ids[bpm.get_patient_id()] = { 'id' :
                                                          bpm.get_patient_id() }
            if bpm.get_measurements():
                bpm_db.insert_measurements(bpm.get_patient_id(),
                                             bpm.get_measurements(),
                                             self.status.showMessage)
            self.setCentralWidget(BPWidget(bpm.get_patient_id(),
                                           self.patient_ids))

    def bluetooth_connect(self, update_id=None):
        if QMessageBox.question(self, 'Start Bluetooth of Blood Pressure Monit'
                                'or ', 'Click OK when Bluetooth icon of Blood'
                                ' Pressure Monitor flashes. Press and hold '
                                'Start button for 8 seconds to get it '
                                'to flash.', QMessageBox.Ok |
                                QMessageBox.Cancel) != QMessageBox.Ok:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            bpm = bpm_bt.Microlife_BTLE(update_id, self.show_message)
            bpm.bluetooth_communication(self.patient_id_callback)

        except Exception as error:
            self.show_message(str(error))
            QApplication.restoreOverrideCursor()
            return

        self.post_communication(bpm, update_id)

    def usb_connect(self, update_id=None):
        if QMessageBox.question(self, 'Connect Blood Pressure Monit'
                                'or with USB cable', 'Click OK when Blood'
                                ' Pressure Monitor is connected via USB.',
                                QMessageBox.Ok |
                                QMessageBox.Cancel) != QMessageBox.Ok:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            with bpm_usb.Microlife_USB(update_id, self.show_message) as bpm:
                bpm.usb_communication(self.patient_id_callback)
                self.post_communication(bpm, update_id)
        except Exception as error:
            self.show_message(str(error))
            QApplication.restoreOverrideCursor()
            return

    # allows to select or add a patient
    def send_id(self, connect_fnc):
        if len(self.patient_ids) == 1:
            connect_fnc(update_id=next(iter(patient_ids)))
        elif QMessageBox.question(self, 'Update Patient Id',
                                'Update Patient Id of Blood Pressure Monitor?',
                                QMessageBox.Ok |
                                QMessageBox.Cancel) == QMessageBox.Ok:
            dialog = PatientDialog(PatientDialog.UPDATE_ID if self.patient_ids
                                   else PatientDialog.ADD_PATIENT,
                                   self.patient_ids)
            info = dialog.run()
            if info:
                bpm_db.insert_patient(info)
                self.patient_ids[info['id']] = info
                connect_fnc(update_id=info['id'])

    def clear_id(self, connect_fnc):
         if QMessageBox.question(self, 'Clear Patient Id',
                                'Clear Patient Id of Blood Pressure Monitor?',
                                QMessageBox.Ok |
                                QMessageBox.Cancel) == QMessageBox.Ok:
              connect_fnc(update_id='')

    def bluetooth_receive(self):
        self.bluetooth_connect()

    def bluetooth_send_id(self):
        self.send_id(self.bluetooth_connect)

    def bluetooth_clear_id(self):
        self.clear_id(self.bluetooth_connect)

    def usb_receive(self):
        self.usb_connect()

    def usb_send_id(self):
        self.send_id(self.usb_connect)

    def usb_clear_id(self):
        self.clear_id(self.usb_connect)

    # Import a Microlife .csv file into our database.
    def import_csv(self):
        try:
            filename,_ = QFileDialog.getOpenFileName(None, 'CSV Dialog',
                                                     os.getcwd(),
                                                     '.csv files (*.csv)')
            with open(filename) as file:
                bpm_db.import_csv(file, self.show_message, self.patient_ids)
        except Exception as error:
            self.status.showMessage(str(error))
        self.refresh_window()

    # Import Microlife Connect app's database into our database.
    def import_db(self):
        try:
            filename,_ = QFileDialog.getOpenFileName(None, 'DB Dialog',
                                                     os.getcwd(),
                                                     'Databases (DBMLBP*)')
            with open(filename) as file:
                bpm_db.import_db(file, self.show_message, self.patient_ids)
        except Exception as error:
            self.status.showMessage(str(error))
        self.refresh_window()


class BPWidget(QWidget):

    def __init__(self, patient_id, patient_ids):
        QWidget.__init__(self)

        self.disabled = False
        self.chart_range = (-1, -1)
        self.visible_rows = -1

        self.patient_id = patient_id
        self.table = self.load_contents(patient_ids[patient_id] if patient_id
                                                                else {})
        self.combo = QComboBox(self)
        if not self.patient_id: self.combo.addItem('')
        for id in patient_ids:
            self.combo.addItem(id_plus_name(id, patient_ids))
        self.combo.setCurrentText(id_plus_name(patient_id, patient_ids))
        self.combo.currentIndexChanged.connect(self.selection_change)

        # QWidget Layout
        self.main_layout = QHBoxLayout()

        self.left = QVBoxLayout()
        self.left.addWidget(self.combo, 1)
        self.left.addWidget(self.table, 7)
        self.table.verticalScrollBar().valueChanged.connect(self.scroll_change)
        self.main_layout.addLayout(self.left, 1)

        self.bpcanvas, self.pulcanvas = self.load_charts(
            self.data[len(self.data)-24:] if len(self.data) > 24 else self.data,
            patient_ids[patient_id] if patient_id else {})

        self.figures = QSplitter(Qt.Vertical)
        self.figures.addWidget(self.bpcanvas)
        self.figures.addWidget(self.pulcanvas)
        self.main_layout.addWidget(self.figures, 4)

        # Set the layout to the QWidget
        self.setLayout(self.main_layout)
        self.adjustSize()

    def load_contents(self, patient_info):
        if self.patient_id:
            self.data = bpm_db.read_measurements(self.patient_id)
        else:
            self.data = []
        return BloodPressureTable(self.data, patient_info)

    def load_charts(self, data, patient_info):
        SECS_PER_DAY = 60 * 60 * 24
        ddates = [d['date'].toSecsSinceEpoch() for d in data]
        dates = []
        xticks = []
        for d in ddates:
            day = secs_at_midnight(d)
            if not xticks or xticks[-1] != day: xticks.append(day)
            dates.append(len(xticks) - 1 + (d - day) / SECS_PER_DAY)
        xlabels = [QDateTime.fromSecsSinceEpoch(tck).toString(XAXIS_FMT)
                   for tck in xticks]
        xticks = [x for x in range(len(xticks))]

        bpfig = Figure(figsize=(800,600), dpi=72, facecolor=(1,1,1),
                       edgecolor=(0,0,0))
        ax = bpfig.add_subplot(111)
        ax.plot(dates, [d['sys'] for d in data], 'b')
        ax.plot(dates, [d['dia'] for d in data], 'g')
        if dates:
            systolic_limit = bpm_db.SYSTOLIC_LIMIT
            if 'systolic_limit' in patient_info:
                systolic_limit = patient_info['systolic_limit']
            diastolic_limit = bpm_db.DIASTOLIC_LIMIT
            if 'diastolic_limit' in patient_info:
                diastolic_limit = patient_info['diastolic_limit']
            xaxis = [xticks[0], dates[-1]]
            if systolic_limit:
                ax.plot(xaxis, [systolic_limit] * 2, 'r:')
            if diastolic_limit:
                ax.plot(xaxis, [diastolic_limit] * 2, 'r:')
            ax.grid(True)
        ax.set_ylabel('mm Hg')
        ax.set_title('Blood Pressure')
        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels)

        pulfig = Figure(figsize=(800,350), dpi=72, facecolor=(1,1,1),
                        edgecolor=(0,0,0))
        ax = pulfig.add_subplot(111)
        ax.plot(dates, [d['pulse'] for d in data], 'c')
        if dates: ax.grid(True)
        ax.set_ylabel('/ min')
        ax.set_title('Pulse')
        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels)

        return FigureCanvas(bpfig), FigureCanvas(pulfig)

    def selection_change(self, i):
        patient_id = self.combo.itemText(i).split(' ')[0]
        if not self.disabled and patient_id != self.patient_id:
            self.disabled = True
            self.parent().set_status_message(patient_id)
            self.parent().setCentralWidget(BPWidget(patient_id,
                                                    self.parent().patient_ids))

    def scroll_change(self):
        if not self.disabled:
            scroll_bar = self.table.verticalScrollBar()
            if scroll_bar.isVisible():
                value = scroll_bar.value()
                if self.visible_rows == -1:
                    self.visible_rows = 0
                    height = self.table.height()
                    for i in range(len(self.data)):
                        rect = self.table.visualItemRect(self.table.item(i, 1))
                        if rect.y() + rect.height() >= 0 and rect.y() < height:
                            self.visible_rows += 1
                if self.chart_range != (value, value+self.visible_rows):
                    self.chart_range = (value, value+self.visible_rows)
                    bpcanvas, pulcanvas = self.load_charts(self.data[value:
                        value+self.visible_rows],
                        self.parent().patient_ids[self.patient_id]
                                            if self.patient_id else {})
                    self.figures.replaceWidget(0, bpcanvas)
                    self.figures.replaceWidget(1, pulcanvas)
                    self.figures.refresh()
                    self.bpcanvas = bpcanvas
                    self.pulcanvas = pulcanvas


class BloodPressureTable(QTableWidget):

    def __init__(self, data, patient_info):
        QTableWidget.__init__(self, len(data), 4)
        self.setData(data, patient_info)

    def setData(self, data, patient_info):
        bold = QFont()
        bold.setBold(True)
        red = QColor(Qt.red)
        sys_limit = (patient_info["systolic_limit"]
                     if "systolic_limit" in patient_info
                     else bpm_db.SYSTOLIC_LIMIT)
        dia_limit = (patient_info["diastolic_limit"]
                     if "diastolic_limit" in patient_info
                     else bpm_db.DIASTOLIC_LIMIT)
        i = 0;
        for d in data:
            it0 = QTableWidgetItem(str(d["date"].toString(DATETIME_FMT)))
            it1 = QTableWidgetItem(str(d["sys"]))
            if d["sys"] >= sys_limit: it1.setFont(bold), it1.setForeground(red)
            it2 = QTableWidgetItem(str(d["dia"]))
            if d["dia"] >= dia_limit: it2.setFont(bold), it2.setForeground(red)
            it3 = QTableWidgetItem(str(d["pulse"]))
            j = 0
            for it in [it0, it1, it2, it3]:
                it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
                self.setItem(i, j, it)
                j += 1
            i += 1
        self.setHorizontalHeaderLabels(["  Date & Time  ", "Systolic",
                                        "Diastolic", "Pulse"])
        self.verticalHeader().setVisible(False)
        self.resizeRowsToContents()
        self.resizeColumnsToContents()
        self.verticalScrollBar().setValue(len(data))


class PatientDialog(QDialog):

    ADD_PATIENT    = 1
    EDIT_PATIENT   = 2
    UPDATE_ID      = 3
    DELETE_PATIENT = 4

    SYSTOLIC_DEFAULT  = 135
    DIASTOLIC_DEFAULT = 90

    def __init__(self, kind, patient_ids):
        QDialog.__init__(self)
        assert kind >= self.ADD_PATIENT and kind <= self.DELETE_PATIENT
        self.kind = kind
        self.patient_ids = patient_ids

        if kind == self.ADD_PATIENT:
            self.id = QLineEdit(self)
            self.id.setMaxLength(20)
        else:
            self.id = QComboBox(self)
            for ident in self.patient_ids:
                self.id.addItem(ident)
            self.id.currentIndexChanged.connect(self.selection_change)

        self.name = QLineEdit()
        self.name.setReadOnly(kind == self.DELETE_PATIENT)

        self.birthday = QDateEdit()
        self.birthday.displayFormat = bpm_db.BIRTHDAY_FMT
        self.birthday.setReadOnly(kind == self.DELETE_PATIENT)

        self.gender = QComboBox(self)
        for choice in ["Female", "Male", "Non-binary"]:
            self.gender.addItem(choice)

        self.sys_limit = QLineEdit(str(self.SYSTOLIC_DEFAULT))
        self.sys_limit.setValidator(QIntValidator(100,180))
        self.sys_limit.setReadOnly(kind == self.DELETE_PATIENT)

        self.dia_limit = QLineEdit(str(self.DIASTOLIC_DEFAULT))
        self.dia_limit.setValidator(QIntValidator(60,120))
        self.dia_limit.setReadOnly(kind == self.DELETE_PATIENT)

        if kind != self.ADD_PATIENT:
            self.selection_change(0)

        self.flo = QFormLayout()
        self.flo.addRow("Id",              self.id)
        self.flo.addRow("Full Name",       self.name)
        self.flo.addRow("Birthday",        self.birthday)
        self.flo.addRow("Gender",          self.gender)
        self.flo.addRow("Systolic limit",  self.sys_limit)
        self.flo.addRow("Diastolic limit", self.dia_limit)

        self.buttonBox = QDialogButtonBox((QDialogButtonBox.Ok
                                           if kind >= self.UPDATE_ID
                                           else QDialogButtonBox.Save) |
                                          QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addLayout(self.flo)
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)
        self.setWindowTitle("Add Patient" if kind == self.ADD_PATIENT else
                            "Delete Patient" if kind == self.DELETE_PATIENT else
                            "Edit Patient" if kind == self.EDIT_PATIENT else
                            "Update ID in Blood Pressure Monitor")
        self.setWindowModality(Qt.ApplicationModal)

    def selection_change(self, i):
        info = self.patient_ids[self.id.currentText()]
        self.name.setText(info['name'] if 'name' in info else "")
        self.birthday.setDate(QDate.fromString(info['birthday'],
                                            bpm_db.BIRTHDAY_FMT) if 'birthday'
                              in info else QDate.fromString("1/1/2000",
                                                        bpm_db.BIRTHDAY_FMT))
        self.gender.setCurrentText(info['gender'] if 'gender' in info
                                   else "Non-binary")
        self.sys_limit.setText(str(info['systolic_limit']) if 'systolic_limit'
                               in info else str(self.SYSTOLIC_DEFAULT))
        self.dia_limit.setText(str(info['diastolic_limit']) if 'diastolic_lim'
                               'it' in info else str(self.DIASTOLIC_DEFAULT))

    def run(self):
        if self.exec_():
            bd = self.birthday.date().toString(bpm_db.BIRTHDAY_FMT)
            return { 'id' : self.id.text() if self.kind == self.ADD_PATIENT
                            else self.id.currentText(),
                     'name' : self.name.text(),
                     'birthday' : bd,
                     'age' : bpm_db.age_from_birthday(bd),
                     'gender' : self.gender.currentText(),
                     'systolic_limit' : int(self.sys_limit.text()),
                     'diastolic_limit' : int(self.dia_limit.text()) }
        else:
            return None


########################################################
#                          Main                        #
########################################################

if __name__ == "__main__":

    # Qt Application
    app = QApplication(sys.argv)

    patient_ids = bpm_db.read_patient_ids()
    widget = BPWidget(next(iter(patient_ids)) if len(patient_ids) == 1
                                              else None,
                      patient_ids)

    main_window = MainWindow(widget, patient_ids, app)
    main_window.set_status_message()
    main_window.show()

    sys.exit(app.exec_())
