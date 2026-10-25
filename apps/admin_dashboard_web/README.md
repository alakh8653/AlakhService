# AlakhService — Admin Dashboard

Central admin panel for AlakhService platform operators to manage disputes, settlements, access control, system monitoring, and audit logs.

## Features

- **Sign-in** — admin accounts only (role `admin` in auth_service); expired sessions return to the sign-in page
- **Users** — search accounts and ban/unban them. A ban deactivates the account in auth_service, so the
  person cannot sign in or refresh a session (an access token already issued lasts until it expires, at most
  `ACCESS_TOKEN_EXPIRE_MINUTES`). Needs `INTERNAL_API_KEY` set for admin_service and auth_service.
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

## Admin accounts

Register the account normally (app or `POST /api/v1/auth/register`), then grant it admin access:

```bash
docker compose exec auth_service python -m app.cli make-admin ops@example.com
# revoke with: python -m app.cli revoke-admin ops@example.com
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
