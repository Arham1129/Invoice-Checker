import streamlit as st
import pdfplumber
import re
import sqlite3
import pandas as pd
import json
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

AI_MODEL = "gemini-3.8-flash"
api_key = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=api_key) if api_key else None

DB_FILE = "data.db"


def setup_database():
    # Create the tables and add sample purchase orders (only if empty)
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


def add_purchase_order(po_number, vendor, amount):
    # Save a new PO (or update it if the PO number already exists)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO purchase_orders VALUES (?, ?, ?)",
        (po_number, vendor, amount),
    )
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


def add_customer(name, phone, address):
    # Save a customer (or update if the name already exists)
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO customers VALUES (?, ?, ?)",
        (name, phone, address),
    )
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


def import_purchase_orders(uploaded_file):
    # Read an Excel or CSV file and save every row as a purchase order.
    # Returns (number of rows saved, error message or None).
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            data = pd.read_csv(uploaded_file)
        else:
            data = pd.read_excel(uploaded_file)
    except Exception as e:
        return 0, f"Could not read the file: {e}"

    data.columns = [str(c).strip().lower() for c in data.columns]

    required = ["po_number", "vendor", "amount"]
    for column in required:
        if column not in data.columns:
            return 0, f"Missing column: {column}"

    saved = 0
    for _, row in data.iterrows():
        po_number = str(row["po_number"]).strip()
        vendor = str(row["vendor"]).strip()
        try:
            amount = float(str(row["amount"]).replace(",", ""))
        except ValueError:
            continue
        if po_number and po_number.lower() != "nan":
            add_purchase_order(po_number, vendor, amount)
            saved += 1
    return saved, None


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

@st.cache_data(show_spinner=False)
def extract_fields_with_ai(text):
    # Ask the AI to read the invoice text and return the fields.
    # Returns None if anything goes wrong, so we can fall back to regex.
    if ai_client is None:
        return None

    prompt = f"""
Extract these fields from the document text below.
Return ONLY a JSON object with exactly these keys:
company_name, address, ntn, invoice_number, date, customer, po_number, total.
Use null if a field is missing. total must be a number without commas.

Document text:
{text}
"""

    try:
        response = ai_client.models.generate_content(
            model=AI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
    except Exception:
        return None

    total = data.get("total")
    try:
        total = float(str(total).replace(",", "")) if total is not None else None
    except ValueError:
        total = None

    return {
        "Company Name": data.get("company_name"),
        "Address": data.get("address"),
        "NTN": data.get("ntn"),
        "Invoice Number": data.get("invoice_number"),
        "Date": data.get("date"),
        "Customer": data.get("customer"),
        "PO Number": data.get("po_number"),
        "Total": total,
    }

def make_csv_report(fields, items, status, message):
    # Build one CSV text with details, result and line items
    details = pd.DataFrame(list(fields.items()), columns=["Field", "Value"])
    details.loc[len(details)] = ["Result", status]
    details.loc[len(details)] = ["Result details", message]
    csv_text = details.to_csv(index=False)

    if items:
        csv_text += "\nLine items\n"
        csv_text += pd.DataFrame(items).to_csv(index=False)
    return csv_text


setup_database()

st.title("Invoice Checker")

with st.expander("Manage purchase orders"):
    new_po = st.text_input("PO number (e.g. PO-892)")
    new_vendor = st.text_input("Vendor")
    new_amount = st.number_input("Amount", min_value=0.0, step=1000.0)

    if st.button("Add purchase order"):
        if new_po.strip() and new_vendor.strip():
            add_purchase_order(new_po.strip(), new_vendor.strip(), new_amount)
            st.success(f"{new_po} saved.")
        else:
            st.warning("Please fill in the PO number and vendor.")

    po_file = st.file_uploader("Or upload many POs (Excel or CSV)", type=["xlsx", "csv"], key="po_upload")
    if po_file is not None and st.button("Import purchase orders"):
        count, error = import_purchase_orders(po_file)
        if error:
            st.error(error)
        else:
            st.success(f"{count} purchase orders saved.")

    st.write("Current purchase orders:")
    st.table(pd.DataFrame(get_all_purchase_orders(), columns=["PO Number", "Vendor", "Amount"]))

file = st.file_uploader("Upload an invoice PDF", type="pdf")

if file:
    text = read_pdf(file)
    if text.strip():
        # Try the AI first. If it fails, fall back to regex.
        ai_fields = extract_fields_with_ai(text)
        if ai_fields is not None:
            fields = ai_fields
            source = "AI"
        else:
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
            source = "regex"

        st.caption(f"Extracted by: {source}")

        # Check the invoice against the database
        status, message = check_invoice(fields["PO Number"], fields["Total"])

        st.subheader("Result")
        if status == "Matched":
            st.success(f"{status}: {message}")
        elif status == "Mismatch":
            st.error(f"{status}: {message}")
        else:
            st.warning(f"{status}: {message}")

        st.subheader("Customer")
        customer_name = fields["Customer"]
        if customer_name is None:
            st.warning("Customer name not found in the invoice.")
        else:
            saved_customer = get_customer_from_db(customer_name)
            if saved_customer:
                st.success(f"Existing customer: {saved_customer[0]}")
                st.write("Phone:", saved_customer[1])
                st.write("Address:", saved_customer[2])
            else:
                st.info(f"New customer: {customer_name}")
                phone = st.text_input("Phone", key="customer_phone")
                address = st.text_input("Address", key="customer_address")
                if st.button("Save customer"):
                    add_customer(customer_name, phone, address)
                    st.rerun()

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

        report = make_csv_report(fields, items, status, message)
        st.download_button(
            label="Download report (CSV)",
            data=report,
            file_name="invoice_report.csv",
            mime="text/csv",
        )

        with st.expander("Show raw text"):
            st.text(text)
    else:
        st.warning("No text found. This may be a scanned PDF.")