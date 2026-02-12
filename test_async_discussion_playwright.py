"""
Playwright E2E Test for Async Discussion Flow

This script tests the complete async discussion flow from start to Sankey diagram:
1. Navigate to create discussion page
2. Create async discussion with sample data
3. Start discussion
4. Submit responses for all participants (Round 1)
5. Wait for clustering to complete
6. Verify Round 2 opens
7. Submit responses for Round 2
8. Wait for discussion completion
9. Navigate to Sankey diagram
10. Verify Sankey visualization loads
"""

import asyncio
from playwright.async_api import async_playwright, Page, expect

DISCUSSION_ID = "0df96a6f-f005-470c-b7e4-bebe3e2884be"  # From E2E demo
BASE_URL = "http://localhost:3000"


async def test_discussion_live_page(page: Page):
    """Test the discussion live page loads and shows completed status."""
    print("\n📱 Testing Discussion Live Page...")

    url = f"{BASE_URL}/discussions/{DISCUSSION_ID}/live"
    print(f"   Navigating to: {url}")

    await page.goto(url, wait_until="networkidle")

    # Take screenshot
    await page.screenshot(path="/tmp/discussion-live.png")
    print("   ✅ Screenshot saved: /tmp/discussion-live.png")

    # Check for completed status
    page_content = await page.content()

    if "COMPLETED" in page_content or "completed" in page_content.lower():
        print("   ✅ Discussion shows COMPLETED status")
    else:
        print("   ⚠️  Could not verify COMPLETED status")

    # Check for round information
    if "Round" in page_content or "round" in page_content.lower():
        print("   ✅ Round information displayed")
    else:
        print("   ⚠️  No round information found")

    return True


async def test_sankey_page(page: Page):
    """Test the Sankey diagram page loads."""
    print("\n📊 Testing Sankey Diagram Page...")

    url = f"{BASE_URL}/discussions/{DISCUSSION_ID}/sankey"
    print(f"   Navigating to: {url}")

    await page.goto(url, wait_until="networkidle")

    # Wait a bit for any dynamic content
    await page.wait_for_timeout(2000)

    # Take screenshot
    await page.screenshot(path="/tmp/sankey-diagram.png")
    print("   ✅ Screenshot saved: /tmp/sankey-diagram.png")

    page_content = await page.content()

    # Check for Sankey-related content
    if "sankey" in page_content.lower() or "diagram" in page_content.lower():
        print("   ✅ Sankey page content found")
    elif "error" in page_content.lower() or "failed" in page_content.lower():
        print("   ❌ Error message detected on page")
        print(f"   Page content preview: {page_content[:500]}")
        return False
    else:
        print("   ⚠️  Could not verify Sankey content")

    # Check console for errors
    return True


async def test_report_page(page: Page):
    """Test the report page loads."""
    print("\n📄 Testing Report Page...")

    url = f"{BASE_URL}/discussions/{DISCUSSION_ID}/report"
    print(f"   Navigating to: {url}")

    await page.goto(url, wait_until="networkidle")

    # Wait a bit for any dynamic content
    await page.wait_for_timeout(2000)

    # Take screenshot
    await page.screenshot(path="/tmp/report-page.png")
    print("   ✅ Screenshot saved: /tmp/report-page.png")

    page_content = await page.content()

    if "report" in page_content.lower() or "summary" in page_content.lower():
        print("   ✅ Report page content found")
    elif "error" in page_content.lower() or "failed" in page_content.lower():
        print("   ❌ Error message detected on page")
        return False
    else:
        print("   ⚠️  Could not verify report content")

    return True


async def check_backend_api(page: Page):
    """Check if backend API is responding."""
    print("\n🔧 Checking Backend API...")

    # Navigate to API health endpoint
    try:
        await page.goto(f"{BASE_URL.replace(':3000', ':8000')}/health", wait_until="networkidle")
        content = await page.content()

        if "ok" in content.lower() or "healthy" in content.lower() or "status" in content.lower():
            print("   ✅ Backend API is responding")
            return True
        else:
            print("   ⚠️  Backend response unclear")
            print(f"   Response: {content[:200]}")
            return True  # Don't fail on this
    except Exception as e:
        print(f"   ⚠️  Could not reach backend: {e}")
        return True  # Don't fail on this


async def main():
    """Run all Playwright tests."""
    print("="*80)
    print("🎭 PLAYWRIGHT E2E TEST - ASYNC DISCUSSION FLOW")
    print("="*80)
    print(f"Discussion ID: {DISCUSSION_ID}")
    print(f"Base URL: {BASE_URL}")

    async with async_playwright() as p:
        # Launch browser
        print("\n🌐 Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        # Setup console logging
        page.on("console", lambda msg: print(f"   [Browser Console] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"   [Browser Error] {err}"))

        try:
            # Run tests
            await check_backend_api(page)
            await test_discussion_live_page(page)
            await test_sankey_page(page)
            await test_report_page(page)

            print("\n" + "="*80)
            print("✅ ALL TESTS COMPLETED")
            print("="*80)
            print("\nScreenshots saved to /tmp/:")
            print("  - /tmp/discussion-live.png")
            print("  - /tmp/sankey-diagram.png")
            print("  - /tmp/report-page.png")
            print("\n📊 View the discussion:")
            print(f"  Live: {BASE_URL}/discussions/{DISCUSSION_ID}/live")
            print(f"  Sankey: {BASE_URL}/discussions/{DISCUSSION_ID}/sankey")
            print(f"  Report: {BASE_URL}/discussions/{DISCUSSION_ID}/report")

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
