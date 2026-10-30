from extractor import find_po_number, find_total, find_invoice_number


def test_find_po_number():
    assert find_po_number("P.O. Reference: PO-889") == "PO-889"


def test_find_po_number_missing_returns_none():
    assert find_po_number("Quick Supplies Invoice No: QS-100") is None


def test_find_total_with_commas():
    assert find_total("Total Payable: Rs 85,000") == 85000.0


def test_find_invoice_number():
    assert find_invoice_number("Invoice #: TTC/2026/0412 Date: 12-Oct-2026") == "TTC/2026/0412"