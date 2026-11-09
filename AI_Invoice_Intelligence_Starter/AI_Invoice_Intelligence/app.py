import streamlit as st
import json
import base64
import re
from pathlib import Path
from datetime import datetime

from modules.pdf_extractor import extract_pdf_text
from modules.groq_extractor import extract_invoice_with_groq
from modules.validator import validate_invoice
from modules.duplicate_checker import (
    is_duplicate_invoice,
    register_invoice,
    record_audit_event,
    get_audit_history
)
from modules.po_matcher import match_purchase_order


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="AI Invoice Intelligence",
    page_icon="📄",
    layout="wide"
)

st.title("📄 AI Invoice Intelligence")

st.caption(
    "AI-powered invoice extraction, duplicate detection, "
    "purchase order matching and financial validation"
)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def display_amount(value):
    try:
        if value is None or value == "":
            return "Not available"

        return f"₹{float(value):,.2f}"

    except (ValueError, TypeError):
        return "Not available"


def is_missing(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


# ==================================================
# ORIGINAL INVOICE FILE STORAGE
# ==================================================

PROJECT_FOLDER = Path(__file__).resolve().parent
PROCESSED_INVOICE_FOLDER = PROJECT_FOLDER / "data" / "processed_invoices"


def save_uploaded_invoice(uploaded_file):
    PROCESSED_INVOICE_FOLDER.mkdir(parents=True, exist_ok=True)
    original_name = Path(uploaded_file.name).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stored_path = PROCESSED_INVOICE_FOLDER / f"{timestamp}__{safe_name}"
    stored_path.write_bytes(uploaded_file.getvalue())
    return stored_path


def find_saved_invoice(source_file):
    if not source_file:
        return None

    safe_name = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        Path(str(source_file)).name
    )

    if not PROCESSED_INVOICE_FOLDER.exists():
        return None

    matches = list(PROCESSED_INVOICE_FOLDER.glob(f"*__{safe_name}"))
    if not matches:
        return None

    return max(matches, key=lambda path: path.stat().st_mtime)


def display_invoice_file_for_review(source_file):
    file_path = find_saved_invoice(source_file)

    if file_path is None:
        st.warning(
            "The original PDF is not available for this older audit record. "
            "Invoices processed after file storage was enabled will be available here."
        )
        return

    pdf_bytes = file_path.read_bytes()

    st.success(f"Original invoice available: {source_file}")

    st.download_button(
        label="📥 Download Original Invoice PDF",
        data=pdf_bytes,
        file_name=Path(source_file).name,
        mime="application/pdf",
        key=f"download_{file_path.name}"
    )

    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    pdf_html = f'''
        <iframe
            src="data:application/pdf;base64,{encoded_pdf}"
            width="100%"
            height="700"
            style="border: 1px solid #444; border-radius: 8px;"
        ></iframe>
    '''

    st.components.v1.html(
        pdf_html,
        height=720,
        scrolling=True
    )


def get_missing_fields(invoice_data):
    required_fields = [
        "vendor_name",
        "gstin",
        "invoice_number",
        "invoice_date",
        "grand_total",
        "po_number"
    ]

    return [
        field
        for field in required_fields
        if is_missing(invoice_data.get(field))
    ]


# ==================================================
# AUDIT DASHBOARD
# ==================================================

