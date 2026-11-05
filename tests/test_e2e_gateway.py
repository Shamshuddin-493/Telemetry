import time
from playwright.sync_api import Page, expect

def test_telemetry_ui_full_flow(page: Page):
    # Assumes local server is running at http://127.0.0.1:8000
    page.goto("http://127.0.0.1:8000")

    # 1. Verify Page Loaded
    expect(page.locator("h1")).to_contain_text("Telemetry Gateway Console")

    # 2. Register New Client
    unique_client_name = f"e2e_client_{int(time.time())}"
    page.locator("#client-name-input").fill(unique_client_name)
    page.locator("#register-client-btn").click()

    # 3. Assert API Key is auto-populated
    api_key_input = page.locator("#api-key-input")
    expect(api_key_input).not_to_have_value("", timeout=5000)

    # 4. Dispatch a Single Event
    page.locator("#event-user-id").fill("e2e_tester_4")
    page.locator("#event-type").fill("playwright_login")
    page.locator("#send-event-btn").click()

    # Assert 202 Accepted message
    expect(page.locator("#ingest-status-msg")).to_contain_text("202 Accepted", timeout=5000)

    # 5. Dispatch a Batch
    page.locator("#send-batch-btn").click()
    expect(page.locator("#ingest-status-msg")).to_contain_text("Batch ingested: 3 events", timeout=5000)

    # 6. Wait 1 second for background tasks to commit to database, then refresh table
    page.wait_for_timeout(1000)
    page.locator("#refresh-events-btn").click()

    # 7. Assert table contains the ingested event
    expect(page.locator("#events-table-body")).to_contain_text("playwright_login", timeout=5000)

    # 8. Test Analytics Summary
    page.locator("#refresh-analytics-btn").click()
    expect(page.locator("#metric-total-events")).not_to_have_text("0", timeout=5000)