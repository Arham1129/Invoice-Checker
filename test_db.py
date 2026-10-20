import sqlite3

# Open (or create) the database file
connection = sqlite3.connect("test.db")
cursor = connection.cursor()

# Create a table for purchase orders
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_number TEXT PRIMARY KEY,
    vendor TEXT,
    amount REAL
)
""")

# Insert three purchase orders
cursor.execute("INSERT OR REPLACE INTO purchase_orders VALUES (?, ?, ?)", ("PO-889", "Taj Trading Co", 85000))
cursor.execute("INSERT OR REPLACE INTO purchase_orders VALUES (?, ?, ?)", ("PO-890", "Karachi Steel Mart", 120000))
cursor.execute("INSERT OR REPLACE INTO purchase_orders VALUES (?, ?, ?)", ("PO-891", "Quick Supplies", 45000))

# Save the changes
connection.commit()

# Read everything back
cursor.execute("SELECT * FROM purchase_orders")
rows = cursor.fetchall()

for row in rows:
    print(row)

connection.close()