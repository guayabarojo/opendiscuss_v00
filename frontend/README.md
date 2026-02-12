# OpenDiscuss Frontend

React + TypeScript frontend for the OpenDiscuss Discussion Protocol.

## Tech Stack

- React 18
- TypeScript (strict mode)
- Vite (build tool)
- React Router (routing)
- TanStack Query (data fetching)
- Axios (HTTP client)
- Vitest + Testing Library (testing)

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development Server

```bash
npm run dev
```

The app will run on http://localhost:3000 and proxy API requests to http://localhost:8000.

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

### Run Tests

```bash
npm test
```

### Linting

```bash
npm run lint
```

### Format Code

```bash
npm run format
```

## Project Structure

```
frontend/
├── src/
│   ├── components/        # React components
│   │   ├── RoundTimer/    # Timer component
│   │   ├── HostControls/  # Host control panel
│   │   └── SankeyDiagram/ # Sankey diagram visualization
│   ├── pages/             # Page components
│   ├── services/          # API services
│   ├── App.tsx            # Main app component with routing
│   ├── main.tsx           # App entry point
│   └── index.css          # Global styles
├── tests/                 # Test files
├── index.html             # HTML template
└── package.json           # Dependencies
```

## Configuration Files

- `tsconfig.json` - TypeScript configuration (strict mode, path aliases)
- `vite.config.ts` - Vite build configuration (port 3000, proxy to backend)
- `.eslintrc.json` - ESLint configuration
- `.prettierrc` - Prettier formatting rules
- `vitest.config.ts` - Test configuration

## Path Aliases

The following path aliases are configured:

- `@/*` - Maps to `src/*`
- `@/components/*` - Maps to `src/components/*`
- `@/pages/*` - Maps to `src/pages/*`
- `@/services/*` - Maps to `src/services/*`

## API Proxy

The development server proxies the following paths to the backend (http://localhost:8000):

- `/api/*` - HTTP API requests
- `/ws` - WebSocket connections
