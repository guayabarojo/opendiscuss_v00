"""
Test that all participants are preserved at every granularity level
"""
import asyncio
from playwright.async_api import async_playwright

async def test_preservation():
    discussion_id = "d4f27873-7c28-4d00-9084-ed2fb0d74b7e"
    url = f"http://localhost:3000/discussions/{discussion_id}/sankey"

    async with async_playwright() as p:
        print("\n" + "="*70)
        print("TESTING: 100% Participant Preservation Across Granularity Levels")
        print("="*70 + "\n")

        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(url)
        await page.wait_for_selector('.sankey-diagram-svg', timeout=15000)
        await page.wait_for_selector('.cluster-granularity-control', timeout=5000)

        print("✓ Page loaded\n")

        slider = page.locator('.cluster-slider')

        # Test at different slider positions
        test_positions = [2, 5, 7, 10]
        participant_counts = {}

        for position in test_positions:
            print(f"📊 Testing slider position: {position}")
            await slider.fill(str(position))
            await asyncio.sleep(1.5)

            # Get participant count labels at bottom of each column
            count_labels = await page.locator('.participant-count-label').all()
            counts = []

            for label in count_labels:
                text = await label.text_content()
                # Extract number from "N participants" or "N participant"
                num = int(text.split()[0])
                counts.append(num)

            participant_counts[position] = counts
            print(f"   Participant counts per round: {counts}")

            # Check if all are equal
            if len(set(counts)) == 1:
                print(f"   ✅ All rounds have {counts[0]} participants (consistent!)")
            else:
                print(f"   ⚠️  Participant counts vary: {set(counts)}")

            # Check for "Other" nodes
            other_nodes = await page.locator('text=/Other clusters/').count()
            if other_nodes > 0:
                print(f"   📦 Found {other_nodes} 'Other' nodes (grouping smaller clusters)")
            else:
                print(f"   🔍 No 'Other' nodes (all clusters shown individually)")

            print()

        # Verification
        print("="*70)
        print("VERIFICATION RESULTS")
        print("="*70 + "\n")

        reference_counts = participant_counts[2]  # Position 2 should show all
        all_preserved = True

        for position, counts in participant_counts.items():
            if counts == reference_counts:
                print(f"✅ Position {position}: Participant counts match reference (100% preserved)")
            else:
                print(f"❌ Position {position}: MISMATCH - {counts} vs {reference_counts}")
                all_preserved = False

        if all_preserved:
            print("\n" + "="*70)
            print("🎉 SUCCESS: All participants preserved at every granularity level!")
            print("="*70 + "\n")
        else:
            print("\n" + "="*70)
            print("❌ FAILURE: Participants not preserved consistently")
            print("="*70 + "\n")

        # Take final screenshot
        await page.screenshot(path="participant-preservation-test.png", full_page=True)
        print("📸 Screenshot saved: participant-preservation-test.png\n")

        print("⏸️  Browser staying open for 20 seconds for inspection...")
        await asyncio.sleep(20)

        await browser.close()
        print("✅ Test complete!\n")

if __name__ == "__main__":
    asyncio.run(test_preservation())
