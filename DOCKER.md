<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Docker Guide

This guide explains how to run CodeWeaver using Docker and Docker Compose, providing an easy setup with integrated Qdrant vector database.

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- At least 4GB RAM available
- Your codebase to index

### Zero-Config Quick Start

The fastest way to get started uses the `quickstart` profile with free, local models:

```bash
# 1. Get the configuration files
curl -O https://raw.githubusercontent.com/knitli/codeweaver/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/knitli/codeweaver/main/.env.example
cp .env.example .env

# 2. Start services (uses free local models by default)
docker compose up -d

# 3. Check health
curl http://localhost:9328/health/
```

That's it! CodeWeaver will index the current directory using free, local embedding models.

### With Cloud Providers (Higher Quality)

For better search quality, use the `recommended` profile with Voyage AI:

```bash
# Set your API key and profile
export VOYAGE_API_KEY=your-voyage-api-key
export CODEWEAVER_PROFILE=recommended

docker compose up -d
```

Get a free Voyage API key at [voyageai.com](https://www.voyageai.com/).

## Configuration Profiles

CodeWeaver uses profiles to simplify configuration. Each profile pre-configures providers and models:

| Profile | Description | API Keys Required | Use Case |
|---------|-------------|-------------------|----------|
| `quickstart` | FastEmbed/Sentence Transformers (free, local) | None | Getting started, offline use |
| `recommended` | Voyage AI (high-quality cloud models) | `VOYAGE_API_KEY` | Production, best quality |
| `backup` | Lightest local models + in-memory vectors | None | Testing, minimal resources |

### Setting the Profile

```bash
# Via environment variable
CODEWEAVER_PROFILE=quickstart docker compose up -d

# Or in .env file
CODEWEAVER_PROFILE=recommended
```

### Profile Details

#### Quickstart Profile (Default)
- **Embeddings**: FastEmbed or Sentence Transformers (local)
- **Reranking**: FastEmbed or Sentence Transformers (local)
- **Vector Store**: Qdrant (local container)
- **Best for**: Getting started quickly, offline development

#### Recommended Profile
- **Embeddings**: Voyage AI `voyage-code-3`
- **Reranking**: Voyage AI `voyage-rerank-2.5`
- **Vector Store**: Qdrant (local container)
- **Best for**: Production use, highest search quality

#### Backup Profile
- **Embeddings**: Lightest available local model
- **Reranking**: Lightest available local model
- **Vector Store**: In-memory (no Qdrant needed)
- **Best for**: Testing, CI/CD, minimal resource usage

## Mounting Your Codebase

### How It Works

CodeWeaver uses Docker bind mounts to access your codebase:

- **Live sync**: Changes you make locally appear instantly in the container
- **Read-only**: The `:ro` flag prevents CodeWeaver from modifying your code
- **Direct access**: No copying - CodeWeaver reads your actual files
- **File watching**: CodeWeaver monitors for changes and re-indexes automatically

### Basic Setup

Set `PROJECT_PATH` in your `.env` file:

```bash
# Absolute path (recommended)
PROJECT_PATH=/home/user/projects/my-app

# Relative path (relative to docker-compose.yml)
PROJECT_PATH=../my-app

# Current directory
PROJECT_PATH=.
```

The codebase is mounted at `/workspace` inside the container.

### Common Patterns

#### Pattern 1: Index a Specific Project

```bash
# .env
PROJECT_PATH=/home/user/projects/my-app
```

```bash
# Or via command line
PROJECT_PATH=/home/user/projects/my-app docker compose up -d
```

#### Pattern 2: Devcontainer-Style (Compose Inside Repo)

Keep docker-compose.yml in your project directory:

```
my-project/
├── docker-compose.yml
├── .env
├── src/
└── ...
```

```bash
# .env
PROJECT_PATH=.
```

This mirrors devcontainer behavior where the compose file lives with your code.

#### Pattern 3: Monorepo with Specific Subdirectory

```bash
# Index only the backend
PROJECT_PATH=/home/user/monorepo/packages/backend
```

### Live Indexing & File Watching

CodeWeaver continuously monitors your codebase while the server is running:

- **New files**: Automatically indexed
- **Modified files**: Re-indexed on detection
- **Deleted files**: Removed from index

This happens automatically - no action required.

#### Manual Re-indexing

Force a full re-index if needed:

```bash
# Via CLI
docker compose exec codeweaver codeweaver index --force

# Check indexing status
curl http://localhost:9328/health/ | jq '.indexing'
```

### Platform-Specific Notes

#### Windows

Use forward slashes or escaped backslashes:

```bash
# .env (Windows)
PROJECT_PATH=C:/Users/me/projects/my-app
```

**WSL2 users**: For best performance, keep your code in the Linux filesystem:
```bash
PROJECT_PATH=/home/user/projects/my-app  # Fast
# Not: PROJECT_PATH=/mnt/c/Users/...     # Slow
```

#### macOS

Docker Desktop for Mac uses gRPC-FUSE for mounts. For large codebases:

1. Enable VirtioFS in Docker Desktop settings
2. Configure exclude patterns (see Performance section)

#### Linux

Native bind mounts - best performance. Ensure the Docker user can read your files:

```bash
chmod -R o+r /path/to/your/project
```

## Persistent Data & Checkpoints

### Why Persistence Matters

CodeWeaver stores critical data that must persist between container restarts:

- **Index checkpoints**: Resume indexing after restart (avoid re-indexing from scratch)
- **Project state**: Track which files have been indexed
- **Generated config**: Profile-based configuration file
- **Secrets**: API keys configured via `cw init`

### Volume Configuration

The docker-compose.yml configures persistence via `XDG_CONFIG_HOME`:

```yaml
environment:
  - XDG_CONFIG_HOME=/app/config

volumes:
  - codeweaver_config:/app/config   # Checkpoints, config, secrets
  - codeweaver_data:/app/data       # Application data
```

**Important**: Without this persistence, CodeWeaver re-indexes from scratch on every restart. For large codebases, this can take significant time.

### Checking Checkpoint Status

```bash
# View checkpoint data
docker compose exec codeweaver ls -la /app/config/codeweaver/

# Check index status
curl http://localhost:9328/health/ | jq '.indexing'
```

### Resetting Checkpoints

To force a fresh re-index:

```bash
# Remove checkpoint data
docker compose exec codeweaver rm -rf /app/config/codeweaver/checkpoints/

# Restart to re-index
docker compose restart codeweaver
```

### Data Locations

| Data Type | Container Path | Mounted Volume |
|-----------|----------------|----------------|
| Config & Checkpoints | `/app/config/codeweaver/` | `codeweaver_config` |
| Application Data | `/app/data/` | `codeweaver_data` |
| Vector Database | (Qdrant container) | `qdrant_storage` |

## Custom Configuration File

For full control beyond profiles, create your own `codeweaver.toml`.

### Config Auto-Discovery

CodeWeaver automatically finds configuration files in these locations (in order of precedence):

**In your project (mounted at `/workspace`):**
- `codeweaver.local.toml` / `.yaml` / `.json`
- `codeweaver.toml` / `.yaml` / `.json`
- `.codeweaver.local.toml` / `.yaml` / `.json`
- `.codeweaver.toml` / `.yaml` / `.json`
- `.codeweaver/codeweaver.local.toml` / `.yaml` / `.json`
- `.codeweaver/codeweaver.toml` / `.yaml` / `.json`

**User config directory (`/app/config/codeweaver/` in Docker):**
- `codeweaver.toml` / `.yaml` / `.json`

The entrypoint generates config to the user config dir. You can override by placing a config in your project root.

### Method 1: Generate Locally First

```bash
# Install CodeWeaver locally (or use pipx)
pipx install codeweaver

# Generate a config file
cw init config --profile quickstart --config-path ./codeweaver.toml

# Edit as needed
vim codeweaver.toml

# Mount in docker-compose.yml
```

### Method 2: Extract from Container

```bash
# Start container (generates config from profile)
docker compose up -d

# Copy config out
docker cp codeweaver-server:/app/config/codeweaver/codeweaver.toml ./codeweaver.toml

# Edit locally
vim codeweaver.toml
```

### Using Your Config

**Option 1: Place in project root (recommended)**

Simply add `codeweaver.toml` to your project - CodeWeaver auto-discovers it:

```
my-project/
├── codeweaver.toml    # Auto-discovered!
├── src/
└── ...
```

**Option 2: Mount to user config location**

For config outside your project, mount explicitly in docker-compose.yml:

```yaml
volumes:
  - ${PROJECT_PATH:-.}:/workspace:ro
  - codeweaver_config:/app/config
  - ./my-config.toml:/app/config/codeweaver/codeweaver.toml:ro  # Add this
```

### Example Configuration

```toml
project_name = "my-project"
project_path = "/workspace"
token_limit = 30000

[provider.embedding]
provider = "voyage"
model_settings = { model = "voyage-code-3" }

[provider.vector_store]
provider = "qdrant"
provider_settings = {
  url = "http://qdrant:6333",  # Docker network hostname
  collection_name = "my-collection"
}

[indexer]
exclude_patterns = ["node_modules", ".git", "dist", "__pycache__"]
```

**Important**: When using the local Qdrant container, use `http://qdrant:6333` (Docker network hostname), not `localhost`.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  CodeWeaver Container                           │
│  ├─ MCP Server (port 9328)                     │
│  ├─ Live File Watcher                          │
│  ├─ Indexing Engine                            │
│  └─ Search API                                 │
│     Connects to ↓                              │
└─────────────────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────┐
│  Qdrant Container                               │
│  ├─ Vector Database (port 6333)                │
│  ├─ gRPC API (port 6334)                       │
│  └─ Persistent Storage                         │
└─────────────────────────────────────────────────┘
```

## Performance Optimization

### Large Codebases

For repositories with >10,000 files:

1. **Configure exclude patterns** in your `codeweaver.toml`:
   ```toml
   [indexer]
   exclude_patterns = [
     "node_modules",
     ".git",
     "dist",
     "build",
     "__pycache__",
     "*.pyc",
     "vendor",
     ".venv"
   ]
   ```

2. **Increase container memory**:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 8G
   ```

3. **Use VirtioFS** on macOS Docker Desktop

### Search Performance

Adjust result limits if needed:

```bash
# In .env
TOKEN_LIMIT=50000
```

## Troubleshooting

### Services Won't Start

**Check Docker resources:**
```bash
docker info | grep -i memory
# Ensure at least 4GB is available
```

**View logs:**
```bash
docker compose logs codeweaver
docker compose logs qdrant
```

### Qdrant Connection Errors

**Verify Qdrant is healthy:**
```bash
curl http://localhost:6333/health
```

**Check network connectivity:**
```bash
docker compose exec codeweaver curl http://qdrant:6333/health
```

### API Key Issues

**Check the profile and key:**
```bash
# View current profile
docker compose exec codeweaver env | grep CODEWEAVER_PROFILE

# Verify API key is passed
docker compose exec codeweaver env | grep VOYAGE_API_KEY
```

**Switch to quickstart profile** (no API key needed):
```bash
CODEWEAVER_PROFILE=quickstart docker compose up -d
```

### Files Not Being Indexed

**Check mount:**
```bash
docker compose exec codeweaver ls -la /workspace
```

**Verify exclude patterns** aren't blocking your files.

**Check indexer logs:**
```bash
docker compose logs codeweaver | grep -i "index\|watch"
```

### Changes Not Detected

If file watching isn't picking up changes:

1. Check the file is in an indexed path
2. Verify it's not in an exclude pattern
3. Restart the container: `docker compose restart codeweaver`

### Permission Denied

The container runs as user `codeweaver` (UID 1000). Ensure your files are readable:

```bash
# Check from inside container
docker compose exec codeweaver ls -la /workspace
```

## Advanced Usage

### Multiple Projects

Run separate instances for different projects:

```bash
# Create project-specific compose files
cp docker-compose.yml docker-compose.project1.yml

# Edit to use different:
# - Container names
# - Ports
# - Volume names

docker compose -f docker-compose.project1.yml up -d
```

### Remote Qdrant

To use Qdrant Cloud instead of the local container:

1. Set the vector deployment and URL:
   ```bash
   VECTOR_DEPLOYMENT=cloud
   VECTOR_URL=https://your-cluster.cloud.qdrant.io:6333
   ```

2. Remove or comment out the `qdrant` service in docker-compose.yml

3. Set your Qdrant API key:
   ```bash
   QDRANT_API_KEY=your-qdrant-api-key
   ```

### Production Deployment

For production use:

1. **Use specific version tags:**
   ```yaml
   image: knitli/codeweaver:v0.1.0
   ```

2. **Set resource limits:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 4G
   ```

3. **Use secrets for API keys:**
   ```yaml
   secrets:
     - voyage_api_key
   environment:
     - VOYAGE_API_KEY_FILE=/run/secrets/voyage_api_key
   ```

4. **Enable restart policies:**
   ```yaml
   restart: unless-stopped
   ```

## Monitoring

### Health Endpoint

```bash
curl http://localhost:9328/health/ | jq
```

Response includes:
- Service status
- Indexing progress
- Provider health
- Memory usage

### Docker Stats

```bash
docker stats codeweaver-server codeweaver-qdrant
```

## Security Considerations

1. **API Keys**: Never commit `.env` files with real API keys
2. **Network**: Services communicate on internal Docker network
3. **User**: Container runs as non-root user (`codeweaver`, UID 1000)
4. **Volumes**: Codebase is mounted read-only (`:ro`)
5. **Updates**: Regularly update to latest image versions

## Building Locally

If you want to build the Docker image yourself:

```bash
# From the repository root
docker build -t codeweaver:local .

# Test the build
docker run --rm codeweaver:local codeweaver --version

# Use in docker-compose.yml
# Change: image: knitli/codeweaver:latest
# To:     build: .
```

## Known Limitations

- **Resource Usage**: Indexing large codebases may require significant memory
- **Platform Support**: Tested on linux/amd64 and linux/arm64
- **CI/CD SSL Issues**: Some CI environments have SSL certificate issues. Use pre-built images as a workaround. See [DOCKER_BUILD_NOTES.md](docs/docker/DOCKER_BUILD_NOTES.md).

## Support

- **Issues**: [GitHub Issues](https://github.com/knitli/codeweaver/issues)
- **Discussions**: [GitHub Discussions](https://github.com/knitli/codeweaver/discussions)
- **Documentation**: [Main README](README.md)

## See Also

- [Main README](README.md) - Project overview and features
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [API Documentation](docs/) - Detailed API reference
