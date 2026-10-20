import streamlit as st
import pdfplumber
import re
import pandas as pd


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