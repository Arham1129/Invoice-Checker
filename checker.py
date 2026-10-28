import re

from database import find_purchase_order


def clean_name(name):
    # Lowercase, remove punctuation and common words like pvt, ltd, co
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    ignore = {"pvt", "ltd", "limited", "private", "co", "company", "inc", "llc"}
    return " ".join(word for word in name.split() if word not in ignore)


def same_vendor(name_a, name_b):
    # True if one cleaned name contains the other
    a = clean_name(name_a)
    b = clean_name(name_b)
    return bool(a) and bool(b) and (a in b or b in a)


def check_invoice(po_number, invoice_total, invoice_vendor):
    # Compare the invoice with the purchase order and return (status, message)
    if po_number is None or invoice_total is None:
        return "Needs review", "Could not read the PO number or the total from this invoice."

    po = find_purchase_order(po_number)
    if po is None:
        return "PO not found", f"{po_number} does not exist in the database."

    po_vendor = po[1]
    po_amount = po[2]

    if not invoice_vendor or not same_vendor(invoice_vendor, po_vendor):
        return "Vendor mismatch", (
            f"{po_number} belongs to {po_vendor}, but this invoice is from "
            f"{invoice_vendor or 'an unknown company'}."
        )

    if abs(invoice_total - po_amount) <= 1:
        return "Matched", f"Invoice total {invoice_total:,.0f} matches {po_number} ({po_vendor})."
    return "Mismatch", f"Invoice total is {invoice_total:,.0f} but {po_number} says {po_amount:,.0f}."