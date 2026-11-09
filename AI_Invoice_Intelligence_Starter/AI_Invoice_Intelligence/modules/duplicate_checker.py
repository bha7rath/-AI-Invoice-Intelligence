import sqlite3
from pathlib import Path
from datetime import datetime


PROJECT_FOLDER = Path(__file__).resolve().parent.parent
DATA_FOLDER = PROJECT_FOLDER / "data"
DB_PATH = DATA_FOLDER / "invoices.db"


def get_connection():
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    # ==============================================
    # TABLE 1: SUCCESSFULLY REGISTERED INVOICES
    # ==============================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS processed_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            source_file TEXT,
            po_number TEXT,
            invoice_amount REAL,
            created_at TEXT,
            UNIQUE(vendor_name, invoice_number)
        )
    """)

    # ------------------------------------------------
    # BACKWARD COMPATIBILITY
    # ------------------------------------------------
    # Existing databases may already have the table
    # without po_number and invoice_amount.
    #
    # Add the columns only if they do not already exist.
    # Existing invoice records are preserved.

    columns = connection.execute(
        "PRAGMA table_info(processed_invoices)"
    ).fetchall()

    column_names = {
        column[1]
        for column in columns
    }

    if "po_number" not in column_names:
        connection.execute("""
            ALTER TABLE processed_invoices
            ADD COLUMN po_number TEXT
        """)

    if "invoice_amount" not in column_names:
        connection.execute("""
            ALTER TABLE processed_invoices
            ADD COLUMN invoice_amount REAL
        """)

    # ==============================================
    # TABLE 2: COMPLETE PROCESSING AUDIT HISTORY
    # ==============================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS invoice_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT,
            invoice_number TEXT,
            source_file TEXT,
            decision TEXT NOT NULL,
            duplicate_status TEXT,
            validation_status TEXT,
            po_status TEXT,
            missing_fields TEXT,
            registration_status INTEGER,
            po_number TEXT,
            po_amount REAL,
            previous_used_amount REAL,
            invoice_amount REAL,
            cumulative_amount REAL,
            maximum_allowed REAL,
            created_at TEXT
        )
    """)

    # ------------------------------------------------
    # BACKWARD COMPATIBILITY FOR AUDIT TABLE
    # ------------------------------------------------
    audit_columns = connection.execute(
        "PRAGMA table_info(invoice_audit_log)"
    ).fetchall()

    audit_column_names = {
        column[1]
        for column in audit_columns
    }

    audit_new_columns = {
        "po_number": "TEXT",
        "po_amount": "REAL",
        "previous_used_amount": "REAL",
        "invoice_amount": "REAL",
        "cumulative_amount": "REAL",
        "maximum_allowed": "REAL",
    }

    for column_name, column_type in audit_new_columns.items():
        if column_name not in audit_column_names:
            connection.execute(
                f"ALTER TABLE invoice_audit_log "
                f"ADD COLUMN {column_name} {column_type}"
            )

    connection.commit()

    return connection


# ==================================================
# DUPLICATE CHECK
# ==================================================

def is_duplicate_invoice(vendor_name, invoice_number):
    """
    Check whether this vendor and invoice number
    already exist in the successfully processed
    invoice table.
    """

    if not vendor_name or not invoice_number:
        return False

    vendor = vendor_name.strip().lower()
    invoice = invoice_number.strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT 1
            FROM processed_invoices
            WHERE vendor_name = ?
              AND invoice_number = ?
            LIMIT 1
        """, (vendor, invoice))

        return cursor.fetchone() is not None

    finally:
        connection.close()


# ==================================================
# REGISTER SUCCESSFULLY PROCESSED INVOICE
# ==================================================

def register_invoice(
    vendor_name,
    invoice_number,
    source_file=None,
    po_number=None,
    invoice_amount=None
):
    """
    Register an invoice only after it passes the
    required automated processing checks.

    po_number and invoice_amount are stored so that
    future invoices can calculate cumulative PO usage.
    """

    if not vendor_name or not invoice_number:
        return False

    vendor = vendor_name.strip().lower()
    invoice = invoice_number.strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO processed_invoices
            (
                vendor_name,
                invoice_number,
                source_file,
                po_number,
                invoice_amount,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            vendor,
            invoice,
            source_file,
            po_number,
            invoice_amount,
            datetime.now().isoformat()
        ))

        connection.commit()

        return cursor.rowcount == 1

    finally:
        connection.close()


# ==================================================
# GET PREVIOUS PO USAGE
# ==================================================

def get_po_usage(po_number):
    """
    Return the total amount already registered against
    a purchase order.

    Only successfully registered invoices are counted.
    """

    if not po_number:
        return {
            "po_number": None,
            "invoice_count": 0,
            "used_amount": 0.0
        }

    normalized_po = po_number.strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(invoice_amount), 0)
            FROM processed_invoices
            WHERE UPPER(TRIM(po_number)) = ?
        """, (normalized_po,))

        row = cursor.fetchone()

        invoice_count = row[0] or 0
        used_amount = row[1] or 0.0

        return {
            "po_number": normalized_po,
            "invoice_count": invoice_count,
            "used_amount": float(used_amount)
        }

    finally:
        connection.close()


