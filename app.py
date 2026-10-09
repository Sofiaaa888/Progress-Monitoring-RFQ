import os
import re
import random
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import uuid
import smtplib
import socket
from email.message import EmailMessage
from email.utils import formataddr
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, jsonify, g, send_from_directory,
                    has_request_context)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env.example'))
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "monitoring progress RFQ")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app = Flask(__name__)
app.secret_key = "sanoh-monitoring-rfq-secret-key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
EMAIL_NOTIFICATIONS_ENABLED = os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "true").lower() == "true"
NOTIFY_MANAGEMENT_CC = os.getenv("NOTIFY_MANAGEMENT_CC", "true").lower() == "true"
DIVISION_ENV_PREFIX = {
    "Marketing": "GROUP_MARKETING",
    "Engineer": "GROUP_ENGINEERING",
    "Purchasing": "GROUP_PURCHASING",
    "Management": "GROUP_MANAGEMENT",
}
GROUP_LABELS = {
    "Marketing": "Marketing",
    "Engineer": "Engineering",
    "Purchasing": "Purchasing",
    "Management": "Management",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _env_bool(value, default):
    return default if value in (None, "") else str(value).lower() == "true"


def get_smtp_account(division):
    """Akun SMTP untuk mengirim atas nama grup `division`.
    Jika akun grup belum lengkap (user/password/from), dipakai akun sistem.
    Host/port/starttls yang kosong di akun grup mengikuti akun sistem."""
    system = {
        "host": SMTP_HOST, "port": SMTP_PORT, "starttls": SMTP_STARTTLS,
        "user": SMTP_USER, "password": SMTP_PASSWORD, "from": SMTP_FROM,
        "label": "akun sistem",
    }
    prefix = DIVISION_ENV_PREFIX.get(division)
    if not prefix:
        return system
    user = os.getenv(f"{prefix}_SMTP_USER", "").strip()
    password = os.getenv(f"{prefix}_SMTP_PASSWORD", "")
    if not user or not password:
        return system
    return {
        "host": os.getenv(f"{prefix}_SMTP_HOST", "").strip() or SMTP_HOST,
        "port": int(os.getenv(f"{prefix}_SMTP_PORT", "").strip() or SMTP_PORT),
        "starttls": _env_bool(os.getenv(f"{prefix}_SMTP_STARTTLS"), SMTP_STARTTLS),
        "user": user, "password": password,
        "from": os.getenv(f"{prefix}_SMTP_FROM", "").strip() or user,
        "label": f"akun grup {division}",
    }


def _set_email_error(reason):
    """Simpan alasan gagal kirim email agar ikut tampil di pesan flash."""
    print(f"[EMAIL] {reason}")
    if has_request_context():
        g.email_error = reason


def _explain_smtp_error(exc, account):
    host, port = account.get("host"), account.get("port")
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (f"login ke {host} ditolak untuk akun {account.get('user')}. Cek app password "
                "(16 huruf tanpa spasi), pastikan verifikasi 2 langkah aktif, dan akun "
                "kampus/kantor tidak diblokir adminnya.")
    if isinstance(exc, socket.gaierror):
        return f"host SMTP '{host}' tidak ditemukan. Cek SMTP_HOST di .env (Gmail: smtp.gmail.com)."
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionRefusedError, OSError)) and not isinstance(exc, smtplib.SMTPException):
        return f"tidak bisa terhubung ke {host}:{port} ({exc}). Cek host, port, dan koneksi internet."
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return f"pengirim {account.get('from')} ditolak server. SMTP_FROM harus sama dengan akun yang login."
    return f"{type(exc).__name__}: {str(exc)[:200]}"


_orig_flash = flash


def flash(message, category="message"):
    """Sama seperti flask.flash, tetapi pesan 'GAGAL terkirim' ditambah penyebabnya."""
    reason = getattr(g, "email_error", "") if has_request_context() else ""
    if reason and "GAGAL terkirim" in message:
        message = f"{message} Penyebab: {reason}"
    return _orig_flash(message, category)


def get_group_member_emails(division):
    """Email semua user yang register di grup (divisi) tersebut."""
    db = get_db()
    rows = db.execute(
        "SELECT email FROM users WHERE divisi=? AND COALESCE(email,'') <> ''",
        (division,),
    ).fetchall()
    emails = []
    for r in rows:
        addr = (r["email"] or "").strip()
        if addr and addr.lower() not in [e.lower() for e in emails]:
            emails.append(addr)
    return emails


def send_email_notification(subject, body, recipient_divisions, attachment_path=None):
    """Kirim email ke seluruh anggota grup tujuan.
    Email keluar dari akun grup si pengirim (mis. user Marketing -> akun
    Marketing), sehingga penerima melihatnya sebagai email dari grup itu.
    Akun sistem menjadi penjembatan/cadangan: dipakai jika akun grup belum diisi."""
    if has_request_context():
        g.email_error = ""
    if not EMAIL_NOTIFICATIONS_ENABLED:
        _set_email_error("EMAIL_NOTIFICATIONS_ENABLED bernilai false di .env.")
        return False
    actor_group = session.get("divisi") if has_request_context() else None
    account = get_smtp_account(actor_group)
    if not account["host"] or not account["from"]:
        _set_email_error(f"SMTP untuk {account['label']} belum lengkap (host atau alamat pengirim kosong) di .env.")
        return False
    recipients = []
    empty_groups = []
    for division in (recipient_divisions or []):
        addresses = get_group_member_emails(division)
        if not addresses:
            empty_groups.append(GROUP_LABELS.get(division, division))
        for address in addresses:
            if address.lower() not in [r.lower() for r in recipients]:
                recipients.append(address)
    if not recipients:
        _set_email_error(
            f"belum ada anggota grup {', '.join(empty_groups) or 'tujuan'} yang emailnya terisi "
            "(user harus register atau mengisi email di halaman Profil)."
        )
        return False
    cc = []
    if NOTIFY_MANAGEMENT_CC and actor_group != "Management":
        taken = [r.lower() for r in recipients]
        cc = [a for a in get_group_member_emails("Management") if a.lower() not in taken]
    sender_name = (
        f"{GROUP_LABELS.get(actor_group, actor_group)} Group - Monitoring RFQ"
        if actor_group else "Monitoring Progress RFQ"
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, account["from"]))
    msg["To"] = ", ".join(recipients)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    if attachment_path and os.path.isfile(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                file_data = f.read()
            filename = os.path.basename(attachment_path)
            import mimetypes
            mime_type, _ = mimetypes.guess_type(filename)
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )
        except OSError as exc:
            _set_email_error(f"gagal membaca lampiran: {exc}")
            return False
    try:
        with smtplib.SMTP(account["host"], account["port"], timeout=15) as smtp:
            if account["starttls"]:
                smtp.starttls()
            if account["user"] and account["password"]:
                smtp.login(account["user"], account["password"])
            smtp.send_message(msg, to_addrs=recipients + cc)
        print(f"[EMAIL] Sent via {account['label']}: {subject} -> To: {recipients} Cc: {cc}")
        return True
    except Exception as exc:
        _set_email_error(_explain_smtp_error(exc, account))
        return False

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

CATEGORIES = ["Chasis", "Nylon", "Brazing"]
DIVISIONS = ["Marketing", "Engineer", "Purchasing", "Management"]
JUDGEMENT_TYPES = ["RFQ Customer Baru", "Commodity Baru"]
JUDGEMENT_DECISIONS = ["Go", "Perlu Diskusi", "No Go"]
ALLOWED_EXTENSIONS = {"zip", "rar", "7z", "pdf", "doc", "docx",
                      "xls", "xlsx", "dwg", "jpg", "jpeg", "png"}

RFQ_INPUT_ITEMS = [
    "Drawing 2D Customer (Note pada Drawing, Appearance check, Material, Surface treatment dll)",
    "Drawing 3D Customer",
    "Drawing Screenshoot",
    "Technical Standard Customer",
    "Volume / Year",
    "Special Characteristic (Jika ada)",
    "Customer current",
    "Customer New",
    "Current Process",
    "New Process",
    "Sample Produk",
]

RFQ_CONDITION_SCHEDULE = {
    "A": {
        "items": frozenset({
            "Drawing 2D Customer (Note pada Drawing, Appearance check, Material, Surface treatment dll)",
            "Drawing 3D Customer",
            "Technical Standard Customer",
            "Volume / Year",
            "Special Characteristic (Jika ada)",
            "Current Process",
            "Customer current",
        }),
        "hours": 22,
    },
    "B": {
        "items": frozenset({
            "Drawing 2D Customer (Note pada Drawing, Appearance check, Material, Surface treatment dll)",
            "Technical Standard Customer",
            "Volume / Year",
            "Special Characteristic (Jika ada)",
            "Current Process",
            "Customer current",
        }),
        "hours": 22,
    },
    "C": {
        "items": frozenset({
            "Drawing 3D Customer",
            "Technical Standard Customer",
            "Volume / Year",
            "Current Process",
            "Customer current",
        }),
        "hours": 35,
    },
    "D": {
        "items": frozenset({
            "Drawing 3D Customer",
            "Volume / Year",
            "Current Process",
            "Customer current",
        }),
        "hours": 47,
    },
    "E": {
        "items": frozenset({
            "Drawing 3D Customer",
            "Volume / Year",
            "Current Process",
            "Customer New",
        }),
        "hours": 56,
    },
    "F": {
        "items": frozenset({
            "Sample Produk",
            "Volume / Year",
            "Current Process",
        }),
        "hours": None,
    },
    "G": {
        "items": frozenset({
            "New Process",
            "Volume / Year",
            "Customer New",
        }),
        "hours": None,
    },
}

def determine_rfq_condition(selected_items):
    OPTIONAL_ITEMS = {"Special Characteristic (Jika ada)"}
    selected = frozenset(item for item in selected_items if item not in OPTIONAL_ITEMS)

    for condition, schedule in RFQ_CONDITION_SCHEDULE.items():
        standard_items = frozenset(item for item in schedule["items"] if item not in OPTIONAL_ITEMS)
        if selected == standard_items:
            return condition, schedule["hours"]

    return None, None 
def calculate_due_date_from_hours(start_dt, hours):
    if hours is None:
        return ""
    from datetime import timedelta
    return (start_dt + timedelta(hours=hours)).date().isoformat()
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


MAX_FILE_SIZE = {
    ".zip": 20 * 1024 * 1024,
    ".rar": 2 * 1024 * 1024,
    ".7z": 2 * 1024 * 1024,
    ".pdf": 2 * 1024 * 1024,
    ".doc": 2 * 1024 * 1024,
    ".docx": 2 * 1024 * 1024,
    ".xls": 2 * 1024 * 1024,
    ".xlsx": 2 * 1024 * 1024,
    ".dwg": 2 * 1024 * 1024,
    ".jpg": 2 * 1024 * 1024,
    ".jpeg": 2 * 1024 * 1024,
    ".png": 2 * 1024 * 1024,
}

def validate_file_size(file):
    filename = secure_filename(file.filename or "")
    extension = os.path.splitext(filename)[1].lower()
    max_size = MAX_FILE_SIZE.get(extension)
    if max_size is None:
        return False, "Batas ukuran untuk tipe file ini belum dikonfigurasi."
    try:
        file.stream.seek(0, os.SEEK_END)
        file_size = file.stream.tell()
        file.stream.seek(0)
    except (AttributeError, OSError):
        return False, "Ukuran file tidak dapat diperiksa."
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"Ukuran file terlalu besar. Maksimal {max_mb:g} MB untuk {extension}."
    return True, None

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Ukuran upload terlalu besar. ZIP maksimal 20 MB; file lainnya maksimal 2 MB.", "error")
    return redirect(request.referrer or url_for("progress"))
class MySQLCursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor
    def execute(self, sql, params=()):
        self.cursor.execute(sql.replace("?", "%s"), params or ())
        return self
    def executemany(self, sql, seq_params):
        self.cursor.executemany(sql.replace("?", "%s"), seq_params)
        return self
    def fetchone(self):
        return self.cursor.fetchone()
    def fetchall(self):
        return self.cursor.fetchall()
    @property
    def lastrowid(self):
        return self.cursor.lastrowid
    @property
    def rowcount(self):
        return self.cursor.rowcount
    def close(self):
        self.cursor.close()
