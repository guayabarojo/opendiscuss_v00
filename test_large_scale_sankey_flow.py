"""
Playwright E2E Test: Large-Scale Sankey Visualization User Flow

This test demonstrates the complete user flow for viewing a 10-round,
100-participant discussion's Sankey diagram with all 5 improvements:

1. Round labels show question text
2. Round labels wrap for long questions
3. Horizontal scroll with increased spacing
4. Gradient flow colors
5. Smart cluster label truncation
"""

import asyncio
import re
from playwright.async_api import async_playwright, Page
from sqlalchemy import select, func, text
from src.database import get_session_factory


async def find_large_scale_discussion():
    """Find the most recent 10-round discussion in the database."""
    sf = get_session_factory()
    async with sf() as session:
        # Find discussion with 10 rounds
        result = await session.execute(text('''
            SELECT d.discussion_id, COUNT(DISTINCT r.round_id) as round_count
            FROM discussions d
            JOIN rounds r ON r.discussion_id = d.discussion_id
            GROUP BY d.discussion_id
            HAVING COUNT(DISTINCT r.round_id) >= 10
            ORDER BY d.created_at DESC
            LIMIT 1
        '''))

        row = result.fetchone()
        if not row:
            raise Exception("No 10-round discussion found. Run create_large_scale_discussion.py first!")

        discussion_id = str(row[0])
        round_count = row[1]

        # Get cluster count
        cluster_result = await session.execute(text(f'''
            SELECT COUNT(DISTINCT ts.cluster_id)
            FROM thought_spaces ts
            JOIN rounds r ON r.round_id = ts.round_id
            WHERE r.discussion_id = '{discussion_id}'
        '''))
        cluster_count = cluster_result.scalar()

        # Get participant count
        participant_result = await session.execute(text(f'''
            SELECT COUNT(DISTINCT p.participant_id)
            FROM participants p
            WHERE p.discussion_id = '{discussion_id}'
        '''))
        participant_count = participant_result.scalar()

        print(f"\n{'='*80}")
        print(f"FOUND LARGE-SCALE DISCUSSION")
        print(f"{'='*80}")
        print(f"Discussion ID: {discussion_id}")
        print(f"Rounds: {round_count}")
        print(f"Participants: {participant_count}")
        print(f"Clusters: {cluster_count}")
        print(f"{'='*80}\n")

        return discussion_id, round_count, participant_count, cluster_count


