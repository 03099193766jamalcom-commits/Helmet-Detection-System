# ================================================================
#   Smart Helmet Detection System — database.py (Complete)
# ================================================================
import sqlite3
import datetime

DB_NAME = 'traffic_fines.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()

    # ---- Vehicle Registration Table ----
    c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
        plate       TEXT PRIMARY KEY,
        owner_name  TEXT NOT NULL,
        contact     TEXT,
        bike_model  TEXT,
        address     TEXT
    )''')

    # ---- Violations Table ----
    c.execute('''CREATE TABLE IF NOT EXISTS violations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        plate       TEXT NOT NULL,
        timestamp   TEXT NOT NULL,
        image_path  TEXT,
        fine_amount INTEGER DEFAULT 500,
        fine_status TEXT DEFAULT 'Pending'
    )''')

    # ---- Admin Table ----
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # ---- Dummy Vehicle Data ----
    dummy_vehicles = [
        ('ABC1234', 'Ali Khan',    '03001234567', 'Honda CD70',  'Karachi'),
        ('XYZ5678', 'Sara Ahmed',  '03119876543', 'Yamaha YBR',  'Lahore'),
        ('DEF9012', 'Ahmed Raza',  '03331122334', 'Honda CG125', 'Islamabad'),
        ('LMN3456', 'Usman Ali',   '03221234567', 'Suzuki GS150','Peshawar'),
        ('PQR7890', 'Fatima Noor', '03451234567', 'Honda CB150', 'Multan'),
    ]
    c.executemany(
        'INSERT OR IGNORE INTO vehicles VALUES (?,?,?,?,?)',
        dummy_vehicles
    )

    # ---- Default Admin Account ----
    c.execute(
        'INSERT OR IGNORE INTO admins (username, password) VALUES (?,?)',
        ('admin', 'admin123')
    )

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def log_violation(plate, timestamp, image_path):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute(
        'INSERT INTO violations (plate, timestamp, image_path) VALUES (?,?,?)',
        (plate, timestamp, image_path)
    )
    conn.commit()
    conn.close()


def get_vehicle_info(plate):
    conn   = sqlite3.connect(DB_NAME)
    c      = conn.cursor()
    c.execute('SELECT * FROM vehicles WHERE plate=?', (plate,))
    result = c.fetchone()
    conn.close()
    return result


def get_all_violations():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute('''
        SELECT
            v.id,
            v.plate,
            COALESCE(ve.owner_name, 'Unknown') as owner_name,
            v.timestamp,
            v.fine_amount,
            v.fine_status,
            v.image_path
        FROM violations v
        LEFT JOIN vehicles ve ON v.plate = ve.plate
        ORDER BY v.timestamp DESC
    ''')
    results = c.fetchall()
    conn.close()
    return results


def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()

    c.execute('SELECT COUNT(*) FROM violations')
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM violations WHERE fine_status='Pending'")
    pending = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM violations WHERE fine_status='Paid'")
    paid = c.fetchone()[0]

    c.execute("SELECT SUM(fine_amount) FROM violations")
    total_fine = c.fetchone()[0] or 0

    c.execute("SELECT SUM(fine_amount) FROM violations WHERE fine_status='Paid'")
    collected = c.fetchone()[0] or 0

    conn.close()
    return {
        'total':       total,
        'pending':     pending,
        'paid':        paid,
        'total_fine':  total_fine,
        'collected':   collected
    }


def verify_admin(username, password):
    conn   = sqlite3.connect(DB_NAME)
    c      = conn.cursor()
    c.execute(
        'SELECT * FROM admins WHERE username=? AND password=?',
        (username, password)
    )
    result = c.fetchone()
    conn.close()
    return result is not None


def mark_fine_paid(violation_id):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute(
        "UPDATE violations SET fine_status='Paid' WHERE id=?",
        (violation_id,)
    )
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()