class MySQLDB:
    def __init__(self, connection):
        self.connection = connection
    def execute(self, sql, params=()):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(sql.replace("?", "%s"), params or ())
        return MySQLCursorAdapter(cursor)
    def cursor(self):
        return MySQLCursorAdapter(self.connection.cursor())
    def executescript(self, script):
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)
    def commit(self):
        self.connection.commit()
    def rollback(self):
        self.connection.rollback()
    def close(self):
        self.connection.close()
def get_db():
    if "db" not in g:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
            )
            g.db = MySQLDB(conn)
        except Error as exc:
            raise RuntimeError(
                f"Tidak dapat terhubung ke MySQL '{MYSQL_DATABASE}'. "
                f"Pastikan MySQL XAMPP aktif dan database sudah dibuat. Detail: {exc}"
            ) from exc
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.after_request
def no_cache_for_pages(response):
    """Halaman HTML jangan di-cache browser, supaya tombol Kembali selalu menampilkan data terbaru
    (status, daftar file) dan tidak perlu refresh manual. File download dan static tidak terpengaruh."""
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(100) NOT NULL,
            password VARCHAR(255) NOT NULL,
            divisi VARCHAR(50) NOT NULL,
            email VARCHAR(255) DEFAULT '',
            UNIQUE(username, divisi)
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            model_name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL,
            year INT NOT NULL,
            month VARCHAR(20) NOT NULL,
            part_no VARCHAR(100) NOT NULL,
            due_date VARCHAR(10) DEFAULT '',

            redraw_status VARCHAR(30) NOT NULL DEFAULT 'Open',
            redraw_done INTEGER NOT NULL DEFAULT 0,
            redraw_total INTEGER NOT NULL DEFAULT 1,
            finish_good VARCHAR(50) DEFAULT '',
            komponen VARCHAR(50) DEFAULT '',
            drawing_tooling VARCHAR(50) DEFAULT '',
            drawing_pipa VARCHAR(50) DEFAULT '',
            redraw_note TEXT,
           
            review_status VARCHAR(30) NOT NULL DEFAULT 'Open',
            review_done INTEGER NOT NULL DEFAULT 0,
            review_total INTEGER NOT NULL DEFAULT 1,
            
            partlist_status VARCHAR(30) NOT NULL DEFAULT 'Open',
            partlist_done INTEGER NOT NULL DEFAULT 0,
            partlist_total INTEGER NOT NULL DEFAULT 1,
            partlist_note TEXT,
            quick_note TEXT
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            divisi VARCHAR(50) NOT NULL,
            author VARCHAR(100) NOT NULL,
            text TEXT,
            created_at VARCHAR(30) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS management_judgements (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            jenis VARCHAR(50) NOT NULL,
            customer VARCHAR(255) DEFAULT '',
            commodity VARCHAR(255) DEFAULT '',
            model_name VARCHAR(255) DEFAULT '',
            partnumber VARCHAR(100) DEFAULT '',
            keputusan VARCHAR(50) NOT NULL,
            catatan TEXT NOT NULL,
            author VARCHAR(100) NOT NULL,
            recipient_divisions VARCHAR(255) DEFAULT '',
            email_sent TINYINT DEFAULT 0,
            created_at VARCHAR(30) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rfq_notes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            divisi VARCHAR(50) NOT NULL,
            author VARCHAR(100) NOT NULL,
            customer VARCHAR(255) DEFAULT '',
            model_name VARCHAR(255) DEFAULT '',
            partnumber VARCHAR(100) DEFAULT '',
            category VARCHAR(50) DEFAULT '',
            text TEXT NOT NULL,
            recipient_divisions VARCHAR(255) DEFAULT '',
            email_sent TINYINT DEFAULT 0,
            created_at VARCHAR(30) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS redraw_files (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            approval_status VARCHAR(30) NOT NULL DEFAULT 'Belum Approval',
            uploaded_by VARCHAR(100) NOT NULL,
            divisi VARCHAR(50) NOT NULL,
            created_at VARCHAR(30) NOT NULL,
            progress_type VARCHAR(50) NOT NULL DEFAULT 'Finish Good',
            display_filename VARCHAR(255) NOT NULL DEFAULT 'Finish Good'
        );
        CREATE TABLE IF NOT EXISTS model_partlists (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            model_name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL,
            year INT NOT NULL,
            partlist_status VARCHAR(30) NOT NULL DEFAULT 'Open',
            partlist_done INTEGER NOT NULL DEFAULT 0,
            partlist_total INTEGER NOT NULL DEFAULT 1,
            partlist_note TEXT,
            created_at VARCHAR(30) NOT NULL DEFAULT '',
            UNIQUE(customer_id, model_name, category, year)
        );
        CREATE TABLE IF NOT EXISTS model_partlist_files (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            model_partlist_id INTEGER NOT NULL REFERENCES model_partlists(id) ON DELETE CASCADE,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            approval_status VARCHAR(30) NOT NULL DEFAULT 'Belum Approval',
            uploaded_by VARCHAR(100) NOT NULL,
            divisi VARCHAR(50) NOT NULL,
            created_at VARCHAR(30) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            description TEXT,
            customer VARCHAR(255) DEFAULT '',
            model_name VARCHAR(255) DEFAULT '',
            partnumber VARCHAR(100) DEFAULT '',
            category VARCHAR(50) DEFAULT 'Chasis',
            year INT,
            kondisi VARCHAR(20) DEFAULT '',
            due_date VARCHAR(10) DEFAULT '',
            part_id INTEGER REFERENCES parts(id) ON DELETE SET NULL,
            item_name VARCHAR(255) DEFAULT '',
            included_items TEXT,
            marketing_note TEXT DEFAULT '',
            note_target_divisions TEXT DEFAULT '',
            uploaded_by VARCHAR(100) NOT NULL,
            divisi VARCHAR(50) NOT NULL,
            created_at VARCHAR(30) NOT NULL
        );
        """
    )
    db.commit()
    user_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    fresh = int(user_count or 0) == 0
    migrate(db)
    if fresh:
        seed(db)
        migrate(db)
    db.execute(
        "INSERT IGNORE INTO users (username, password, divisi, email) VALUES (?,?,?,?)",
        ("management1", "management123", "Management", ""),
    )
    db.commit()
    backfill_demo_due_dates(db)

    db.execute("""
        UPDATE parts
        SET review_total=1,
            review_done=CASE WHEN review_done > 0 THEN 1 ELSE 0 END,
            review_status=CASE WHEN review_done > 0 THEN 'Close' ELSE 'Open' END
    """)
    db.execute("""
        UPDATE parts
        SET partlist_total=1,
            partlist_done=CASE WHEN partlist_done > 0 THEN 1 ELSE 0 END,
            partlist_status=CASE WHEN partlist_done > 0 THEN 'Close' ELSE 'Open' END
    """)
    db.execute("""
        UPDATE model_partlists
        SET partlist_total=1,
            partlist_done=CASE WHEN partlist_done > 0 THEN 1 ELSE 0 END,
            partlist_status=CASE WHEN partlist_done > 0 THEN 'Close' ELSE 'Open' END
    """)
    db.commit()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def migrate(db):
    extra_columns = [
        ("users", "email", "VARCHAR(255) DEFAULT ''"),
        ("parts", "redraw_note", "TEXT DEFAULT ''"),
        ("parts", "drawing_pipa", "TEXT DEFAULT ''"),
        ("parts", "partlist_note", "TEXT DEFAULT ''"),
        ("parts", "due_date", "TEXT DEFAULT ''"),
        ("parts", "year", "INT"),
        ("redraw_files", "progress_type", "TEXT NOT NULL DEFAULT 'Finish Good'"),
        ("redraw_files", "display_filename", "TEXT NOT NULL DEFAULT 'Finish Good'"),
        ("submissions", "description", "TEXT DEFAULT ''"),
        ("submissions", "customer", "TEXT DEFAULT ''"),
        ("submissions", "model_name", "TEXT DEFAULT ''"),
        ("submissions", "partnumber", "TEXT DEFAULT ''"),
        ("submissions", "category", "TEXT DEFAULT 'Chasis'"),
        ("submissions", "kondisi", "TEXT DEFAULT ''"),
        ("submissions", "due_date", "TEXT DEFAULT ''"),
        ("submissions", "year", "INT"),
        ("submissions", "part_id", "INTEGER REFERENCES parts(id) ON DELETE SET NULL"),
        ("submissions", "item_name", "TEXT DEFAULT ''"),
        ("submissions", "included_items", "TEXT DEFAULT ''"),
        ("submissions", "marketing_note", "TEXT DEFAULT ''"),
        ("submissions", "note_target_divisions", "TEXT DEFAULT ''"),
        ("notes", "attachment_filename", "VARCHAR(255) DEFAULT ''"),
        ("notes", "attachment_stored_filename", "VARCHAR(255) DEFAULT ''"),
        ("notes", "recipient_divisions", "TEXT DEFAULT ''"),
        ("model_partlists", "year", "INT"),
    ]
    for table, col, coltype in extra_columns:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        except Error:
            pass
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS model_partlists (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            model_name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL,
            year INT NOT NULL,
            partlist_status VARCHAR(30) NOT NULL DEFAULT 'Open',
            partlist_done INTEGER NOT NULL DEFAULT 0,
            partlist_total INTEGER NOT NULL DEFAULT 1,
            partlist_note TEXT,
            created_at VARCHAR(30) NOT NULL DEFAULT '',
            UNIQUE(customer_id, model_name, category)
        );
        CREATE TABLE IF NOT EXISTS model_partlist_files (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            model_partlist_id INTEGER NOT NULL REFERENCES model_partlists(id) ON DELETE CASCADE,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            approval_status VARCHAR(30) NOT NULL DEFAULT 'Belum Approval',
            uploaded_by VARCHAR(100) NOT NULL,
            divisi VARCHAR(50) NOT NULL,
            created_at VARCHAR(30) NOT NULL
        );
        """
    )
    db.execute(
        """INSERT IGNORE INTO model_partlists
           (customer_id, model_name, category, year, partlist_status, partlist_done, partlist_total, partlist_note, created_at)
           SELECT customer_id, model_name, category, year,
                  'Open', 0, 1, '', ''
           FROM parts
           GROUP BY customer_id, model_name, category"""
    )
    db.commit()
def get_or_create_model_partlist(db, customer_id, model_name, category, year=None):
    if year is None:
        year = datetime.now().year
    row = db.execute(
        "SELECT * FROM model_partlists WHERE customer_id=? AND model_name=? AND category=? AND year=?",
        (customer_id, model_name, category, year),
    ).fetchone()
    if row:
        return row
    new_id = db.execute(
        """INSERT INTO model_partlists
           (customer_id, model_name, category, year, partlist_status, partlist_done, partlist_total, created_at)
           VALUES (?,?,?,?,'Open',0,1,?)""",
        (customer_id, model_name, category, year, datetime.now().strftime('%d-%m-%Y %H:%M')),
    ).lastrowid
    return db.execute("SELECT * FROM model_partlists WHERE id=?", (new_id,)).fetchone()
def sync_model_partlist(db, model_partlist_id):
    row = db.execute("SELECT * FROM model_partlists WHERE id=?", (model_partlist_id,)).fetchone()
    if not row:
        return
    total = 1
    approved = db.execute(
        "SELECT COUNT(*) c FROM model_partlist_files WHERE model_partlist_id=? AND approval_status='Sudah Approval'",
        (model_partlist_id,),
    ).fetchone()['c']
    done = min(approved, total)
    status = 'Close' if done >= total else ('Pending' if approved > 0 else 'Open')
    db.execute(
        "UPDATE model_partlists SET partlist_done=?, partlist_status=?, partlist_total=1 WHERE id=?",
        (done, status, model_partlist_id),
    )
def sync_redraw_progress(db, part_id):
    part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        return
    fields = {
        "Finish Good": "finish_good",
        "Komponen": "komponen",
        "Drawing Tooling": "drawing_tooling",
        "Drawing Pipa": "drawing_pipa",
    }
    total = 0
    done = 0
    for ptype, field in fields.items():
        value = str(part[field] or "0").strip()
        qty = int(value) if value.isdigit() else 0
        total += qty
        approved = db.execute(
            "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
            (part_id, ptype),
        ).fetchone()["c"]
        done += min(approved, qty)
    if total > 0 and done >= total:
        status = "Close"
        done = total
    elif total > 0:
        status = "Pending"
    else:
        status = "Open"
    db.execute("UPDATE parts SET redraw_status=?, redraw_done=?, redraw_total=? WHERE id=?",
               (status, done, total, part_id))
