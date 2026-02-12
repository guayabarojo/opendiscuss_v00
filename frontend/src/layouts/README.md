# DesktopLayout - 4-Column Responsive Layout System

A modern, responsive 4-column layout for the OpenDiscuss frontend with sticky navigation and customizable sidebars.

## Architecture

### Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│                         Topbar (60px)                         │
│                    Sticky Header + Search                     │
├────┬─────────────┬──────────────────────┬────────────────────┤
│    │             │                      │                    │
│ R  │  Sidebar    │       Main          │   Right Sidebar    │
│ a  │  (260px)    │    (Flexible)       │      (320px)       │
│ i  │             │                      │                    │
│ l  │  Navigation │    Page Content     │     Widgets        │
│    │             │                      │                    │
│(56)│             │                      │                    │
│    │             │                      │                    │
└────┴─────────────┴──────────────────────┴────────────────────┘
```

### Components

1. **DesktopLayout** (`DesktopLayout.tsx`)
   - Main layout container
   - Manages 4-column structure
   - Props: `showRail`, `showSidebar`, `showRightSidebar`

2. **Topbar** (`components/Topbar/`)
   - Sticky header (60px height)
   - Search bar
   - User actions and navigation

3. **CommunityRail** (`components/CommunityRail/`)
   - 56px icon rail (leftmost column)
   - Main navigation icons
   - Community/discussion quick access

4. **CommunitySidebar** (`components/CommunitySidebar/`)
   - 260px navigation sidebar (second column)
   - Detailed navigation links
   - Section-based organization

5. **RightSidebar** (`components/RightSidebar/`)
   - 320px widget sidebar (rightmost column)
   - Contextual widgets
   - Activity feeds, stats, etc.

## Responsive Breakpoints

- **< 1100px**: Hide right sidebar
- **< 820px**: Hide left sidebar
- **< 600px**: Hide rail

All sidebars use CSS media queries to hide/show automatically.

## CSS Custom Properties (Design Tokens)

```css
:root {
  --bg: #f5f5f5;           /* Background color */
  --panel: #ffffff;         /* Panel/card color */
  --border: #e0e0e0;        /* Border color */
  --text: #213547;          /* Primary text */
  --muted: #666666;         /* Muted text */
  --accent: #667eea;        /* Accent color */
  --radius: 8px;            /* Border radius */
}
```

## Usage

### Basic Integration

```tsx
import { DesktopLayout } from './layouts/DesktopLayout';

function MyPage() {
  return (
    <DesktopLayout>
      <YourPageContent />
    </DesktopLayout>
  );
}
```

### Selective Sidebars

```tsx
// Hide right sidebar for focused content
<DesktopLayout showRightSidebar={false}>
  <FocusedContent />
</DesktopLayout>

// Show only main content (no sidebars)
<DesktopLayout
  showRail={false}
  showSidebar={false}
  showRightSidebar={false}
>
  <FullWidthContent />
</DesktopLayout>
```

### Route-Based Layout

```tsx
// In App.tsx or your router
<Route
  path="/discussions/:id/live"
  element={
    <DesktopLayout showRightSidebar={false}>
      <DiscussionLive />
    </DesktopLayout>
  }
/>
```

## Integration with Existing Pages

### Example: ApprovalInterface

```tsx
// ApprovalInterfaceWithLayout.tsx
import { DesktopLayout } from '../../layouts/DesktopLayout';
import { ApprovalInterface } from './ApprovalInterface';

export const ApprovalInterfaceWithLayout = () => (
  <DesktopLayout>
    <ApprovalInterface />
  </DesktopLayout>
);
```

### Migration Strategy

1. **Keep existing routes working**: The original `App.tsx` remains unchanged
2. **Create new layout-wrapped components**: See `AppWithLayout.tsx` for examples
3. **Gradual migration**: Wrap pages one at a time
4. **Test responsiveness**: Verify breakpoints work for each page

## Styling Guidelines

### Using Design Tokens

```css
/* Good - Uses CSS custom properties */
.my-component {
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius);
}

/* Avoid - Hardcoded values */
.my-component {
  background: #ffffff;
  border: 1px solid #e0e0e0;
}
```

### Layout-Aware Content

```css
/* Use utility classes for consistent spacing */
.desktop-layout__content-wrapper {
  max-width: 1200px;
  margin: 0 auto;
}

.desktop-layout__content-narrow {
  max-width: 800px;
  margin: 0 auto;
}
```

## Customization

### Changing Column Widths

Edit `DesktopLayout.css`:

```css
:root {
  --rail-width: 56px;           /* Icon rail */
  --sidebar-width: 260px;        /* Left sidebar */
  --right-sidebar-width: 320px;  /* Right sidebar */
  --topbar-height: 60px;         /* Header */
}
```

### Adjusting Breakpoints

```css
:root {
  --bp-hide-right: 1100px;
  --bp-hide-sidebar: 820px;
}

@media (max-width: 1100px) {
  .desktop-layout__right-sidebar {
    display: none;
  }
}
```

### Custom Widgets

Add new widgets to `RightSidebar.tsx`:

```tsx
const widgets: Widget[] = [
  {
    id: 'my-widget',
    title: 'My Custom Widget',
    content: <MyWidgetComponent />,
  },
  // ... other widgets
];
```

## Testing

### Build Test

```bash
cd frontend
npm run build
```

### Development Server

```bash
npm run dev
```

### Test Responsive Breakpoints

1. Open browser dev tools
2. Toggle device emulation
3. Test at: 1400px, 1100px, 820px, 600px widths
4. Verify sidebars hide/show correctly

## Performance Considerations

- **Sticky positioning**: Uses `position: sticky` for performant scrolling
- **Flex layout**: Efficient column layout with flexbox
- **Lazy loading**: Sidebar content can be lazy-loaded
- **Memoization**: Consider memoizing expensive sidebar widgets

## Accessibility

- Semantic HTML5 elements (`<header>`, `<nav>`, `<main>`, `<aside>`)
- ARIA labels on navigation elements
- Keyboard navigation support
- Focus management for interactive elements

## Browser Support

- Chrome/Edge 88+
- Firefox 85+
- Safari 14+
- Modern mobile browsers

## Future Enhancements

- [ ] Dark mode support (extend CSS custom properties)
- [ ] Collapsible sidebars with toggle buttons
- [ ] Persistent sidebar state (localStorage)
- [ ] Animated transitions
- [ ] Widget drag-and-drop reordering
- [ ] Mobile navigation drawer
- [ ] Context-aware widget loading

## Files Created

```
frontend/src/
├── layouts/
│   ├── DesktopLayout.tsx
│   ├── DesktopLayout.css
│   └── README.md (this file)
├── components/
│   ├── Topbar/
│   │   ├── Topbar.tsx
│   │   └── Topbar.css
│   ├── CommunityRail/
│   │   ├── CommunityRail.tsx
│   │   └── CommunityRail.css
│   ├── CommunitySidebar/
│   │   ├── CommunitySidebar.tsx
│   │   └── CommunitySidebar.css
│   └── RightSidebar/
│       ├── RightSidebar.tsx
│       └── RightSidebar.css
├── AppWithLayout.tsx (example integration)
└── pages/
    └── ApprovalInterface/
        └── ApprovalInterfaceWithLayout.tsx (example)
```

## Support

For questions or issues with the layout system, check:
1. This README
2. Component source code comments
3. `AppWithLayout.tsx` for integration examples
