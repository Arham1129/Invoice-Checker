from fastapi import FastAPI, UploadFile

from checker import check_invoice
from database import setup_database
from extractor import extract_fields_with_ai, extract_fields_with_regex, read_pdf

api = FastAPI(title="Invoice Checker API")
setup_database()


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/check-invoice")
def check_invoice_endpoint(file: UploadFile):
    text = read_pdf(file.file)
    if not text.strip():
        return {"error": "No text found. This may be a scanned PDF."}

    fields = extract_fields_with_ai(text)
    source = "AI"
    if fields is None:
        fields = extract_fields_with_regex(text)
        source = "regex"

    status, message = check_invoice(fields["PO Number"], fields["Total"], fields["Company Name"])
    return {"source": source, "fields": fields, "status": status, "message": message}