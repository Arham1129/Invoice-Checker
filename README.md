# Invoice Checker

A tool that reads supplier invoices (PDF), extracts the key fields with AI,
and checks them against purchase orders to catch mismatches, wrong vendors
and duplicate invoices.

> This is a learning project. The roadmap below shows where it could go next, not a promise.

## What it does

- Upload an invoice PDF. Fields are extracted by Gemini AI, with a regex fallback if the AI is unavailable
- Matches the invoice to a purchase order by PO number, vendor and amount
- Returns one of: **Matched**, **Mismatch**, **Vendor mismatch**, **PO not found**, **Needs review**
- Detects duplicate invoices (same invoice number from the same company)
- Manage purchase orders: add by form, bulk import from Excel/CSV, delete
- Remembers customers and lets you edit their details
- Reads line items and checks that they add up to the invoice total
- Download a CSV report

## Key design decision

The AI only **reads** the invoice and turns messy text into structured fields.
The **decision** (matched or not) is made by plain Python code in `checker.py`.
This keeps results deterministic, testable and explainable, which matters for
financial checks. If the AI fails or is busy, the app falls back to regex
extraction instead of stopping.

## Tech stack

Python, Streamlit, FastAPI, SQLite, Gemini API, pandas, pdfplumber, pytest

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface |
| `api.py` | FastAPI backend (`/health`, `/check-invoice`) |
| `extractor.py` | PDF reading, regex and AI field extraction |
| `checker.py` | Matching logic (vendor, amount, tolerance) |
| `database.py` | SQLite functions (POs, customers, processed invoices) |
| `test_checker.py`, `test_extractor.py` | pytest tests |

## Run it locally

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
2. Install packages:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project folder:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a free key at [Google AI Studio](https://aistudio.google.com).
4. Start the app:
   ```
   python -m streamlit run app.py
   ```
5. Optional API:
   ```
   python -m uvicorn api:api --port 8000
   ```
   Then open `http://localhost:8000/docs`.
6. Run tests:
   ```
   python -m pytest
   ```

## Example POs file (Excel/CSV import)

| po_number | vendor | amount |
|---|---|---|
| PO-889 | Taj Trading Co | 85000 |
| PO-890 | Karachi Steel Mart | 120000 |

## Limitations

- No login or per-company data separation yet
- Scanned (image-only) PDFs are not supported
- The Streamlit UI still calls the extraction code directly in some places
- Not deployed

## Roadmap

**v1.0 (current)**
- [x] AI + regex extraction, PO / vendor / amount matching
- [x] Duplicate detection, customers, Excel/CSV import, CSV report
- [x] FastAPI backend, pytest tests

**Planned**
- [ ] Streamlit UI fully connected to the FastAPI backend
- [ ] Login and separate data per company
- [ ] Scanned PDF support
- [ ] Docker and GitHub Actions (run tests on every push)
- [ ] Live deployment
- [ ] Chatbot to ask questions about POs and invoices

## What I learned

- How a project is split into a frontend (Streamlit), a backend (FastAPI) and
  a database (SQLite), and how data moves between them: PDF upload, text
  extraction, AI-to-JSON, matching logic, and the result back to the screen.
- Why the AI should only read and structure data, while a tested Python
  function makes the actual decision.
- Debugging real problems: I found a bug where an invoice from one company
  matched another company's PO because I only compared PO number and amount.
  Adding a vendor check and a pytest test fixed it.
- Working with environments and tooling: virtual environments, Git/GitHub,
  and handling AI errors with retries and a regex fallback.