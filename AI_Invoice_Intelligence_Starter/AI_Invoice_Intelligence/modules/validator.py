from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def money(value):
    """Convert a value into a precise monetary amount.

    Returns None when the value is missing or cannot be converted
    into a valid finite monetary amount.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        amount = Decimal(str(value).strip())

        if not amount.is_finite():
            return None

        return amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None


def number(value):
    """Convert a numeric value into Decimal safely."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = Decimal(str(value).strip())

        if not result.is_finite():
            return None

        return result

    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None


def validate_invoice(invoice):
    """Validate invoice calculations and return detailed results.

    Invalid or malformed extracted data results in NEEDS REVIEW
    instead of crashing the application.
    """

    checks = []

    def add_check(name, passed, expected, actual, message):
        checks.append({
            "check": name,
            "status": "PASS" if passed else "FAIL",
            "expected": str(expected) if expected is not None else "Missing",
            "actual": str(actual) if actual is not None else "Missing",
            "message": message
        })

    # ---------------------------------------------------------
    # Basic invoice structure
    # ---------------------------------------------------------

    if not isinstance(invoice, dict):
        add_check(
            "Invoice structure",
            False,
            "Dictionary",
            type(invoice).__name__,
            "Invoice extraction result is not a valid object."
        )

        return {
            "checks": checks,
            "overall_status": "NEEDS REVIEW",
            "passed_count": 0,
            "failed_count": 1
        }

    # ---------------------------------------------------------
    # 1. Validate individual line items
    # ---------------------------------------------------------

    items = invoice.get("line_items")

    if items is None:
        items = []

    if not isinstance(items, list):
        add_check(
            "Line item validation",
            False,
            "List of line items",
            type(items).__name__,
            "Line items are not in the expected list format."
        )
        items = []

    item_amounts = []

    if not items:
        add_check(
            "Line item validation",
            False,
            "At least one line item",
            None,
            "No line items were extracted."
        )

    for index, item in enumerate(items, start=1):

        if not isinstance(item, dict):
            add_check(
                f"Line item {index}",
                False,
                "Line item object",
                type(item).__name__,
                "Line item is not in the expected object format."
            )
            continue

        quantity = number(item.get("quantity"))
        unit_price = money(item.get("unit_price"))
        actual_amount = money(item.get("amount"))

        # Missing or malformed values
        if quantity is None or unit_price is None or actual_amount is None:
            add_check(
                f"Line item {index}",
                False,
                "Valid quantity, unit price and amount",
                actual_amount,
                "Missing or invalid quantity, unit price or amount."
            )
            continue

        # Reject negative or zero quantity
        if quantity <= 0:
            add_check(
                f"Line item {index}",
                False,
                "> 0",
                quantity,
                "Quantity must be greater than zero."
            )
            continue

        # Reject negative unit price
        if unit_price < 0:
            add_check(
                f"Line item {index}",
                False,
                ">= 0.00",
                unit_price,
                "Unit price cannot be negative."
            )
            continue

        # Reject negative line amount
        if actual_amount < 0:
            add_check(
                f"Line item {index}",
                False,
                ">= 0.00",
                actual_amount,
                "Line-item amount cannot be negative."
            )
            continue

        expected_amount = money(
            quantity * unit_price
        )

        passed = expected_amount == actual_amount

        add_check(
            f"Line item {index}: {item.get('description')}",
            passed,
            expected_amount,
            actual_amount,
            "Quantity × Unit Price matches Amount."
            if passed
            else "Line-item amount does not match calculation."
        )

        if passed:
            item_amounts.append(actual_amount)

    # ---------------------------------------------------------
    # 2. Validate subtotal
    # ---------------------------------------------------------

    subtotal = money(invoice.get("subtotal"))

    if subtotal is not None and subtotal < 0:
        add_check(
            "Subtotal validation",
            False,
            ">= 0.00",
            subtotal,
            "Subtotal cannot be negative."
        )
        subtotal = None

    if not item_amounts:
        add_check(
            "Subtotal validation",
            False,
            "Sum of valid line items",
            subtotal,
            "Cannot validate subtotal because valid line items are missing."
        )

    elif subtotal is None:
        add_check(
            "Subtotal validation",
            False,
            money(sum(item_amounts)),
            None,
            "Subtotal is missing or invalid."
        )

    else:
        calculated_subtotal = money(sum(item_amounts))

        passed = calculated_subtotal == subtotal

        add_check(
            "Subtotal validation",
            passed,
            calculated_subtotal,
            subtotal,
            "Line-item amounts match subtotal."
            if passed
            else "Subtotal does not match line-item amounts."
        )

    # ---------------------------------------------------------
    # 3. Validate taxes
    # ---------------------------------------------------------

    cgst = money(invoice.get("cgst"))
    sgst = money(invoice.get("sgst"))

    tax_valid = True

    if cgst is None or sgst is None:
        tax_valid = False

        add_check(
            "Tax validation",
            False,
            "Valid CGST and SGST",
            None,
            "CGST or SGST is missing or invalid."
        )

    elif cgst < 0 or sgst < 0:
        tax_valid = False

        add_check(
            "Tax validation",
            False,
            "CGST and SGST >= 0.00",
            f"CGST={cgst}, SGST={sgst}",
            "Tax values cannot be negative."
        )

    else:
        total_tax = money(cgst + sgst)

        add_check(
            "Tax validation",
            True,
            total_tax,
            total_tax,
            "CGST and SGST values are valid."
        )

    # ---------------------------------------------------------
    # 4. Validate grand total
    # ---------------------------------------------------------

    grand_total = money(invoice.get("grand_total"))

    if grand_total is not None and grand_total < 0:
        add_check(
            "Grand total validation",
            False,
            ">= 0.00",
            grand_total,
            "Grand total cannot be negative."
        )
        grand_total = None

    if subtotal is None or cgst is None or sgst is None:
        add_check(
            "Grand total validation",
            False,
            "Subtotal + CGST + SGST",
            grand_total,
            "Cannot calculate total because subtotal or tax is missing or invalid."
        )

    elif grand_total is None:
        expected_total = money(
            subtotal + cgst + sgst
        )

        add_check(
            "Grand total validation",
            False,
            expected_total,
            None,
            "Grand total is missing or invalid."
        )

    else:
        expected_total = money(
            subtotal + cgst + sgst
        )

        passed = expected_total == grand_total

        add_check(
            "Grand total validation",
            passed,
            expected_total,
            grand_total,
            "Grand total calculation is correct."
            if passed
            else "Grand total does not match subtotal plus taxes."
        )

    # ---------------------------------------------------------
    # Overall validation result
    # ---------------------------------------------------------

    all_passed = bool(checks) and all(
        check["status"] == "PASS"
        for check in checks
    )

    return {
        "checks": checks,
        "overall_status": "PASS" if all_passed else "NEEDS REVIEW",
        "passed_count": sum(
            check["status"] == "PASS"
            for check in checks
        ),
        "failed_count": sum(
            check["status"] == "FAIL"
            for check in checks
        )
    }