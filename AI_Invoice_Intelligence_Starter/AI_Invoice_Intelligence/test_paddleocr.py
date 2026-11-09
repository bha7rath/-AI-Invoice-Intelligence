from paddleocr import PaddleOCR

IMAGE_PATH = "sample_data/invoices/paddle_test.png"

print("Loading PaddleOCR model...")

ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="en"
)

print("Running OCR on invoice...")

results = ocr.predict(IMAGE_PATH)

print("\n========== OCR OUTPUT ==========\n")

for page in results:
    page.print()

print("\n========== OCR TEST COMPLETED ==========") 