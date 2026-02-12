"""
Quick Test Script for Sankey Visualization Improvements

This script uses Playwright to open a browser and display the Sankey diagram
so you can visually inspect the improvements.

Prerequisites:
- Backend running on localhost:8000
- Frontend running on localhost:3000
- Discussion with Sankey data (use the discussion_id from demo script)

Usage:
  python test_sankey_improvements.py <discussion_id>

Example:
  python test_sankey_improvements.py d72d4e69-497c-4909-8e07-a6210c642f76
"""

import asyncio
import sys
from playwright.async_api import async_playwright


async def test_sankey_visualization(discussion_id: str):
    """Open browser and navigate to Sankey visualization."""
    print(f"\n{'='*80}")
    print("Sankey Visualization Improvements - Visual Test")
    print(f"{'='*80}\n")
    print(f"Discussion ID: {discussion_id}")
    print(f"Opening browser to: http://localhost:3000/discussions/{discussion_id}/sankey")
    print("\n✨ Check for these improvements:")
    print("  1. Round labels show question text (not 'Round 1', 'Round 2')")
    print("  2. Horizontal scroll enabled (try scrolling if 3+ rounds)")
    print("  3. Flow edges use gradient colors (source → target)")
    print("  4. Cluster labels truncated at sentence boundaries")
    print("\nPress Ctrl+C when done inspecting...")
    print(f"{'='*80}\n")

    async with async_playwright() as p:
        # Launch browser in headed mode so you can see it
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # Navigate to Sankey page
        try:
            await page.goto(
                f"http://localhost:3000/discussions/{discussion_id}/sankey",
                wait_until="networkidle",
                timeout=10000
            )
            print("✅ Page loaded successfully!")

            # Wait for Sankey to render
            try:
                await page.wait_for_selector('.sankey-diagram-container', timeout=5000)
                print("✅ Sankey diagram container found!")

                # Check for round labels
                round_labels = await page.locator('.round-label').count()
                print(f"✅ Found {round_labels} round labels")

                # Check for gradient edges
                edges = await page.locator('.sankey-edge-path').count()
                if edges > 0:
                    edge_fill = await page.locator('.sankey-edge-path').first.get_attribute('fill')
                    if edge_fill and 'gradient' in edge_fill:
                        print(f"✅ Edges using gradients! ({edges} edges)")
                    else:
                        print(f"⚠️  Edges found but not using gradients: {edge_fill}")
                else:
                    print("⚠️  No edges found (may be single-round discussion)")

                # Check for nodes
                nodes = await page.locator('.sankey-node-rect').count()
                print(f"✅ Found {nodes} cluster nodes")

                print(f"\n{'='*80}")
                print("Browser is open! Inspect the visualization...")
                print("Press Ctrl+C in this terminal when done.")
                print(f"{'='*80}\n")

                # Keep browser open until user presses Ctrl+C
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\n\n✅ Closing browser...")

            except Exception as e:
                print(f"⚠️  Could not find Sankey diagram: {e}")
                print("The page loaded but the diagram may not have rendered.")
                print("Check browser console for errors...")
                await asyncio.sleep(30)  # Keep browser open for 30s

        except Exception as e:
            print(f"❌ Failed to load page: {e}")
            print("\nTroubleshooting:")
            print("  - Is the frontend running on localhost:3000?")
            print("  - Is the backend running on localhost:8000?")
            print("  - Is the discussion_id correct?")
            print("  - Try: cd frontend && npm run dev")
            print("  - Try: cd backend && poetry run uvicorn src.main:app --reload")
        finally:
            await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_sankey_improvements.py <discussion_id>")
        print("\nExample:")
        print("  python test_sankey_improvements.py d72d4e69-497c-4909-8e07-a6210c642f76")
        print("\nTo get a discussion_id, run:")
        print("  cd backend && poetry run python run_async_e2e_demo.py")
        sys.exit(1)

    discussion_id = sys.argv[1]
    asyncio.run(test_sankey_visualization(discussion_id))
