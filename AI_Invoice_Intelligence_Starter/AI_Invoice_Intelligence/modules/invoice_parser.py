
import re


def clean_amount(value):
    """Convert extracted invoice amount into a number."""
    if not value:
        return None

    value = value.replace(",", "").strip()
    value = value.replace("₹", "")

    # Handle the sample PDF's incorrect rupee symbol extraction.
    if value.startswith("I"):
        value = value[1:]

    try:
        return float(value)
    except ValueError:
        return None


def extract_invoice_fields(text):
    """Extract structured invoice information from PDF text."""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    lines = [
        line for line in lines
        if not line.startswith("--- Page")
    ]

    cleaned_text = "\n".join(lines)

    invoice = {
        "vendor_name": lines[0] if lines else None,
        "invoice_number": None,
        "invoice_date": None,
        "po_number": None,
        "due_date": None,
        "payment_terms": None,
        "subtotal": None,
        "cgst": None,
        "sgst": None,
        "grand_total": None,
        "line_items": []
    }

    # Invoice number
    match = re.search(
        r"Invoice Number\s+([A-Z0-9/-]+)",
        cleaned_text,
        re.IGNORECASE
    )
    if match:
        invoice["invoice_number"] = match.group(1)

    # Invoice date
    match = re.search(
        r"Invoice Date\s+(\d{1,2}[-/]\w{3}[-/]\d{4})",
        cleaned_text,
        re.IGNORECASE
    )
    if match:
        invoice["invoice_date"] = match.group(1)

    # Purchase order number
    match = re.search(
        r"Purchase Order\s+(PO[-/]?\d+)",
        cleaned_text,
        re.IGNORECASE
    )
    if match:
        invoice["po_number"] = match.group(1)

    # Due date
    match = re.search(
        r"Due Date\s+(\d{1,2}[-/]\w{3}[-/]\d{4})",
        cleaned_text,
        re.IGNORECASE
    )
    if match:
        invoice["due_date"] = match.group(1)

    # Payment terms
    match = re.search(
        r"Payment Terms\s+(.+)",
        cleaned_text,
        re.IGNORECASE
    )
    if match:
        invoice["payment_terms"] = match.group(1)

    # Financial amounts
    amount_pattern = r"[₹I]?\s*([\d,]+\.\d{2})"

    total_patterns = {
        "subtotal": r"Subtotal\s+" + amount_pattern,
        "cgst": r"CGST\s*\(\s*9%\s*\)\s+" + amount_pattern,
        "sgst": r"SGST\s*\(\s*9%\s*\)\s+" + amount_pattern,
        "grand_total": r"Grand Total\s+" + amount_pattern,
    }

    for field, pattern in total_patterns.items():
        match = re.search(
            pattern,
            cleaned_text,
            re.IGNORECASE
        )

        if match:
            invoice[field] = clean_amount(match.group(1))

    # Line items
    for i, line in enumerate(lines):

        if line.isdigit() and i + 5 < len(lines):

            description = lines[i + 1]
            hsn_sac = lines[i + 2]
            quantity = lines[i + 3]
            unit_price = lines[i + 4]
            amount = lines[i + 5]

            if hsn_sac.isdigit() and quantity.isdigit():

                item = {
                    "description": description,
                    "hsn_sac": hsn_sac,
                    "quantity": int(quantity),
                    "unit_price": clean_amount(unit_price),
                    "amount": clean_amount(amount)
                }

                invoice["line_items"].append(item)

    return invoice
