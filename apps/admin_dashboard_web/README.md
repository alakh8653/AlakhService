# AlakhService — Admin Dashboard

Central admin panel for AlakhService platform operators to manage disputes, settlements, access control, system monitoring, and audit logs.

## Features

- **Audit Logs** — Full activity trail with actor, action, resource, and timestamp filters
- **Disputes** — View, investigate, and resolve customer/shop disputes with evidence
- **Finance** — Settlement runs, revenue reports, export to CSV
- **System Monitoring** — Real-time service health, uptime, error rates, latency charts
- **Access Control** — Manage admin roles and fine-grained permission matrices

## Tech Stack

React 18 · TypeScript · Redux Toolkit · React Router v6 · Axios · Recharts · Tailwind CSS · Vite

## Getting Started

```bash
cd apps/admin_dashboard_web
cp .env.example .env
npm install
npm run dev   # http://localhost:5174
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API base URL |
| `VITE_APP_TITLE` | Browser tab title |
| `VITE_SENTRY_DSN` | Sentry error tracking DSN |

## Project Structure

```
src/
├── access_control/   # Roles & permissions pages + service
├── audit/            # Audit log page + service
├── disputes/         # Dispute list, detail, service
├── finance/          # Settlements, revenue reports, service
├── monitoring/       # System health, metrics, service
├── components/       # AdminSidebar, AdminHeader, DataTable
└── main.tsx
```
