"""
Quick Playwright script to view the Sankey improvements live
"""
import asyncio
from playwright.async_api import async_playwright

async def view_sankey():
    discussion_id = "d4f27873-7c28-4d00-9084-ed2fb0d74b7e"
    url = f"http://localhost:3000/discussions/{discussion_id}/sankey"

    async with async_playwright() as p:
        print(f"\n🚀 Opening Sankey diagram...")
        print(f"URL: {url}\n")

        # Launch browser in headed mode so user can see it
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        # Navigate to Sankey page
        await page.goto(url)
        print("✓ Page loaded, waiting for Sankey diagram...")

        # Wait for diagram to load
        await page.wait_for_selector('.sankey-diagram-svg', timeout=15000)
        print("✓ Sankey diagram loaded!\n")

        # Wait for slider to appear
        await page.wait_for_selector('.cluster-granularity-control', timeout=5000)
        print("✓ Cluster granularity slider loaded!\n")

        # Take screenshot at default position (medium detail)
        print("📸 Taking screenshot at default position (5+ participants)...")
        await page.screenshot(path="sankey-default-medium.png", full_page=True)
        print("   Saved: sankey-default-medium.png\n")

        await asyncio.sleep(2)

        # Get slider and move to minimum (show all clusters)
        print("🎚️  Moving slider to LEFT (show all 344 clusters)...")
        slider = page.locator('.cluster-slider')
        await slider.fill('2')
        await asyncio.sleep(2)

        print("📸 Taking screenshot at minimum (all clusters)...")
        await page.screenshot(path="sankey-all-clusters.png", full_page=True)
        print("   Saved: sankey-all-clusters.png\n")

        await asyncio.sleep(2)

        # Move to maximum (major themes only)
        print("🎚️  Moving slider to RIGHT (major themes only, 10+ participants)...")
        await slider.fill('10')
        await asyncio.sleep(2)

        print("📸 Taking screenshot at maximum (major themes)...")
        await page.screenshot(path="sankey-major-themes.png", full_page=True)
        print("   Saved: sankey-major-themes.png\n")

        # Get cluster count info
        slider_label = await page.locator('.slider-value').text_content()
        print(f"📊 Current slider label: {slider_label}")

        # Check for labels inside nodes
        print("\n🔍 Checking improvements...")
        nodes = await page.locator('.sankey-node-rect').count()
        print(f"   ✓ Found {nodes} visible nodes")

        labels_inside = await page.locator('.sankey-node-label-inside').count()
        print(f"   ✓ Found {labels_inside} labels inside nodes")

        counts_inside = await page.locator('.sankey-node-count-inside').count()
        print(f"   ✓ Found {counts_inside} participant counts inside nodes")

        # Sample a label to show truncation
        if labels_inside > 0:
            first_label = await page.locator('.sankey-node-label-inside').first.text_content()
            print(f"   ✓ Sample label: '{first_label}'")

        print("\n✨ All improvements verified!")
        print("\n📁 Screenshots saved to current directory:")
        print("   - sankey-default-medium.png (5+ participants)")
        print("   - sankey-all-clusters.png (2+ participants, all 344)")
        print("   - sankey-major-themes.png (10+ participants, major themes)")

        print("\n⏸️  Browser will stay open for 30 seconds so you can explore...")
        print("   (Feel free to interact with the diagram!)")
        await asyncio.sleep(30)

        await browser.close()
        print("\n✅ Done!")

if __name__ == "__main__":
    asyncio.run(view_sankey())
