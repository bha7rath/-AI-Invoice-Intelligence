from pathlib import Path
from paddleocr import PaddleOCR


# Initialise the OCR model once
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="en"
)


def extract_text_with_paddleocr(image_path: str) -> dict:
    """
    Extract text and confidence scores from an invoice image.
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    results = ocr.predict(str(image_path))

    extracted_text = []
    confidence_scores = []

    for page in results:
        data = page.json

        if "res" in data:
            data = data["res"]

        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])

        for text, score in zip(texts, scores):
            extracted_text.append(text)
            confidence_scores.append(float(score))

    return {
        "text": "\n".join(extracted_text),
        "confidence_scores": confidence_scores,
        "average_confidence": (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores else 0.0
        ),
        "line_count": len(extracted_text)
    }