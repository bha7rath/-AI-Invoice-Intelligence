
import sqlite3

db_path = "data/invoices.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("""
    SELECT id, vendor_name, invoice_number, source_file, created_at
    FROM processed_invoices
    ORDER BY id DESC
""")

rows = cursor.fetchall()

print("\n===== PROCESSED INVOICES =====")

for row in rows:
    print(row)

print("\nTotal registered invoices:", len(rows))

connection.close()
