# How Invoice Checker Works

This document explains the whole project in simple language: what it does,
how the pieces fit together, and what happens to one invoice from the moment
you upload it until you see the result.

---

## 1. The problem in one paragraph

When a company buys something, it first creates a **purchase order (PO)**:
"We will buy cement worth Rs 85,000 from Taj Trading, PO number PO-889."
Later the supplier sends an **invoice** asking for payment. Before paying,
someone must check: *Is this invoice really for that PO? Is the supplier the
right one? Is the amount the same? Did we already pay this invoice before?*

Doing this by hand for hundreds of PDFs is slow and mistakes are easy.
Invoice Checker does this check automatically.

---

## 2. The restaurant picture

| Restaurant | Project | Job |
|---|---|---|
| Dining hall and menu | `app.py` (Streamlit) | What the user sees: upload box, buttons, tables |
| Waiter | `api.py` (FastAPI) | Takes a request, passes it to the kitchen, returns the answer |
| Kitchen | `extractor.py`, `checker.py` | Does the real work |
| Store room / ledger | `database.py` + `data.db` (SQLite) | Remembers POs, customers, processed invoices |
| Smart reader | Gemini AI | Reads the messy invoice text and writes it as clean data |

---

## 3. The big picture

```
 PDF invoice
     |
     v
 [read_pdf]  ->  raw text
     |
     v
 [Gemini AI]  ->  clean fields (JSON)      <- if AI fails: [regex fallback]
     |
     v
 [check_invoice]  <-->  SQLite database (purchase orders)
     |
     v
 Result: Matched / Mismatch / Vendor mismatch / PO not found / Needs review
     |
     v
 Screen (and optional CSV report)
```

The most important idea: **the AI only reads. Python decides.**

---

## 4. The journey of one invoice

### Step 1: Upload
The user drops a PDF into the upload box in the Streamlit page.

### Step 2: Read the PDF text (`read_pdf` in `extractor.py`)
The library `pdfplumber` opens the PDF and pulls out the text, page by page.
Result: one long block of text. It is messy: no labels, no structure, just
lines of words and numbers.

> This only works for PDFs that contain real text. A scanned photo of a paper
> invoice has no text inside, so the app shows "No text found".

### Step 3: Turn messy text into clean fields (`extract_fields_with_ai`)
The text is sent to Gemini with a clear instruction: "Return only a JSON object
with these keys: company_name, address, ntn, invoice_number, date, customer,
po_number, total."

JSON is just a neat way to write labeled data, like a filled form:

```json
{
  "company_name": "TAJ TRADING CO. (PVT) LTD",
  "invoice_number": "TTC/2026/0412",
  "po_number": "PO-889",
  "total": 85000
}
```

Python can read this easily: `data["total"]` gives `85000`.

Safety features around the AI call:
- It tries the main model twice, then a backup model twice.
- Each request has a 15 second timeout, so the app never hangs forever.
- Only the first 3000 characters are sent (invoice fields are at the top).
- Successful results are remembered for the session, so uploading the same
  invoice again is instant.

### Step 4: If the AI fails, use regex (`extract_fields_with_regex`)
Sometimes Google's server is busy (error 503) or the network drops.
The app then falls back to **regex**: pattern rules written by hand, such as
"PO- followed by digits" or "the text after `Invoice #:`".
Regex is fast and free but only understands formats it was written for.
The screen shows **Extracted by: AI** or **Extracted by: regex**, so the user
always knows which one was used.

### Step 5: Check the invoice (`check_invoice` in `checker.py`)
This is the brain. It uses plain Python `if` statements, no AI:

1. PO number or total missing? -> **Needs review**
2. PO number not in the database? -> **PO not found**
3. PO belongs to a different vendor than the invoice sender? -> **Vendor mismatch**
4. Amount differs by more than Rs 1? -> **Mismatch**
5. Everything fits? -> **Matched**

**Vendor matching** (`same_vendor`): names are cleaned first (lowercase,
punctuation removed, words like "pvt", "ltd", "co" ignored), so
"TAJ TRADING CO. (PVT) LTD" and "Taj Trading Co" count as the same vendor,
while "Taj Trading" and "Hamza Garments" do not.

**Amount tolerance**: a difference of up to Rs 1 is accepted, so tiny rounding
differences do not cause false alarms.

