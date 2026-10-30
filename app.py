import pandas as pd
import streamlit as st
import requests

API_URL = "http://localhost:8000/check-invoice"




from checker import check_invoice
from database import (
    add_customer,
    add_purchase_order,
    delete_purchase_order,
    find_processed_invoice,
    get_all_purchase_orders,
    get_customer_from_db,
    save_processed_invoice,
    setup_database,
)
from extractor import (
    extract_fields_with_ai,
    extract_fields_with_regex,
    find_line_items,
    read_pdf,
)

# TODO: add chatbot, login page, static memory


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


def get_fields_with_ai(text):
    # Remember only successful AI results (failures are retried next time)
    if "ai_cache" not in st.session_state:
        st.session_state["ai_cache"] = {}
    cache = st.session_state["ai_cache"]
    if text not in cache:
        result = extract_fields_with_ai(text)
        if result is None:
            return None
        cache[text] = result
    return cache[text]


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

    all_pos = get_all_purchase_orders()
    po_numbers = [row[0] for row in all_pos]

    if po_numbers:
        po_to_delete = st.selectbox("Select a PO to delete", po_numbers, key="po_delete")
        confirm = st.checkbox(f"Yes, delete {po_to_delete}", key="po_delete_confirm")
        if st.button("Delete purchase order"):
            if confirm:
                delete_purchase_order(po_to_delete)
                st.rerun()
            else:
                st.warning("Tick the confirmation box first.")

    st.write("Current purchase orders:")
    st.table(pd.DataFrame(get_all_purchase_orders(), columns=["PO Number", "Vendor", "Amount"]))

file = st.file_uploader("Upload an invoice PDF", type="pdf")
if file:
    text = read_pdf(file)
    if text.strip():
        try:
            response = requests.post(
                API_URL,
                files={"file": (file.name, file.getvalue(), "application/pdf")},
                timeout=60,
            )
            result = response.json()
        except Exception as e:
            st.error(f"Could not reach the API. Is uvicorn running? ({e})")
            st.stop()

        if "error" in result:
            st.warning(result["error"])
            st.stop()

        fields = result["fields"]
        source = result["source"]
        status = result["status"]
        message = result["message"]

        st.caption(f"Extracted by: {source} (via API)")

        # Check if this invoice was already processed
        invoice_no = fields["Invoice Number"]
        company = fields["Company Name"]
        duplicate = None
        if invoice_no and company:
            duplicate = find_processed_invoice(invoice_no, company)

        if duplicate:
            st.error(f"Duplicate invoice: {invoice_no} from {company} was already processed (status: {duplicate[3]}).")
        elif invoice_no and company:
            if st.button("Save this invoice as processed"):
                save_processed_invoice(invoice_no, company, fields["Total"], status)
                st.rerun()

        st.subheader("Result")
        if status == "Matched":
            st.success(f"{status}: {message}")
        elif status in ("Mismatch", "Vendor mismatch"):
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
                st.write("Phone:", saved_customer[1] or "Not saved")
                st.write("Address:", saved_customer[2] or "Not saved")
                with st.expander("Edit customer info"):
                    new_phone = st.text_input("Phone", value=saved_customer[1] or "", key="edit_phone")
                    new_address = st.text_input("Address", value=saved_customer[2] or "", key="edit_address")
                    if st.button("Update customer"):
                        add_customer(saved_customer[0], new_phone, new_address)
                        st.rerun()
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
            if invoice_total is not None and abs(total_of_items - invoice_total) <= 1:
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