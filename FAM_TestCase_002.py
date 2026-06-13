"""
FAM_TestCase_002 - Self-contained Playwright UI test.

Run:
  pip install playwright
  playwright install chromium
  python FAM_TestCase_002.py
"""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

CONTEXT = {
    "Application URL": "https://sg01dvxicta0003.csgidev.com:19100/ords/f?p=100:1:3135060356707::::",
    "Username": "ADMIN",
    "Password": "admin123",
    "Transaction Type": "ACTUAL",
    "Billing Period": "2026/02/01 - 2026/02/28",
    "Agreement": "RJILDL_AIRTKN_ACTUAL_OFF_E_SO",
}

SHOT_DIR = Path("screenshots") / "FAM_TestCase_002"
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
        name="2026/02/01 - 2026/02/28 OPEN CHSMS->Commercial SMS INR USAGE 17,120 17,120.00 0 1,198.40 OFFNET RJILDL AIRTKN",
    )
    if line_item_row.count() > 0:
        invoice["Sample Line Item"] = line_item_row.inner_text()

    return invoice


def run_test():
    context = dict(CONTEXT)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page_context = browser.new_context(ignore_https_errors=True)
        page = page_context.new_page()

        # Step 1: Login
        page.goto(context["Application URL"])
        page.wait_for_load_state("networkidle")
        if page.get_by_role("textbox", name="Username or email").count() > 0:
            page.get_by_role("textbox", name="Username or email").fill(context["Username"])
            page.get_by_role("textbox", name="Password").fill(context["Password"])
            page.get_by_role("button", name="Sign In").click()
            page.wait_for_load_state("networkidle")
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
                f"ACTUAL INVOICE {context['Agreement']} {context['Billing Period']} "
                "OPEN TBD INR SUCCESS 178,590 178,590.00 12,033.40 0.00 0.00 0.00 12,033.40 - - - - - 0.00 0 0 0 0 0 12,033.40 ADMIN - Pending Document Approval -"
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


if __name__ == "__main__":
    run_test()
