# PikaTunnel — Codebase Guide

PikaTunnel is a self-hosted reverse proxy and tunnel manager. This file documents the architecture, patterns, and conventions to help Claude Code work effectively in this codebase.

## Project Overview

PikaTunnel manages:
- **HTTP proxy routes** → nginx virtual host configs with SSL termination
- **TCP/UDP streams** → nginx stream module configs
- **VPN tunnels** → WireGuard/OpenVPN interfaces
- **Kubernetes ingresses** → syncs per-route Ingress resources + LoadBalancer Service ports
- **TLS certificates** → cert-manager integration or manual PEM management

## Tech Stack

| Layer    | Tech                                      |
|----------|-------------------------------------------|
| Frontend | React 19, TypeScript, Tailwind CSS, Vite |
| Backend  | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL (async via asyncpg)            |
| Proxy    | Nginx (stream + http modules)            |
| K8s      | kubernetes Python client                 |

## Directory Structure

```
pikatunnel/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI app, includes router registration
│       ├── config.py        # Pydantic Settings (env vars)
│       ├── models.py        # SQLAlchemy ORM models
│       ├── schemas.py       # Pydantic request/response schemas
│       ├── routers/         # API route handlers
│       │   ├── routes.py    # HTTP proxy routes CRUD
│       │   ├── streams.py   # TCP/UDP stream routes CRUD
│       │   ├── certs.py     # TLS certificates
│       │   ├── nginx.py     # nginx config preview + reload
│       │   ├── cluster.py   # K8s cluster settings + sync all
│       │   └── health.py    # Health check endpoint
│       └── services/
│           ├── nginx_config.py   # Generates nginx .conf from DB routes
│           └── k8s_ingress.py    # K8s Ingress + Service sync logic
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Routes.tsx       # HTTP routes management UI
│       │   ├── Streams.tsx     # TCP/UDP streams UI
│       │   ├── Certs.tsx        # TLS certificates UI
│       │   ├── NginxConfig.tsx # nginx config preview
│       │   └── ClusterSettings.tsx
│       ├── api/             # Typed API clients
│       ├── components/      # Shared UI components
│       └── types/index.ts   # TypeScript interfaces
├── K8S_SETUP.md             # Kubernetes RBAC manifests
└── examples/
    └── pritunl-migration-onprem-routes.csv
```

## Key Data Models

### ProxyRoute
Core route entity. Fields include:
- `host`, `path`, `destination`, `port` — routing
- `ssl_enabled`, `ssl_cert_name`, `ssl_cert_path/key_path` — TLS
- `k8s_ingress_enabled` — enables K8s Ingress management
- `k8s_cloudflare_proxied`, `k8s_cert_manager_enabled`, `k8s_cluster_issuer` — DNS/TLS integration
- `k8s_authentik_enabled` — OIDC authentication
- `k8s_proxy_body_size`, `k8s_proxy_read_timeout`, `k8s_proxy_send_timeout`, `k8s_proxy_connect_timeout` — nginx ingress annotations
- `k8s_custom_annotations` — arbitrary extra annotations

### StreamRoute
TCP/UDP port forwarding. Fields: `name`, `destination`, `port`, `listen_port`, `protocol`, `proxy_protocol`, `enabled`.

### ClusterSettings
Global K8s cluster configuration: `k8s_api_url`, `k8s_token`, `k8s_ca_cert`, `k8s_namespace`, `k8s_in_cluster`, `default_ingress_class`, `default_cluster_issuer`, etc.

## API Design

All API endpoints are under `/api/`. Key patterns:
- `GET/POST /api/routes` — list/create HTTP routes
- `GET/PUT/DELETE /api/routes/{id}` — read/update/delete route
- `POST /api/routes/{id}/sync` — sync single route's K8s ingress
- `POST /api/routes/sync-all` — sync all K8s ingresses
- `GET /api/nginx/config` — preview generated nginx.conf
- `POST /api/nginx/reload` — reload nginx

## Kubernetes Ingress Annotations

PikaTunnel maps route fields to nginx ingress annotations:

| Route field | K8s annotation |
|---|---|
| `k8s_proxy_body_size` | `nginx.ingress.kubernetes.io/proxy-body-size` |
| `k8s_proxy_connect_timeout` | `nginx.ingress.kubernetes.io/proxy-connect-timeout` |
| `k8s_proxy_read_timeout` | `nginx.ingress.kubernetes.io/proxy-read-timeout` |
| `k8s_proxy_send_timeout` | `nginx.ingress.kubernetes.io/proxy-send-timeout` |
| `k8s_custom_annotations` | merged verbatim |

## Nginx Config Generation

`nginx_config.py` generates two config files:
- `/etc/nginx/nginx.conf` (HTTP) — virtual hosts from ProxyRoute rows
- `/etc/nginx/nginx.stream.conf` (Stream) — raw TCP/UDP from StreamRoute rows

The stream config is included inside a `stream {}` block in the main config via `include`.

## DB Migrations

Alembic is used. Migration files are in `backend/alembic/versions/`. New fields on models require a migration.

## Env Vars

See `backend/app/config.py` and `.env.example`. Key vars:
- `DATABASE_URL` — PostgreSQL connection
- `SECRET_KEY` — session/cookie secret
- `PUBLIC_URL` — external URL for OIDC callbacks
- `VPN_ENABLED` — enable WireGuard/OpenVPN
- `CORS_ORIGINS` — allowed origins

## Running

```bash
# Development
pnpm dev                    # starts frontend + backend in parallel
# or backend: cd backend && uvicorn app.main:app --reload
# or frontend: cd frontend && pnpm dev

# Docker
docker compose up

# DB migrations
cd backend && alembic upgrade head
```

## Testing

```bash
cd backend && pytest
```
