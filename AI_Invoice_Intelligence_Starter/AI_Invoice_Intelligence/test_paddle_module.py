from modules.paddle_ocr_extractor import (
    extract_text_with_paddleocr
)

image_path = "sample_data/invoices/paddle_test.png"

result = extract_text_with_paddleocr(image_path)

print("\n========== EXTRACTED TEXT ==========\n")
print(result["text"])

print("\n========== OCR SUMMARY ==========")
print("Detected lines:", result["line_count"])
print("Average confidence:", round(result["average_confidence"], 4))