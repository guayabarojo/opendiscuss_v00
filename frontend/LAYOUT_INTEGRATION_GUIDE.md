# Desktop Layout Integration Guide

## Overview

The new 4-column responsive desktop layout has been integrated into the OpenDiscuss frontend. This guide shows you how to use it.

## Files Created

### Layout System
- `/src/layouts/DesktopLayout.tsx` - Main layout component
- `/src/layouts/DesktopLayout.css` - Layout styles
- `/src/layouts/README.md` - Detailed documentation

### Components
- `/src/components/Topbar/Topbar.tsx` - Header with search
- `/src/components/Topbar/Topbar.css`
- `/src/components/CommunityRail/CommunityRail.tsx` - 56px icon rail
- `/src/components/CommunityRail/CommunityRail.css`
- `/src/components/CommunitySidebar/CommunitySidebar.tsx` - 260px sidebar
- `/src/components/CommunitySidebar/CommunitySidebar.css`
- `/src/components/RightSidebar/RightSidebar.tsx` - 320px widget sidebar
- `/src/components/RightSidebar/RightSidebar.css`

### Examples
- `/src/AppWithLayout.tsx` - Example App integration
- `/src/pages/ApprovalInterface/ApprovalInterfaceWithLayout.tsx` - Example page wrapper

## Quick Start

### Option 1: Wrap Individual Pages

```tsx
import { DesktopLayout } from './layouts/DesktopLayout';
import { YourPage } from './pages/YourPage';

function PageWithLayout() {
  return (
    <DesktopLayout>
      <YourPage />
    </DesktopLayout>
  );
}
```

### Option 2: Wrap Routes in App.tsx

```tsx
import { DesktopLayout } from './layouts/DesktopLayout';

// In your Routes:
<Route
  path="/some-page"
  element={
    <DesktopLayout>
      <SomePage />
    </DesktopLayout>
  }
/>
```

### Option 3: Use AppWithLayout.tsx

Replace your current `App.tsx` import in `main.tsx`:

```tsx
// Before
import App from './App.tsx'

// After
import App from './AppWithLayout.tsx'
```

## Customization

### Hide Specific Sidebars

```tsx
// Hide right sidebar for focused content
<DesktopLayout showRightSidebar={false}>
  <FocusedContent />
</DesktopLayout>

// Show only main content
<DesktopLayout
  showRail={false}
  showSidebar={false}
  showRightSidebar={false}
>
  <FullWidthContent />
</DesktopLayout>
```

## Responsive Breakpoints

The layout automatically adjusts:
- **< 1100px**: Right sidebar hidden
- **< 820px**: Left sidebar hidden
- **< 600px**: Rail hidden

## Design Tokens (CSS Variables)

Updated in `/src/index.css`:

```css
:root {
  --bg: #f5f5f5;        /* Background */
  --panel: #ffffff;      /* Panels/cards */
  --border: #e0e0e0;     /* Borders */
  --text: #213547;       /* Text */
  --muted: #666666;      /* Muted text */
  --accent: #667eea;     /* Accent color */
  --radius: 8px;         /* Border radius */
}
```

Use these in your components for consistency:

```css
.my-component {
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--text);
}
```

## Integration with ApprovalInterface

For the approval interface specifically:

```tsx
// Original route
<Route path="/approval" element={<ApprovalInterface />} />

// With layout at appropriate breakpoint
<Route
  path="/approval"
  element={
    <DesktopLayout showRightSidebar={true}>
      <ApprovalInterface />
    </DesktopLayout>
  }
/>
```

The `ApprovalInterface` content will automatically adapt to the available width.

## Testing

### Build Test
```bash
cd frontend
npm run build
```

### Development Test
```bash
npm run dev
```

Then test responsive breakpoints:
1. Open http://localhost:5173
2. Open browser DevTools
3. Toggle responsive design mode
4. Test at widths: 1400px, 1100px, 820px, 600px

## Migration Strategy

**Recommended approach:**

1. **Keep existing App.tsx** - Don't break current functionality
2. **Test with AppWithLayout.tsx** - Import it in a test route
3. **Migrate pages gradually** - Wrap one page at a time
4. **Test at each breakpoint** - Ensure responsive behavior works
5. **Replace App.tsx when ready** - After all pages are tested

## Customizing Components

### Add New Navigation Items

Edit `/src/components/CommunityRail/CommunityRail.tsx`:

```tsx
const railItems: RailItem[] = [
  // Add your custom items
  {
    id: 'my-feature',
    label: 'My Feature',
    path: '/my-feature',
    icon: <YourIcon />,
  },
  // ...
];
```

### Add Custom Widgets

Edit `/src/components/RightSidebar/RightSidebar.tsx`:

```tsx
const widgets: Widget[] = [
  {
    id: 'my-widget',
    title: 'My Widget',
    content: <MyCustomWidget />,
  },
  // ...
];
```

### Customize Colors

Edit CSS custom properties in `/src/index.css`:

```css
:root {
  --accent: #667eea;  /* Change this to your brand color */
}
```

## Common Patterns

### Full-Width Content Pages

```tsx
<DesktopLayout
  showRail={false}
  showSidebar={false}
  showRightSidebar={false}
>
  <FullPageContent />
</DesktopLayout>
```

### Focus Mode (No Distractions)

```tsx
<DesktopLayout showRightSidebar={false}>
  <DiscussionLive />
</DesktopLayout>
```

### Dashboard View (All Sidebars)

```tsx
<DesktopLayout>
  <DashboardContent />
</DesktopLayout>
```

## Troubleshooting

### Layout Doesn't Show

- Check that DesktopLayout is imported correctly
- Verify CSS files are being imported
- Check browser console for errors

### Responsive Breakpoints Not Working

- Clear browser cache
- Check CSS custom properties are defined
- Verify viewport meta tag in index.html

### Content Overlapping

- Check z-index values
- Verify sticky positioning
- Ensure parent containers have proper overflow

## Additional Resources

- See `/src/layouts/README.md` for detailed documentation
- Check `/src/AppWithLayout.tsx` for complete integration example
- Review component source files for inline comments

## Support

For issues or questions:
1. Check this guide
2. Review `/src/layouts/README.md`
3. Examine example files in `/src/AppWithLayout.tsx`
4. Check component source code comments
