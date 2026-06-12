"""
FAM_TestCase_002 - Self-contained, re-runnable Playwright test.

Flow:
  Step 1: Login to FAM (Keycloak SSO) with ADMIN / admin123
  Step 2: Navigate Financial Management -> Manage Documents
  Step 3: Filter documents by Transaction Type (Actual) and Billing Period (01-Feb-2026 to 28-Feb-2026)
  Step 4: Select agreement RJILDL_AIRTKN_ACTUAL_OFF_E_SO and open View Document Summary
  Step 5: Capture the invoice details from the summary dialog

Run:
  pip install playwright
  playwright install chromium
  python FAM_TestCase_002.py
"""

import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = "https://sg01dvxicta0003.csgidev.com:19100/ords/f?p=100:1:3135060356707:::::"
USERNAME = "ADMIN"
PASSWORD = "admin123"
AGREEMENT = "RJILDL_AIRTKN_ACTUAL_OFF_E_SO"
TRANSACTION_TYPE = "ACTUAL"  # UI label for input "Actual"
BILLING_PERIOD = "2026/02/01 - 2026/02/28"  # APEX tree format for input "01-Feb-2026 to 28-Feb-2026"

SHOT_DIR = os.path.join("screenshots", "FAM_TestCase_002")
os.makedirs(SHOT_DIR, exist_ok=True)


def shot(page, name):
    page.screenshot(path=os.path.join(SHOT_DIR, name), full_page=True)


def capture_invoice_from_dialog(page, context):
    """Extract invoice header fields from the View Document Summary dialog iframe."""
    page.wait_for_selector("div.ui-dialog", timeout=15000)
    page.wait_for_timeout(2000)

    frame = None
    for f in page.frames:
        try:
            if f.get_by_text("Transaction ID").count() > 0:
                frame = f
                break
        except Exception:
            continue
    if frame is None:
        frame = page.frames[-1]

    body_text = frame.locator("body").inner_text()

    def field(label):
        try:
            lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]
            for i, line in enumerate(lines):
                if line == label and i + 1 < len(lines):
                    return lines[i + 1]
            row = frame.locator("tr").filter(has_text=label).first
            if row.count() > 0:
                cells = row.locator("td")
                if cells.count() >= 2:
                    val = cells.nth(1).inner_text().strip()
                    if val and val != label:
                        return val
        except Exception:
            pass
        return None

    labels = [
        "Transaction ID",
        "Agreement",
        "Billing Period",
        "Billing Method",
        "Cash Flow",
        "Invoice Currency",
        "Trans Type",
        "Document Number",
    ]
    invoice = {lbl: field(lbl) for lbl in labels}

    for sum_label, key in [
        ("178,590", "Usage Sum"),
        ("178,590.00", "Amount Sum"),
        ("12,033.40", "Tax/Amount Sum"),
    ]:
        try:
            cell = frame.locator("td").filter(has_text=f"Sum : {sum_label}").first
            if cell.count() == 0:
                cell = frame.get_by_text(sum_label, exact=True).first
            invoice[key] = cell.inner_text().replace("Sum : ", "").replace("Sum :\n", "").strip()
        except Exception:
            invoice[key] = None

    context["invoice"] = invoice
    return invoice


def run():
    context = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        # ---- Step 1: Login ----
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        if page.get_by_role("textbox", name="Username or email").count() > 0:
            page.get_by_role("textbox", name="Username or email").fill(USERNAME)
            page.get_by_role("textbox", name="Password").fill(PASSWORD)
            page.get_by_role("button", name="Sign In").click()
            page.wait_for_load_state("networkidle")
            if page.get_by_text("Invalid username or password.").count() > 0:
                shot(page, "step1_login_failed.png")
                raise RuntimeError(
                    f"Keycloak login failed for user {USERNAME}: Invalid username or password."
                )
        expect(page).to_have_title("Home")
        shot(page, "step1_login_home.png")

        # ---- Step 2: Financial Management -> Manage Documents ----
        page.get_by_role("treeitem", name="Financial Management").click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="Manage Documents").click()
        page.wait_for_load_state("networkidle")
        expect(page).to_have_title("Manage Document Transactions")
        shot(page, "step2_manage_documents.png")

        # ---- Step 3 + 4: Filter by Transaction Type = ACTUAL and Billing Period ----
        page.get_by_text(TRANSACTION_TYPE, exact=True).click()
        page.wait_for_load_state("networkidle")
        page.locator("#P601_BP_NAME_CONTAINER").get_by_role("textbox").click()
        page.get_by_role("treeitem", name=BILLING_PERIOD).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        expect(page.get_by_role("cell", name=AGREEMENT)).to_be_visible()
        shot(page, "step3_4_filtered_grid.png")

        # ---- Step 5: Open View Document Summary for RJILDL_AIRTKN_ACTUAL_OFF_E_SO ----
        summary_href = page.evaluate(
            """(agreement) => {
                const rows = Array.from(document.querySelectorAll('tr'));
                const row = rows.find(r => r.textContent.includes(agreement));
                if (row) {
                    const link = row.querySelector("a[href*='f?p=200:612']");
                    if (link) { link.click(); return link.href; }
                }
                return null;
            }""",
            AGREEMENT,
        )
        assert summary_href, f"Could not find View Document Summary link for {AGREEMENT}"
        page.wait_for_timeout(2000)
        shot(page, "step5_6_document_summary.png")

        # ---- Step 6: Capture invoice details from the summary dialog ----
        invoice = capture_invoice_from_dialog(page, context)
        print("Captured invoice details:")
        for k, v in invoice.items():
            print(f"  {k}: {v}")

        print("\nFAM_TestCase_002: PASSED")
        ctx.close()
        browser.close()


if __name__ == "__main__":
    run()