def overall_progress(row):
    total = int(row["total_parts"] or 0)
    done = int(row["completed_parts"] or 0)
    if total and done >= total:
        return "Close"
    return f"{done}/{total}" if total else "0/0"
def fmt_status(status, done, total):
    if status == "Close":
        return "Close"
    return f"{int(done or 0)}/{int(total or 0)}"
def backfill_demo_due_dates(db):
    month_num = {name: i for i, name in enumerate(MONTHS, start=1)}
    rows = db.execute("SELECT id, month, year FROM parts WHERE COALESCE(due_date, '')='' ").fetchall()
    for r in rows:
        m = month_num.get(r["month"], 1)
        day = (int(r["id"]) % 25) + 1
        year = int(r["year"] or datetime.now().year)
        db.execute("UPDATE parts SET due_date=? WHERE id=?", (f"{year}-{m:02d}-{day:02d}", r["id"]))
    if rows:
        db.commit()
def seed(db):
    random.seed(42)
    cur = db.cursor()
    users = [
        ("marketing1", "marketing123", "Marketing", ""),
        ("engineer1", "engineer123", "Engineer", ""),
        ("purchasing1", "purchasing123", "Purchasing", ""),
    ]
    cur.executemany("INSERT INTO users (username, password, divisi, email) VALUES (?,?,?,?)", users)
    customer_names = ["PT A", "PT B", "PT C", "PT D"]
    for name in customer_names:
        cur.execute("INSERT INTO customers (name) VALUES (?)", (name,))
    db.commit()
    cur.execute("SELECT id FROM customers")
    customer_ids = [r[0] for r in cur.fetchall()]

    qty_per_month = {
        "January": 1, "February": 3, "March": 50, "April": 6, "May": 5,
        "June": 7, "July": 6, "August": 5, "September": 43, "October": 3,
        "November": 4, "December": 5,
    }
    statuses_weighted = ["Open", "Pending", "Pending", "Close"]

    for month, qty in qty_per_month.items():
        for i in range(qty):
            customer_id = random.choice(customer_ids)
            model_name = f"Model {random.choice('ABCDEFGH')}{random.randint(1,9)}"
            category = random.choice(CATEGORIES)
            n_parts = random.randint(1, 3)
            for p in range(1, n_parts + 1):
                def rand_progress():
                    status = random.choice(statuses_weighted)
                    total = random.randint(1, 5)
                    done = total if status == "Close" else random.randint(0, total - 1)
                    if status != "Close" and done == total:
                        status = "Close"
                    return status, done, total

                r_status, r_done, r_total = rand_progress()
                rv_done = 1 if random.choice(statuses_weighted) == "Close" else 0
                rv_total = 1
                rv_status = "Close" if rv_done else "Open"
                pl_done = 1 if random.choice(statuses_weighted) == "Close" else 0
                pl_total = 1
                pl_status = "Close" if pl_done else "Open"

                cur.execute(
                    """INSERT INTO parts (
                        customer_id, model_name, category, year, month, part_no, due_date,
                        redraw_status, redraw_done, redraw_total,
                        finish_good, komponen, drawing_tooling,
                        review_status, review_done, review_total,
                        partlist_status, partlist_done, partlist_total,
                        quick_note
                    ) VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?,?, ?)""",
                    (
                        customer_id, model_name, category, 2026, month, str(p),
                        f"2026-{MONTHS.index(month)+1:02d}-{(i % 25)+1:02d}",
                        r_status, r_done, r_total,
                        "Cek", "Cek", "Cek",
                        rv_status, rv_done, rv_total,
                        pl_status, pl_done, pl_total,
                        "",
                    ),
                )
    db.commit()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped
def current_divisi():
    return session.get("divisi")

def can_edit(field):
    divisi = current_divisi()
    if field in ("review", "redraw", "partlist"):
        return divisi == "Engineer"
    return False
def can_upload():
    return current_divisi() == "Engineer"
app.jinja_env.globals.update(can_edit=can_edit, fmt_status=fmt_status)

def other_divisions(actor_division):
    return [d for d in ("Marketing", "Engineer", "Purchasing") if d != actor_division]
def notify_new_rfq(part, filename, marketing_note='', recipients=None):
    actor = current_divisi()
    recipients = recipients or ["Engineer"]
    return send_email_notification(
        f"[Monitoring RFQ] Dokumen RFQ (Request For Quotation) baru - Model {part['model_name']} dengan Partnumber {part['part_no']}",
        f"""Dokumen RFQ baru telah dikirim.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
Partnumber : {part['part_no']}
Kategori : {part['category']}
Due Date : {part['due_date'] or '-'}
File     : {filename}
PIC: {session.get('username', '-')} ({actor})
Catatan:
{marketing_note or '-'}

Informasi selengkapnya silakan cek pada menu progress RFQ pada Monitoring RFQ.
""",
        recipients,
    )

def notify_redraw_requirement(part, progress_text):
    if current_divisi() != "Engineer":
        return False
    return send_email_notification(
        f"[Monitoring RFQ] Redraw diperbarui - Model {part['model_name']} dengan Partnumber {part['part_no']}",
        f"""Engineering telah memperbarui kebutuhan Redraw.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
Partnumber : {part['part_no']}
Kategori : {part['category']}

Drawing Require:
{progress_text}

PIC : {session.get('username', '-')} (Engineer)

informasi selengkapnya silakan cek menu Progress Redraw untuk melihat detail.
""",
        ["Marketing", "Purchasing"],
    )

def notify_progress_approval(part, progress_type, filename, approved):
    actor = current_divisi()
    recipients = ["Marketing", "Purchasing"]
    status = "Sudah Approval" if approved else "Belum Approval"
    return send_email_notification(
        f"[Monitoring RFQ] {progress_type} - {status} - Model {part['model_name']} dengan Partnumber {part['part_no']}",
        f"""Status approval progress telah diperbarui.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
Partnumber : {part['part_no']}
Progress : {progress_type}
File     : {filename}
Status   : {status}
PIC : {session.get('username', '-')} ({actor})

Informasi selengkapnya silakan cek menu Progress RFQ untuk melihat status terbaru.
""",
        recipients,
    )

def notify_file_submission(part, progress_type, filename):
    actor = current_divisi()
    return send_email_notification(
        f"[Monitoring RFQ] {progress_type} - File baru disubmit - Model {part['model_name']} dengan Partnumber {part['part_no']}",
        f"""File {progress_type} baru telah disubmit.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
Partnumber : {part['part_no']}
Progress : {progress_type}
File     : {filename}
PIC : {session.get('username', '-')} ({actor})

Informasi selengkapnya silakan cek menu Progress untuk melihat detail.
""",
        ["Marketing", "Purchasing"],
    )

def parse_note_targets(actor_division, always_include=None):
    """Ambil tujuan note dari form (checkbox `note_targets`). Hanya grup lain
    yang valid; urutan mengikuti DIVISIONS."""
    chosen = set(request.form.getlist("note_targets"))
    if always_include:
        chosen.add(always_include)
    return [d for d in DIVISIONS if d in chosen and d != actor_division]


def notify_standalone_note(text, recipients, customer="", model_name="", partnumber="", category=""):
    actor = current_divisi()
    ref = " - ".join(x for x in (model_name, f"P/N {partnumber}" if partnumber else "") if x)
    subject = f"[Monitoring RFQ] Note dari {GROUP_LABELS.get(actor, actor)}" + (f" - {ref}" if ref else "")
    return send_email_notification(
        subject,
        f"""Ada Note baru (tanpa pengiriman file) pada Monitoring RFQ.

Dari       : {session.get('username', '-')} ({actor})
Customer   : {customer or '-'}
Model      : {model_name or '-'}
Partnumber : {partnumber or '-'}
Kategori   : {category or '-'}

Note:
{text}
""",
        recipients,
    )


def notify_note(part, note_text):
    actor = current_divisi()
    recipients = other_divisions(actor)
    send_email_notification(
        f"[Monitoring RFQ] Note baru - Model {part['model_name']} dengan Partnumber {part['part_no']}",
        f"""Ada Note baru pada Monitoring RFQ.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
Partnumber : {part['part_no']}
Divisi : {actor}
Penulis : {session.get('username', '-')}

Note:
{note_text}
""",
        recipients,
    )

def get_customer_name(customer_id):
    db = get_db()
    row = db.execute("SELECT name FROM customers WHERE id=?", (customer_id,)).fetchone()
    return row["name"] if row else "-"


def verify_password(stored, given):
    """Mendukung hash baru dan password lama (plain text) dari data awal."""
    if not stored:
        return False
    if stored.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(stored, given)
    return stored == given


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        divisi = request.form.get("divisi", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND divisi=?",
            (username, divisi),
        ).fetchone()
        if user and verify_password(user["password"], password):
            if not user["password"].startswith(("scrypt:", "pbkdf2:")):
                db.execute("UPDATE users SET password=? WHERE id=?",
                           (generate_password_hash(password), user["id"]))
                db.commit()
            session["username"] = user["username"]
            session["divisi"] = user["divisi"]
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt)
        flash("Username, password, atau divisi salah.", "error")
    return render_template("login.html", divisions=DIVISIONS, group_labels=GROUP_LABELS)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = {"username": "", "email": "", "divisi": ""}
    if request.method == "POST":
        form["username"] = request.form.get("username", "").strip()
        form["email"] = request.form.get("email", "").strip()
        form["divisi"] = request.form.get("divisi", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        db = get_db()
        error = None
        if not form["username"] or not password:
            error = "Username dan password wajib diisi."
        elif form["divisi"] not in DIVISIONS:
            error = "Pilih grup user (role) yang valid."
        elif not EMAIL_RE.match(form["email"]):
            error = "Format email tidak valid."
        elif len(password) < 6:
            error = "Password minimal 6 karakter."
        elif password != confirm:
            error = "Konfirmasi password tidak sama."
        elif db.execute("SELECT 1 FROM users WHERE username=?",
                        (form["username"],)).fetchone():
            error = "Username sudah dipakai."
        elif db.execute("SELECT 1 FROM users WHERE LOWER(email)=LOWER(?)",
                        (form["email"],)).fetchone():
            error = "Email sudah terdaftar."
        if error:
            flash(error, "error")
        else:
            db.execute(
                "INSERT INTO users (username, password, divisi, email) VALUES (?,?,?,?)",
                (form["username"], generate_password_hash(password),
                 form["divisi"], form["email"]),
            )
            db.commit()
            flash(f"Registrasi berhasil. Anda masuk ke grup {GROUP_LABELS[form['divisi']]}. Silakan login.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", divisions=DIVISIONS,
                           group_labels=GROUP_LABELS, form=form)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username=? AND divisi=?",
        (session["username"], session["divisi"]),
    ).fetchone()
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not EMAIL_RE.match(email):
            flash("Format email tidak valid.", "error")
        elif db.execute("SELECT 1 FROM users WHERE LOWER(email)=LOWER(?) AND id<>?",
                        (email, user["id"])).fetchone():
            flash("Email sudah dipakai user lain.", "error")
        else:
            db.execute("UPDATE users SET email=? WHERE id=?", (email, user["id"]))
            db.commit()
            flash("Email berhasil diperbarui.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user,
                           group_label=GROUP_LABELS.get(user["divisi"], user["divisi"]))


@app.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    """Hapus akun sendiri (mis. pindah departemen / resign). Setelah dihapus,
    email user tidak lagi menerima notifikasi grup. Data riwayat (upload, note,
    judgement) tetap ada karena hanya menyimpan nama user."""
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username=? AND divisi=?",
        (session["username"], session["divisi"]),
    ).fetchone()
    if not user:
        session.clear()
        return redirect(url_for("login"))
    if not verify_password(user["password"], request.form.get("password", "")):
        flash("Password salah. Akun tidak dihapus.", "error")
        return redirect(url_for("profile"))
    if user["divisi"] == "Management":
        others = db.execute(
            "SELECT COUNT(*) AS c FROM users WHERE divisi='Management' AND id<>?",
            (user["id"],),
        ).fetchone()["c"]
        if not others:
            flash("Anda satu-satunya anggota Management, akun tidak bisa dihapus.", "error")
            return redirect(url_for("profile"))
    db.execute("DELETE FROM users WHERE id=?", (user["id"],))
    db.commit()
    session.clear()
    flash("Akun berhasil dihapus.", "success")
    return redirect(url_for("login"))




