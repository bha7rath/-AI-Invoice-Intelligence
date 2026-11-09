
from modules.groq_extractor import extract_invoice_with_groq
from modules.pdf_extractor import extract_pdf_text

pdf_path = "sample_data/invoices/sample_scanned_invoice.pdf"

# Step 1: Read the PDF
with open(pdf_path, "rb") as file:
    pdf_bytes = file.read()

# Step 2: Extract text using PyMuPDF or PaddleOCR
pdf_result = extract_pdf_text(pdf_bytes)

print("Extraction method:", pdf_result["extraction_methods"])

# Step 3: Send the extracted text to Groq
print("\nSending extracted text to Groq...")

invoice_data = extract_invoice_with_groq(pdf_result["text"])

# Step 4: Display structured invoice data
print("\n========== GROQ INVOICE DATA ==========\n")

for key, value in invoice_data.items():
    print(f"{key}: {value}")
