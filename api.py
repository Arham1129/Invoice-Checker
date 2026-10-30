from fastapi import FastAPI

api = FastAPI(title="Invoice Checker API")


@api.get("/health")
def health():
    return {"status": "ok"}