def render_dashboard(dashboard_placeholder):
    with dashboard_placeholder.container():
        st.header("📊 AP Processing Dashboard")

        try:

            audit_records = get_audit_history(limit=100)

            # ----------------------------------------------
            # Normalize audit records
            # ----------------------------------------------

            normalized_records = []

            for record in audit_records:

                if isinstance(record, dict):

                    normalized_records.append({
                        "id": record.get("id"),
                        "vendor_name": record.get("vendor_name"),
                        "invoice_number": record.get("invoice_number"),
                        "source_file": record.get("source_file"),
                        "decision": record.get("decision"),
                        "duplicate_status": record.get("duplicate_status"),
                        "validation_status": record.get("validation_status"),
                        "po_status": record.get("po_status"),
                        "missing_fields": record.get("missing_fields"),
                        "registration_status": record.get(
                            "registration_status"
                        ),
                        "po_number": record.get("po_number"),
                        "po_amount": record.get("po_amount"),
                        "previous_used_amount": record.get("previous_used_amount"),
                        "invoice_amount": record.get("invoice_amount"),
                        "cumulative_amount": record.get("cumulative_amount"),
                        "maximum_allowed": record.get("maximum_allowed"),
                        "created_at": record.get("created_at")
                    })

                elif isinstance(record, (tuple, list)):

                    # Expected audit table column order
                    normalized_records.append({
                        "id": record[0] if len(record) > 0 else None,
                        "vendor_name": record[1] if len(record) > 1 else None,
                        "invoice_number": record[2] if len(record) > 2 else None,
                        "source_file": record[3] if len(record) > 3 else None,
                        "decision": record[4] if len(record) > 4 else None,
                        "duplicate_status": record[5] if len(record) > 5 else None,
                        "validation_status": record[6] if len(record) > 6 else None,
                        "po_status": record[7] if len(record) > 7 else None,
                        "missing_fields": record[8] if len(record) > 8 else None,
                        "registration_status": record[9] if len(record) > 9 else None,
                        "po_number": record[11] if len(record) > 11 else None,
                        "po_amount": record[12] if len(record) > 12 else None,
                        "previous_used_amount": record[13] if len(record) > 13 else None,
                        "invoice_amount": record[14] if len(record) > 14 else None,
                        "cumulative_amount": record[15] if len(record) > 15 else None,
                        "maximum_allowed": record[16] if len(record) > 16 else None,
                        "created_at": record[10] if len(record) > 10 else None
                    })


            # ----------------------------------------------
            # Dashboard statistics
            # ----------------------------------------------

            total_processed = len(normalized_records)

            approved_count = sum(
                1
                for record in normalized_records
                if record["decision"] == "APPROVED FOR HUMAN REVIEW"
            )

            duplicate_count = sum(
                1
                for record in normalized_records
                if record["decision"] == "DUPLICATE - STOPPED"
            )

            po_mismatch_count = sum(
                1
                for record in normalized_records
                if record["decision"] == "HOLD - PO MISMATCH"
            )

            needs_review_count = sum(
                1
                for record in normalized_records
                if record["decision"] == "NEEDS REVIEW"
            )

            # ----------------------------------------------
            # Metrics
            # ----------------------------------------------

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "Total Attempts",
                    total_processed
                )

            with col2:
                st.metric(
                    "Approved",
                    approved_count
                )

            with col3:
                st.metric(
                    "Needs Review",
                    needs_review_count
                )

            with col4:
                st.metric(
                    "Duplicates Stopped",
                    duplicate_count
                )

            with col5:
                st.metric(
                    "PO Mismatches",
                    po_mismatch_count
                )


            # ----------------------------------------------
            # Recent history
            # ----------------------------------------------

            st.subheader("🧾 Recent Processing History")

            if normalized_records:

                history_rows = []

                for record in normalized_records:

                    invoice_number = record["invoice_number"]

                    if not invoice_number:
                        invoice_number = "Missing"

                    decision = record["decision"] or "Unknown"

                    history_rows.append({
                        "Invoice": invoice_number,
                        "Vendor": record["vendor_name"] or "Unknown",
                        "Decision": decision,
                        "Duplicate": record["duplicate_status"] or "N/A",
                        "Validation": record["validation_status"] or "N/A",
                        "PO Status": record["po_status"] or "N/A",
                        "Missing Fields": (
                            record["missing_fields"]
                            if record["missing_fields"]
                            else "None"
                        ),
                        "Source File": record["source_file"] or "Unknown",
                        "Registered": (
                            "Yes"
                            if record["registration_status"]
                            else "No"
                        ),
                        "Processed At": record["created_at"] or ""
                    })

                st.dataframe(
                    history_rows,
                    use_container_width=True,
                    hide_index=True
                )

                # ----------------------------------------------
                # Original invoice download / review
                # ----------------------------------------------

                st.subheader("📎 Original Invoice Files")

                st.caption(
                    "For invoices marked NEEDS REVIEW, HOLD or DUPLICATE, "
                    "use the Download button below to inspect the exact PDF "
                    "that was processed."
                )

                for index, record in enumerate(normalized_records):
                    invoice_label = record["invoice_number"] or "Missing"
                    vendor_label = record["vendor_name"] or "Unknown"
                    decision_label = record["decision"] or "Unknown"
                    source_label = record["source_file"] or "Unknown file"

                    col_a, col_b, col_c, col_d = st.columns([1.2, 2.2, 2.2, 1.2])

                    with col_a:
                        st.write(f"**{invoice_label}**")

                    with col_b:
                        st.write(vendor_label)

                    with col_c:
                        st.write(decision_label)

                    with col_d:
                        file_path = find_saved_invoice(source_label)

                        if file_path is not None:
                            st.download_button(
                                label="📥 Download",
                                data=file_path.read_bytes(),
                                file_name=Path(source_label).name,
                                mime="application/pdf",
                                key=f"history_download_{index}_{file_path.name}"
                            )
                        else:
                            st.caption("Not available")

                    if decision_label in {
                        "NEEDS REVIEW",
                        "HOLD - PO MISMATCH",
                        "DUPLICATE - STOPPED"
                    }:
                        st.caption(
                            f"⚠️ {decision_label} — Original invoice: {source_label}"
                        )

                st.divider()

            else:

                st.info(
                    "No invoice processing history is available yet."
                )

        except Exception as dashboard_error:

            st.warning(
                f"Audit dashboard could not be loaded: {dashboard_error}"
            )


        st.divider()


