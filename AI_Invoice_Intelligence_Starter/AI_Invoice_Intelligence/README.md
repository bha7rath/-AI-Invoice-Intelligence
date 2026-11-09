# AI Invoice Intelligence

A staged prototype for the Zamp AI Solutions Analyst PS-1 case study.

## Stage 1
- Upload a PDF invoice.
- Extract selectable PDF text with PyMuPDF.
- Detect likely scanned PDFs when no selectable text is found.

## Run locally (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If `py -3.11` is unavailable, use `python` to create the virtual environment.

## Important
This is only the first module. It does not yet approve invoices, make payments,
or verify bank details. Scanned-PDF OCR, LLM extraction, validation, duplicate
checks, PO matching, human review, audit logging and deployment are later stages.