def overdue_months(db, year):
    """Bulan (nama) yang punya pekerjaan belum Close dengan due date hari ini
    atau sudah lewat. Pending yang due date-nya masih ke depan tidak dihitung."""
    today = datetime.now().date().isoformat()
    rows = db.execute(
        """SELECT DISTINCT p.month
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.year=?
             AND COALESCE(p.due_date, '') <> ''
             AND date(p.due_date) <= date(?)
             AND (p.redraw_status <> 'Close'
                  OR p.review_status <> 'Close'
                  OR COALESCE(mp.partlist_status,'Open') <> 'Close')""",
        (year, today),
    ).fetchall()
    return {r["month"] for r in rows}


def category_overdue_map(db, month, year=None):
    today = datetime.now().date().isoformat()
    if year is None:
        year = datetime.now().year
    rows = db.execute(
        """SELECT p.category,
                  MAX(CASE WHEN COALESCE(p.due_date, '') <> ''
                                AND date(p.due_date) <= date(?)
                                AND (p.redraw_status != 'Close'
                                     OR p.review_status != 'Close'
                                     OR COALESCE(mp.partlist_status,'Open') != 'Close')
                           THEN 1 ELSE 0 END) AS overdue
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.month=? AND p.year=?
           GROUP BY p.category""",
        (today, month, year),
    ).fetchall()
    return {r["category"]: bool(r["overdue"]) for r in rows}


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    current_year = datetime.now().year
    year_rows = db.execute("SELECT DISTINCT year FROM parts ORDER BY year DESC").fetchall()
    year_options = sorted(
        {current_year, current_year + 1, current_year + 2}
        | {int(r["year"]) for r in year_rows if r["year"] is not None},
        reverse=True,
    )
    selected_year = request.args.get("year", str(current_year), type=str)
    try:
        selected_year = int(selected_year)
    except (TypeError, ValueError):
        selected_year = current_year
    if selected_year not in year_options:
        year_options.append(selected_year)
        year_options.sort(reverse=True)

    total_rfq = db.execute(
        """SELECT COUNT(*) AS c
           FROM (
             SELECT customer_id, model_name
             FROM parts
             WHERE year=?
             GROUP BY customer_id, model_name
           ) x""",
        (selected_year,),
    ).fetchone()["c"]

    status_rows = db.execute(
        """SELECT
             p.customer_id,
             p.model_name,
             p.year,
             SUM(CASE
                   WHEN p.redraw_status='Close'
                    AND p.review_status='Close'
                    AND COALESCE(mp.partlist_status,'Open')='Close'
                   THEN 1 ELSE 0
                 END) AS completed_parts,
             COUNT(*) AS total_parts
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.year=?
           GROUP BY p.customer_id, p.model_name, p.year""",
        (selected_year,),
    ).fetchall()

    total_rfq_selesai = sum(
        1 for r in status_rows
        if int(r["total_parts"] or 0) > 0
        and int(r["completed_parts"] or 0) >= int(r["total_parts"] or 0)
    )
    total_rfq_pending = max(0, int(total_rfq) - total_rfq_selesai)

    qty_rows = db.execute(
        """SELECT month, COUNT(*) AS qty
           FROM (
             SELECT month, customer_id, model_name
             FROM parts
             WHERE year=?
             GROUP BY month, customer_id, model_name
           ) x
           GROUP BY month""",
        (selected_year,),
    ).fetchall()
    qty_by_month = {r["month"]: int(r["qty"]) for r in qty_rows}

    pending_rows = db.execute(
        """SELECT DISTINCT p.month
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.year=?
             AND (p.redraw_status <> 'Close'
                  OR p.review_status <> 'Close'
                  OR COALESCE(mp.partlist_status,'Open') <> 'Close')""",
        (selected_year,),
    ).fetchall()
    months_with_pending = {r["month"] for r in pending_rows}

    months_overdue = overdue_months(db, selected_year)
    month_table = []
    for m in MONTHS:
        qty = qty_by_month.get(m, 0)
        if qty == 0:
            status = "empty"
        elif m in months_with_pending:
            status = "overdue" if m in months_overdue else "pending"
        else:
            status = "done"
        month_table.append((m, qty, status))

    selected_month = request.args.get("month", "May")
    if selected_month not in MONTHS:
        selected_month = MONTHS[0]

    def category_progress_summary(month):
        rows = db.execute(
            """SELECT
                 m.category,
                 COUNT(*) AS total_models,
                 SUM(CASE WHEN m.parts_complete=1 AND m.partlist_status='Close'
                          THEN 1 ELSE 0 END) AS completed_models
               FROM (
                 SELECT
                   p.customer_id, p.model_name, p.category,
                   CASE WHEN SUM(
                          CASE WHEN p.redraw_status='Close'
                                AND p.review_status='Close'
                               THEN 1 ELSE 0 END
                        ) = COUNT(*)
                        THEN 1 ELSE 0 END AS parts_complete,
                   COALESCE(mp.partlist_status,'Open') AS partlist_status
                 FROM parts p
                 LEFT JOIN model_partlists mp
                   ON mp.customer_id=p.customer_id
                  AND mp.model_name=p.model_name
                  AND mp.category=p.category
                  AND mp.year=p.year
                 WHERE p.year=? AND p.month=?
                 GROUP BY p.customer_id,p.model_name,p.category,mp.partlist_status
               ) m
               GROUP BY m.category""",
            (selected_year, month),
        ).fetchall()
        row_map = {r["category"]: r for r in rows}
        overdue_map = category_overdue_map(db, month, selected_year)
        summary, close_values, open_values = [], [], []
        for cat in CATEGORIES:
            r = row_map.get(cat)
            total = int(r["total_models"] or 0) if r else 0
            done = int(r["completed_models"] or 0) if r else 0
            summary.append({
                "name": cat,
                "count": total,
                "status": "Close" if total and done >= total else (f"{done}/{total}" if total else "-"),
                "overdue": overdue_map.get(cat, False),
            })
            close_values.append(done)
            open_values.append(max(0, total-done))
        return summary, close_values, open_values

    category_summary, close_chart_values, open_chart_values = category_progress_summary(selected_month)

    redraw_pending = db.execute(
        "SELECT COUNT(*) AS c FROM parts WHERE year=? AND redraw_status <> 'Close'",
        (selected_year,),
    ).fetchone()["c"]
    review_pending = db.execute(
        "SELECT COUNT(*) AS c FROM parts WHERE year=? AND review_status <> 'Close'",
        (selected_year,),
    ).fetchone()["c"]
    partlist_pending = db.execute(
        """SELECT COUNT(*) AS c
           FROM (
             SELECT p.customer_id,p.model_name,p.category
             FROM parts p
             LEFT JOIN model_partlists mp
               ON mp.customer_id=p.customer_id
              AND mp.model_name=p.model_name
              AND mp.category=p.category
              AND mp.year=p.year
             WHERE p.year=? AND COALESCE(mp.partlist_status,'Open') <> 'Close'
             GROUP BY p.customer_id,p.model_name,p.category
           ) x""",
        (selected_year,),
    ).fetchone()["c"]

    pending_months = db.execute(
        """SELECT DISTINCT p.month
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.year=?
             AND (p.redraw_status <> 'Close'
                  OR p.review_status <> 'Close'
                  OR COALESCE(mp.partlist_status,'Open') <> 'Close')""",
        (selected_year,),
    ).fetchall()
    pending_months_sorted = [m for m in MONTHS if m in {r["month"] for r in pending_months}]

    return render_template(
        "rfq.html",
        month_table=month_table,
        total_rfq=total_rfq,
        total_rfq_selesai=total_rfq_selesai,
        total_rfq_pending=total_rfq_pending,
        selected_year=selected_year,
        year_options=year_options,
        selected_month=selected_month,
        category_summary=category_summary,
        close_chart_values=close_chart_values,
        open_chart_values=open_chart_values,
        redraw_pending=redraw_pending,
        review_pending=review_pending,
        partlist_pending=partlist_pending,
        pending_months=pending_months_sorted,
    )


@app.route("/dashboard/rfqs/<status>")
@login_required
def dashboard_rfqs(status):
    if status not in ("close", "pending"):
        return redirect(url_for("dashboard"))

    db = get_db()
    year = request.args.get("year", datetime.now().year, type=int)
    rows = db.execute(
        """SELECT
             p.customer_id, c.name AS customer, p.model_name, p.year,
             COUNT(*) AS total_parts,
             SUM(CASE
                   WHEN p.redraw_status='Close'
                    AND p.review_status='Close'
                    AND COALESCE(mp.partlist_status,'Open')='Close'
                   THEN 1 ELSE 0 END) AS completed_parts,
             GROUP_CONCAT(DISTINCT p.category ORDER BY p.category SEPARATOR ', ') AS categories
           FROM parts p
           JOIN customers c ON c.id=p.customer_id
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.year=?
           GROUP BY p.customer_id,c.name,p.model_name,p.year
           ORDER BY c.name,p.model_name""",
        (year,),
    ).fetchall()

    rfqs = []
    for r in rows:
        is_close = int(r["total_parts"] or 0) > 0 and int(r["completed_parts"] or 0) >= int(r["total_parts"] or 0)
        if (status == "close" and is_close) or (status == "pending" and not is_close):
            rfqs.append(r)

    return render_template(
        "dashboard_rfqs.html",
        rfqs=rfqs,
        status=status,
        year=year,
    )


