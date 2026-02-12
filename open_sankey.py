"""
Open Sankey diagram in Playwright browser and keep it running
"""
import asyncio
from playwright.async_api import async_playwright

async def open_sankey():
    discussion_id = "d4f27873-7c28-4d00-9084-ed2fb0d74b7e"
    url = f"http://localhost:3000/discussions/{discussion_id}/sankey"

    async with async_playwright() as p:
        print(f"\n🚀 Opening Sankey diagram in browser...")
        print(f"URL: {url}\n")

        # Launch browser in headed mode
        browser = await p.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            no_viewport=True  # Let it use the maximized window size
        )

        page = await context.new_page()

        # Navigate to Sankey page
        print("📄 Loading page...")
        await page.goto(url)

        # Wait for everything to load
        await page.wait_for_selector('.sankey-diagram-svg', timeout=15000)
        await page.wait_for_selector('.cluster-granularity-control', timeout=5000)

        print("✅ Sankey diagram loaded successfully!\n")
        print("=" * 60)
        print("🎨 SANKEY IMPROVEMENTS LIVE DEMO")
        print("=" * 60)
        print("\n📊 What to try:")
        print("  • Move the slider at the top to filter clusters")
        print("  • Hover over nodes to see full cluster details")
        print("  • Scroll horizontally to see all 10 rounds")
        print("  • Notice labels are inside nodes (white text)")
        print("  • Notice tight spacing (1px gaps between nodes)")
        print("\n🎚️  Slider positions:")
        print("  • Left (2): Show all 344 clusters")
        print("  • Middle (5-7): Balanced view")
        print("  • Right (10): Major themes only")
        print("\n" + "=" * 60)
        print("\n⏳ Browser will stay open. Press Ctrl+C to close.\n")

        # Keep the browser open indefinitely
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Closing browser...")
            await browser.close()
            print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(open_sankey())