### Step 6: Duplicate check
If the same invoice number from the same company was already saved as
processed, the app shows a red **Duplicate invoice** warning. This catches
the classic mistake of paying one invoice twice. The user can press
"Save this invoice as processed" to remember it.

### Step 7: Customer lookup
The customer named on the invoice (the buyer) is looked up in the `customers`
table. If found, the saved phone and address are shown and can be edited.
If not, the app shows "New customer" with a small form to save the details.

### Step 8: Line items
Lines such as `1 Cement bags (50kg) 100 650.00 65,000.00` are picked out with
a regex and shown as a table. The app adds up the amounts and checks that they
match the invoice total.

### Step 9: Show and export
The page shows the result in a colored box (green for Matched, red for
problems, yellow for review), the extracted details, the line items, and a
button to download everything as a CSV report.

---

## 5. The files, one by one

| File | What it does |
|---|---|
| `app.py` | The Streamlit screen. Upload box, tables, buttons, forms to manage POs. Contains almost no business logic. |
| `api.py` | FastAPI backend with `/health` and `/check-invoice`. Anyone (another app, another program) can send a PDF and get the result as JSON, without Streamlit. |
| `extractor.py` | Reads the PDF, extracts fields with AI or regex, finds line items. Has no Streamlit code, so tests and the API can reuse it. |
| `checker.py` | The matching rules (`clean_name`, `same_vendor`, `check_invoice`). |
| `database.py` | All SQLite functions: add, find, delete POs; save and find customers; save and find processed invoices. |
| `test_checker.py`, `test_extractor.py` | pytest tests that prove the rules work. |
| `.env` | Holds the secret API key. Never uploaded to GitHub. |
| `data.db` | The database file. Never uploaded to GitHub. |

Why split into files? Each file has one job, so it is easier to understand,
test, and reuse. The API and the Streamlit page both use the **same**
`extractor.py` and `checker.py`: one set of logic, two ways to reach it.

---

## 6. The database

SQLite is a database stored in a single file (`data.db`). Data lives in tables,
like Excel sheets.

**purchase_orders**

| po_number | vendor | amount |
|---|---|---|
| PO-889 | Taj Trading Co | 85000 |

**customers**

| name | phone | address |
|---|---|---|

**processed_invoices**

| invoice_number | company | total | status |
|---|---|---|---|

Purchase orders can be added one by one in the app or imported from an Excel/CSV
file with the columns `po_number`, `vendor`, `amount`.

SQL queries use `?` placeholders instead of pasting text into the query. This
prevents SQL injection, a common attack.

---

## 7. Why the AI does not make the decision

An AI can be wrong, and the same input can sometimes give different answers.
For money-related checks that is not acceptable. So:

- The AI does the part it is good at: understanding messy, differently formatted text.
- Normal Python code does the part that must be exact and explainable: comparing numbers and names.
- Because the rules are plain code, they can be tested with pytest, and every
  result can be explained ("PO-889 belongs to Hamza Garments, but this invoice
  is from Taj Trading").

A real bug found during development shows why this matters: an invoice from one
company was matched against another company's PO, because only the PO number and
amount were compared. Adding the vendor check and a test fixed it.

---

## 8. Tests

Run with `python -m pytest`. The tests cover:
- cleaning vendor names and comparing vendors,
- finding the PO number, invoice number and total in text,
- a missing PO number returning `None` instead of crashing.

Tests are small checks that prove the code still works after every change.

---

## 9. Running it

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your_key_here
```

Start the screen:

```
python -m streamlit run app.py
```

Optional: start the API and open `http://localhost:8000/docs`:

```
python -m uvicorn api:api --port 8000
```

---

## 10. Known limits and next steps

- No login, and no separation of data between companies yet.
- Scanned image PDFs are not supported.
- The Streamlit page currently uses the extraction and checking code directly;
  the FastAPI backend exists and works on its own, and connecting the two fully is planned.
- Not deployed online.

---

## 11. Small glossary

- **PO (purchase order):** the buyer's order document.
- **Invoice:** the supplier's bill.
- **NTN:** Pakistan's National Tax Number.
- **Frontend:** what the user sees.
- **Backend:** the code that does the work behind the screen.
- **API:** a "door" a program can call to ask the backend to do something.
- **JSON:** labeled data written as text.
- **Regex:** pattern rules for finding things in text.
- **Fallback:** a backup plan used when the first one fails.
- **Virtual environment (`.venv`):** a private box of packages for one project.
