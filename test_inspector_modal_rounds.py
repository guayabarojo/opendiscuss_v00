"""
Test inspector modal round selector functionality
"""
import asyncio
from playwright.async_api import async_playwright

async def test_inspector_modal():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Capture console messages
        console_messages = []
        def handle_console(msg):
            console_messages.append(f"[{msg.type}] {msg.text}")
        page.on("console", handle_console)

        # Capture network failures and responses
        def handle_request_failed(request):
            print(f"❌ Request failed: {request.url}")
        page.on("requestfailed", handle_request_failed)

        async def handle_response(response):
            if response.status >= 400:
                print(f"❌ HTTP {response.status}: {response.url}")
        page.on("response", handle_response)

        discussion_id = "824d3126-66f6-42e8-a61a-115c502dcd2f"

        print("1. Navigate to Sankey page...")
        await page.goto(f"http://localhost:3000/discussions/{discussion_id}/sankey")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        print("2. Click 'Inspect Clustering' button...")
        # Find the button with the magnifying glass emoji
        inspect_button = page.locator('button:has-text("🔍 Inspect Clustering")')
        await inspect_button.click()
        await asyncio.sleep(1)

        print("3. Wait for modal to appear...")
        modal = page.locator('div.fixed.inset-0')
        await modal.wait_for(state="visible", timeout=5000)
        print("✅ Modal opened successfully")

        print("4. Check if round selector is present...")
        # Find the select element by its label
        round_select = page.locator('select').first
        await round_select.wait_for(state="visible", timeout=5000)
        print("✅ Round selector found")

        print("5. Check if rounds are loaded...")
        # Wait a moment for the API call to complete
        await asyncio.sleep(2)

        # Get all options in the select
        options = await round_select.locator('option').all()
        print(f"✅ Round selector has {len(options)} options")

        if len(options) > 1:  # More than just placeholder
            print("6. Select the first round...")
            await round_select.select_option(index=1)
            await asyncio.sleep(2)

            print("7. Check if inspector table is populated...")
            table_rows = page.locator('table tbody tr')
            row_count = await table_rows.count()
            print(f"✅ Inspector table has {row_count} rows")

            if row_count > 0:
                print("✅ ROUND SELECTOR IS WORKING!")

                # Take screenshot
                await page.screenshot(path="inspector-modal-working.png", full_page=True)
                print("📸 Screenshot saved: inspector-modal-working.png")
            else:
                print("⚠️ Round selected but no data loaded")
        else:
            print("⚠️ Round selector has no options (only placeholder)")

        # Print all captured console messages
        if console_messages:
            print("\n📋 Console messages:")
            for msg in console_messages:
                print(f"  {msg}")

        print("\n8. Close modal and browser...")
        await asyncio.sleep(2)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_inspector_modal())
