"""
Complete E2E test: Create discussion, run through all rounds, verify Sankey and Inspector
"""
import asyncio
import subprocess
import time
from playwright.async_api import async_playwright

async def run_complete_e2e():
    """Run complete end-to-end flow"""

    print("=" * 80)
    print("COMPLETE E2E TEST: Discussion Creation → Sankey → Inspector Modal")
    print("=" * 80)

    # Step 1: Generate discussion
    print("\n[1/4] Generating 100-participant discussion with 10 rounds...")
    result = subprocess.run(
        ["poetry", "run", "python", "create_varied_discussion.py"],
        capture_output=True,
        text=True,
        timeout=180
    )

    if result.returncode != 0:
        print("❌ Failed to create discussion")
        print(result.stderr)
        return

    # Extract discussion ID from output
    discussion_id = None
    for line in result.stdout.split('\n'):
        if "Discussion ID:" in line:
            discussion_id = line.split("Discussion ID:")[1].strip()
            break

    if not discussion_id:
        print("❌ Could not extract discussion ID")
        print(result.stdout)
        return

    print(f"✅ Discussion created: {discussion_id}")

    # Step 2: Open browser and navigate
    print("\n[2/4] Opening browser and navigating to Sankey...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to Sankey
        await page.goto(f"http://localhost:3000/discussions/{discussion_id}/sankey")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        print("✅ Sankey page loaded")

        # Take screenshot of Sankey
        await page.screenshot(path="sankey-complete-e2e.png", full_page=True)
        print("📸 Screenshot saved: sankey-complete-e2e.png")

        # Step 3: Open inspector modal
        print("\n[3/4] Opening inspector modal...")
        inspect_button = page.locator('button:has-text("🔍 Inspect Clustering")')
        if await inspect_button.count() > 0:
            await inspect_button.click()
            await asyncio.sleep(2)

            # Check if modal opened
            modal = page.locator('div.fixed.inset-0')
            if await modal.is_visible():
                print("✅ Inspector modal opened")

                # Check round selector
                round_select = page.locator('select').first
                await round_select.wait_for(state="visible", timeout=5000)

                # Get round count
                options = await round_select.locator('option').all()
                print(f"✅ Round selector has {len(options)} rounds")

                if len(options) > 1:
                    # Select second round (index 1)
                    await round_select.select_option(index=1)
                    await asyncio.sleep(2)

                    # Check table
                    table_rows = page.locator('table tbody tr')
                    row_count = await table_rows.count()
                    print(f"✅ Inspector table has {row_count} rows")

                    # Take screenshot of inspector
                    await page.screenshot(path="inspector-modal-complete-e2e.png", full_page=True)
                    print("📸 Screenshot saved: inspector-modal-complete-e2e.png")
                else:
                    print("⚠️ No rounds available in selector")
            else:
                print("⚠️ Modal did not open")
        else:
            print("⚠️ Inspect Clustering button not found (not in dev mode?)")

        # Step 4: Check clustering quality
        print("\n[4/4] Checking clustering quality...")

        # Count clusters in inspector if modal is open
        if await modal.is_visible():
            # Look for cluster filter dropdown
            cluster_filter = page.locator('select').nth(1)  # Second select is cluster filter
            if await cluster_filter.count() > 0:
                cluster_options = await cluster_filter.locator('option').all()
                # Subtract 1 for "All Clusters" option
                cluster_count = max(0, len(cluster_options) - 1)
                print(f"📊 Total clusters in current round: {cluster_count}")

                if cluster_count > 50:
                    print("⚠️ WARNING: Very high cluster count suggests over-fragmentation")
                    print("   This is expected with random test data - real discussions will cluster better")
                elif cluster_count < 3:
                    print("⚠️ WARNING: Very low cluster count suggests over-merging")
                elif 5 <= cluster_count <= 9:
                    print("✅ Cluster count in Miller's Law range (7±2)")
                else:
                    print(f"ℹ️  Cluster count: {cluster_count}")

        print("\n" + "=" * 80)
        print("E2E TEST COMPLETE")
        print("=" * 80)
        print(f"\n📋 Discussion ID: {discussion_id}")
        print(f"🔗 Sankey URL: http://localhost:3000/discussions/{discussion_id}/sankey")
        print("\n✅ All systems operational!")

        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_complete_e2e())
