
from modules.po_matcher import match_purchase_order

def run_test(test_name, invoice_data):
    print(f"\n========== {test_name} ==========")

    result = match_purchase_order(invoice_data)

    for key, value in result.items():
        print(f"{key}: {value}")


# Test 1: Exact PO amount
run_test(
    "TEST 1 - EXACT MATCH",
    {
        "vendor_name": "TAMIL TECH SUPPLIES",
        "po_number": "PO-5001",
        "subtotal": 50000
    }
)


# Test 2: Amount within downward tolerance
run_test(
    "TEST 2 - WITHIN TOLERANCE",
    {
        "vendor_name": "TAMIL TECH SUPPLIES",
        "po_number": "PO-5001",
        "subtotal": 49500
    }
)


# Test 3: Amount above permitted tolerance
run_test(
    "TEST 3 - AMOUNT MISMATCH",
    {
        "vendor_name": "TAMIL TECH SUPPLIES",
        "po_number": "PO-5001",
        "subtotal": 50500
    }
)


# Test 4: Incorrect vendor
run_test(
    "TEST 4 - VENDOR MISMATCH",
    {
        "vendor_name": "ABC TECHNOLOGIES",
        "po_number": "PO-5001",
        "subtotal": 50000
    }
)
