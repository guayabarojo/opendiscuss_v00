"""
Debug script to see what's rendering on the Sankey page
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_sankey():
    discussion_id = "d4f27873-7c28-4d00-9084-ed2fb0d74b7e"
    url = f"http://localhost:3000/discussions/{discussion_id}/sankey"

    async with async_playwright() as p:
        print(f"\n🔍 Debugging Sankey page...")
        print(f"URL: {url}\n")

        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  ERROR: {err}"))

        await page.goto(url)
        print("✓ Page loaded\n")

        # Wait for Sankey
        await page.wait_for_selector('.sankey-diagram-svg', timeout=15000)
        print("✓ Sankey SVG found\n")

        # Take full screenshot
        print("📸 Taking full page screenshot...")
        await page.screenshot(path="sankey-debug-full.png", full_page=True)
        print("   Saved: sankey-debug-full.png\n")

        # Check what classes exist on page
        print("🔍 Checking page structure...\n")

        has_control = await page.locator('.cluster-granularity-control').count()
        print(f"   cluster-granularity-control: {has_control}")

        has_slider = await page.locator('.cluster-slider').count()
        print(f"   cluster-slider: {has_slider}")

        has_metadata_panel = await page.locator('.sankey-metadata-panel').count()
        print(f"   sankey-metadata-panel: {has_metadata_panel}")

        has_diagram_wrapper = await page.locator('.sankey-diagram-wrapper').count()
        print(f"   sankey-diagram-wrapper: {has_diagram_wrapper}")

        nodes = await page.locator('.sankey-node-rect').count()
        print(f"   sankey-node-rect (nodes): {nodes}")

        labels_inside = await page.locator('.sankey-node-label-inside').count()
        print(f"   sankey-node-label-inside: {labels_inside}")

        labels_old = await page.locator('.sankey-node-label').count()
        print(f"   sankey-node-label (old style): {labels_old}")

        # Check page HTML for debugging
        print("\n📄 Checking if slider HTML exists...")
        html = await page.content()
        if 'cluster-granularity-control' in html:
            print("   ✓ Slider HTML found in page!")
        else:
            print("   ✗ Slider HTML NOT found - frontend needs refresh")

        if 'sankey-node-label-inside' in html:
            print("   ✓ New label classes found!")
        else:
            print("   ✗ New label classes NOT found")

        print("\n⏸️  Browser staying open for 30 seconds...")
        await asyncio.sleep(30)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_sankey())
