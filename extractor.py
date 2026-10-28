import json
import os
import re
import time

import pdfplumber
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

AI_MODELS = ["gemini-3.8-flash", "gemini-flash-lite-latest"]
api_key = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=15000),
) if api_key else None


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


def extract_fields_with_regex(text):
    # Regex version of the field extraction (used when the AI fails)
    return {
        "Company Name": find_company_name(text),
        "Address": find_address(text),
        "NTN": find_ntn(text),
        "Invoice Number": find_invoice_number(text),
        "Date": find_date(text),
        "Customer": find_customer(text),
        "PO Number": find_po_number(text),
        "Total": find_total(text),
    }


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
{text[:3000]}
"""

    data = None
    for model_name in AI_MODELS:
        for attempt in range(2):
            start = time.time()
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                data = json.loads(response.text)
                print("AI ok:", model_name, "took", round(time.time() - start, 1), "seconds")
                break
            except Exception as e:
                print("AI error:", model_name, "attempt", attempt + 1, "|", e)
                time.sleep(1)
        if data is not None:
            break

    if data is None:
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