# ==================================================
# GET REGISTERED INVOICES FOR A PO
# ==================================================

def get_invoices_for_po(po_number):
    """
    Return all successfully registered invoices
    associated with a purchase order.
    """

    if not po_number:
        return []

    normalized_po = po_number.strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                vendor_name,
                invoice_number,
                source_file,
                po_number,
                invoice_amount,
                created_at
            FROM processed_invoices
            WHERE UPPER(TRIM(po_number)) = ?
            ORDER BY id ASC
        """, (normalized_po,))

        rows = cursor.fetchall()

        columns = [
            "id",
            "vendor_name",
            "invoice_number",
            "source_file",
            "po_number",
            "invoice_amount",
            "created_at"
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        connection.close()


# ==================================================
# AUDIT LOG
# ==================================================

def record_audit_event(
    vendor_name,
    invoice_number,
    source_file,
    decision,
    duplicate_status=None,
    validation_status=None,
    po_status=None,
    missing_fields=None,
    registration_status=False,
    po_number=None,
    po_amount=None,
    previous_used_amount=None,
    invoice_amount=None,
    cumulative_amount=None,
    maximum_allowed=None
):
    """
    Record every invoice-processing attempt.

    This table is separate from processed_invoices.
    Therefore, invoices that are rejected, duplicated,
    or sent for review are still visible in history.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if missing_fields is None:
            missing_fields = []

        missing_fields_text = ", ".join(missing_fields)

        cursor.execute("""
            INSERT INTO invoice_audit_log
            (
                vendor_name,
                invoice_number,
                source_file,
                decision,
                duplicate_status,
                validation_status,
                po_status,
                missing_fields,
                registration_status,
                po_number,
                po_amount,
                previous_used_amount,
                invoice_amount,
                cumulative_amount,
                maximum_allowed,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vendor_name,
            invoice_number,
            source_file,
            decision,
            str(duplicate_status),
            validation_status,
            po_status,
            missing_fields_text,
            1 if registration_status else 0,
            po_number,
            po_amount,
            previous_used_amount,
            invoice_amount,
            cumulative_amount,
            maximum_allowed,
            datetime.now().isoformat()
        ))

        connection.commit()

        return True

    finally:
        connection.close()


# ==================================================
# GET AUDIT HISTORY
# ==================================================

def get_audit_history(limit=100):
    """
    Return recent invoice-processing attempts.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                vendor_name,
                invoice_number,
                source_file,
                decision,
                duplicate_status,
                validation_status,
                po_status,
                missing_fields,
                registration_status,
                po_number,
                po_amount,
                previous_used_amount,
                invoice_amount,
                cumulative_amount,
                maximum_allowed,
                created_at
            FROM invoice_audit_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()

        columns = [
            "id",
            "vendor_name",
            "invoice_number",
            "source_file",
            "decision",
            "duplicate_status",
            "validation_status",
            "po_status",
            "missing_fields",
            "registration_status",
            "po_number",
            "po_amount",
            "previous_used_amount",
            "invoice_amount",
            "cumulative_amount",
            "maximum_allowed",
            "created_at"
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        connection.close()


# ==================================================
# DASHBOARD SUMMARY
# ==================================================

def get_audit_summary():
    """
    Return summary statistics for the dashboard.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM invoice_audit_log
        """)

        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM invoice_audit_log
            WHERE decision = 'APPROVED FOR HUMAN REVIEW'
        """)

        approved = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM invoice_audit_log
            WHERE decision = 'NEEDS REVIEW'
        """)

        needs_review = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM invoice_audit_log
            WHERE decision = 'DUPLICATE - STOPPED'
        """)

        duplicates = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM invoice_audit_log
            WHERE decision = 'HOLD - PO MISMATCH'
        """)

        po_mismatches = cursor.fetchone()[0]

        return {
            "total": total,
            "approved": approved,
            "needs_review": needs_review,
            "duplicates": duplicates,
            "po_mismatches": po_mismatches
        }

    finally:
        connection.close()


# ==================================================
# BACKWARD-COMPATIBLE FUNCTION
# ==================================================

def check_and_register_invoice(
    vendor_name,
    invoice_number,
    source_file=None
):
    """
    Backward-compatible check-and-register function.
    """

    if is_duplicate_invoice(
        vendor_name,
        invoice_number
    ):
        return True

    register_invoice(
        vendor_name,
        invoice_number,
        source_file
    )

    return False