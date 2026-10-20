# Invoice Checker

A Streamlit app that reads B2B invoices (PDF) and extracts key details.

## Features
- Upload a PDF invoice
- Extracts company name, address, NTN, invoice number, date, customer, PO number and total
- Extracts line items and checks that they add up to the invoice total

## How to run
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `venv\Scripts\activate`
3. Install packages: `pip install -r requirements.txt`
4. Start the app: `streamlit run app.py`

## Roadmap
- Purchase order matching (SQLite)
- Download report
- AI-based extraction
- Login and chatbot