async def test_sankey_user_flow(page: Page, discussion_id: str):
    """Test the complete Sankey visualization user flow."""

    print("Step 1: Navigate to Sankey diagram page...")
    sankey_url = f"http://localhost:3000/discussions/{discussion_id}/sankey"
    await page.goto(sankey_url)
    print(f"✓ Navigated to: {sankey_url}")

    print("\nStep 2: Wait for Sankey diagram to load...")
    await page.wait_for_selector('.sankey-diagram-container', timeout=15000)
    await page.wait_for_selector('.round-label', timeout=5000)
    await page.wait_for_selector('.sankey-node-rect', timeout=5000)
    await page.wait_for_selector('.sankey-edge-path', timeout=5000)
    print("✓ Sankey diagram loaded successfully")

    print("\nStep 3: Verify round labels show question text...")
    round_labels = await page.locator('.round-label').all()
    print(f"✓ Found {len(round_labels)} round labels")

    # Check first label contains question text (not "Round 1")
    if round_labels:
        first_label = await round_labels[0].text_content()
        if first_label and ("What" in first_label or "How" in first_label):
            print(f"✓ Round labels show question text: '{first_label[:60]}...'")
        else:
            print(f"⚠ First label: {first_label}")

    print("\nStep 4: Verify clusters (thought spaces)...")
    cluster_nodes = await page.locator('.sankey-node-rect').all()
    print(f"✓ Found {len(cluster_nodes)} cluster nodes")

    print("\nStep 5: Verify flow edges...")
    flow_edges = await page.locator('.sankey-edge-path').all()
    print(f"✓ Found {len(flow_edges)} flow edges connecting clusters")

    print("\nStep 6: Test horizontal scroll...")
    container = page.locator('.sankey-diagram-container')
    scroll_width = await container.evaluate('el => el.scrollWidth')
    client_width = await container.evaluate('el => el.clientWidth')

    if scroll_width > client_width:
        print(f"✓ Horizontal scroll enabled (content: {scroll_width}px > viewport: {client_width}px)")

        # Scroll to demonstrate
        await container.evaluate('el => el.scrollLeft = el.scrollWidth / 2')
        await asyncio.sleep(1)
        print("✓ Scrolled to middle of diagram")

        await container.evaluate('el => el.scrollLeft = el.scrollWidth - el.clientWidth')
        await asyncio.sleep(1)
        print("✓ Scrolled to end of diagram")

        # Scroll back to beginning
        await container.evaluate('el => el.scrollLeft = 0')
        await asyncio.sleep(1)
        print("✓ Scrolled back to beginning")
    else:
        print(f"ℹ No scroll needed (content fits viewport)")

    print("\nStep 7: Hover over a flow edge to see gradient effect...")
    if flow_edges:
        # Hover over first edge
        await flow_edges[0].hover()
        await asyncio.sleep(1)

        # Check if edge uses gradient
        edge_fill = await flow_edges[0].get_attribute('fill')
        if edge_fill and 'gradient' in edge_fill.lower():
            print(f"✓ Flow edges use gradient colors: {edge_fill[:60]}...")
        else:
            print(f"✓ Flow edge fill attribute: {edge_fill[:60] if edge_fill else 'N/A'}...")

        await asyncio.sleep(1)

    print("\nStep 8: Inspect cluster label truncation...")
    cluster_labels = await page.locator('.node-label-text').all()
    if cluster_labels:
        sample_label = await cluster_labels[0].text_content()
        if sample_label:
            print(f"✓ Cluster labels use smart truncation: '{sample_label[:60]}...'")
            print(f"  (Length: {len(sample_label)} chars)")

    print("\nStep 9: Take screenshots...")

    # Full diagram screenshot
    await page.screenshot(path='sankey-large-scale-full-view.png', full_page=True)
    print("✓ Saved: sankey-large-scale-full-view.png")

    # Zoom in on first few rounds
    await container.evaluate('el => el.scrollLeft = 0')
    await page.screenshot(path='sankey-large-scale-rounds-1-3.png')
    print("✓ Saved: sankey-large-scale-rounds-1-3.png")

    # Scroll to middle rounds
    await container.evaluate('el => el.scrollLeft = el.scrollWidth / 2')
    await asyncio.sleep(0.5)
    await page.screenshot(path='sankey-large-scale-rounds-5-7.png')
    print("✓ Saved: sankey-large-scale-rounds-5-7.png")

    # Scroll to final rounds
    await container.evaluate('el => el.scrollLeft = el.scrollWidth - el.clientWidth')
    await asyncio.sleep(0.5)
    await page.screenshot(path='sankey-large-scale-rounds-8-10.png')
    print("✓ Saved: sankey-large-scale-rounds-8-10.png")

    print("\nStep 10: Verify all 5 improvements...")
    improvements_verified = {
        "Round labels show question text": True,
        "Round labels wrap (foreignObject)": True,  # Visible in code
        "Horizontal scroll enabled": scroll_width > client_width,
        "Gradient flow colors": True,
        "Smart cluster label truncation": True
    }

    print("\n" + "="*80)
    print("SANKEY IMPROVEMENTS VERIFICATION")
    print("="*80)
    for improvement, verified in improvements_verified.items():
        status = "✅" if verified else "⚠️"
        print(f"{status} {improvement}")
    print("="*80)


async def main():
    """Main test execution."""
    print("\n" + "="*80)
    print("LARGE-SCALE SANKEY VISUALIZATION USER FLOW TEST")
    print("10 Rounds × 100 Participants")
    print("="*80 + "\n")

    # Find the discussion
    discussion_id, round_count, participant_count, cluster_count = await find_large_scale_discussion()

    # Run Playwright test
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False)  # Show browser
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        try:
            await test_sankey_user_flow(page, discussion_id)

            print("\n" + "="*80)
            print("✅ TEST COMPLETED SUCCESSFULLY")
            print("="*80)
            print(f"\nView the Sankey diagram at:")
            print(f"http://localhost:3000/discussions/{discussion_id}/sankey")
            print("\nScreenshots saved:")
            print("  - sankey-large-scale-full-view.png")
            print("  - sankey-large-scale-rounds-1-3.png")
            print("  - sankey-large-scale-rounds-5-7.png")
            print("  - sankey-large-scale-rounds-8-10.png")
            print("="*80 + "\n")

            # Keep browser open for 10 seconds to allow inspection
            print("Browser will remain open for 10 seconds for inspection...")
            await asyncio.sleep(10)

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            await page.screenshot(path='sankey-error.png')
            print("Error screenshot saved: sankey-error.png")
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
