
from modules.validator import validate_invoice

invoice_data = {
    "vendor_name": "TAMIL TECH SUPPLIES",
    "gstin": "33AABCT1234F1Z5",
    "invoice_number": "INV-1001",
    "subtotal": 50000,
    "cgst": 4500,
    "sgst": 4500,
    "grand_total": 59000,
    "line_items": [
        {
            "description": "Wireless barcode scanner",
            "hsn_sac": "847160",
            "quantity": 10,
            "unit_price": 2500,
            "amount": 25000
        },
        {
            "description": "Thermal label printer",
            "hsn_sac": "844332",
            "quantity": 5,
            "unit_price": 5000,
            "amount": 25000
        }
    ]
}

result = validate_invoice(invoice_data)

print("\n========== FINANCIAL VALIDATION ==========\n")

for check in result["checks"]:
    print(check)

print("\n========== VALIDATION SUMMARY ==========")
print("Overall status:", result["overall_status"])
print("Passed checks:", result["passed_count"])
print("Failed checks:", result["failed_count"])