@app.route("/dashboard/rfqs/<int:customer_id>/<path:model_name>/<int:year>")
@login_required
def dashboard_rfq_model_detail(customer_id, model_name, year):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not customer:
        flash("Customer tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    status = request.args.get("status", "close")

    raw_parts = db.execute(
        """SELECT p.*, mp.id AS model_partlist_id,
                 COALESCE(mp.partlist_status, 'Open') AS model_partlist_status,
                 COALESCE(mp.partlist_done, 0) AS model_partlist_done,
                 COALESCE(mp.partlist_total, 1) AS model_partlist_total
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id
            AND mp.model_name=p.model_name
            AND mp.category=p.category
            AND mp.year=p.year
           WHERE p.customer_id=? AND p.model_name=? AND p.year=?
           ORDER BY p.category, p.part_no""",
        (customer_id, model_name, year),
    ).fetchall()

    if not raw_parts:
        flash("Data RFQ untuk model ini tidak ditemukan.", "error")
        return redirect(url_for("dashboard_rfqs", status=status, year=year))

    model_counts = {}
    for r in raw_parts:
        key = (r["model_name"], r["category"])
        model_counts[key] = model_counts.get(key, 0) + 1
    seen = set()
    parts = []
    for r in raw_parts:
        item = dict(r)
        key = (r["model_name"], r["category"])
        item["show_partlist"] = key not in seen
        item["model_span"] = model_counts[key]
        seen.add(key)
        parts.append(item)

    return render_template(
        "dashboard_rfq_model_detail.html",
        customer=customer,
        model_name=model_name,
        year=year,
        status=status,
        parts=parts,
    )


@app.route("/months/<month>")
@login_required
def months_fragment(month):
    db = get_db()
    year = request.args.get("year", datetime.now().year, type=int)
    rows = db.execute(
        """SELECT m.category,
                  COUNT(*) AS total_models,
                  SUM(CASE WHEN m.parts_complete=1 AND m.partlist_status='Close'
                           THEN 1 ELSE 0 END) AS completed_models
           FROM (
               SELECT p.customer_id, p.model_name, p.category,
                      CASE WHEN SUM(CASE WHEN p.redraw_status='Close'
                                              AND p.review_status='Close'
                                         THEN 1 ELSE 0 END)=COUNT(*)
                           THEN 1 ELSE 0 END AS parts_complete,
                      COALESCE(mp.partlist_status, 'Open') AS partlist_status
               FROM parts p
               LEFT JOIN model_partlists mp
                 ON mp.customer_id=p.customer_id
                AND mp.model_name=p.model_name
                AND mp.category=p.category
               WHERE p.month=? AND p.year=?
               GROUP BY p.customer_id, p.model_name, p.category, mp.partlist_status
           ) m
           GROUP BY m.category""",
        (month, year),
    ).fetchall()
    row_map = {r["category"]: r for r in rows}
    overdue_map = category_overdue_map(db, month, year)
    category_summary = []
    for cat in CATEGORIES:
        r = row_map.get(cat)
        count = int(r["total_models"] or 0) if r else 0
        done = int(r["completed_models"] or 0) if r else 0
        status_label = "Close" if count and done >= count else (f"{done}/{count}" if count else "-")
        category_summary.append({
            "name": cat,
            "count": count,
            "status": status_label,
            "overdue": overdue_map.get(cat, False),
        })
    return render_template("months.html", category_summary=category_summary, month=month, selected_year=year, selected_month=month)


@app.route("/months-chart/<month>")
@login_required
def months_chart(month):
    if month not in MONTHS:
        month = MONTHS[0]
    db = get_db()
    year = request.args.get("year", datetime.now().year, type=int)
    rows = db.execute(
        """SELECT m.category,
                  COUNT(*) AS total_models,
                  SUM(CASE WHEN m.parts_complete=1 AND m.partlist_status='Close'
                           THEN 1 ELSE 0 END) AS completed_models
           FROM (
               SELECT p.customer_id, p.model_name, p.category,
                      CASE WHEN SUM(CASE WHEN p.redraw_status='Close'
                                              AND p.review_status='Close'
                                         THEN 1 ELSE 0 END)=COUNT(*)
                           THEN 1 ELSE 0 END AS parts_complete,
                      COALESCE(mp.partlist_status, 'Open') AS partlist_status
               FROM parts p
               LEFT JOIN model_partlists mp
                 ON mp.customer_id=p.customer_id
                AND mp.model_name=p.model_name
                AND mp.category=p.category
               WHERE p.month=? AND p.year=?
               GROUP BY p.customer_id, p.model_name, p.category, mp.partlist_status
           ) m
           GROUP BY m.category""",
        (month, year),
    ).fetchall()
    row_map = {r["category"]: r for r in rows}
    close_values, open_values = [], []
    for cat in CATEGORIES:
        r = row_map.get(cat)
        total = int(r["total_models"] or 0) if r else 0
        done = int(r["completed_models"] or 0) if r else 0
        close_values.append(done)
        open_values.append(max(0, total-done))
    return jsonify({
        "month": month,
        "labels": CATEGORIES,
        "close": close_values,
        "open": open_values,
    })


@app.route("/progress")
@login_required
def progress():
    db = get_db()
    category = request.args.get("category", "Chasis")
    selected_month = request.args.get("month", "")
    selected_year = request.args.get("year", "", type=int)
    if category not in CATEGORIES:
        category = "Chasis"
    if selected_month and selected_month not in MONTHS:
        selected_month = ""

    where = "WHERE p.category=?"
    params = [category]
    if selected_year:
        where += " AND p.year=?"
        params.append(selected_year)
    if selected_month:
        where += " AND p.month=?"
        params.append(selected_month)

    rows = db.execute(
        f"""SELECT p.customer_id, c.name customer, COUNT(p.id) total_parts,
                  SUM(CASE WHEN p.redraw_status='Close' AND p.review_status='Close'
                           AND COALESCE(mp.partlist_status, 'Open')='Close'
                           THEN 1 ELSE 0 END) completed_parts
           FROM parts p
           JOIN customers c ON c.id=p.customer_id
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id AND mp.model_name=p.model_name AND mp.category=p.category AND mp.year=p.year
           {where}
           GROUP BY p.customer_id, c.name
           HAVING SUM(CASE WHEN p.redraw_status='Close' AND p.review_status='Close'
                           AND COALESCE(mp.partlist_status, 'Open')='Close'
                           THEN 1 ELSE 0 END) < COUNT(p.id)
           ORDER BY c.name""",
        params,
    ).fetchall()
    models = [{
        "customer_id": r["customer_id"], "customer": r["customer"],
        "partnumber": r["total_parts"], "progres": overall_progress(r)
    } for r in rows]
    return render_template("progress.html", category=category, categories=CATEGORIES,
                           models=models, selected_month=selected_month, selected_year=selected_year)


@app.route("/progress/<category>/<int:customer_id>")
@login_required
def progress_model(category, customer_id):
    db = get_db()
    if category not in CATEGORIES:
        return redirect(url_for("progress"))
    customer = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not customer:
        return redirect(url_for("progress", category=category))

    selected_month = request.args.get("month", "")
    selected_year = request.args.get("year", "", type=int)
    if selected_month and selected_month not in MONTHS:
        selected_month = ""

    where = "WHERE p.category=? AND p.customer_id=?"
    params = [category, customer_id]
    if selected_year:
        where += " AND p.year=?"
        params.append(selected_year)
    if selected_month:
        where += " AND p.month=?"
        params.append(selected_month)

    raw_parts = db.execute(
        f"""SELECT p.*, mp.id AS model_partlist_id,
                  COALESCE(mp.partlist_status, 'Open') AS model_partlist_status,
                  COALESCE(mp.partlist_done, 0) AS model_partlist_done,
                  COALESCE(mp.partlist_total, 1) AS model_partlist_total
           FROM parts p
           LEFT JOIN model_partlists mp
             ON mp.customer_id=p.customer_id AND mp.model_name=p.model_name AND mp.category=p.category AND mp.year=p.year
           {where}
           ORDER BY p.model_name, p.part_no""",
        params,
    ).fetchall()

    parts = []
    model_counts = {}
    for r in raw_parts:
        model_counts[r['model_name']] = model_counts.get(r['model_name'], 0) + 1
    seen = set()
    for r in raw_parts:
        item = dict(r)
        key = r['model_name']
        item['show_partlist'] = key not in seen
        item['model_span'] = model_counts[key]
        seen.add(key)
        parts.append(item)

    return render_template("progress.html", category=category, categories=CATEGORIES,
                           customer=customer, parts=parts, drill=True,
                           selected_month=selected_month, selected_year=selected_year)


@app.route("/model-partlist/<int:model_partlist_id>", methods=["GET", "POST"])
@login_required
def model_partlist_detail(model_partlist_id):
    db = get_db()
    mp = db.execute("SELECT * FROM model_partlists WHERE id=?", (model_partlist_id,)).fetchone()
    if not mp:
        flash("Partlist model tidak ditemukan.", "error")
        return redirect(url_for("progress"))
    customer = db.execute("SELECT * FROM customers WHERE id=?", (mp['customer_id'],)).fetchone()

    if request.method == "POST":
        action = request.form.get("action")
        if not can_edit("partlist"):
            flash("Anda tidak memiliki akses untuk mengubah Partlist.", "error")
        elif action == "save_partlist":
            db.execute("UPDATE model_partlists SET partlist_total=1, partlist_note=? WHERE id=?",
                       (request.form.get("partlist_note", ""), model_partlist_id))
            sync_model_partlist(db, model_partlist_id)
            db.commit()
            flash("Partlist model berhasil disimpan.", "success")
            return redirect(url_for("model_partlist_detail", model_partlist_id=model_partlist_id, month=request.args.get("month", "")))
        elif action == "upload":
            file = request.files.get("file")
            if not file or not file.filename:
                flash("Pilih file terlebih dahulu.", "error")
            elif not allowed_file(file.filename):
                flash("Tipe file tidak didukung.", "error")
            elif (size_error := validate_file_size(file)[1]) is not None:
                flash(size_error, "error")
            else:
                existing = db.execute(
                    "SELECT id FROM model_partlist_files WHERE model_partlist_id=? LIMIT 1",
                    (model_partlist_id,)
                ).fetchone()
                if existing:
                    flash("Partlist untuk model ini sudah ada. Hapus file lama terlebih dahulu jika ingin menggantinya.", "error")
                    return redirect(url_for("model_partlist_detail", model_partlist_id=model_partlist_id))
                original_name = secure_filename(file.filename)
                stored_name = f"{uuid.uuid4().hex}_{original_name}"
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
                db.execute(
                    """INSERT INTO model_partlist_files
                       (model_partlist_id, original_filename, stored_filename, approval_status, uploaded_by, divisi, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (model_partlist_id, original_name, stored_name, "Belum Approval",
                     session['username'], current_divisi(), datetime.now().strftime("%d-%m-%Y %H:%M")),
                )
                email_sent = send_email_notification(
                    f"[Monitoring RFQ] Partlist - File baru disubmit - {mp['model_name']}",
                    f"""File Partlist baru telah disubmit.

Customer : {customer['name']}
Model    : {mp['model_name']}
Kategori : {mp['category']}
Progress : Partlist
File     : {original_name}
Diupload oleh : {session.get('username', '-')} ({current_divisi()})

Silakan cek menu Progress untuk melihat detail.
""",
                    ["Marketing", "Purchasing"],
                )
                db.commit()
                if email_sent:
                    flash("File Partlist berhasil diupload. Notifikasi email terkirim ke Marketing & Purchasing.", "success")
                else:
                    flash("File Partlist berhasil diupload, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.", "warning")
                return redirect(url_for("model_partlist_detail", model_partlist_id=model_partlist_id, month=request.args.get("month", "")))

        elif action in ("approve", "unapprove", "delete"):
            file_id = request.form.get("file_id", type=int)
            row = db.execute("SELECT * FROM model_partlist_files WHERE id=? AND model_partlist_id=?",
                             (file_id, model_partlist_id)).fetchone()
            if not row:
                flash("File tidak ditemukan.", "error")
            elif action == "approve":
                db.execute("UPDATE model_partlist_files SET approval_status='Sudah Approval' WHERE id=?", (file_id,))
                sync_model_partlist(db, model_partlist_id)
                db.commit()
                email_sent = send_email_notification(
                    f"[Monitoring RFQ] Partlist - Sudah Approval - {mp['model_name']}",
                    f"""Status approval progress berubah.

Customer : {customer['name']}
Model    : {mp['model_name']}
Kategori : {mp['category']}
Progress : Partlist
File     : {row['original_filename']}
Status   : Sudah Approval
Diubah oleh : {session.get('username', '-')} ({current_divisi()})

Silakan cek menu Progress untuk melihat status terbaru.
""",
                    ["Marketing", "Purchasing"],
                )
                flash(
                    "Status diubah ke Sudah Approval. Notifikasi email terkirim ke Marketing & Purchasing."
                    if email_sent else
                    "Status diubah ke Sudah Approval, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.",
                    "success" if email_sent else "warning",
                )
            elif action == "unapprove":
                db.execute("UPDATE model_partlist_files SET approval_status='Belum Approval' WHERE id=?", (file_id,))
                sync_model_partlist(db, model_partlist_id)
                db.commit()
                email_sent = send_email_notification(
                    f"[Monitoring RFQ] Partlist - Approval dibatalkan - {mp['model_name']}",
                    f"""Status approval progress berubah.

Customer : {customer['name']}
Model    : {mp['model_name']}
Kategori : {mp['category']}
Progress : Partlist
File     : {row['original_filename']}
Status   : Belum Approval
Diubah oleh : {session.get('username', '-')} ({current_divisi()})

Silakan cek menu Progress untuk melihat status terbaru.
""",
                    ["Marketing", "Purchasing"],
                )
                flash(
                    "Status diubah ke Belum Approval. Notifikasi email terkirim ke Marketing & Purchasing."
                    if email_sent else
                    "Status diubah ke Belum Approval, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.",
                    "success" if email_sent else "warning",
                )
            else:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row['stored_filename']))
                except OSError:
                    pass
                db.execute("DELETE FROM model_partlist_files WHERE id=?", (file_id,))
                sync_model_partlist(db, model_partlist_id)
                db.commit()

        return redirect(url_for("model_partlist_detail", model_partlist_id=model_partlist_id, month=request.args.get("month", "")))

    mp = db.execute("SELECT * FROM model_partlists WHERE id=?", (model_partlist_id,)).fetchone()
    files = db.execute("SELECT * FROM model_partlist_files WHERE model_partlist_id=? ORDER BY id DESC",
                       (model_partlist_id,)).fetchall()
    return render_template("model_partlist_detail.html", mp=mp, customer=customer, files=files)


@app.route("/model-partlist-files/<path:stored_filename>")
@login_required
def download_model_partlist_file(stored_filename):
    db = get_db()
    row = db.execute("SELECT original_filename FROM model_partlist_files WHERE stored_filename=?", (stored_filename,)).fetchone()
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_filename,
                               as_attachment=True,
                               download_name=row['original_filename'] if row else stored_filename)


@app.route("/redraw/<int:part_id>", methods=["GET", "POST"])
@login_required
def redraw_detail(part_id):
    db = get_db()
    part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        flash("Data tidak ditemukan.", "error")
        return redirect(url_for("progress"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_redraw" and can_edit("redraw"):
            db.execute(
                "UPDATE parts SET finish_good=?, komponen=?, drawing_tooling=?, drawing_pipa=?, redraw_note=? WHERE id=?",
                (request.form.get("finish_good", "0"), request.form.get("komponen", "0"),
                 request.form.get("drawing_tooling", "0"), request.form.get("drawing_pipa", "0"),
                 request.form.get("redraw_note", ""), part_id),
            )
            sync_redraw_progress(db, part_id)
            db.commit()
            updated_part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
            email_sent = notify_redraw_requirement(
                updated_part,
                f"Finish Good: {updated_part['finish_good'] or 0}\n"
                f"Komponen: {updated_part['komponen'] or 0}\n"
                f"Drawing Tooling: {updated_part['drawing_tooling'] or 0}\n"
                f"Drawing Pipa: {updated_part['drawing_pipa'] or 0}"
            )
            if email_sent:
                flash("Kebutuhan Redraw berhasil disimpan. Notifikasi email terkirim ke Marketing & Purchasing.", "success")
            elif email_sent is False and current_divisi() == "Engineer":
                flash("Kebutuhan Redraw berhasil disimpan, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.", "warning")
            else:
                flash("Kebutuhan Redraw berhasil disimpan.", "success")
        elif action == "save_review" and can_edit("review"):
            new_status = request.form.get("review_status", part["review_status"])
            db.execute(
                "UPDATE parts SET review_status=?, review_done=?, review_total=? WHERE id=?",
                (
                    new_status,
                    1 if request.form.get("review_done", part["review_done"], type=int) > 0 else 0,
                    1,
                    part_id,
                ),
            )
            db.commit()
            updated_part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
            email_sent = notify_progress_approval(updated_part, "Drawing Review", "-", new_status == "Sudah Approval")
            if email_sent:
                flash("Drawing Review berhasil disimpan. Notifikasi email terkirim ke Marketing & Purchasing.", "success")
            else:
                flash("Drawing Review berhasil disimpan, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.", "warning")
        elif action == "save_partlist" and can_edit("partlist"):
            new_status = request.form.get("partlist_status", part["partlist_status"])
            db.execute(
                "UPDATE parts SET partlist_note=?, partlist_status=?, partlist_done=?, "
                "partlist_total=? WHERE id=?",
                (
                    request.form.get("partlist_note", ""),
                    new_status,
                    1 if request.form.get("partlist_done", part["partlist_done"], type=int) > 0 else 0,
                    1,
                    part_id,
                ),
            )
            db.commit()
            updated_part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
            email_sent = notify_progress_approval(updated_part, "Partlist", "-", new_status == "Sudah Approval")
            if email_sent:
                flash("Partlist berhasil disimpan. Notifikasi email terkirim ke Marketing & Purchasing.", "success")
            else:
                flash("Partlist berhasil disimpan, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.", "warning")
        elif action == "save_quick_note":
            db.execute("UPDATE parts SET quick_note=? WHERE id=?",
                       (request.form.get("quick_note", ""), part_id))
            db.commit()
        elif action == "upload_progress_file":
            progress_type = request.form.get("progress_type", "").strip()
            permission_field = "review" if progress_type == "Drawing Review" else ("partlist" if progress_type == "Partlist" else "redraw")
            if not can_edit(permission_field):
                flash("Anda tidak memiliki akses untuk upload file pada progress ini.", "error")
            else:
                approval_status = request.form.get("approval_status", "Belum Approval")
                if approval_status not in ("Belum Approval", "Sudah Approval"):
                    approval_status = "Belum Approval"
                file = request.files.get("file")
                if not file or file.filename == "":
                    flash("Pilih file terlebih dahulu.", "error")
                elif not allowed_file(file.filename):
                    flash("Tipe file tidak didukung. Gunakan zip, pdf, doc(x), xls(x), dwg, rar, atau gambar.", "error")
                elif (size_error := validate_file_size(file)[1]) is not None:
                    flash(size_error, "error")
                elif progress_type not in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa", "Drawing Review", "Partlist"):
                    flash("Jenis progress file tidak valid.", "error")
                else:
                    original_name = secure_filename(file.filename)
                    extension = original_name.rsplit(".", 1)[1].lower() if "." in original_name else ""
                    display_name = progress_type
                    stored_name = f"{uuid.uuid4().hex}_{original_name}"
                    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
                    db.execute(
                        """INSERT INTO redraw_files
                           (part_id, original_filename, stored_filename, approval_status,
                            uploaded_by, divisi, created_at, progress_type, display_filename)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            part_id, original_name, stored_name, approval_status,
                            session["username"], current_divisi(),
                            datetime.now().strftime("%d-%m-%Y %H:%M"), progress_type, display_name,
                        ),
                    )
                    if progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                        sync_redraw_progress(db, part_id)
                    db.commit()
                    email_sent = None
                    if current_divisi() == "Engineer" and progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa", "Drawing Review", "Partlist"):
                        email_sent = notify_file_submission(part, progress_type, original_name)
                    if email_sent is False:
                        flash(f"File '{original_name}' berhasil diupload ke {progress_type} ({approval_status}), tetapi email notifikasi GAGAL terkirim ke Marketing & Purchasing. Cek email grup divisi di .env dan konfigurasi SMTP.", "warning")
                    elif email_sent is True:
                        flash(f"File '{original_name}' berhasil diupload ke {progress_type} ({approval_status}). Notifikasi email terkirim ke Marketing & Purchasing.", "success")
                    else:
                        flash(f"File '{original_name}' berhasil diupload ke {progress_type} ({approval_status}).", "success")
                    return redirect(url_for("redraw_upload_page", part_id=part_id, progress_type=progress_type, month=request.args.get("month", "")))
        elif action in ("approve_progress_file", "unapprove_progress_file", "delete_progress_file"):
            file_id = request.form.get("file_id", type=int)
            row = db.execute(
                "SELECT * FROM redraw_files WHERE id=? AND part_id=?", (file_id, part_id)
            ).fetchone()
            if not row:
                flash("File tidak ditemukan.", "error")
            else:
                permission_field = "review" if row["progress_type"] == "Drawing Review" else ("partlist" if row["progress_type"] == "Partlist" else "redraw")
                if not can_edit(permission_field):
                    flash("Anda tidak memiliki akses untuk mengubah file ini.", "error")
                elif action == "approve_progress_file":
                    db.execute("UPDATE redraw_files SET approval_status='Sudah Approval' WHERE id=? AND part_id=?", (file_id, part_id))
                    if row["progress_type"] in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                        sync_redraw_progress(db, part_id)
                    db.commit()
                    email_sent = notify_progress_approval(part, row["progress_type"], row["original_filename"], True)
                    flash(
                        "File dipindahkan ke Sudah Approval. Notifikasi email terkirim ke Marketing & Purchasing."
                        if email_sent else
                        "File dipindahkan ke Sudah Approval, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.",
                        "success" if email_sent else "warning",
                    )
                elif action == "unapprove_progress_file":
                    db.execute("UPDATE redraw_files SET approval_status='Belum Approval' WHERE id=? AND part_id=?", (file_id, part_id))
                    if row["progress_type"] in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                        sync_redraw_progress(db, part_id)
                    db.commit()
                    email_sent = notify_progress_approval(part, row["progress_type"], row["original_filename"], False)
                    flash(
                        "File dipindahkan ke Belum Approval. Notifikasi email terkirim ke Marketing & Purchasing."
                        if email_sent else
                        "File dipindahkan ke Belum Approval, tetapi email notifikasi GAGAL terkirim. Cek email grup divisi di .env dan konfigurasi SMTP.",
                        "success" if email_sent else "warning",
                    )
                else:
                    try:
                        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["stored_filename"]))
                    except OSError:
                        pass
                    db.execute("DELETE FROM redraw_files WHERE id=?", (file_id,))
                    if row["progress_type"] in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                        sync_redraw_progress(db, part_id)
                    db.commit()
                    flash("File dihapus.", "success")
        elif action == "add_note":
            divisi = current_divisi()
            text = request.form.get("text", "").strip()
            recipient_divisions = [
                d for d in request.form.getlist("recipient_divisions")
                if d in DIVISIONS and d != divisi
            ]
            feedback_file = request.files.get("feedback_file")

            if divisi == "Management":
                flash("Management memberi keputusan lewat menu Judgement.", "error")
            elif divisi not in DIVISIONS:
                flash("Divisi tidak valid untuk Note.", "error")
            elif not text and (not feedback_file or not feedback_file.filename):
                flash("Isi catatan atau pilih file feedback terlebih dahulu.", "error")
            elif not recipient_divisions:
                flash("Pilih minimal satu divisi tujuan.", "error")
            else:
                attachment_filename = ""
                attachment_stored_filename = ""
                attachment_path = None

                if feedback_file and feedback_file.filename:
                    if not allowed_file(feedback_file.filename):
                        flash("Tipe file feedback tidak didukung. Gunakan zip, rar, pdf, doc(x), xls(x), dwg, atau gambar.", "error")
                        return redirect(url_for(
                            "redraw_detail",
                            part_id=part_id,
                            tab=request.args.get("tab", "redraw"),
                            month=request.args.get("month", ""),
                        ))

                    size_ok, size_error = validate_file_size(feedback_file)
                    if not size_ok:
                        flash(size_error, "error")
                        return redirect(url_for(
                            "redraw_detail",
                            part_id=part_id,
                            tab=request.args.get("tab", "redraw"),
                            month=request.args.get("month", ""),
                        ))

                    attachment_filename = secure_filename(feedback_file.filename)
                    attachment_stored_filename = f"note_{uuid.uuid4().hex}_{attachment_filename}"
                    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                    attachment_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], attachment_stored_filename
                    )
                    feedback_file.save(attachment_path)

                recipient_text = ", ".join(recipient_divisions)
                db.execute(
                    "INSERT INTO notes "
                    "(part_id, divisi, author, text, created_at, attachment_filename, "
                    "attachment_stored_filename, recipient_divisions) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        part_id,
                        divisi,
                        session["username"],
                        text,
                        datetime.now().strftime("%d-%m-%Y %H:%M"),
                        attachment_filename,
                        attachment_stored_filename,
                        recipient_text,
                    ),
                )
                db.commit()

                email_body = f"""Feedback baru pada Monitoring RFQ.

Customer : {get_customer_name(part['customer_id'])}
Model    : {part['model_name']}
P/N      : {part['part_no']}
Kategori : {part['category']}
Dari     : {session['username']} ({divisi})

Note:
{text or '(Tidak ada teks, lihat lampiran.)'}

Lampiran:
{attachment_filename or 'Tidak ada'}
"""
                email_sent = send_email_notification(
                    f"[Monitoring RFQ] Feedback dari {divisi} - {part['model_name']} / P/N {part['part_no']}",
                    email_body,
                    recipient_divisions,
                    attachment_path=attachment_path,
                )

                if email_sent:
                    flash(f"Feedback berhasil disimpan dan email dikirim ke: {recipient_text}.", "success")
                else:
                    flash(f"Feedback berhasil disimpan, tetapi email belum berhasil dikirim ke: {recipient_text}. Cek konfigurasi SMTP.", "warning")
        elif action == "remove_note":
            note_id = request.form.get("note_id", type=int)
            note = db.execute(
                "SELECT divisi, attachment_stored_filename FROM notes WHERE id=? AND part_id=?",
                (note_id, part_id),
            ).fetchone()
            if note and note["divisi"] == current_divisi():
                if note["attachment_stored_filename"]:
                    try:
                        os.remove(os.path.join(
                            app.config["UPLOAD_FOLDER"],
                            note["attachment_stored_filename"]
                        ))
                    except OSError:
                        pass
                db.execute("DELETE FROM notes WHERE id=? AND part_id=?", (note_id, part_id))
                db.commit()
                flash("Note dihapus.", "success")
            else:
                flash("Anda tidak memiliki akses untuk menghapus Note ini.", "error")
        else:
            flash("Anda tidak memiliki akses untuk mengubah data ini.", "error")
        return redirect(url_for("redraw_detail", part_id=part_id, tab=request.form.get("tab", request.args.get("tab", "redraw")), month=request.args.get("month", "")))
    part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    notes = db.execute(
        "SELECT * FROM notes WHERE part_id=? ORDER BY id DESC", (part_id,)
    ).fetchall()
    notes_by_divisi = {d: [n for n in notes if n["divisi"] == d] for d in DIVISIONS}
    customer = db.execute("SELECT * FROM customers WHERE id=?", (part["customer_id"],)).fetchone()
    progress_files = db.execute(
        "SELECT * FROM redraw_files WHERE part_id=? ORDER BY id DESC", (part_id,)
    ).fetchall()
    progress_file_groups = {}
    for progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa", "Drawing Review", "Partlist"):
        progress_file_groups[progress_type] = {
            "belum": [f for f in progress_files if f["progress_type"] == progress_type and f["approval_status"] != "Sudah Approval"],
            "sudah": [f for f in progress_files if f["progress_type"] == progress_type and f["approval_status"] == "Sudah Approval"],
        }
    initial_tab = request.args.get("tab", "redraw")
    if initial_tab not in ("redraw", "review", "partlist"):
        initial_tab = "redraw"
    return render_template(
        "reason_detail.html", part=part, notes_by_divisi=notes_by_divisi,
        divisions=DIVISIONS, customer=customer, initial_tab=initial_tab,
        progress_file_groups=progress_file_groups,
    )

