import streamlit as st
import pdfplumber
import re
import sqlite3
import pandas as pd

DB_FILE = "data.db"


def setup_database():
    # Create the table and add sample purchase orders (only if empty)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        po_number TEXT PRIMARY KEY,
        vendor TEXT,
        amount REAL
    )
    """)
    cursor.execute("SELECT COUNT(*) FROM purchase_orders")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO purchase_orders VALUES (?, ?, ?)", ("PO-889", "Taj Trading Co", 85000))
        cursor.execute("INSERT INTO purchase_orders VALUES (?, ?, ?)", ("PO-890", "Karachi Steel Mart", 120000))
        cursor.execute("INSERT INTO purchase_orders VALUES (?, ?, ?)", ("PO-891", "Quick Supplies", 45000))
    connection.commit()
    connection.close()


def find_purchase_order(po_number):
    # Look up one PO in the database. Returns None if not found.
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("SELECT po_number, vendor, amount FROM purchase_orders WHERE po_number = ?", (po_number,))
    row = cursor.fetchone()
    connection.close()
    return row


def check_invoice(po_number, invoice_total):
    # Compare the invoice with the purchase order and return (status, message)
    if po_number is None or invoice_total is None:
        return "Needs review", "Could not read the PO number or the total from this invoice."

    po = find_purchase_order(po_number)
    if po is None:
        return "PO not found", f"{po_number} does not exist in the database."

    po_amount = po[2]
    if invoice_total == po_amount:
        return "Matched", f"Invoice total {invoice_total:,.0f} matches {po_number}."
    return "Mismatch", f"Invoice total is {invoice_total:,.0f} but {po_number} says {po_amount:,.0f}."


def read_pdf(file):
    # Read every page of the PDF and join the text together
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def get_lines(text):
    # Split the text into a list of non-empty lines
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line:
            lines.append(line)
    return lines


def find_company_name(text):
    # The company name is the first line of the invoice
    lines = get_lines(text)
    if len(lines) > 0:
        return lines[0]
    return None


def find_address(text):
    # The address is the second line of the invoice
    lines = get_lines(text)
    if len(lines) > 1:
        return lines[1]
    return None


def find_ntn(text):
    # Look for the text after "NTN:"
    match = re.search(r"NTN:\s*(\S+)", text)
    if match:
        return match.group(1)
    return None


def find_invoice_number(text):
    # Look for the text after "Invoice #:" or "Invoice No:"
    match = re.search(r"Invoice\s*(?:#|No)\s*:\s*(\S+)", text)
    if match:
        return match.group(1)
    return None


def find_date(text):
    # Look for dates like 12-Oct-2026 or 15 October 2026
    match = re.search(r"Date:\s*(\d{1,2}[- ][A-Za-z]+[- ]\d{4})", text)
    if match:
        return match.group(1)
    return None


def find_customer(text):
    # Everything after "Customer:" until the end of the line
    match = re.search(r"Customer:\s*(.+)", text)
    if match:
        return match.group(1)
    return None


def find_po_number(text):
    # Look for something like PO-889
    match = re.search(r"PO-\d+", text)
    if match:
        return match.group()
    return None


def find_total(text):
    # Look for "Total Payable: Rs 85,000" or "GRAND TOTAL: Rs 128,500"
    match = re.search(r"\bTotal[A-Za-z ]*:\s*(?:Rs\.?)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def find_line_items(text):
    # Find every line that looks like: 1 Cement bags (50kg) 100 650.00 65,000.00
    items = []
    for line in text.split("\n"):
        match = re.match(r"^(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$", line.strip())
        if match:
            items.append({
                "Sr": int(match.group(1)),
                "Description": match.group(2),
                "Qty": int(match.group(3)),
                "Rate": float(match.group(4).replace(",", "")),
                "Amount": float(match.group(5).replace(",", "")),
            })
    return items


setup_database()

st.title("Invoice Checker")

file = st.file_uploader("Upload an invoice PDF", type="pdf")

if file:
    text = read_pdf(file)
    if text.strip():
        fields = {
            "Company Name": find_company_name(text),
            "Address": find_address(text),
            "NTN": find_ntn(text),
            "Invoice Number": find_invoice_number(text),
            "Date": find_date(text),
            "Customer": find_customer(text),
            "PO Number": find_po_number(text),
            "Total": find_total(text),
        }

        # Check the invoice against the database
        status, message = check_invoice(fields["PO Number"], fields["Total"])

        st.subheader("Result")
        if status == "Matched":
            st.success(f"{status}: {message}")
        elif status == "Mismatch":
            st.error(f"{status}: {message}")
        else:
            st.warning(f"{status}: {message}")

        table = pd.DataFrame(list(fields.items()), columns=["Field", "Value"])
        table["Value"] = table["Value"].astype(str)

        st.subheader("Invoice details")
        st.table(table)

        items = find_line_items(text)

        st.subheader("Line items")
        if items:
            st.table(pd.DataFrame(items))

            total_of_items = sum(item["Amount"] for item in items)
            st.write("Sum of items:", total_of_items)

            invoice_total = fields["Total"]
            if invoice_total is not None and total_of_items == invoice_total:
                st.success("Items add up to the invoice total.")
            else:
                st.warning("Items do not add up to the invoice total. Please review.")
        else:
            st.info("No line items found.")

        with st.expander("Show raw text"):
            st.text(text)
    else:
        st.warning("No text found. This may be a scanned PDF.")