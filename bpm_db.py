import argparse, csv, datetime, os, sqlite3, sys
from PyQt5.QtCore import QDate, QDateTime

########################################################
#                    Database Access                   #
########################################################

if sys.platform == 'win32':
    DB_DIRECTORY = os.path.join(os.path.expanduser('~'),
                                'AppData', 'Local', 'BPM')
else:
    DB_DIRECTORY = os.path.join(os.path.expanduser('~'),
                                '.local', 'share', 'bpm')
DB_FILE = os.path.join(DB_DIRECTORY, 'bpm.db')

DATETIME_FMT = 'yyyy-MM-dd HH:mm' # date and time stored in database as this
BIRTHDAY_FMT = 'M/d/yyyy'     # birthdays are stored in database in this format

SYSTOLIC_LIMIT  = 140  # unless specified otherwise in database
DIASTOLIC_LIMIT =  90

# given the birthday, return patient's age
def age_from_birthday(birthday):
    bd = QDate.fromString(birthday, BIRTHDAY_FMT)
    today = QDate.currentDate()
    age = today.year() - bd.year()
    if (today.month() < bd.month() or
        today.month() == bd.month() and today.day() < bd.day()):
        age -= 1
    return age

def open_db():
    if not os.path.exists(DB_DIRECTORY):
        os.makedirs(DB_DIRECTORY)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(""" CREATE TABLE IF NOT EXISTS measurements (
                  _id integer PRIMARY KEY,
                  patient_id text NOT NULL,
                  date text NOT NULL,
                  dia integer NOT NULL,
                  sys integer NOT NULL,
                  pulse integer NOT NULL); """)
    c.execute(""" CREATE TABLE IF NOT EXISTS patients (
                  _id integer PRIMARY KEY,
                  patient_id text NOT NULL,
                  patient_name text,
                  patient_birthday text,
                  patient_gender text,
                  systolic_limit integer,
                  diastolic_limit integer); """)
    return conn

# returns all the patient ids in database
def read_patient_ids():
    ids = {}
    with open_db() as conn:
        # get all patient id's from measurements table
        cur = conn.cursor()
        cur.execute("SELECT patient_id FROM measurements")
        s = set()
        for (id,) in cur.fetchall():
            if not id in s:
                s.add(id)
        # add patient id's from patients table
        cur.execute("SELECT patient_id FROM patients")
        for (id,) in cur.fetchall():
            if not id in s:
                s.add(id)
        # augment patient id's with patient info
        for id in sorted(s):
            cur.execute("SELECT patient_name,patient_birthday,patient_gender,"
                        "systolic_limit,diastolic_limit FROM patients "
                        "WHERE patient_id=?", (id,))
            info = { "id" : id }
            rows = cur.fetchall()
            if rows:
                row = rows[0]
                assert len(rows) == 1
                if row[0]: info["name"] = row[0]
                if row[1]:
                    info["birthday"] = row[1]
                    info["age"] = age_from_birthday(row[1])
                if row[2]: info["gender"] = row[2]
                if row[3]: info["systolic_limit"] = row[3]
                if row[4]: info["diastolic_limit"] = row[4]
            ids[id] = info
    return ids

# returns measurements for given patient from database
def read_measurements(patient_id):
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT date,dia,sys,pulse FROM measurements WHERE "
                    "patient_id=?", (patient_id,))
        data = cur.fetchall()
    rsl = [{'date' : QDateTime().fromString(d[0], DATETIME_FMT),
            'dia' : d[1], 'sys' : d[2], 'pulse' : d[3]} for d in data]
    return sorted(rsl, key=lambda d:d['date'])

# inserts measurements into database for given patient
def insert_measurements(patient_id, measurements, prnt = lambda s : print(s)):
    no_inserted = 0
    with open_db() as conn:
        cur = conn.cursor()
        for (date, sys, dia, pulse) in measurements:
            cur.execute("SELECT * FROM measurements WHERE date=? AND "
                        "patient_id=?", (date, patient_id))
            if not cur.fetchall():
                no_inserted += 1
                cur = conn.cursor()
                cur.execute(''' INSERT INTO measurements(patient_id,date,
                                                         sys,dia,pulse)
                                VALUES(?,?,?,?,?) ''',
                            (patient_id, date, sys, dia, pulse))
        prnt('Downloaded %d measurements, inserted %d into database %s.' %
             (len(measurements), no_inserted, DB_FILE))


# inserts patient into the database, deletes previous record if one exists
def insert_patient(info):
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE patient_id=?", (info["id"],))
        conn.commit()
        cur = conn.cursor()
        cur.execute("INSERT INTO patients(patient_id,patient_name,patient_birth"
                    "day,patient_gender,systolic_limit,diastolic_limit)"
                    "VALUES(?,?,?,?,?,?)",
                    (info["id"], info["name"], info["birthday"], info["gender"],
                     info["systolic_limit"], info["diastolic_limit"]))

# deletes a patient from database
def delete_patient(info):
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE patient_id=?", (info["id"],))
        cur.execute("DELETE FROM measurements WHERE patient_id=?",
                    (info["id"],))
        conn.commit()


######################################
# Import files from Microlife tools. #
######################################