@app.route("/notes/download/<path:stored_filename>")
@login_required
def download_note_attachment(stored_filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        stored_filename,
        as_attachment=True,
    )


@app.route("/redraw/<int:part_id>/upload/<path:progress_type>", methods=["GET", "POST"])
@login_required
def redraw_upload_page(part_id, progress_type):
    allowed_types = ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa", "Drawing Review", "Partlist")
    if progress_type not in allowed_types:
        return redirect(url_for("redraw_detail", part_id=part_id, tab="redraw"))

    permission_field = "review" if progress_type == "Drawing Review" else ("partlist" if progress_type == "Partlist" else "redraw")
    tab_name = "review" if progress_type == "Drawing Review" else ("partlist" if progress_type == "Partlist" else "redraw")

    if not can_edit(permission_field):
        flash("Anda tidak memiliki akses untuk mengupload file pada progress ini.", "error")
        return redirect(url_for("redraw_detail", part_id=part_id, tab=tab_name))

    db = get_db()

    if progress_type == "Partlist":
        part_row = db.execute("SELECT customer_id, model_name, category, year FROM parts WHERE id=?", (part_id,)).fetchone()
        if part_row:
            mp_row = db.execute(
                "SELECT id FROM model_partlists WHERE customer_id=? AND model_name=? AND category=? AND year=?",
                (part_row["customer_id"], part_row["model_name"], part_row["category"], part_row["year"])
            ).fetchone()
            if mp_row:
                return redirect(url_for("model_partlist_detail", model_partlist_id=mp_row["id"], month=request.args.get("month", "")))
    part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        flash("Data tidak ditemukan.", "error")
        return redirect(url_for("progress"))
    customer = db.execute("SELECT * FROM customers WHERE id=?", (part["customer_id"],)).fetchone()

    if request.method == "POST":
        action = request.form.get("action")
        if action in ("approve", "unapprove", "delete"):
            file_id = request.form.get("file_id", type=int)
            row = db.execute(
                "SELECT * FROM redraw_files WHERE id=? AND part_id=? AND progress_type=?",
                (file_id, part_id, progress_type),
            ).fetchone()
            if not row:
                flash("File tidak ditemukan.", "error")
            elif action == "approve":
                db.execute("UPDATE redraw_files SET approval_status='Sudah Approval' WHERE id=?", (file_id,))
                if progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                    sync_redraw_progress(db, part_id)
                elif progress_type == "Drawing Review":
                    total = 1
                    done = db.execute(
                        "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
                        (part_id, progress_type),
                    ).fetchone()["c"]
                    done = min(done, total) if total > 0 else done
                    db.execute("UPDATE parts SET review_done=?, review_status=? WHERE id=?",
                               (done, "Close" if total > 0 and done >= total else "Pending", part_id))
                elif progress_type == "Partlist":
                    total = 1
                    done = db.execute(
                        "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
                        (part_id, progress_type),
                    ).fetchone()["c"]
                    done = min(done, total) if total > 0 else done
                    db.execute("UPDATE parts SET partlist_done=?, partlist_status=? WHERE id=?",
                               (done, "Close" if total > 0 and done >= total else "Pending", part_id))
                db.commit()
                notify_progress_approval(part, progress_type, row["original_filename"], True)
                flash("File berhasil di-approve.", "success")
            elif action == "unapprove":
                db.execute("UPDATE redraw_files SET approval_status='Belum Approval' WHERE id=?", (file_id,))
                if progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                    sync_redraw_progress(db, part_id)
                elif progress_type in ("Drawing Review", "Partlist"):
                    approved = db.execute(
                        "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
                        (part_id, progress_type),
                    ).fetchone()["c"]
                    field_done = "review_done" if progress_type == "Drawing Review" else "partlist_done"
                    field_status = "review_status" if progress_type == "Drawing Review" else "partlist_status"
                    total = 1
                    done = min(approved, total) if total > 0 else approved
                    db.execute(f"UPDATE parts SET {field_done}=?, {field_status}=? WHERE id=?",
                               (done, "Close" if total > 0 and done >= total else "Pending", part_id))
                db.commit()
                notify_progress_approval(part, progress_type, row["original_filename"], False)
                flash("Approval file dibatalkan.", "success")
            else:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["stored_filename"]))
                except OSError:
                    pass
                db.execute("DELETE FROM redraw_files WHERE id=?", (file_id,))
                if progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
                    sync_redraw_progress(db, part_id)
                elif progress_type in ("Drawing Review", "Partlist"):
                    approved = db.execute(
                        "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
                        (part_id, progress_type),
                    ).fetchone()["c"]
                    field_done = "review_done" if progress_type == "Drawing Review" else "partlist_done"
                    field_status = "review_status" if progress_type == "Drawing Review" else "partlist_status"
                    total = 1
                    done = min(approved, total) if total > 0 else approved
                    db.execute(f"UPDATE parts SET {field_done}=?, {field_status}=? WHERE id=?",
                               (done, "Close" if total > 0 and done >= total else "Pending", part_id))
                db.commit()
                flash("File dihapus.", "success")
            return redirect(url_for("redraw_upload_page", part_id=part_id, progress_type=progress_type, month=request.args.get("month", "")))

        file = request.files.get("file")
        if not file or not file.filename:
            flash("Pilih file terlebih dahulu.", "error")
        elif not allowed_file(file.filename):
            flash("Tipe file tidak didukung.", "error")
        elif (size_error := validate_file_size(file)[1]) is not None:
            flash(size_error, "error")
        else:
            if progress_type == "Drawing Review":
                existing = db.execute(
                    "SELECT id FROM redraw_files WHERE part_id=? AND progress_type=? LIMIT 1",
                    (part_id, progress_type)
                ).fetchone()
                if existing:
                    flash("Drawing Review untuk Partnumber ini sudah ada. Hapus file lama terlebih dahulu jika ingin menggantinya.", "error")
                    return redirect(url_for("redraw_upload_page", part_id=part_id, progress_type=progress_type, month=request.args.get("month", "")))
            original_name = secure_filename(file.filename)
            stored_name = f"{uuid.uuid4().hex}_{original_name}"
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            db.execute(
                """INSERT INTO redraw_files
                   (part_id, original_filename, stored_filename, approval_status, uploaded_by, divisi, created_at, progress_type, display_filename)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (part_id, original_name, stored_name, "Belum Approval", session["username"], current_divisi(),
                 datetime.now().strftime("%d-%m-%Y %H:%M"), progress_type, progress_type),
            )
            db.commit()
            if current_divisi() == "Engineer" and progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa", "Drawing Review", "Partlist"):
                notify_file_submission(part, progress_type, original_name)
            flash(f"File {progress_type} berhasil diupload.", "success")
            return redirect(url_for("redraw_upload_page", part_id=part_id, progress_type=progress_type, month=request.args.get("month", "")))

    files = db.execute(
        "SELECT * FROM redraw_files WHERE part_id=? AND progress_type=? ORDER BY id DESC",
        (part_id, progress_type),
    ).fetchall()

    if progress_type in ("Finish Good", "Komponen", "Drawing Tooling", "Drawing Pipa"):
        field = {"Finish Good":"finish_good", "Komponen":"komponen", "Drawing Tooling":"drawing_tooling", "Drawing Pipa":"drawing_pipa"}[progress_type]
        required_qty = int(part[field] or 0) if str(part[field] or "").isdigit() else 0
    else:
        required_qty = 1

    approved_qty = db.execute(
        "SELECT COUNT(*) c FROM redraw_files WHERE part_id=? AND progress_type=? AND approval_status='Sudah Approval'",
        (part_id, progress_type),
    ).fetchone()["c"]
    if required_qty > 0:
        approved_qty = min(approved_qty, required_qty)

    return render_template(
        "redraw_upload.html", part=part, customer=customer, progress_type=progress_type,
        files=files, required_qty=required_qty, approved_qty=approved_qty, tab_name=tab_name,
    )


@app.route("/redraw-files/<path:stored_filename>")
@login_required
def download_redraw_file(stored_filename):
    db = get_db()
    row = db.execute(
        "SELECT original_filename FROM redraw_files WHERE stored_filename=?", (stored_filename,)
    ).fetchone()
    if row:
        extension = row["original_filename"].rsplit(".", 1)[1] if "." in row["original_filename"] else ""
        display_name = row["display_filename"] if "display_filename" in row.keys() else row["original_filename"]
        download_name = f"{display_name}.{extension}" if extension else display_name
    else:
        download_name = stored_filename
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_filename,
                               as_attachment=True, download_name=download_name)


@app.route("/customers", methods=["GET", "POST"])
@login_required
def companies():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                db.execute("INSERT INTO customers (name) VALUES (?)", (name,))
                db.commit()
                flash(f"Customer '{name}' ditambahkan.", "success")
            except Error:
                flash("Customer sudah ada.", "error")
        return redirect(url_for("companies"))

    rows = db.execute(
        """SELECT c.id, c.name,
           SUM(CASE WHEN p.redraw_status != 'Close' THEN 1 ELSE 0 END) redraw_pending,
           SUM(CASE WHEN p.review_status != 'Close' THEN 1 ELSE 0 END) review_pending,
           SUM(CASE WHEN COALESCE(mp.partlist_status, 'Open') != 'Close' THEN 1 ELSE 0 END) partlist_pending,
           COUNT(p.id) total_parts
           FROM customers c
           LEFT JOIN parts p ON p.customer_id = c.id
           LEFT JOIN model_partlists mp
             ON mp.customer_id = p.customer_id
            AND mp.model_name = p.model_name
            AND mp.category = p.category
            AND mp.year = p.year
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    return render_template("companies.html", customers=rows)


@app.route("/details", methods=["GET", "POST"])
@login_required
def details():
    db = get_db()

    if request.method == "POST":
        if current_divisi() != "Marketing":
            flash("Hanya divisi Marketing yang dapat mengirim file.", "error")
            return redirect(url_for("details"))

        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Pilih file terlebih dahulu.", "error")
            return redirect(url_for("details"))
        if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() != "zip":
            flash("RFQ Document hanya dapat diupload dalam format ZIP.", "error")
            return redirect(url_for("details"))

        size_ok, size_error = validate_file_size(file)
        if not size_ok:
            flash(size_error, "error")
            return redirect(url_for("details"))

        original_name = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4().hex}_{original_name}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))

        selected_items = request.form.getlist("items")
        customer_name = request.form.get("customer", "").strip()
        model_name = request.form.get("model_name", "").strip()
        partnumber = request.form.get("partnumber", "").strip()
        category = request.form.get("category", "Chasis").strip()
        marketing_note = request.form.get("marketing_note", "").strip()
        note_targets = parse_note_targets("Marketing", always_include="Engineer")
        note_target_text = ", ".join(note_targets)

        kondisi, standard_hours = determine_rfq_condition(selected_items)
        due_date = calculate_due_date_from_hours(datetime.now(), standard_hours)
        if category not in CATEGORIES:
            category = "Chasis"
        if not kondisi:
            flash("Kombinasi checklist belum sesuai standar kondisi A-G pada jadwal RFQ. Silakan cek kembali dokumen yang dikirim.", "error")
            try: os.remove(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            except OSError: pass
            return redirect(url_for("details"))
        if not customer_name or not model_name or not partnumber:
            flash("Customer, Model, dan Partnumber wajib diisi.", "error")
            try: os.remove(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            except OSError: pass
            return redirect(url_for("details"))
        customer_row = db.execute("SELECT id FROM customers WHERE name=?", (customer_name,)).fetchone()
        if customer_row:
            customer_id = customer_row["id"]
        else:
            customer_id = db.execute("INSERT INTO customers (name) VALUES (?)", (customer_name,)).lastrowid
        year = datetime.now().year
        month = datetime.now().strftime("%B")
        if due_date:
            try:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                year = due_dt.year
                month = due_dt.strftime("%B")
            except ValueError:
                pass

        part_row = db.execute(
            "SELECT id FROM parts WHERE customer_id=? AND model_name=? AND part_no=? AND category=? AND year=?",
            (customer_id, model_name, partnumber, category, year)).fetchone()
        if part_row:
            part_id = part_row["id"]
        else:
            part_id = db.execute(
                """INSERT INTO parts (customer_id, model_name, category, year, month, part_no, due_date,
                   redraw_status, redraw_done, redraw_total, review_status, review_done, review_total,
                   partlist_status, partlist_done, partlist_total)
                   VALUES (?,?,?,?,?,?,?, 'Open',0,0, 'Open',0,1, 'Open',0,1)""",
                (customer_id, model_name, category, year, month, partnumber, due_date)
            ).lastrowid

        if due_date:
            db.execute(
                "UPDATE parts SET due_date=?, month=?, year=? WHERE customer_id=? AND model_name=? AND category=? AND year=?",
                (due_date, month, year, customer_id, model_name, category, year),
            )
        get_or_create_model_partlist(db, customer_id, model_name, category, year)

        db.execute(
            """INSERT INTO submissions
               (original_filename, stored_filename, description, customer, model_name, partnumber, category,
                kondisi, due_date, year, part_id, uploaded_by, divisi, created_at, included_items, marketing_note,
                note_target_divisions)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (original_name, stored_name, "", customer_name, model_name, partnumber, category, kondisi, due_date, year,
             part_id, session["username"], current_divisi(), datetime.now().strftime("%d-%m-%Y %H:%M"),
             "; ".join(selected_items), marketing_note, note_target_text))

        db.commit()
        new_part = db.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
        email_sent = notify_new_rfq(new_part, original_name, marketing_note, note_targets)
        if email_sent:
            flash(f"File '{original_name}' berhasil dikirim. Notifikasi email terkirim ke {note_target_text}.", "success")
        else:
            flash(f"File '{original_name}' berhasil dikirim, tetapi email notifikasi ke {note_target_text} GAGAL terkirim. Cek konfigurasi SMTP dan email anggota grup.", "warning")
        return redirect(url_for("details"))

    submissions = db.execute("SELECT * FROM submissions ORDER BY id DESC LIMIT 200").fetchall()
    customers = db.execute("SELECT name FROM customers ORDER BY name").fetchall()
    rfq_notes = db.execute("SELECT * FROM rfq_notes ORDER BY id DESC LIMIT 100").fetchall()

    return render_template(
        "details.html",
        submissions=submissions,
        rfq_notes=rfq_notes,
        group_labels=GROUP_LABELS,
        customers=customers,
        can_submit=(current_divisi() == "Marketing"),
        divisions=DIVISIONS,
        rfq_input_items=RFQ_INPUT_ITEMS,
        rfq_condition_schedule=[
            {"condition": k, "items": list(v["items"]), "hours": v["hours"]}
            for k, v in RFQ_CONDITION_SCHEDULE.items()
        ],
    )


@app.route("/judgement", methods=["GET", "POST"])
@login_required
def judgement():
    """Menu Judgement: Management memberi keputusan untuk RFQ customer baru
    dan commodity baru. Semua divisi bisa melihat; hanya Management yang input."""
    db = get_db()
    is_mgmt = current_divisi() == "Management"
    if request.method == "POST":
        if not is_mgmt:
            flash("Hanya Management yang dapat memberi judgement.", "error")
            return redirect(url_for("judgement"))
        jenis = request.form.get("jenis", "")
        customer = request.form.get("customer", "").strip()
        commodity = request.form.get("commodity", "").strip()
        model_name = request.form.get("model_name", "").strip()
        partnumber = request.form.get("partnumber", "").strip()
        keputusan = request.form.get("keputusan", "")
        catatan = request.form.get("catatan", "").strip()
        recipients = ["Management"]
        error = None
        if jenis not in JUDGEMENT_TYPES:
            error = "Pilih jenis judgement."
        elif jenis == "RFQ Customer Baru" and not customer:
            error = "Customer wajib diisi untuk RFQ Customer Baru."
        elif jenis == "Commodity Baru" and not commodity:
            error = "Commodity wajib diisi untuk Commodity Baru."
        elif keputusan not in JUDGEMENT_DECISIONS:
            error = "Pilih keputusan."
        elif not catatan:
            error = "Isi alasan / catatan judgement."
        if error:
            flash(error, "error")
            return redirect(url_for("judgement"))
        subject_ref = customer or commodity
        sent = send_email_notification(
            f"[Monitoring RFQ] Judgement Management - {jenis} - {subject_ref} - {keputusan}",
            f"""Management telah memberikan judgement.

Jenis      : {jenis}
Customer   : {customer or '-'}
Commodity  : {commodity or '-'}
Model      : {model_name or '-'}
Partnumber : {partnumber or '-'}
Keputusan  : {keputusan}
Oleh       : {session.get('username', '-')} (Management)

Alasan / Catatan:
{catatan}

Riwayat lengkap ada di menu Judgement pada Monitoring RFQ.
""",
            recipients,
        )
        recipient_text = ", ".join(recipients)
        db.execute(
            "INSERT INTO management_judgements (jenis, customer, commodity, model_name, partnumber, "
            "keputusan, catatan, author, recipient_divisions, email_sent, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (jenis, customer, commodity, model_name, partnumber, keputusan, catatan,
             session["username"], recipient_text, 1 if sent else 0,
             datetime.now().strftime("%d-%m-%Y %H:%M")),
        )
        db.commit()
        if sent:
            flash(f"Judgement tersimpan dan email terkirim ke {recipient_text}.", "success")
        else:
            flash(f"Judgement tersimpan, tetapi email ke {recipient_text} GAGAL terkirim. Cek konfigurasi SMTP dan email anggota grup.", "warning")
        return redirect(url_for("judgement"))

    jenis_filter = request.args.get("jenis", "")
    if jenis_filter in JUDGEMENT_TYPES:
        rows = db.execute("SELECT * FROM management_judgements WHERE jenis=? ORDER BY id DESC LIMIT 300",
                          (jenis_filter,)).fetchall()
    else:
        jenis_filter = ""
        rows = db.execute("SELECT * FROM management_judgements ORDER BY id DESC LIMIT 300").fetchall()
    customers = db.execute("SELECT name FROM customers ORDER BY name").fetchall()
    return render_template(
        "judgement.html", rows=rows, is_mgmt=is_mgmt, divisions=DIVISIONS,
        group_labels=GROUP_LABELS, types=JUDGEMENT_TYPES, decisions=JUDGEMENT_DECISIONS,
        jenis_filter=jenis_filter, customers=customers,
    )


@app.route("/judgement/delete/<int:judgement_id>", methods=["POST"])
@login_required
def delete_judgement(judgement_id):
    if current_divisi() != "Management":
        flash("Hanya Management yang dapat menghapus judgement.", "error")
        return redirect(url_for("judgement"))
    db = get_db()
    db.execute("DELETE FROM management_judgements WHERE id=?", (judgement_id,))
    db.commit()
    flash("Judgement dihapus.", "success")
    return redirect(url_for("judgement"))


@app.route("/details/note", methods=["POST"])
@login_required
def send_rfq_note():
    """Kirim note saja (tanpa file) ke grup yang dipilih, mis. untuk memberi
    tahu kendala."""
    if current_divisi() != "Marketing":
        flash("Hanya divisi Marketing yang dapat mengirim note dari halaman ini.", "error")
        return redirect(url_for("details"))
    text = request.form.get("marketing_note", "").strip()
    recipients = parse_note_targets("Marketing")
    customer = request.form.get("customer", "").strip()
    model_name = request.form.get("model_name", "").strip()
    partnumber = request.form.get("partnumber", "").strip()
    category = request.form.get("category", "").strip() if (customer or model_name or partnumber) else ""
    if category not in CATEGORIES:
        category = ""
    if not text:
        flash("Isi note terlebih dahulu sebelum mengirim.", "error")
        return redirect(url_for("details"))
    if not recipients:
        flash("Pilih minimal satu tujuan pengiriman note.", "error")
        return redirect(url_for("details"))
    sent = notify_standalone_note(text, recipients, customer, model_name, partnumber, category)
    recipient_text = ", ".join(recipients)
    db = get_db()
    db.execute(
        "INSERT INTO rfq_notes (divisi, author, customer, model_name, partnumber, category, text, "
        "recipient_divisions, email_sent, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (current_divisi(), session["username"], customer, model_name, partnumber, category, text,
         recipient_text, 1 if sent else 0, datetime.now().strftime("%d-%m-%Y %H:%M")),
    )
    db.commit()
    if sent:
        flash(f"Note berhasil dikirim ke {recipient_text}.", "success")
    else:
        flash(f"Note tersimpan, tetapi email ke {recipient_text} GAGAL terkirim. Cek konfigurasi SMTP dan email anggota grup.", "warning")
    return redirect(url_for("details"))


@app.route("/details/delete/<int:submission_id>", methods=["POST"])
@login_required
def delete_submission(submission_id):
    db = get_db()
    row = db.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
    if not row:
        return redirect(url_for("details"))
    if current_divisi() != "Marketing":
        flash("Hanya divisi Marketing yang dapat menghapus file.", "error")
        return redirect(url_for("details"))
    try:
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["stored_filename"]))
    except OSError:
        pass
    part_id = row["part_id"] if "part_id" in row.keys() else None
    db.execute("DELETE FROM submissions WHERE id=?", (submission_id,))
    if part_id:
        linked = db.execute("SELECT COUNT(*) c FROM submissions WHERE part_id=?", (part_id,)).fetchone()["c"]
        if linked == 0:
            db.execute("DELETE FROM parts WHERE id=?", (part_id,))
    db.commit()
    flash("File dihapus.", "success")
    return redirect(url_for("details"))


@app.route("/uploads/<path:stored_filename>")
@login_required
def download_submission(stored_filename):
    db = get_db()
    row = db.execute(
        "SELECT original_filename FROM submissions WHERE stored_filename=?", (stored_filename,)
    ).fetchone()
    if row:
        extension = row["original_filename"].rsplit(".", 1)[1] if "." in row["original_filename"] else ""
        display_name = row["display_filename"] if "display_filename" in row.keys() else row["original_filename"]
        download_name = f"{display_name}.{extension}" if extension else display_name
    else:
        download_name = stored_filename
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_filename,
                               as_attachment=True, download_name=download_name)


@app.route("/reason/<kind>")
@login_required
def reason(kind):
    field_map = {
        "redraw": ("redraw_status", "Redraw Pending"),
        "review": ("review_status", "Drawing Review Pending"),
        "partlist": ("partlist_status", "Partlist Pending"),
    }
    if kind not in field_map:
        return redirect(url_for("dashboard"))
    col, title = field_map[kind]

    db = get_db()
    year = request.args.get("year", datetime.now().year, type=int)
    rows = db.execute(
        f"""SELECT p.id, p.month, p.model_name, p.{col} status, c.name customer
            FROM parts p JOIN customers c ON c.id = p.customer_id
            WHERE p.year=? AND p.{col} != 'Close' ORDER BY
            CASE p.month {' '.join(f"WHEN '{m}' THEN {i}" for i, m in enumerate(MONTHS))} END""",
        (year,)
    ).fetchall()

    label_map = {"Pending": "On going", "Open": "On Process"}
    items = [{
        "id": r["id"], "month": r["month"],
        "marketing": label_map.get(r["status"], r["status"]),
        "customer": r["customer"], "model": r["model_name"],
    } for r in rows]

    return render_template("reason.html", kind=kind, title=title, items=items, year=year)


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)