# Dashboard placeholder is created once and refreshed after processing.
dashboard_placeholder = st.empty()
render_dashboard(dashboard_placeholder)


# ==================================================
# SIDEBAR
# ==================================================

with st.sidebar:

    st.header("System Information")

    st.success("Groq AI: Connected")
    st.success("PDF Extraction: PyMuPDF + PaddleOCR")
    st.success("Duplicate Detection: Ready")
    st.success("Financial Validation: Ready")
    st.success("PO Matching: Ready")
    st.success("Audit Logging: Ready")

    st.divider()

    st.subheader("Processing Workflow")

    workflow = [
        "Upload company PO spreadsheet",
        "Upload vendor invoice",
        "Extract PDF text",
        "Extract invoice fields using AI",
        "Check duplicate invoices",
        "Validate financial information",
        "Match purchase order",
        "Make processing decision",
        "Register eligible invoice",
        "Record audit history"
    ]

    for index, step in enumerate(workflow, start=1):
        st.write(f"{index}. {step}")


# ==================================================
# FILE UPLOAD
# ==================================================

st.header("1. Upload Company PO Spreadsheet")

po_file = st.file_uploader(
    "Upload the company's purchase-order/master spreadsheet",
    type=["xlsx"],
    help="Upload the Excel file containing PO number, vendor name, PO amount and optional tolerance columns."
)

st.header("2. Upload Vendor Invoice")

uploaded_file = st.file_uploader(
    "Upload a vendor invoice PDF",
    type=["pdf"]
)

if po_file is not None:
    st.success(f"Company PO spreadsheet uploaded: {po_file.name}")
else:
    st.info("No company spreadsheet uploaded. The system will use the default purchase_orders.json file.")

