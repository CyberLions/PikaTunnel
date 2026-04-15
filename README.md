<p align="center">
  <img src="logo.png" alt="PikaTunnel" width="150" />
</p>

<h1 align="center">PikaTunnel</h1>

<p align="center">
  A self-hosted reverse proxy and tunnel manager with a playful UI.<br/>
  Manage HTTP routes, TCP/UDP streams, VPN connections, and nginx — all from one dashboard.
</p>

---

## Features

- **HTTP Reverse Proxy** — Create and manage nginx-backed proxy routes with SSL support
- **TCP/UDP Streaming** — Forward raw stream traffic with optional proxy protocol
- **VPN Management** — Connect and manage Pritunl, WireGuard, and OpenVPN tunnels
- **OIDC Authentication** — Secure access with configurable OpenID Connect providers
- **Nginx Control** — Preview generated configs and reload nginx from the UI
- **Live Dashboard** — System health, route stats, and service status at a glance

## Tech Stack

| Layer    | Tech                          |
| -------- | ----------------------------- |
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| Backend  | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL                    |
| Proxy    | Nginx                         |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Or: Node.js 20+, Python 3.12+, PostgreSQL, pnpm

### Development (devcontainer)

This project includes a devcontainer config. Open it in VS Code or GitHub Codespaces and everything is set up automatically.

```bash
pnpm dev
```

This starts both the frontend (Vite on port 5174) and backend (FastAPI on port 8000) in parallel.

### Development (manual)

1. **Clone and install dependencies**

```bash
git clone https://github.com/your-org/pikatunnel.git
cd pikatunnel

# Frontend
cd frontend && pnpm install && cd ..

# Backend
cd backend && pip install -e '.[dev]' && cd ..
```

2. **Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your database connection and secrets
```

3. **Start the dev servers**

```bash
pnpm dev
```

### Docker

```bash
docker compose up
```

### OIDC Providers From Env

You can preconfigure login providers without creating database rows by setting `AUTH_PROVIDERS` in `.env` or your container environment. The value is a JSON array.

```bash
AUTH_PROVIDERS=[{"id":"authentik","name":"Authentik","issuer_url":"https://auth.example.com/application/o/pikatunnel/","client_id":"pikatunnel","client_secret":"change-me","groups_claim":"groups","admin_group":"platform-admins","enabled":true}]
```

`admin_group` is optional per provider. If omitted, PikaTunnel falls back to the global `ADMIN_GROUP` value.

If PikaTunnel sits behind a reverse proxy or ingress that terminates TLS, set `PUBLIC_URL` to the externally visible HTTPS URL so OIDC callbacks are generated correctly:

```bash
PUBLIC_URL=https://pikatunnel.example.com
```

## Project Structure

```
pikatunnel/
├── frontend/          # React + Vite frontend
│   ├── src/
│   │   ├── api/       # API client modules
│   │   ├── components/# Reusable UI components
│   │   ├── pages/     # Route pages
│   │   └── types/     # TypeScript type definitions
│   └── public/        # Static assets (logo, etc.)
├── backend/           # FastAPI backend
│   └── app/
│       ├── routers/   # API route handlers
│       ├── models.py  # SQLAlchemy models
│       ├── schemas.py # Pydantic schemas
│       └── services/  # Business logic (nginx, vpn)
├── docker-compose.yml
└── Dockerfile
```

## License

MIT