# Import a Microlife .csv file into our database.
def import_csv(csvfile, prnt = lambda s : print(s),
               patient_ids = read_patient_ids()):
    patient_info = {}
    measurements = {}
    # find line "date,time,sys..." in csv file
    while True:
        position = csvfile.tell()
        line = csvfile.readline()
        if line == '':
            return # end-of-file
        if line.startswith('date,time,sys'):
            csvfile.seek(position)
            break
        data = line.split(',')
        if len(data) > 2 and data[1] != '""':
            patient_info[data[0]] = data[1]

    for row in csv.DictReader(csvfile):
        date  = row['date']
        time  = row['time']
        try:
            dt = datetime.datetime.strptime(date + ' ' + time,
                                            "%Y/%m/%d %I:%M %p")
        except Exception:
            continue
        measurements[dt] = row

    patient_id = patient_info["ID"]
    if not patient_id in patient_ids:
        bday_list = patient_info["Date of Birth"].split('/')
        assert len(bday_list[0]) == 4 # year is first in .csv
        bday = '%s/%s/%s' % (bday_list[1], bday_list[2], bday_list[0])
        info = { 'id' : patient_id,
                 'name' : patient_info["Given Name(s)"] + " " +
                          patient_info["Family Name"],
                 'birthday' : bday,
                 'age' : age_from_birthday(bday),
                 'gender' : patient_info["Sex"],
                 'systolic_limit' : SYSTOLIC_LIMIT,
                 'diastolic_limit' : DIASTOLIC_LIMIT }
        patient_ids[patient_id] = info
        insert_patient(info)

    no_inserted = 0
    with open_db() as conn:
        for dt, values in measurements.items():
            date = dt.strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()
            cur.execute("SELECT * FROM measurements WHERE date=? AND "
                        "patient_id=?", (date, patient_id))
            if not cur.fetchall():
                no_inserted += 1
                cur = conn.cursor()
                cur.execute(''' INSERT INTO measurements(patient_id,
                                                 date,sys,dia,pulse)
                                VALUES(?,?,?,?,?) ''',
                            (patient_id, date, values['sys(mmHg)'],
                             values['dia(mmHg)'],
                             values['pulse(P/min)']))

    prnt('Read %d measurements from %s for patient "%s", inserted %d into '
         'database %s.' % (len(measurements), csvfile.name, patient_id,
                           no_inserted, DB_FILE))

# Import Microlife Connect app's database into our database.
def import_db(file, prnt = lambda s : print(s),
              patient_ids = read_patient_ids()):
    file.close()
    with sqlite3.connect(file.name) as ml_conn:
        ml_cur = ml_conn.cursor()
        ml_cur.execute("SELECT person_userid,person_name,"
                       "person_birthday,person_gender,"
                       "systolic_limit,diastolic_limit "
                       "FROM person")
        for row in ml_cur.fetchall():
            if not row[0] in patient_ids:
                info = { 'id' : row[0], 'name' : row[1],
                         'birthday' : row[2],
                         'age' : age_from_birthday(row[2]),
                         'gender' : row[3],
                         'systolic_limit' : int(row[4]),
                         'diastolic_limit' : int(row[5]) }
                patient_ids[row[0]] = info
                insert_patient(info)

        no_inserted = 0
        no_measurements = 0
        with open_db() as conn:
            ml_cur.execute("SELECT name_id,date,sys,dia,pul "
                           "FROM contacts")
            for row in ml_cur.fetchall():
                no_measurements += 1
                patient_id = row[0]
                date = row[1]
                sys = row[2]
                dia = row[3]
                pulse = row[4]
                cur = conn.cursor()
                cur.execute("SELECT * FROM measurements WHERE date=? "
                            "AND patient_id=?", (date, patient_id))
                if not cur.fetchall():
                    no_inserted += 1
                    cur = conn.cursor()
                    cur.execute(''' INSERT INTO measurements(patient_id,
                                                     date,sys,dia,pulse)
                                    VALUES(?,?,?,?,?) ''',
                                (patient_id, date, sys, dia, pulse))
        prnt('Read %d measurements from %s, inserted %d into database %s.' %
             (no_measurements, file.name, no_inserted, DB_FILE))


##################################################################
# Functions used in command-line tools bpm_bt.py and bpm_usb.py. #
##################################################################

def patient_id_format(arg):
    if not arg or arg != arg.strip():
        raise argparse.ArgumentTypeError('not a valid patient id')
    return arg

def parse_commandline():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=patient_id_format,
                        help="Patient id to be sent to blood pressure monitor.")
    parser.add_argument("--import_csv", type=argparse.FileType('r'),
                        help="Import a .csv file written by Microlife's "
                             "Windows software.")
    parser.add_argument("--import_db", type=argparse.FileType('r'),
                        help="Import a database used by Microlife Connect "
                             "phone app.")
    args = parser.parse_args()

    files_imported = False
    if args.import_csv:
        files_imported = True
        import_csv(args.import_csv)
    if args.import_db:
        files_imported = True
        import_db(args.import_db)
    if files_imported: # import only, skip communication and exit
        sys.exit(0)
    return args

def patient_id_callback(patient_id):
    if not patient_id:
        print("Error: No patient id set in blood pressure monitor. "
              "Run with option '--id' to set one.", file=sys.stderr)
    return patient_id, False


if __name__ == '__main__':

    assert not 'Not a top-level Python module!'
