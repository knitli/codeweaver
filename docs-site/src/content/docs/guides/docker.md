---
title: "Running CodeWeaver in Docker"
description: "Run CodeWeaver and Qdrant together with Docker Compose. The fastest way to get a persistent indexer running without touching your Python environment."
---

# Running CodeWeaver in Docker

> **TL;DR:** Docker is the easiest way to run CodeWeaver as a persistent service alongside Qdrant. Use it when you want a one-command setup, an isolated environment, or a long-running indexer that survives across shells. It saves you from managing a Python install and gives you a clean separation between CodeWeaver and your project.

If you'd rather install CodeWeaver directly into a Python environment, see [Installation & Setup](../installation/). Everything else in the docs (configuration, profiles, providers) applies the same way once the container is running.

---

## 1. Prerequisites

- **Docker Engine 20.10+** and **Docker Compose v2**
- **At least 4 GB of RAM** available to the Docker daemon
- A **codebase** you want to index

---

## 2. Quickstart: Free, Local Models

The default setup uses the `quickstart` profile — free local embeddings and a local Qdrant container. No API keys required.

```bash
# Grab the compose file and an example .env
curl -O https://raw.githubusercontent.com/knitli/codeweaver/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/knitli/codeweaver/main/.env.example
cp .env.example .env

# Start CodeWeaver and Qdrant
docker compose up -d

# Confirm it's healthy
curl http://localhost:9328/health/
```

That's it. CodeWeaver will index the directory pointed to by `PROJECT_PATH` (defaults to `.`) and start serving the MCP HTTP transport on port `9328`.

### Higher-Quality Search with Voyage AI

