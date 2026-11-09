
from modules.duplicate_checker import check_and_register_invoice
from datetime import datetime

vendor = "TAMIL TECH SUPPLIES"

# Generate a fresh invoice number for every test run
invoice_number = "TEST-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

print("Test invoice:", invoice_number)

print("\nFirst submission:")

first_result = check_and_register_invoice(
    vendor,
    invoice_number,
    "duplicate_test.pdf"
)

print("Duplicate:", first_result)

print("\nSecond submission:")

second_result = check_and_register_invoice(
    vendor,
    invoice_number,
    "duplicate_test.pdf"
)

print("Duplicate:", second_result)
