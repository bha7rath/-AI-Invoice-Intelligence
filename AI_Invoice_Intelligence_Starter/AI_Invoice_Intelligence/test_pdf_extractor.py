from modules.pdf_extractor import extract_pdf_text

pdf_path = "sample_data/invoices/sample_scanned_invoice.pdf"

with open(pdf_path, "rb") as file:
    pdf_bytes = file.read()

result = extract_pdf_text(pdf_bytes)

print("\n========== EXTRACTED TEXT ==========\n")
print(result["text"])

print("\n========== EXTRACTION SUMMARY ==========")
print("Pages:", result["page_count"])
print("Methods:", result["extraction_methods"])