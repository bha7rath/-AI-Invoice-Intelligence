import io
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation

import pandas as pd
from modules.duplicate_checker import get_po_usage

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
PO_FILE = PROJECT_FOLDER / "data" / "purchase_orders.json"


def normalize(value):
    """Normalize text before comparing vendor names and PO numbers."""

    if value is None:
        return ""

    return " ".join(str(value).strip().lower().split())


def to_decimal(value):
    """Safely convert a value into Decimal."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        cleaned = (
            str(value)
            .replace(",", "")
            .replace("₹", "")
            .strip()
        )

        result = Decimal(cleaned)

        if not result.is_finite():
            return None

        return result

    except (InvalidOperation, ValueError, TypeError):
        return None


def find_column(columns, possible_names):
    """
    Find a spreadsheet column using several possible column names.
    """

    normalized_columns = {
        normalize(column): column
        for column in columns
    }

    for name in possible_names:

        normalized_name = normalize(name)

        if normalized_name in normalized_columns:
            return normalized_columns[normalized_name]

    return None


def load_purchase_orders_from_excel(excel_source):
    """
    Read purchase orders from an Excel spreadsheet.

    Required columns:
        PO Number
        Vendor
        PO Amount

    Optional columns:
        Upward Tolerance %
        Downward Tolerance %
    """

    try:

        if isinstance(excel_source, bytes):
            excel_source = io.BytesIO(excel_source)

        dataframe = pd.read_excel(excel_source)

    except Exception as error:

        raise ValueError(
            f"Unable to read PO spreadsheet: {error}"
        )

    if dataframe.empty:

        raise ValueError(
            "The PO spreadsheet is empty."
        )

    # ---------------------------------------------------------
    # Find required columns
    # ---------------------------------------------------------

    po_number_column = find_column(
        dataframe.columns,
        [
            "PO Number",
            "PO",
            "PO No",
            "PO Number",
            "Purchase Order",
            "Purchase Order Number",
        ],
    )

    vendor_column = find_column(
        dataframe.columns,
        [
            "Vendor",
            "Vendor Name",
            "Supplier",
            "Supplier Name",
        ],
    )

    po_amount_column = find_column(
        dataframe.columns,
        [
            "PO Amount",
            "PO Value",
            "Purchase Order Amount",
            "Purchase Order Value",
            "Amount",
        ],
    )

    # ---------------------------------------------------------
    # Find optional tolerance columns
    # ---------------------------------------------------------

    upward_column = find_column(
        dataframe.columns,
        [
            "Upward Tolerance %",
            "Upward Tolerance",
            "Upward Tolerance Percent",
            "Up Tolerance %",
        ],
    )

    downward_column = find_column(
        dataframe.columns,
        [
            "Downward Tolerance %",
            "Downward Tolerance",
            "Downward Tolerance Percent",
            "Down Tolerance %",
        ],
    )

    # ---------------------------------------------------------
    # Check required columns
    # ---------------------------------------------------------

    missing_columns = []

    if po_number_column is None:
        missing_columns.append("PO Number")

    if vendor_column is None:
        missing_columns.append("Vendor")

    if po_amount_column is None:
        missing_columns.append("PO Amount")

    if missing_columns:

        raise ValueError(
            "The PO spreadsheet is missing required column(s): "
            + ", ".join(missing_columns)
        )

    # ---------------------------------------------------------
    # Convert spreadsheet rows into PO records
    # ---------------------------------------------------------

    purchase_orders = []

    for _, row in dataframe.iterrows():

        po_number = row[po_number_column]
        vendor_name = row[vendor_column]
        po_amount = row[po_amount_column]

        # Ignore completely empty rows
        if (
            pd.isna(po_number)
            and pd.isna(vendor_name)
            and pd.isna(po_amount)
        ):
            continue

        upward_tolerance = (
            row[upward_column]
            if upward_column is not None
            else 0
        )

        downward_tolerance = (
            row[downward_column]
            if downward_column is not None
            else 0
        )

        purchase_orders.append(
            {
                "po_number": po_number,
                "vendor_name": vendor_name,
                "po_amount": po_amount,
                "upward_tolerance_percent": upward_tolerance,
                "downward_tolerance_percent": downward_tolerance,
            }
        )

    if not purchase_orders:

        raise ValueError(
            "No valid purchase orders were found in the spreadsheet."
        )

    return purchase_orders


def load_purchase_orders_from_json():
    """
    Load purchase orders from the existing JSON file.

    This is retained as a fallback so the old project data
    continues to work.
    """

    if not PO_FILE.exists():

        raise ValueError(
            "Purchase order database not found."
        )

    try:

        with open(
            PO_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

    except (OSError, json.JSONDecodeError):

        raise ValueError(
            "Unable to read purchase order database."
        )

    purchase_orders = data.get(
        "purchase_orders",
        [],
    )

    if not purchase_orders:

        raise ValueError(
            "No purchase orders found in the database."
        )

    return purchase_orders


def load_purchase_orders(po_source=None):
    """
    Load purchase orders.

    If po_source is provided:
        Use the uploaded Excel spreadsheet.

    If po_source is not provided:
        Use the existing JSON database.
    """

    if po_source is None:

        return load_purchase_orders_from_json()

    return load_purchase_orders_from_excel(
        po_source
    )


def match_purchase_order(
    invoice_data,
    po_source=None,
):
    """
    Match invoice details with a purchase order.

    po_source:
        Uploaded Excel spreadsheet bytes/file.

    If po_source is None, the existing JSON database
    is used as a fallback.

    Returns:
        MATCH
        MISMATCH
        NEEDS REVIEW
    """

    # ---------------------------------------------------------
    # Get invoice information
    # ---------------------------------------------------------

    po_number = invoice_data.get(
        "po_number"
    )

    vendor_name = invoice_data.get(
        "vendor_name"
    )

    invoice_amount = invoice_data.get(
        "subtotal"
    )

    # ---------------------------------------------------------
    # Check required invoice fields
    # ---------------------------------------------------------

    if (
        not po_number
        or not vendor_name
        or invoice_amount is None
    ):

        return {
            "status": "NEEDS REVIEW",
            "message": (
                "PO number, vendor name or "
                "invoice subtotal is missing."
            ),
        }

    # ---------------------------------------------------------
    # Convert invoice amount
    # ---------------------------------------------------------

    invoice_amount = to_decimal(
        invoice_amount
    )

    if (
        invoice_amount is None
        or invoice_amount < 0
    ):

        return {
            "status": "NEEDS REVIEW",
            "message": (
                "Invoice subtotal is invalid."
            ),
        }

    # ---------------------------------------------------------
    # Load company PO data
    # ---------------------------------------------------------

    try:

        purchase_orders = load_purchase_orders(
            po_source
        )

    except ValueError as error:

        return {
            "status": "NEEDS REVIEW",
            "message": str(error),
        }

    # ---------------------------------------------------------
    # Find matching PO number
    # ---------------------------------------------------------

    matched_po = None

    for po in purchase_orders:

        if (
            normalize(
                po.get("po_number")
            )
            == normalize(po_number)
        ):

            matched_po = po
            break

    # ---------------------------------------------------------
    # PO not found
    # ---------------------------------------------------------

    if matched_po is None:

        return {
            "status": "NEEDS REVIEW",
            "po_number": po_number,
            "invoice_amount": float(
                invoice_amount
            ),
            "message": (
                f"Purchase order {po_number} "
                "was not found in the company PO data."
            ),
        }

    # ---------------------------------------------------------
    # Verify vendor
    # ---------------------------------------------------------

    po_vendor = normalize(
        matched_po.get(
            "vendor_name"
        )
    )

    invoice_vendor = normalize(
        vendor_name
    )

    if po_vendor != invoice_vendor:

        return {
            "status": "MISMATCH",
            "po_number": po_number,
            "po_amount": float(
                to_decimal(
                    matched_po.get(
                        "po_amount"
                    )
                )
                or Decimal("0")
            ),
            "invoice_amount": float(
                invoice_amount
            ),
            "difference": None,
            "message": (
                "Invoice vendor does not match "
                "the PO vendor."
            ),
        }

    # ---------------------------------------------------------
    # Read PO amount
    # ---------------------------------------------------------

    po_amount = to_decimal(
        matched_po.get(
            "po_amount"
        )
    )

    if (
        po_amount is None
        or po_amount <= 0
    ):

        return {
            "status": "NEEDS REVIEW",
            "po_number": po_number,
            "message": (
                "PO amount is missing or invalid."
            ),
        }

    # ---------------------------------------------------------
    # Read tolerance percentages
    # ---------------------------------------------------------

    upward_percent = to_decimal(
        matched_po.get(
            "upward_tolerance_percent",
            0,
        )
    )

    downward_percent = to_decimal(
        matched_po.get(
            "downward_tolerance_percent",
            0,
        )
    )

    if upward_percent is None:
        upward_percent = Decimal("0")

    if downward_percent is None:
        downward_percent = Decimal("0")

    # ---------------------------------------------------------
    # Validate tolerance configuration
    # ---------------------------------------------------------

    if (
        upward_percent < 0
        or downward_percent < 0
        or upward_percent > 100
        or downward_percent > 100
    ):

        return {
            "status": "NEEDS REVIEW",
            "po_number": po_number,
            "message": (
                "PO tolerance configuration is invalid."
            ),
        }

    # ---------------------------------------------------------
    # Calculate tolerance range
    # ---------------------------------------------------------

    upward_amount = (
        po_amount
        * upward_percent
        / Decimal("100")
    )

    downward_amount = (
        po_amount
        * downward_percent
        / Decimal("100")
    )

    minimum_amount = (
        po_amount
        - downward_amount
    )

    maximum_amount = (
        po_amount
        + upward_amount
    )

    # ---------------------------------------------------------
    # Check cumulative PO usage
    # ---------------------------------------------------------

    try:
        po_usage = get_po_usage(
            po_number
        )
    except Exception:
        return {
            "status": "NEEDS REVIEW",
            "po_number": po_number,
            "message": (
                "Unable to read previous "
                "invoice usage for this PO."
            ),
        }

    previous_invoice_count = int(
        po_usage.get(
            "invoice_count",
            0
        )
        or 0
    )

    previous_used_amount = to_decimal(
        po_usage.get(
            "used_amount",
            0
        )
    )

    if previous_used_amount is None:
        previous_used_amount = Decimal("0")

    cumulative_amount = (
        previous_used_amount
        + invoice_amount
    )

    cumulative_difference = (
        cumulative_amount
        - po_amount
    )

    remaining_before_invoice = (
        maximum_amount
        - previous_used_amount
    )

    # ---------------------------------------------------------
    # Compare cumulative invoice amount against PO limit
    # ---------------------------------------------------------

    if (
        minimum_amount
        <= cumulative_amount
        <= maximum_amount
    ):

        return {
            "status": "MATCH",
            "po_number": po_number,
            "po_amount": float(
                po_amount
            ),
            "invoice_amount": float(
                invoice_amount
            ),
            "previous_invoice_count": (
                previous_invoice_count
            ),
            "previous_used_amount": float(
                previous_used_amount
            ),
            "cumulative_amount": float(
                cumulative_amount
            ),
            "remaining_before_invoice": float(
                remaining_before_invoice
            ),
            "upward_tolerance_percent": float(
                upward_percent
            ),
            "downward_tolerance_percent": float(
                downward_percent
            ),
            "minimum_allowed": float(
                minimum_amount
            ),
            "maximum_allowed": float(
                maximum_amount
            ),
            "difference": float(
                cumulative_difference
            ),
            "message": (
                "Invoice and previous invoices "
                "are within the permitted "
                "cumulative PO tolerance."
            ),
        }

    # ---------------------------------------------------------
    # Amount mismatch
    # ---------------------------------------------------------

    return {
        "status": "MISMATCH",
        "po_number": po_number,
        "po_amount": float(
            po_amount
        ),
        "invoice_amount": float(
            invoice_amount
        ),
        "previous_invoice_count": (
            previous_invoice_count
        ),
        "previous_used_amount": float(
            previous_used_amount
        ),
        "cumulative_amount": float(
            cumulative_amount
        ),
        "remaining_before_invoice": float(
            remaining_before_invoice
        ),
        "upward_tolerance_percent": float(
            upward_percent
        ),
        "downward_tolerance_percent": float(
            downward_percent
        ),
        "minimum_allowed": float(
            minimum_amount
        ),
        "maximum_allowed": float(
            maximum_amount
        ),
        "difference": float(
            cumulative_difference
        ),
        "message": (
            "Cumulative invoice amount is outside "
            "the permitted PO tolerance."
        ),
    }
