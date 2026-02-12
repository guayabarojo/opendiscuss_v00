"""
E2E Tests for Sankey Visualization Improvements

Tests the complete user flow for enhanced Sankey diagram features:
1. Round labels show question text (not "Round X")
2. Horizontal scroll enabled for 3+ rounds
3. Edges use gradient colors (source -> target)
4. Cluster labels use first sentence truncation
5. Complete visualization integration

Prerequisites:
- Backend server running on localhost:8000
- Frontend server running on localhost:3000
- Playwright browser installed (pytest-playwright)
- Discussion with completed Sankey diagram

Run: pytest tests/e2e/test_sankey_visualization.py -v -s
"""

import pytest
import asyncio
from playwright.async_api import async_playwright, Page, expect


# Test Data Fixtures
@pytest.fixture
def discussion_with_sankey_id():
    """
    Discussion ID with pre-constructed Sankey diagram.

    NOTE: This should be replaced with actual discussion ID from demo script
    or create a fixture that runs the demo and returns the ID.
    """
    # TODO: Run run_async_e2e_demo.py and return discussion_id
    # For now, return a placeholder
    return "replace-with-actual-discussion-id"


@pytest.fixture
async def browser_page():
    """Launch Playwright browser and return page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        yield page
        await browser.close()


# Test 1: Round Names Display Question Text
@pytest.mark.asyncio
async def test_sankey_round_names_show_questions(browser_page: Page, discussion_with_sankey_id: str):
    """Verify round labels display actual question text, not 'Round X'"""

    # Skip if no valid discussion ID
    if discussion_with_sankey_id == "replace-with-actual-discussion-id":
        pytest.skip("No valid discussion_id provided. Run demo script first.")

    # Navigate to Sankey page
    await browser_page.goto(f"http://localhost:3000/discussions/{discussion_with_sankey_id}/sankey")

    # Wait for Sankey diagram to render
    await browser_page.wait_for_selector('.round-label', timeout=10000)

    # Get first round label
    round1_label = await browser_page.locator('.round-label').first.text_content()

    # Should contain question words, not "Round 1"
    assert round1_label is not None, "Round label should exist"
    assert "What" in round1_label or "How" in round1_label, \
        f"Round label should show question text, got: {round1_label}"
    assert "Round 1" not in round1_label, \
        f"Round label should not show 'Round 1', got: {round1_label}"

    print(f"✓ Round label shows question: {round1_label}")


# Test 2: Horizontal Scroll Enabled
@pytest.mark.asyncio
async def test_sankey_horizontal_scroll_enabled(browser_page: Page, discussion_with_sankey_id: str):
    """Verify horizontal scroll container works correctly"""

    # Skip if no valid discussion ID
    if discussion_with_sankey_id == "replace-with-actual-discussion-id":
        pytest.skip("No valid discussion_id provided. Run demo script first.")

    # Navigate to Sankey page
    await browser_page.goto(f"http://localhost:3000/discussions/{discussion_with_sankey_id}/sankey")

    # Wait for container
    await browser_page.wait_for_selector('.sankey-diagram-container', timeout=10000)

    container = browser_page.locator('.sankey-diagram-container')

    # Check if content is wider than container (scroll needed)
    scroll_width = await container.evaluate('el => el.scrollWidth')
    client_width = await container.evaluate('el => el.clientWidth')

    # For 3+ rounds with increased spacing, should trigger scroll
    if scroll_width > client_width:
        print(f"✓ Horizontal scroll enabled (scrollWidth: {scroll_width} > clientWidth: {client_width})")

        # Test scrolling works
        await container.evaluate('el => el.scrollLeft = 100')
        scroll_left = await container.evaluate('el => el.scrollLeft')
        assert scroll_left == 100, "Scroll should work"
        print("✓ Scrolling works correctly")
    else:
        print(f"ℹ No scroll needed for this viewport (scrollWidth: {scroll_width}, clientWidth: {client_width})")


# Test 3: Edge Colors Use Gradients
@pytest.mark.asyncio
async def test_edge_colors_use_source_gradients(browser_page: Page, discussion_with_sankey_id: str):
    """Verify edges use gradient colors from source to target, not slate gray"""

    # Skip if no valid discussion ID
    if discussion_with_sankey_id == "replace-with-actual-discussion-id":
        pytest.skip("No valid discussion_id provided. Run demo script first.")

    # Navigate to Sankey page
    await browser_page.goto(f"http://localhost:3000/discussions/{discussion_with_sankey_id}/sankey")

    # Wait for edges to render
    await browser_page.wait_for_selector('.sankey-edge-path', timeout=10000)

    # Get first edge's fill attribute
    edge_fill = await browser_page.locator('.sankey-edge-path').first.get_attribute('fill')

    # Should use gradient (starts with "url(#gradient-")
    assert edge_fill is not None, "Edge should have fill attribute"
    assert edge_fill.startswith('url(#gradient-'), \
        f"Edge should use gradient, got: {edge_fill}"

    print(f"✓ Edges use gradient colors: {edge_fill}")


# Test 4: Cluster Labels Truncated Smartly
@pytest.mark.asyncio
async def test_cluster_labels_sentence_truncation(browser_page: Page, discussion_with_sankey_id: str):
    """Verify cluster labels use first sentence extraction"""

    # Skip if no valid discussion ID
    if discussion_with_sankey_id == "replace-with-actual-discussion-id":
        pytest.skip("No valid discussion_id provided. Run demo script first.")

    # Navigate to Sankey page
    await browser_page.goto(f"http://localhost:3000/discussions/{discussion_with_sankey_id}/sankey")

    # Wait for node labels
    await browser_page.wait_for_selector('.node-label-text', timeout=10000)

    # Get first cluster label
    label = await browser_page.locator('.node-label-text').first.text_content()

    # Should not exceed 65 chars (60 + ellipsis)
    assert label is not None, "Label should exist"
    assert len(label) <= 65, f"Label too long: {len(label)} chars"

    # If truncated, should end with period or ellipsis
    if len(label) >= 20:
        assert label.endswith('.') or label.endswith('...'), \
            f"Truncated label should end with . or ..., got: {label}"

    print(f"✓ Label truncated smartly: {label}")


# Test 5: Complete Flow Integration
@pytest.mark.asyncio
async def test_complete_sankey_visualization_flow(browser_page: Page, discussion_with_sankey_id: str):
    """Test complete userflow: load Sankey with all improvements"""

    # Skip if no valid discussion ID
    if discussion_with_sankey_id == "replace-with-actual-discussion-id":
        pytest.skip("No valid discussion_id provided. Run demo script first.")

    # Navigate to Sankey page
    await browser_page.goto(f"http://localhost:3000/discussions/{discussion_with_sankey_id}/sankey")

    # Wait for Sankey to render
    await browser_page.wait_for_selector('.sankey-diagram-container', timeout=10000)
    await browser_page.wait_for_selector('.round-label', timeout=5000)
    await browser_page.wait_for_selector('.sankey-node-rect', timeout=5000)
    await browser_page.wait_for_selector('.sankey-edge-path', timeout=5000)

    # Check all components rendered
    round_labels = await browser_page.locator('.round-label').count()
    assert round_labels >= 2, f"Should have at least 2 round labels, got {round_labels}"

    nodes = await browser_page.locator('.sankey-node-rect').count()
    assert nodes >= 2, f"Should have at least 2 cluster nodes, got {nodes}"

    edges = await browser_page.locator('.sankey-edge-path').count()
    assert edges >= 1, f"Should have at least 1 flow edge, got {edges}"

    print(f"✓ Complete Sankey rendered: {round_labels} rounds, {nodes} nodes, {edges} edges")

    # Take screenshot for manual verification
    await browser_page.screenshot(path='sankey-complete-visualization.png')
    print("✓ Screenshot saved: sankey-complete-visualization.png")


# Helper: Create discussion with Sankey (integration with backend demo)
@pytest.fixture
async def create_test_discussion_with_sankey():
    """
    Run async demo script and return discussion_id.

    This fixture should:
    1. Import and run run_async_e2e_demo.py
    2. Wait for Sankey construction
    3. Return discussion_id
    """
    # TODO: Import and run demo script
    # from run_async_e2e_demo import main
    # discussion_id = await main()
    # return discussion_id

    pytest.skip("Demo script integration not yet implemented")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
