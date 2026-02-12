# ✅ shadcn/ui Setup Complete

## What Was Installed

### Core Dependencies
- ✅ Tailwind CSS 4.1.18
- ✅ tailwindcss-animate
- ✅ class-variance-authority
- ✅ clsx
- ✅ tailwind-merge
- ✅ lucide-react

### shadcn/ui Components Added
- ✅ Button
- ✅ Card
- ✅ Table
- ✅ Badge
- ✅ Select
- ✅ Input
- ✅ Dialog
- ✅ Dropdown Menu

## Files Created/Modified

### New Files
- `tailwind.config.js` - Tailwind configuration with shadcn theme
- `components.json` - shadcn CLI configuration
- `src/lib/utils.ts` - `cn()` utility for class merging
- `src/components/ui/` - All shadcn UI components

### Modified Files
- `src/index.css` - Added Tailwind directives and CSS variables

## How to Use

### 1. Import Components

```typescript
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
```

### 2. Example Usage

#### Button

```tsx
<Button variant="default">Default Button</Button>
<Button variant="destructive">Delete</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
<Button size="icon">🔍</Button>
```

#### Card

```tsx
<Card>
  <CardHeader>
    <CardTitle>Discussion Flow</CardTitle>
    <CardDescription>Participant movement across rounds</CardDescription>
  </CardHeader>
  <CardContent>
    <p>Card content goes here</p>
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

#### Badge

```tsx
<Badge variant="default">New</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Error</Badge>
<Badge variant="outline">Outline</Badge>
```

#### Table

```tsx
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Status</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell>Item 1</TableCell>
      <TableCell>Active</TableCell>
    </TableRow>
  </TableBody>
</Table>
```

### 3. Using the `cn()` Utility

The `cn()` utility combines class names intelligently:

```typescript
import { cn } from "@/lib/utils"

// Merge classes with conditional logic
className={cn(
  "base-class",
  isActive && "active-class",
  error && "error-class"
)}
```

## Adding More Components

To add additional shadcn components:

```bash
npx shadcn@latest add [component-name]
```

Examples:
```bash
npx shadcn@latest add alert
npx shadcn@latest add tabs
npx shadcn@latest add toast
npx shadcn@latest add skeleton
```

Browse all components: https://ui.shadcn.com/docs/components

## Theme Customization

Edit `tailwind.config.js` and `src/index.css` to customize:
- Colors
- Border radius
- Spacing
- Typography

### CSS Variables (in `src/index.css`)

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 242 47% 63%;  /* Purple accent */
  /* ... more variables */
}
```

## Dark Mode

Dark mode is already configured! To toggle:

```typescript
// Add this to your root component
<html className={isDark ? "dark" : ""}>
```

## Quick Modernization Examples

### Replace Old Button

**Before:**
```tsx
<button className="btn btn-primary" onClick={handleClick}>
  Click Me
</button>
```

**After:**
```tsx
<Button onClick={handleClick}>
  Click Me
</Button>
```

### Replace Old Card/Panel

**Before:**
```tsx
<div className="sankey-metadata-panel">
  <h2>Metadata</h2>
  <div>Content</div>
</div>
```

**After:**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Metadata</CardTitle>
  </CardHeader>
  <CardContent>
    <div>Content</div>
  </CardContent>
</Card>
```

### Replace Loading State

**Before:**
```tsx
{loading && <div className="loading-spinner">Loading...</div>}
```

**After:**
```tsx
import { Skeleton } from "@/components/ui/skeleton"

{loading && (
  <div className="space-y-2">
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-[90%]" />
    <Skeleton className="h-4 w-[80%]" />
  </div>
)}
```

## TypeScript Support

All components are fully typed with TypeScript. Use IntelliSense for prop suggestions.

## Best Practices

1. **Use `cn()` for conditional classes**
   ```tsx
   <Button className={cn("w-full", isLoading && "opacity-50")}>
   ```

2. **Compose components**
   ```tsx
   <Card>
     <CardHeader>
       <div className="flex items-center justify-between">
         <CardTitle>Title</CardTitle>
         <Badge>New</Badge>
       </div>
     </CardHeader>
   </Card>
   ```

3. **Maintain consistency**
   - Use shadcn components throughout the app
   - Stick to the design system (colors, spacing, radius)

## Next Steps

1. **Add Skeleton component** for better loading states:
   ```bash
   npx shadcn@latest add skeleton
   ```

2. **Add Toast notifications**:
   ```bash
   npx shadcn@latest add toast sonner
   ```

3. **Add Form components**:
   ```bash
   npx shadcn@latest add form label checkbox
   ```

4. **Gradually migrate** existing components to use shadcn/ui

---

**🎨 Your frontend is now ready for modern UI development with shadcn/ui!**
