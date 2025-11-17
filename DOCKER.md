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
- VoyageAI API key (get one at [voyageai.com](https://www.voyageai.com/))
- At least 4GB RAM available
- Your codebase to index

### 1. Get the Configuration Files

If you're using the CodeWeaver Docker image from Docker Hub:

```bash
# Download the example docker-compose.yml
curl -O https://raw.githubusercontent.com/knitli/codeweaver-mcp/main/docker-compose.yml

# Download the example .env file
curl -O https://raw.githubusercontent.com/knitli/codeweaver-mcp/main/.env.example
cp .env.example .env

# Optional: Download and run the setup validator
curl -O https://raw.githubusercontent.com/knitli/codeweaver-mcp/main/scripts/docker/validate-setup.sh
chmod +x validate-setup.sh
./validate-setup.sh
```

Or if you've cloned the repository:
```bash
git clone https://github.com/knitli/codeweaver-mcp.git
cd codeweaver-mcp
cp .env.example .env

# Optional: Validate your setup
./scripts/docker/validate-setup.sh
```

### 2. Configure Your Environment

Edit the `.env` file with your settings:

```bash
# Required: Your VoyageAI API key
VOYAGE_API_KEY=your-actual-api-key-here

# Path to your codebase (relative to docker-compose.yml)
PROJECT_PATH=/path/to/your/codebase

# Optional: Customize ports if needed
CODEWEAVER_PORT=9328
QDRANT_PORT=6333
```

### 3. Start the Services

```bash
# Start both CodeWeaver and Qdrant
docker compose up -d

# View logs
docker compose logs -f

# Check service health
curl http://localhost:9328/health/
```

### 4. Use CodeWeaver

Once the services are running:

```bash
# Search your codebase via CLI (inside container)
docker compose exec codeweaver codeweaver search "authentication logic"

# Or access via HTTP for MCP integration
curl http://localhost:9328/health/
```

### 5. Stop the Services

```bash
# Stop services (preserves data)
docker compose stop

# Stop and remove containers (preserves volumes)
docker compose down

# Stop and remove everything including indexed data
docker compose down -v
```

## Architecture

The Docker setup includes two services:

```
┌─────────────────────────────────────────────┐
│  CodeWeaver Container                        │
│  - MCP Server (port 9328)                   │
│  - Indexing Engine                           │
│  - Search API                                │
│  └──────────────────────────────────────────┤
│     Connects to ↓                            │
└─────────────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────┐
│  Qdrant Container                            │
│  - Vector Database (port 6333)              │
│  - gRPC API (port 6334)                     │
│  - Persistent Storage                        │
└─────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

#### Required

- `VOYAGE_API_KEY` - Your VoyageAI API key for embeddings and reranking

#### Project Settings

- `PROJECT_PATH` - Path to your codebase to index (default: `.`)
- `COLLECTION_NAME` - Qdrant collection name (default: `codeweaver`)

#### Service Ports

- `CODEWEAVER_PORT` - CodeWeaver server port (default: `9328`)
- `QDRANT_PORT` - Qdrant REST API port (default: `6333`)
- `QDRANT_GRPC_PORT` - Qdrant gRPC port (default: `6334`)

#### Provider Configuration

##### Embedding Provider
- `EMBEDDING_PROVIDER` - Provider name (default: `voyage`)
- `EMBEDDING_MODEL` - Model name (default: `voyage-code-3`)

Supported providers: `voyage`, `openai`, `cohere`, `fastembed`, `sentence-transformers`

##### Sparse Embedding Provider
- `SPARSE_EMBEDDING_PROVIDER` - Provider name (default: `fastembed`)
- `SPARSE_EMBEDDING_MODEL` - Model name (default: `prithivida/Splade_PP_en_v1`)

Note: FastEmbed runs locally, no API key needed.

##### Reranking Provider
- `RERANKING_PROVIDER` - Provider name (default: `voyage`)
- `RERANKING_MODEL` - Model name (default: `voyage-rerank-2.5`)

#### Operational Settings

- `ENABLE_TELEMETRY` - Enable usage analytics (default: `false`)
- `LOG_LEVEL` - Logging verbosity (default: `INFO`)
- `MAX_CHUNK_SIZE` - Max tokens per chunk (default: `800`)
- `TOKEN_LIMIT` - Max response tokens (default: `10000`)

### Using Alternative Providers

#### OpenAI Embeddings

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_API_KEY=your-openai-key
```

#### Cohere Embeddings

```env
EMBEDDING_PROVIDER=cohere
EMBEDDING_MODEL=embed-english-v3.0
COHERE_API_KEY=your-cohere-key
```

#### Local-Only Setup (No API Keys)

```env
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
SPARSE_EMBEDDING_PROVIDER=fastembed
SPARSE_EMBEDDING_MODEL=prithivida/Splade_PP_en_v1
RERANKING_PROVIDER=fastembed
RERANKING_MODEL=BAAI/bge-reranker-base
```

Note: Local models have lower accuracy but require no API keys.

## Volume Mounts

### Persistent Volumes

The setup creates three Docker volumes:

1. **qdrant_storage** - Vector database data
2. **codeweaver_data** - CodeWeaver application data
3. **codeweaver_cache** - Indexing cache and temporary files

### Mounted Directories

1. **Project Source** - Your codebase (read-only)
   ```yaml
   volumes:
     - ${PROJECT_PATH}:/workspace:ro
   ```

2. **Configuration** (optional) - Custom config file
   ```yaml
   volumes:
     - ./codeweaver.toml:/app/config/codeweaver.toml:ro
   ```

## Custom Configuration File

If you prefer a TOML configuration file over environment variables:

1. Create `codeweaver.toml`:
   ```toml
   project_name = "my-project"
   project_path = "/workspace"
   token_limit = 10000
   max_chunk_size = 800
   
   [provider.embedding]
   provider = "voyage"
   model_settings = { model = "voyage-code-3" }
   
   [provider.vector_store]
   provider = "qdrant"
   provider_settings = { 
     url = "http://qdrant:6333",
     collection_name = "my-collection"
   }
   ```

2. Update docker-compose.yml:
   ```yaml
   volumes:
     - ./codeweaver.toml:/app/config/codeweaver.toml:ro
   ```

3. Set the config path in the command:
   ```yaml
   command: ["codeweaver", "server", "--config", "/app/config/codeweaver.toml"]
   ```

## Building the Image Locally

If you want to build the Docker image yourself:

```bash
# From the repository root
docker build -t codeweaver:local .

# Test the build
docker run --rm codeweaver:local codeweaver --version

# Update docker-compose.yml to use local image
# Change: image: knitli/codeweaver:latest
# To:     image: codeweaver:local
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
docker compose logs qdrant
docker compose logs codeweaver
```

### Qdrant Connection Errors

**Verify Qdrant is healthy:**
```bash
curl http://localhost:6333/health
```

**Check network connectivity:**
```bash
docker compose exec codeweaver ping qdrant
```

### Indexing Takes Too Long

**Check resource allocation:**
```yaml
# In docker-compose.yml, increase memory:
deploy:
  resources:
    limits:
      memory: 8G
```

**Monitor progress:**
```bash
curl http://localhost:9328/health/ | jq '.indexing'
```

### API Key Issues

**Verify environment variable is set:**
```bash
docker compose exec codeweaver env | grep VOYAGE_API_KEY
```

**Test API key manually:**
```bash
curl -H "Authorization: Bearer $VOYAGE_API_KEY" \
  https://api.voyageai.com/v1/models
```

### Out of Memory Errors

**Reduce chunk size and batch size:**
```env
MAX_CHUNK_SIZE=500
TOKEN_LIMIT=5000
```

**Increase Docker memory limit:**
```bash
# Update Docker Desktop settings or:
docker compose down
# Edit docker-compose.yml memory limits
docker compose up -d
```

## Advanced Usage

### Multiple Projects

Run separate instances for different projects:

```bash
# Project 1
docker compose -f docker-compose.project1.yml up -d

# Project 2  
docker compose -f docker-compose.project2.yml up -d
```

Each compose file should use different:
- Container names
- Ports
- Volume names
- Collection names

### Production Deployment

For production use:

1. **Use specific version tags:**
   ```yaml
   image: knitli/codeweaver:v0.1.0
   ```

2. **Enable health checks:**
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:9328/health/"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```

3. **Set resource limits:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 4G
       reservations:
         cpus: '1.0'
         memory: 2G
   ```

4. **Use secrets for API keys:**
   ```yaml
   secrets:
     - voyage_api_key
   environment:
     - VOYAGE_API_KEY_FILE=/run/secrets/voyage_api_key
   ```

5. **Enable restart policies:**
   ```yaml
   restart: unless-stopped
   ```

### Remote Qdrant

To use a remote Qdrant instance instead of the local container:

1. Remove the `qdrant` service from docker-compose.yml

2. Update environment variables:
   ```env
   CODEWEAVER_VECTOR_STORE_URL=https://your-qdrant-instance.com:6333
   # If using Qdrant Cloud, add API key:
   QDRANT_API_KEY=your-qdrant-api-key
   ```

## Performance Tuning

### Indexing Performance

- **Parallel processing:** Default is optimized, but you can adjust:
  ```env
  # Increase for more cores (uses more memory)
  CODEWEAVER_WORKERS=8
  ```

- **Batch size:** Control memory usage:
  ```env
  CODEWEAVER_BATCH_SIZE=50
  ```

### Search Performance

- **Result limits:**
  ```env
  CODEWEAVER_MAX_RESULTS=50
  ```

- **Enable caching:**
  ```env
  CODEWEAVER_ENABLE_CACHE=true
  CODEWEAVER_CACHE_TTL=3600
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
- Error counts

### Metrics Endpoint

```bash
curl http://localhost:9328/metrics
```

Provides Prometheus-compatible metrics for monitoring.

### Docker Stats

```bash
# Monitor resource usage
docker stats codeweaver-server codeweaver-qdrant
```

## Security Considerations

1. **API Keys:** Never commit `.env` files with real API keys
2. **Network:** Use internal networks for service communication
3. **User:** Container runs as non-root user (`codeweaver`)
4. **Volumes:** Use read-only mounts where possible
5. **Updates:** Regularly update to latest image versions

## Support

- **Issues:** [GitHub Issues](https://github.com/knitli/codeweaver-mcp/issues)
- **Discussions:** [GitHub Discussions](https://github.com/knitli/codeweaver-mcp/discussions)
- **Documentation:** [Main README](README.md)

## Known Limitations

- **PyPI Publishing:** CodeWeaver is in alpha; Docker images are built from source
- **Resource Usage:** Indexing large codebases (>100k files) requires significant memory
- **API Keys:** Default configuration requires VoyageAI API key (use local providers as alternative)
- **Platform Support:** Currently tested on linux/amd64 and linux/arm64
- **CI/CD SSL Issues:** Building in some CI environments may encounter SSL certificate issues. Use pre-built images from Docker Hub as a workaround. See [DOCKER_BUILD_NOTES.md](DOCKER_BUILD_NOTES.md) for details.

## See Also

- [Main README](README.md) - Project overview and features
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [API Documentation](docs/) - Detailed API reference