Switch to the `recommended` profile to use Voyage AI's code embeddings. You'll need a free key from [voyageai.com](https://www.voyageai.com/).

```bash
# In .env
CODEWEAVER_PROFILE=recommended
VOYAGE_API_KEY=your-voyage-api-key
```

```bash
docker compose up -d
```

For a deeper comparison of profiles, see [Choosing a Profile](../profiles/).

---

## 3. Pointing CodeWeaver at Your Codebase

The compose file mounts your codebase **read-only** at `/workspace` inside the container. Local edits show up immediately, and CodeWeaver re-indexes changed files automatically through its file watcher.

Set `PROJECT_PATH` in your `.env` to control what gets mounted:

```bash
# Absolute path (recommended)
PROJECT_PATH=/home/you/projects/my-app

# Relative to docker-compose.yml
PROJECT_PATH=../my-app

# Current directory (default)
PROJECT_PATH=.
```

A few common patterns:

- **Devcontainer-style** — Keep `docker-compose.yml` and `.env` inside the project and set `PROJECT_PATH=.`. The compose file lives next to the code it indexes.
- **Monorepo subdirectory** — Point `PROJECT_PATH` at a single package (`/path/to/monorepo/packages/backend`) to scope indexing.
- **Multiple projects** — Copy `docker-compose.yml` per project, change container names, ports, and volume names, and run `docker compose -f docker-compose.<name>.yml up -d`.

### Platform Notes

- **WSL2** — Keep your code in the Linux filesystem (`/home/...`). Indexing files on `/mnt/c/...` is slow.
- **macOS** — Enable VirtioFS in Docker Desktop for large repositories.
- **Linux** — Native bind mounts. Make sure the files are readable by UID 1000 (the `codeweaver` user inside the container).

---

## 4. Persistence: Why It Matters

Indexing a large codebase isn't free, so CodeWeaver stores its checkpoints, generated config, and provider secrets in a persistent volume. The compose file wires this up via `XDG_CONFIG_HOME=/app/config` and three named volumes:

| Container path | Volume | What lives here |
|---|---|---|
| `/app/config/codeweaver/` | `codeweaver_config` | Generated config, checkpoints, secrets |
| `/app/data/` | `codeweaver_data` | Application data and cache |
| Qdrant container | `qdrant_storage` | Vector database files |

If you remove these volumes, CodeWeaver re-indexes from scratch on next start.

To force a clean re-index without losing other state:

```bash
# Drop only the indexing checkpoints
docker compose exec codeweaver rm -rf /app/config/codeweaver/checkpoints/
docker compose restart codeweaver
```

---

## 5. Architecture at a Glance

The compose setup runs CodeWeaver in **HTTP transport** mode and exposes two ports.

```
┌────────────────────────────────────────────┐
│ codeweaver (port 9328 — MCP HTTP)          │
│   ├─ Indexing engine                       │
│   ├─ File watcher                          │
│   └─ find_code search API                  │
│      Connects to ↓                         │
└────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────┐
│ qdrant (port 6333 REST, 6334 gRPC)         │
│   └─ Vector storage                        │
└────────────────────────────────────────────┘
```

The default transport in non-Docker setups is stdio, with the daemon running in the background. In Docker we run the HTTP transport directly because the container itself is the long-lived process — no separate daemon needed. The compose file calls `codeweaver server --transport streamable-http`; the image's default `CMD` (`codeweaver start --foreground`) is what you'd use if you wanted both the management server and HTTP transport in one process.

To connect an MCP client (Claude Desktop, Cursor, etc.) to a Docker-hosted CodeWeaver, point it at the HTTP endpoint at `http://localhost:9328/`. The management server lives on port `9329` for health checks and metrics.

---

## 6. Custom Configuration

Profiles cover most cases, but if you want full control, drop a `codeweaver.toml` into your project root. CodeWeaver's auto-discovery picks it up from `/workspace` inside the container.

The easiest workflow:

```bash
# Let the container generate a starting config from your profile
docker compose up -d
docker cp codeweaver-server:/app/config/codeweaver/codeweaver.toml ./codeweaver.toml

# Edit and restart — auto-discovery takes care of the rest
docker compose restart codeweaver
```

If your config needs to live somewhere other than the project root, mount it explicitly:

```yaml
volumes:
  - ${PROJECT_PATH:-.}:/workspace:ro
  - codeweaver_config:/app/config
  - ./my-config.toml:/app/config/codeweaver/codeweaver.toml:ro
```

> **Talking to Qdrant from your config** — Inside the Docker network, Qdrant lives at `http://qdrant:6333`, not `http://localhost:6333`. The entrypoint rewrites the generated config for you, but if you author your own, use the network hostname.

For the full configuration model (providers, vector store, indexer settings), see the [Configuration Architecture](../configuration/) guide.

---

## 7. Using a Cloud Vector Store

To use Qdrant Cloud (or any remote Qdrant) instead of the bundled container, set the deployment type and URL in your `.env`:

```bash
VECTOR_DEPLOYMENT=cloud
VECTOR_URL=https://your-cluster.cloud.qdrant.io:6333
QDRANT__SERVICE__API_KEY=your-qdrant-api-key
```

Then comment out (or remove) the `qdrant` service block in `docker-compose.yml` so you're not paying for a local Qdrant you don't use.

---

## 8. Troubleshooting

**Services won't start.** Check Docker has enough memory (`docker info | grep -i memory`) and look at the logs:

```bash
docker compose logs codeweaver
docker compose logs qdrant
```

**Qdrant connection errors.** Verify Qdrant is reachable from the CodeWeaver container — it should resolve `qdrant`, not `localhost`:

```bash
docker compose exec codeweaver curl http://qdrant:6333/healthz
```

**API key errors.** The `recommended` profile fails fast if `VOYAGE_API_KEY` isn't set. Either set the key or switch profiles:

```bash
CODEWEAVER_PROFILE=quickstart docker compose up -d
```

**Files aren't being indexed.** Confirm the mount looks right and your files aren't excluded:

```bash
docker compose exec codeweaver ls -la /workspace
docker compose logs codeweaver | grep -iE 'index|watch'
```

**Permission denied on mounted files.** The container runs as UID 1000 (`codeweaver`). Make sure your project files are world-readable, or own them as UID 1000 on the host.

---

## 9. Production Notes

If you're running CodeWeaver as a real service rather than a development tool, a few things to set:

- **Pin the image version.** The published image is [`knitli/codeweaver`](https://hub.docker.com/r/knitli/codeweaver) on Docker Hub. Replace `build: .` with `image: knitli/codeweaver:vX.Y.Z` (or `:latest` if you really want it to track) so deploys are reproducible.
- **Set restart policies.** The compose file already includes `restart: unless-stopped`. Keep it.
- **Use Docker secrets** for API keys instead of `.env` files in production environments.
- **Tune resource limits.** The defaults give CodeWeaver 4 GB; large repositories may need more.
- **Don't commit `.env`.** Real keys belong in your secret manager.

---

## 10. Building the Image Yourself

The image uses [`uv`](https://astral.sh/uv) for dependency installation and pulls all CodeWeaver workspace packages from a single VCS-derived version. To build locally:

```bash
# From the repository root
docker build -t codeweaver:local .

# Use it in compose
# Replace `build: .` with `image: codeweaver:local`
```

If you hit SSL certificate errors during a CI build (corporate proxies, self-signed roots in the chain), the simplest workaround is to use the pre-built image rather than rebuilding. See [`docs/docker/DOCKER_BUILD_NOTES.md`](https://github.com/knitli/codeweaver/blob/main/docs/docker/DOCKER_BUILD_NOTES.md) in the repo for environment-specific notes.

---

## See Also

- [Installation & Setup](../installation/) — The non-Docker install path
- [Configuration Architecture](../configuration/) — How settings, profiles, and `.toml` files compose
- [Choosing a Profile](../profiles/) — Picking between `recommended`, `quickstart`, and `testing`
- [Local-Only Operation](../local-only/) — Running fully airgapped (works in Docker too)
- [Resilience & Fallbacks](../resilience/) — How CodeWeaver stays up when cloud providers don't
