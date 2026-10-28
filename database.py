import sqlite3

DB_FILE = "data.db"


def setup_database():
    # Create the tables if they do not exist yet
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        po_number TEXT PRIMARY KEY,
        vendor TEXT,
        amount REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        name TEXT PRIMARY KEY,
        phone TEXT,
        address TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_invoices (
        invoice_number TEXT,
        company TEXT,
        total REAL,
        status TEXT,
        PRIMARY KEY (invoice_number, company)
    )
    """)
    connection.commit()
    connection.close()


def find_purchase_order(po_number):
    # Look up one PO. Returns None if not found.
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("SELECT po_number, vendor, amount FROM purchase_orders WHERE po_number = ?", (po_number,))
    row = cursor.fetchone()
    connection.close()
    return row


def add_purchase_order(po_number, vendor, amount):
    # Save a new PO (or update it if the PO number already exists)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("INSERT OR REPLACE INTO purchase_orders VALUES (?, ?, ?)", (po_number, vendor, amount))
    connection.commit()
    connection.close()


def get_all_purchase_orders():
    # Return every PO as a list of rows
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("SELECT po_number, vendor, amount FROM purchase_orders")
    rows = cursor.fetchall()
    connection.close()
    return rows


def delete_purchase_order(po_number):
    # Remove one PO from the database
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM purchase_orders WHERE po_number = ?", (po_number,))
    connection.commit()
    connection.close()


def add_customer(name, phone, address):
    # Save a customer (or update if the name already exists)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("INSERT OR REPLACE INTO customers VALUES (?, ?, ?)", (name, phone, address))
    connection.commit()
    connection.close()


def get_customer_from_db(name):
    # Look up a customer by name (capital/small letters do not matter)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name, phone, address FROM customers WHERE lower(name) = lower(?)",
        (name,),
    )
    row = cursor.fetchone()
    connection.close()
    return row


def find_processed_invoice(invoice_number, company):
    # Returns the saved row if this invoice was already processed, else None
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT invoice_number, company, total, status FROM processed_invoices "
        "WHERE lower(invoice_number) = lower(?) AND lower(company) = lower(?)",
        (invoice_number, company),
    )
    row = cursor.fetchone()
    connection.close()
    return row


def save_processed_invoice(invoice_number, company, total, status):
    # Remember this invoice so we can catch duplicates later
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO processed_invoices VALUES (?, ?, ?, ?)",
        (invoice_number, company, total, status),
    )
    connection.commit()
    connection.close()