if uploaded_file is not None:

    st.success(f"Uploaded: {uploaded_file.name}")

    if st.button("Process Invoice", type="primary"):

        # Initialise output variables
        pdf_result = {}
        invoice_data = {}
        validation_result = {}
        po_result = {}

        duplicate = None
        registration_status = False
        decision = "PROCESSING FAILED"
        missing_fields = []
        extraction_methods = []
        validation_status = "NEEDS REVIEW"
        po_status = "NEEDS REVIEW"
        stored_invoice_path = None

        try:

            # ======================================
            # STEP 1: PDF EXTRACTION
            # ======================================

            with st.status(
                "Processing invoice...",
                expanded=True
            ) as status:

                st.write(
                    "Step 0: Saving original vendor invoice for audit review..."
                )

                stored_invoice_path = save_uploaded_invoice(
                    uploaded_file
                )

                st.success(
                    "Original invoice PDF saved for later review."
                )

                st.write(
                    "Step 1: Extracting PDF text..."
                )

                pdf_result = extract_pdf_text(
                    uploaded_file.getvalue()
                )

                extracted_text = pdf_result.get(
                    "text",
                    ""
                )

                if (
                    not extracted_text
                    or not extracted_text.strip()
                ):
                    raise ValueError(
                        "No readable text could be extracted "
                        "from this invoice."
                    )

                extraction_methods = pdf_result.get(
                    "extraction_methods",
                    []
                )

                st.success(
                    f"Extracted text from "
                    f"{pdf_result.get('page_count', 0)} page(s)."
                )

                st.write(
                    "Extraction method(s):",
                    ", ".join(extraction_methods)
                    or "Unknown"
                )


                # ==================================
                # STEP 2: GROQ EXTRACTION
                # ==================================

                st.write(
                    "Step 2: Extracting invoice fields using Groq..."
                )

                invoice_data = extract_invoice_with_groq(
                    extracted_text
                )

                if not isinstance(
                    invoice_data,
                    dict
                ):
                    raise ValueError(
                        "AI extraction did not return valid "
                        "invoice data."
                    )

                st.success(
                    "Invoice data extraction completed."
                )


                # ==================================
                # STEP 3: DUPLICATE CHECK
                # ==================================

                st.write(
                    "Step 3: Checking for duplicate invoices..."
                )

                vendor_name = invoice_data.get(
                    "vendor_name"
                )

                invoice_number = invoice_data.get(
                    "invoice_number"
                )

                if (
                    is_missing(vendor_name)
                    or is_missing(invoice_number)
                ):

                    duplicate = None

                    st.warning(
                        "Duplicate check could not be completed "
                        "because vendor name or invoice number "
                        "is missing."
                    )

                else:

                    duplicate = is_duplicate_invoice(
                        vendor_name,
                        invoice_number
                    )

                    if duplicate:

                        st.error(
                            "Duplicate invoice detected."
                        )

                    else:

                        st.success(
                            "No existing duplicate found."
                        )


                # ==================================
                # STEP 4: FINANCIAL VALIDATION
                # ==================================

                st.write(
                    "Step 4: Validating financial information..."
                )

                validation_result = validate_invoice(
                    invoice_data
                )

                validation_status = validation_result.get(
                    "overall_status",
                    "NEEDS REVIEW"
                )

                st.write(
                    "Financial validation:",
                    validation_status
                )


                # ==================================
                # STEP 5: PURCHASE ORDER MATCHING
                # ==================================

                st.write(
                    "Step 5: Matching purchase order..."
                )

                po_source = (
                    po_file.getvalue()
                    if po_file is not None
                    else None
                )

                po_result = match_purchase_order(
                    invoice_data,
                    po_source=po_source
                )

                po_status = po_result.get(
                    "status",
                    "NEEDS REVIEW"
                )

                st.write(
                    "PO matching status:",
                    po_status
                )


                # ==================================
                # STEP 6: REQUIRED FIELD CHECK
                # ==================================

                st.write(
                    "Step 6: Checking mandatory invoice fields..."
                )

                missing_fields = get_missing_fields(
                    invoice_data
                )

                line_items = (
                    invoice_data.get("line_items")
                    or []
                )

                if missing_fields:

                    st.warning(
                        "Missing fields: "
                        + ", ".join(missing_fields)
                    )

                else:

                    st.success(
                        "All mandatory fields are available."
                    )

                if not line_items:

                    st.warning(
                        "No line items were extracted."
                    )


                # ==================================
                # STEP 7: PROCESSING DECISION
                # ==================================

                st.write(
                    "Step 7: Evaluating final processing decision..."
                )

                decision = "NEEDS REVIEW"

                if duplicate is True:

                    decision = "DUPLICATE - STOPPED"

                elif po_status == "MISMATCH":

                    decision = "HOLD - PO MISMATCH"

                elif (
                    duplicate is False
                    and validation_status == "PASS"
                    and po_status == "MATCH"
                    and not missing_fields
                    and line_items
                ):

                    decision = "ELIGIBLE FOR REGISTRATION"

                else:

                    decision = "NEEDS REVIEW"


                # ==================================
                # STEP 8: SAFE REGISTRATION
                # ==================================

                st.write(
                    "Step 8: Recording eligible invoice..."
                )

                if decision == "ELIGIBLE FOR REGISTRATION":

                    registration_status = register_invoice(
                        vendor_name=vendor_name,
                        invoice_number=invoice_number,
                        source_file=uploaded_file.name,
                        po_number=invoice_data.get("po_number"),
                        invoice_amount=invoice_data.get("subtotal")
                         

                    )

                    if registration_status:

                        decision = (
                            "APPROVED FOR HUMAN REVIEW"
                        )

                        st.success(
                            "Invoice successfully registered."
                        )

                    else:

                        decision = "DUPLICATE - STOPPED"

                        st.warning(
                            "Invoice was not registered. "
                            "It may have been submitted simultaneously."
                        )

                else:

                    registration_status = False

                    st.warning(
                        "Invoice was not registered as successfully "
                        "processed because it did not pass all "
                        "automated checks."
                    )


                # ==================================
                # STEP 9: AUDIT LOGGING
                # ==================================

                st.write(
                    "Step 9: Recording audit history..."
                )

                record_audit_event(
                    vendor_name=vendor_name,
                    invoice_number=invoice_number,
                    source_file=uploaded_file.name,
                    decision=decision,
                    duplicate_status=(
                        "DUPLICATE"
                        if duplicate is True
                        else "NOT DUPLICATE"
                        if duplicate is False
                        else "NOT CHECKED"
                    ),
                    validation_status=validation_status,
                    po_status=po_status,
                    missing_fields=missing_fields,
                    registration_status=registration_status,
                    po_number=po_result.get("po_number"),
                    po_amount=po_result.get("po_amount"),
                    previous_used_amount=po_result.get("previous_used_amount"),
                    invoice_amount=po_result.get("invoice_amount"),
                    cumulative_amount=po_result.get("cumulative_amount"),
                    maximum_allowed=po_result.get("maximum_allowed")
                )

                st.success(
                    "Audit event recorded successfully."
                )

                status.update(
                    label="Invoice processing completed!",
                    state="complete",
                    expanded=False
                )


            # ======================================
            # EXTRACTED INVOICE INFORMATION
            # ======================================

            st.divider()

            st.header(
                "2. Extracted Invoice Information"
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "Vendor",
                    invoice_data.get(
                        "vendor_name"
                    ) or "Missing"
                )

                st.metric(
                    "GSTIN",
                    invoice_data.get(
                        "gstin"
                    ) or "Missing"
                )

                st.metric(
                    "Invoice Number",
                    invoice_data.get(
                        "invoice_number"
                    ) or "Missing"
                )

            with col2:

                st.metric(
                    "Invoice Date",
                    invoice_data.get(
                        "invoice_date"
                    ) or "Missing"
                )

                st.metric(
                    "PO Number",
                    invoice_data.get(
                        "po_number"
                    ) or "Missing"
                )

                st.metric(
                    "Due Date",
                    invoice_data.get(
                        "due_date"
                    ) or "Missing"
                )

            with col3:

                st.metric(
                    "Grand Total",
                    display_amount(
                        invoice_data.get(
                            "grand_total"
                        )
                    )
                )

                st.metric(
                    "Extraction Pages",
                    pdf_result.get(
                        "page_count",
                        0
                    )
                )

                st.metric(
                    "Extraction Method",
                    ", ".join(
                        extraction_methods
                    ) or "Unknown"
                )


            # ======================================
            # FINANCIAL SUMMARY
            # ======================================

            st.divider()

            st.header(
                "3. Financial Summary"
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                st.metric(
                    "Subtotal",
                    display_amount(
                        invoice_data.get(
                            "subtotal"
                        )
                    )
                )

            with col2:

                st.metric(
                    "CGST",
                    display_amount(
                        invoice_data.get(
                            "cgst"
                        )
                    )
                )

            with col3:

                st.metric(
                    "SGST",
                    display_amount(
                        invoice_data.get(
                            "sgst"
                        )
                    )
                )

            with col4:

                st.metric(
                    "Grand Total",
                    display_amount(
                        invoice_data.get(
                            "grand_total"
                        )
                    )
                )


            # ======================================
            # LINE ITEMS
            # ======================================

            st.divider()

            st.header(
                "4. Invoice Line Items"
            )

            line_items = (
                invoice_data.get("line_items")
                or []
            )

            if line_items:

                st.dataframe(
                    line_items,
                    use_container_width=True
                )

            else:

                st.warning(
                    "No line items were extracted. "
                    "Manual review is required."
                )


            # ======================================
            # FINANCIAL VALIDATION
            # ======================================

            st.divider()

            st.header(
                "5. Financial Validation"
            )

            checks = validation_result.get(
                "checks",
                []
            )

            if checks:

                for check in checks:

                    if isinstance(
                        check,
                        dict
                    ):

                        check_name = check.get(
                            "name",
                            check.get(
                                "check",
                                "Validation"
                            )
                        )

                        passed = check.get(
                            "passed",
                            check.get(
                                "status"
                            ) == "PASS"
                        )

                        message = check.get(
                            "message",
                            ""
                        )

                        if passed:

                            st.success(
                                f"PASS: {check_name} {message}"
                            )

                        else:

                            st.error(
                                f"FAIL: {check_name} {message}"
                            )

                    else:

                        st.write(check)

            else:

                st.warning(
                    "No financial validation checks "
                    "were returned."
                )

            st.write(
                "**Overall financial status:**",
                validation_result.get(
                    "overall_status",
                    "NEEDS REVIEW"
                )
            )


            # ======================================
            # PO MATCHING
            # ======================================

            st.divider()

            st.header(
                "6. Purchase Order Matching"
            )

            po_status = po_result.get(
                "status",
                "NEEDS REVIEW"
            )

            if po_status == "MATCH":

                st.success(
                    "PURCHASE ORDER MATCHED"
                )

            elif po_status == "MISMATCH":

                st.error(
                    "PURCHASE ORDER MISMATCH"
                )

            else:

                st.warning(
                    "PURCHASE ORDER NEEDS REVIEW"
                )

            st.write(
                po_result.get(
                    "message",
                    "No PO message available."
                )
            )

            if "po_amount" in po_result:

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.metric(
                        "PO Amount",
                        display_amount(
                            po_result.get(
                                "po_amount"
                            )
                        )
                    )

                with col2:

                    st.metric(
                        "Invoice Subtotal",
                        display_amount(
                            po_result.get(
                                "invoice_amount"
                            )
                        )
                    )

                with col3:

                    st.metric(
                        "Difference",
                        display_amount(
                            po_result.get(
                                "difference"
                            )
                        )
                    )

                if (
                    "minimum_allowed"
                    in po_result
                    and
                    "maximum_allowed"
                    in po_result
                ):

                    st.write(
                        "Permitted range: "
                        f"{display_amount(po_result['minimum_allowed'])}"
                        " – "
                        f"{display_amount(po_result['maximum_allowed'])}"
                    )


            # ======================================
            # FINAL DECISION
            # ======================================

            st.divider()

            st.header(
                "7. Processing Decision"
            )

            if decision == (
                "APPROVED FOR HUMAN REVIEW"
            ):

                st.success(
                    "APPROVED FOR HUMAN REVIEW — "
                    "All automated checks passed."
                )

            elif decision == (
                "DUPLICATE - STOPPED"
            ):

                st.error(
                    "DUPLICATE INVOICE — "
                    "Processing stopped."
                )

            elif decision == (
                "HOLD - PO MISMATCH"
            ):

                st.error(
                    "HOLD — Vendor or purchase "
                    "order mismatch."
                )

            else:

                st.warning(
                    "NEEDS REVIEW — "
                    "Manual inspection is required."
                )

            if missing_fields:

                st.write(
                    "**Missing required fields:** "
                    + ", ".join(
                        missing_fields
                    )
                )

            if duplicate is None:

                st.write(
                    "Duplicate verification "
                    "could not be completed."
                )

            if not line_items:

                st.write(
                    "Line items are missing. "
                    "Manual review is required."
                )

            st.info(
                "Important: This application does not "
                "release payments automatically. "
                "Human review and approval are required."
            )


            # ======================================
            # AUDIT RECORD
            # ======================================

            st.divider()

            st.header(
                "8. Audit Record"
            )

            st.success(
                "This invoice processing attempt has "
                "been recorded in the audit history."
            )

            st.write(
                f"**Decision recorded:** {decision}"
            )


            # ======================================
            # JSON OUTPUT
            # ======================================

            st.divider()

            st.header(
                "9. Extracted JSON Output"
            )

            output = {
                "invoice": invoice_data,
                "extraction": {
                    "page_count": pdf_result.get(
                        "page_count",
                        0
                    ),
                    "methods": extraction_methods
                },
                "validation": validation_result,
                "duplicate": duplicate,
                "po_matching": po_result,
                "po_source": (
                    po_file.name
                    if po_file is not None
                    else "data/purchase_orders.json"
                ),
                "registration_status": registration_status,
                "missing_fields": missing_fields,
                "decision": decision,
                "source_file": uploaded_file.name,
                "stored_original_invoice": (
                    str(stored_invoice_path)
                    if stored_invoice_path
                    else None
                )
            }

            st.json(output)

            st.download_button(
                label="Download Invoice JSON",
                data=json.dumps(
                    output,
                    indent=4,
                    ensure_ascii=False,
                    default=str
                ),
                file_name="invoice_output.json",
                mime="application/json"
            )

            # Refresh the dashboard after the audit event has been written.
            render_dashboard(dashboard_placeholder)


        except Exception as error:

            st.error(
                f"Invoice processing failed: {error}"
            )

            st.info(
                "The invoice was not registered by the "
                "application after an unexpected processing "
                "error. Check the error and retry after "
                "correcting the issue."
            )

else:

    st.info(
        "Upload a PDF invoice to begin processing."
    )

    st.write(
        "Supported format: PDF"
    )