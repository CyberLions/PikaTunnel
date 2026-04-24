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

- **HTTP Reverse Proxy** — nginx-backed proxy routes with SSL support, per-route OIDC auth, and custom annotations
- **TCP/UDP Streaming** — Forward raw stream traffic with optional proxy protocol
- **VPN Management** — Connect and manage WireGuard and OpenVPN tunnels
- **Kubernetes Integration** — Syncs Ingress resources and LoadBalancer Service ports per route
- **OIDC Authentication** — Secure dashboard access with configurable OpenID Connect providers
- **TLS Certificates** — Upload inline PEM or reference mounted k8s secrets; cert-manager integration
- **Nginx Control** — Preview generated configs and reload nginx from the UI

## Tech Stack

| Layer    | Tech                                      |
|----------|-------------------------------------------|
| Frontend | React 19, TypeScript, Tailwind CSS, Vite  |
| Backend  | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL (async via asyncpg)            |
| Proxy    | Nginx (stream + http modules)             |
| K8s      | kubernetes Python client                 |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Or: Node.js 20+, Python 3.12+, PostgreSQL, pnpm

### Development (devcontainer)

Open in VS Code (with Dev Containers extension) or GitHub Codespaces — everything is pre-configured.

### Development (manual)

```bash
# Clone
git clone https://github.com/your-org/pikatunnel.git
cd pikatunnel

# Frontend
cd frontend && pnpm install && cd ..

# Backend
cd backend && pip install -e '.[dev]' && cd ..

# Environment
cp .env.example .env
# Edit .env with your database URL and secrets

# Run
pnpm dev
```

This starts both the frontend (Vite on port 5174) and backend (FastAPI on port 8000) in parallel.

### Docker

```bash
docker compose up
```

Apply database migrations manually:

```bash
docker compose exec backend alembic upgrade head
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `SECRET_KEY` | *(auto-generated)* | Session/cookie secret. Set for production. |
| `PUBLIC_URL` | `None` | External HTTPS URL for OIDC callbacks |
| `VPN_ENABLED` | `false` | Enable WireGuard/OpenVPN management |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

### OIDC Providers From Env

Preconfigure login providers via `AUTH_PROVIDERS` JSON (avoids creating DB rows):

```bash
AUTH_PROVIDERS=[{"id":"authentik","name":"Authentik","issuer_url":"https://auth.example.com/application/o/pikatunnel/","client_id":"pikatunnel","client_secret":"change-me","groups_claim":"groups","admin_group":"platform-admins","enabled":true}]
```

The `admin_group` is optional; falls back to the global `ADMIN_GROUP` env var.

### OIDC Provider Settings (UI)

OIDC providers can also be managed via the UI at **Cluster Settings → OIDC Providers**. The UI form requires `issuer_url`, `client_id`, and `client_secret`.

## HTTP Routes

Routes proxy `host + path` to a `destination:port`. Features per route:

- **SSL termination** — select a TLS certificate or use path-based cert/key files
- **Kubernetes Ingress** — enable to sync an Ingress resource to your cluster
- **Cloudflare Proxy** — toggle DNS-only vs proxied (respects cluster defaults)
- **Cert-Manager TLS** — automatic ACME certs via a cluster issuer
- **Authentik Auth** — protect routes with OIDC authentication
- **Proxy Timeouts** — body size, connect/read/send timeouts (applied as nginx ingress annotations)
- **Custom Annotations** — arbitrary key-value pairs merged into the Ingress

### Nginx Ingress Annotations

These are set per-route and applied as nginx ingress annotations:

| Field | Annotation |
|---|---|
| `k8s_proxy_body_size` | `nginx.ingress.kubernetes.io/proxy-body-size` |
| `k8s_proxy_connect_timeout` | `nginx.ingress.kubernetes.io/proxy-connect-timeout` |
| `k8s_proxy_read_timeout` | `nginx.ingress.kubernetes.io/proxy-read-timeout` |
| `k8s_proxy_send_timeout` | `nginx.ingress.kubernetes.io/proxy-send-timeout` |
| `k8s_custom_annotations` | merged verbatim |

### CSV Import/Export

Routes can be bulk-imported from CSV. Columns match `ProxyRoute` fields. See `examples/pritunl-migration-onprem-routes.csv` for the full column list including all K8s fields.

## TCP/UDP Streams

Stream routes forward raw network traffic by protocol:
- `listen_port` — port on the PikaTunnel host
- `destination:port` — where traffic is forwarded
- `protocol` — TCP or UDP
- `proxy_protocol` — prepend PROXY protocol header

Streams use nginx's `stream` module. No Host/Path routing — pure port forwarding.

## TLS Certificates

Two sources supported:
- **Inline PEM** — upload cert + key via UI; stored encrypted in DB
- **Mounted paths** — reference files already mounted in the container (e.g., from k8s TLS secrets)

When using cert-manager, leave cert fields empty and enable `k8s_cert_manager_enabled` + set `k8s_cluster_issuer` on the route.

## Kubernetes

PikaTunnel can manage `Ingress` resources per proxy route and sync a `LoadBalancer Service`'s ports. See [K8S_SETUP.md](K8S_SETUP.md) for `ServiceAccount`, `Role`, and `RoleBinding` manifests.

### Requirements

- `NET_ADMIN` capability for VPN tunnel interfaces
- `net.ipv4.conf.all.src_valid_mark` sysctl (WireGuard default-route support)
- `wireguard` kernel module on each node

## Project Structure

```
pikatunnel/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app entry point
│       ├── config.py             # Environment settings
│       ├── models.py             # SQLAlchemy models
│       ├── schemas.py            # Pydantic request/response schemas
│       ├── routers/              # API route handlers
│       │   ├── routes.py         # HTTP proxy routes
│       │   ├── streams.py        # TCP/UDP streams
│       │   ├── certs.py          # TLS certificates
│       │   ├── nginx.py          # nginx config & reload
│       │   ├── cluster.py        # K8s cluster settings
│       │   └── health.py         # Health check
│       └── services/
│           ├── nginx_config.py   # nginx.conf generation
│           └── k8s_ingress.py    # K8s Ingress sync
├── frontend/
│   └── src/
│       ├── pages/                # Route-level page components
│       ├── components/           # Shared UI components
│       ├── api/                  # Typed API client modules
│       └── types/index.ts       # TypeScript interfaces
├── examples/
│   └── pritunl-migration-onprem-routes.csv
├── K8S_SETUP.md                  # Kubernetes RBAC manifests
├── CLAUDE.md                     # Codebase documentation
└── AGENTS.md                     # Agent instructions
```

## API

All endpoints are under `/api/`. Key routes:

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/routes` | List/create HTTP routes |
| GET/PUT/DELETE | `/api/routes/{id}` | Read/update/delete route |
| POST | `/api/routes/{id}/sync` | Sync single route's K8s Ingress |
| POST | `/api/routes/sync-all` | Sync all K8s Ingresses |
| POST | `/api/routes/import` | Bulk import from CSV |
| GET | `/api/routes/export` | Export all routes as CSV |
| GET/POST | `/api/streams` | List/create stream routes |
| GET/PUT/DELETE | `/api/streams/{id}` | Read/update/delete stream |
| GET | `/api/nginx/config` | Preview generated nginx.conf |
| POST | `/api/nginx/reload` | Reload nginx |
| GET | `/api/health` | Health check |

## Database Migrations

New fields on models require a migration:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## License

MIT
