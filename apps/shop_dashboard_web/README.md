# AlakhService — Shop Dashboard

A React + TypeScript single-page application for shop owners to manage their bookings, services, staff, and analytics on the AlakhService platform.

## Features

- **Dashboard Overview** — At-a-glance stats: total bookings, revenue, active customers, and average rating
- **Bookings Management** — View, filter, approve, reject, and cancel bookings in real time
- **Services Catalogue** — Create, edit, and deactivate services offered by the shop
- **Staff Management** — Manage staff profiles, assign services, view weekly schedules
- **Analytics** — Revenue trends, booking volume charts, top-performing services
- **Settings** — Update shop profile, operating hours, notification preferences, and payment details

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | React 18 + TypeScript |
| Routing | React Router v6 |
| State Management | Redux Toolkit |
| HTTP Client | Axios |
| Charts | Recharts |
| Forms | React Hook Form + Zod |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| Build Tool | Vite |
| Testing | Vitest |

## Getting Started

### Prerequisites

- Node.js ≥ 18
- npm ≥ 9

### Installation

```bash
cd apps/shop_dashboard_web
cp .env.example .env
# Edit .env with your API base URL
npm install
```

### Development

```bash
npm run dev
# Opens at http://localhost:5173
```

### Production Build

```bash
npm run build
npm run preview
```

### Linting

```bash
npm run lint
```

### Tests

```bash
npm test
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000/api/v1` |
| `VITE_APP_TITLE` | Browser tab title | `AlakhService Shop Dashboard` |
| `VITE_SENTRY_DSN` | Sentry error tracking DSN | _(empty)_ |

## Project Structure

```
src/
├── components/       # Shared UI components (Sidebar, Header, Charts …)
├── hooks/            # Custom React hooks
├── pages/            # Route-level page components
├── services/         # Axios service modules (API calls)
├── state/            # Redux store, slices
├── types/            # Shared TypeScript interfaces
└── main.tsx          # Application entry point
```

## Authentication

The dashboard uses JWT-based authentication. The access token is stored in Redux state (in-memory) and injected into every API request via an Axios request interceptor. A response interceptor automatically attempts a token refresh on `401` responses.
