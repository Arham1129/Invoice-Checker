import json
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

invoice_text = """
TAJ TRADING CO. (PVT) LTD
Plot 14, Korangi Industrial Area, Karachi
NTN: 1234567-8
Invoice #: TTC/2026/0412   Date: 12-Oct-2026
Customer: Al-Noor Constructions
P.O. Reference: PO-889
Total Payable: Rs 85,000
"""

prompt = f"""
Extract these fields from the invoice text below.
Return ONLY a JSON object with exactly these keys:
company_name, address, ntn, invoice_number, date, customer, po_number, total.
Use null if a field is missing. total must be a number without commas.

Invoice text:
{invoice_text}
"""

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt,
    config={"response_mime_type": "application/json"},
)

print(response.text)
data = json.loads(response.text)
print(data["total"])