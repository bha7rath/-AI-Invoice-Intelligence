
import fitz
import pytesseract
import cv2
import numpy as np

from PIL import Image
from io import BytesIO


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_scanned_pdf_text(file_bytes: bytes) -> dict:

    if not file_bytes:
        raise ValueError("PDF file is empty.")

    document = fitz.open(
        stream=file_bytes,
        filetype="pdf"
    )

    try:
        pages = []

        for page_number, page in enumerate(document, start=1):

            # Step 1: Convert PDF page into a high-resolution image
            pixmap = page.get_pixmap(dpi=300)

            image_bytes = pixmap.tobytes("png")

            image = Image.open(
                BytesIO(image_bytes)
            ).convert("RGB")

            # Step 2: Convert PIL image into OpenCV format
            image_array = np.array(image)

            # Step 3: Convert to grayscale
            gray = cv2.cvtColor(
                image_array,
                cv2.COLOR_RGB2GRAY
            )

            # Step 4: Remove small image noise
            blurred = cv2.GaussianBlur(
                gray,
                (3, 3),
                0
            )

            # Step 5: Improve text contrast
            processed = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11
            )

            # Step 6: Run Tesseract OCR
            page_text = pytesseract.image_to_string(
                processed,
                lang="eng",
                config="--psm 3"
            )

            pages.append(
                f"--- Page {page_number} ---\n{page_text}"
            )

        return {
            "page_count": document.page_count,
            "text": "\n\n".join(pages).strip()
        }

    finally:
        document.close()
