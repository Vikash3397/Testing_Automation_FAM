"""
FAM_TestCase_001 - self-contained Playwright + DB verification flow.

Run:
  pip install playwright oracledb python-dotenv
  playwright install chromium
  python FAM_TestCase_001.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import expect, sync_playwright

from DBLibrary import DBLibrary

load_dotenv()

CONTEXT = {
    "Application URL": "https://sg01dvxicta0003.csgidev.com:19100/ords/f?p=100:1:3135060356707::::",
    "Username": "ADMIN",
    "Password": "admin123",
    "Transaction Type": "ACCRUALS",
    "Billing Period": "2026/02/01 - 2026/02/28",
    "Agreement": "RJILKO_AIRTTN_Exp",
}

SHOT_DIR = Path("screenshots") / "FAM_TestCase_001"
SHOT_DIR.mkdir(parents=True, exist_ok=True)


def take_shot(page, name):
    page.screenshot(path=str(SHOT_DIR / name), full_page=True)


def extract_invoice_details(page):
    page.wait_for_selector("div[role='dialog']", timeout=20000)
    expect(page.get_by_role("dialog", name="View Document Transactions Summary")).to_be_visible()

    details_frame = None
    for frame in page.frames:
        if frame.locator("body").count() == 0:
            continue
        body_text = frame.locator("body").inner_text()
        if "Transaction ID" in body_text and "View Invoice Transaction Summary" in body_text:
            details_frame = frame
            break

    if details_frame is None:
        raise RuntimeError("Could not locate summary dialog frame for invoice details.")

    body_lines = [line.strip() for line in details_frame.locator("body").inner_text().splitlines() if line.strip()]

    def value_for(label):
        for index, line in enumerate(body_lines):
            if line == label and index + 1 < len(body_lines):
                return body_lines[index + 1]
        return ""

    invoice = {
        "Transaction ID": value_for("Transaction ID"),
        "Agreement": value_for("Agreement"),
        "Billing Period": value_for("Billing Period"),
        "Billing Method": value_for("Billing Method"),
        "Cash Flow": value_for("Cash Flow"),
        "Invoice Currency": value_for("Invoice Currency"),
        "Trans Type": value_for("Trans Type"),
        "Document Number": value_for("Document Number"),
    }

    line_item_row = details_frame.get_by_role(
        "row",
        name="2026/02/01 - 2026/02/28 OPEN CHSMS->Commercial SMS INR USAGE 75 75.00 0 5.25 OFFNET RJILKO AIRTTN",
    )
    if line_item_row.count() > 0:
        invoice["Sample Line Item"] = line_item_row.inner_text()

    return invoice


def verify_invoice_against_db(context):
    db = DBLibrary(
        os.getenv("ORACLE_DB_USER"),
        os.getenv("ORACLE_DB_PASSWORD"),
        os.getenv("ORACLE_DB_HOST"),
        os.getenv("ORACLE_DB_PORT"),
        os.getenv("ORACLE_DB_SERVICE"),
    )

    agreement_query = (
        "SELECT agreement_id, cash_flow, agreement_name FROM dm_agreement "
        f"WHERE UPPER(agreement_name) = UPPER('{context['Agreement']}')"
    )
    agreement_rows = db.ExecuteDB(agreement_query)
    if not agreement_rows or not agreement_rows.get("AGREEMENT_ID"):
        raise AssertionError(f"No DM_agreement row for {context['Agreement']}")

    agreement_id = str(agreement_rows["AGREEMENT_ID"][0])
    db_cash_flow = agreement_rows["CASH_FLOW"][0]
    context["agreement_id"] = agreement_id
    context["dm_cash_flow"] = db_cash_flow

    trans_id = context["invoice_details"]["Transaction ID"]
    doc_query = (
        "SELECT id, agreement_id, trans_type, billing_method, cash_flow, bp_name, "
        "currency, document_number, callcount, usage, total_amount "
        "FROM fm_document_trans "
        f"WHERE agreement_id = {agreement_id} AND id = {trans_id}"
    )
    doc_rows = db.ExecuteDB(doc_query)
    if not doc_rows or not doc_rows.get("ID"):
        raise AssertionError(f"No FM_Document_Trans row for agreement_id={agreement_id}, id={trans_id}")

    context["db_document_trans"] = {key: doc_rows[key][0] for key in doc_rows}

    ui = context["invoice_details"]
    db_doc = context["db_document_trans"]

    cash_flow_map = {"EXPENSE": "E", "REVENUE": "R"}
    billing_method_map = {"INVOICE": "I", "CREDIT NOTE": "C"}

    checks = [
        (ui["Agreement"], agreement_rows["AGREEMENT_NAME"][0]),
        (ui["Billing Period"], db_doc["BP_NAME"]),
        (ui["Trans Type"], db_doc["TRANS_TYPE"]),
        (ui["Invoice Currency"], db_doc["CURRENCY"]),
        (cash_flow_map.get(ui["Cash Flow"], ui["Cash Flow"]), db_doc["CASH_FLOW"]),
        (cash_flow_map.get(ui["Cash Flow"], ui["Cash Flow"]), db_cash_flow),
        (billing_method_map.get(ui["Billing Method"], ui["Billing Method"]), db_doc["BILLING_METHOD"]),
        (agreement_id, str(db_doc["AGREEMENT_ID"])),
    ]

    failures = [f"{ui_val!r} != {db_val!r}" for ui_val, db_val in checks if str(ui_val) != str(db_val)]
    if failures:
        raise AssertionError("DB verification failed: " + "; ".join(failures))

    return context


def run_test():
    context = dict(CONTEXT)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page_context = browser.new_context(ignore_https_errors=True)
        page = page_context.new_page()

        # Step 1: Login
        page.goto(context["Application URL"])
        page.wait_for_load_state("networkidle")
        page.get_by_role("textbox", name="Username or email").fill(context["Username"])
        page.get_by_role("textbox", name="Password").fill(context["Password"])
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_title("Home")
        take_shot(page, "step1_login.png")

        # Step 2: Navigate to Manage Documents
        page.get_by_role("treeitem", name="Financial Management").click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("treeitem", name="Manage Documents").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_title("Manage Document Transactions")
        take_shot(page, "step2_manage_documents.png")

        # Step 3: Filter by transaction type and billing period
        page.get_by_text(context["Transaction Type"], exact=True).click()
        page.locator("#P601_BP_NAME_CONTAINER").get_by_role("textbox").click()
        page.get_by_role("treeitem", name=context["Billing Period"]).click()
        page.wait_for_load_state("networkidle")
        take_shot(page, "step3_filtered_documents.png")

        # Step 4: Select agreement, load data, open document summary
        page.locator("#P601_AGREEMENT_ID_CONTAINER").get_by_role("textbox").click()
        page.get_by_role("treeitem", name=context["Agreement"]).click()
        page.get_by_role("button", name="Load Data").click()
        page.wait_for_timeout(3000)
        target_row = page.get_by_role(
            "row",
            name=(
                f"ACCRUALS INVOICE SEND {context['Agreement']} {context['Billing Period']} "
                "OPEN TBD INR 0 12,089 0 12,089.00 0.00 835.48 0.00 0.00 0.00 835.48 - ADMIN - Pending Document Approval -"
            ),
        )
        expect(target_row).to_be_visible()
        target_row.locator("a[href*='f?p=200:612']").first.click()
        take_shot(page, "step4_view_document_summary.png")

        # Step 5: Capture invoice details
        context["invoice_details"] = extract_invoice_details(page)
        take_shot(page, "step5_invoice_details.png")
        print("Captured invoice details:")
        for key, value in context["invoice_details"].items():
            print(f"{key}: {value}")

        page_context.close()
        browser.close()

    # Step 6: DB verification
    verify_invoice_against_db(context)
    print("DB verification passed.")
    print(f"agreement_id={context['agreement_id']}, cash_flow={context['dm_cash_flow']}")
    print(f"FM_Document_Trans: {context['db_document_trans']}")


if __name__ == "__main__":
    run_test()
