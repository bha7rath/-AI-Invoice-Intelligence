
import fitz  # PyMuPDF
from pathlib import Path
from paddleocr import PaddleOCR
from PIL import Image
import numpy as np
import io


# Load PaddleOCR model only once
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="en"
)


def extract_pdf_text(file_bytes: bytes) -> dict:
    """
    Extract text from normal and scanned PDFs.

    Normal PDF:
        Uses PyMuPDF.

    Scanned PDF:
        Uses PaddleOCR.
    """

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    document = fitz.open(
        stream=file_bytes,
        filetype="pdf"
    )

    try:
        pages = []
        extraction_methods = []

        for page_number, page in enumerate(document, start=1):

            # First try extracting selectable text
            page_text = page.get_text("text").strip()

            if len(page_text) >= 30:
                extraction_methods.append("PyMuPDF")
                pages.append(
                    f"--- Page {page_number} ---\n{page_text}"
                )

            else:
                # If selectable text is missing, use PaddleOCR
                pixmap = page.get_pixmap(dpi=200)
                image_bytes = pixmap.tobytes("png")

                image = Image.open(
                    io.BytesIO(image_bytes)
                ).convert("RGB")

                image_array = np.array(image)

                results = ocr.predict(image_array)

                ocr_lines = []

                for result in results:
                    data = result.json

                    if "res" in data:
                        data = data["res"]

                    texts = data.get("rec_texts", [])

                    ocr_lines.extend(texts)

                page_text = "\n".join(ocr_lines)

                extraction_methods.append("PaddleOCR")

                pages.append(
                    f"--- Page {page_number} ---\n{page_text}"
                )

        return {
            "page_count": document.page_count,
            "text": "\n\n".join(pages).strip(),
            "extraction_methods": extraction_methods,
        }

    finally:
        document.close()
