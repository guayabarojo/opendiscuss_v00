"""Check if the inspector button is visible on Sankey page"""
import asyncio
from playwright.async_api import async_playwright

async def check_button():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to the latest discussion
        discussion_id = "f4dc8a42-e8b7-4be0-9dd9-a34f82a0c55f"
        print(f"🔍 Checking Sankey page: http://localhost:3000/discussions/{discussion_id}/sankey")

        await page.goto(f"http://localhost:3000/discussions/{discussion_id}/sankey")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Look for the inspect button
        inspect_buttons = page.locator('button:has-text("Inspect")')
        button_count = await inspect_buttons.count()

        print(f"\n📊 Inspect Clustering Button Status:")
        print(f"  Buttons found: {button_count}")

        if button_count > 0:
            print(f"  ✅ Button IS visible on page")

            # Check if it's actually visible (not hidden by CSS)
            is_visible = await inspect_buttons.first.is_visible()
            print(f"  Visible: {is_visible}")

            # Get button text
            text = await inspect_buttons.first.inner_text()
            print(f"  Button text: '{text}'")
        else:
            print(f"  ❌ Button NOT FOUND on page")
            print(f"\n  Possible reasons:")
            print(f"    1. Not running in dev mode (npm run dev)")
            print(f"    2. Button removed from component")
            print(f"    3. CSS hiding the button")

        # Take screenshot
        await page.screenshot(path="sankey-button-check.png", full_page=True)
        print(f"\n📸 Screenshot saved: sankey-button-check.png")

        await asyncio.sleep(2)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_button())
