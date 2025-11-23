# MCP Registry Submission Guide

This document explains how CodeWeaver is configured for submission to the [Model Context Protocol (MCP) Registry](https://registry.modelcontextprotocol.io) and other distribution channels.

## Overview

CodeWeaver is published to the MCP Registry to enable easy discovery and installation by developers using MCP-compatible AI agents and tools. The registry acts as a centralized directory of MCP servers, similar to how package registries work for software libraries.

## Files

### `server.json`

The `server.json` file in the repository root is the metadata descriptor for MCP Registry submission. It follows the [MCP Server Schema 2025-09-16](https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json) specification.

**Key sections:**

- **Metadata**: Name, description, version, repository URL
- **Packages**: Multiple distribution methods
  - **PyPI**: Python package distribution with stdio transport
  - **Docker (OCI)**: Container-based deployment with runtime arguments
- **Arguments**: Command-line arguments for server configuration
- **Environment Variables**: Configuration via environment variables (including API keys)
- **Capabilities**: Extended metadata describing supported features

### `tools.json`

The `tools.json` file describes the MCP tools exposed by CodeWeaver. It follows the [MCP Tools Schema 2025-09-16](https://static.modelcontextprotocol.io/schemas/2025-09-16/tools.schema.json) specification.

**Contents:**
- **find_code tool**: Complete schema for the primary semantic search tool
  - Input parameters with validation
  - Output schema with result structure
  - Usage examples
  - Tool annotations (read-only, idempotent)

### `Dockerfile`

The Dockerfile includes the required MCP registry label for Docker image validation:

```dockerfile
LABEL io.modelcontextprotocol.server-name="io.github.knitli/codeweaver"
```

This label enables the MCP registry to verify ownership and link the Docker image to the server metadata.

### GitHub Actions Workflows

#### `mcp-registry-submit.yml`

Automatically submits CodeWeaver to the MCP Registry when a new release is published.

**Trigger**: Release publication on GitHub

**Process:**
1. Extracts version from release tag
2. Updates `server.json` with release version
3. Validates JSON format and required fields
4. Waits for PyPI package availability (up to 30 minutes)
5. Installs `mcp-publisher` CLI tool
6. Validates against MCP schema
7. Submits to registry via API

**Requirements:**
- Package must be published to PyPI first
- Release tag should match package version (e.g., `v0.1.0`)
- `GITHUB_TOKEN` is used for authentication

#### `mcp-registry-validate.yml`

Validates `server.json` configuration on pull requests and pushes.

**Trigger**: 
- PRs modifying `server.json`
- Pushes to `main` or `develop` branches
- Manual workflow dispatch

**Checks:**
- JSON syntax validity
- Required fields presence and format
- Namespace format (reverse-DNS)
- Version format (no ranges/wildcards)
- Package configuration completeness
- Argument naming conventions
- PyPI package existence

## Submission Requirements

### Prerequisites

Before CodeWeaver can be submitted to the MCP Registry:

#### For PyPI Package:
1. **PyPI Publication**: Package must exist on PyPI at the specified version
2. **README Metadata**: PyPI package must include `mcp-name: codeweaver` in README or package description
3. **Version Alignment**: Versions in `server.json`, `pyproject.toml`, and PyPI must match

#### For Docker Image:
1. **Docker Hub Publication**: Image must be pushed to Docker Hub at `knitli/codeweaver`
2. **MCP Label**: Dockerfile must include `LABEL io.modelcontextprotocol.server-name="io.github.knitli/codeweaver"`
3. **Version Tags**: Docker images must be tagged with version numbers matching `server.json`
4. **Health Check**: Container must expose health endpoint at `/health/`

#### General:
1. **Namespace Ownership**: GitHub authentication proves ownership of `io.github.knitli` namespace
2. **Version Consistency**: All package versions must match across PyPI, Docker, and `server.json`

### Version Format

The registry requires **pinned versions** (no ranges or wildcards):

✅ Valid:
- `0.1.0` (semantic version)
- `0.1.0-alpha.1` (pre-release)
- `0.1.0-rc778` (release candidate)

❌ Invalid:
- `^0.1.0` (caret range)
- `~0.1.0` (tilde range)
- `>=0.1.0` (comparison)
- `latest` (keyword)
- `0.1.*` (wildcard)

### Namespace Format

CodeWeaver uses the GitHub-based namespace: `io.github.knitli/codeweaver`

Format: `io.github.{username}/{server-name}`

This requires GitHub OAuth authentication but allows flexible hosting for remote servers.

## Manual Submission

If automated submission fails, you can submit manually:

### Using mcp-publisher CLI

```bash
# Install mcp-publisher
curl -L "https://github.com/modelcontextprotocol/registry/releases/download/v1.0.0/mcp-publisher_1.0.0_linux_amd64.tar.gz" \
  -o mcp-publisher.tar.gz

# TODO: Verify checksum when official checksums are published by registry maintainers
# Example: sha256sum -c mcp-publisher.tar.gz.sha256

tar xzf mcp-publisher.tar.gz
sudo mv mcp-publisher /usr/local/bin/

# Initialize (creates server.json template)
mcp-publisher init

# Validate configuration
mcp-publisher validate server.json

# Submit to registry
mcp-publisher submit server.json
```

**Security Note**: The mcp-publisher binary is downloaded from the official MCP registry repository. When checksum files become available, verify downloads before installation.

### Using Web Interface

Visit [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) and follow the submission process:

1. Sign in with GitHub
2. Click "Submit Server"
3. Upload `server.json` or provide repository URL
4. Verify ownership
5. Submit for publication

### Using API

```bash
# Submit via REST API
curl -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @server.json \
  https://registry.modelcontextprotocol.io/v0/servers
```

## Configuration Details

### Package Configuration

CodeWeaver supports multiple deployment methods:

#### PyPI Package

Distributed via PyPI and runs locally using stdio transport:

```json
{
  "registryType": "pypi",
  "identifier": "codeweaver",
  "version": "0.0.1rc778",
  "runtimeHint": "uvx",
  "transport": {
    "type": "stdio"
  }
}
```

**Runtime Hint**: `uvx` indicates the recommended execution method (uv's package runner)

**Transport**: `stdio` means the server communicates via standard input/output streams

#### Docker (OCI) Container

Distributed via Docker Hub as a containerized deployment:

```json
{
  "registryType": "oci",
  "identifier": "knitli/codeweaver",
  "version": "0.0.1rc778",
  "runtimeHint": "docker",
  "transport": {
    "type": "stdio"
  }
}
```

**Runtime Hint**: `docker` indicates container execution

**Runtime Arguments**: The Docker package includes comprehensive runtime arguments for:
- Volume mounting (`-v {workspace}:/workspace:ro`)
- Environment variables (`-e VOYAGE_API_KEY={voyage_api_key}`)
- Port mapping (`-p {host_port}:9328`)
- Network configuration (`--network {network}`)

**Example Docker usage:**

```bash
docker run --rm \
  -v /path/to/your/code:/workspace:ro \
  -e VOYAGE_API_KEY=your_key \
  -e CODEWEAVER_REPO_PATH=/workspace \
  -p 9328:9328 \
  knitli/codeweaver:latest
```

### Command-Line Arguments

Users can configure CodeWeaver via command-line arguments:

- `--repo-path`: Repository to index and search
- `--config`: Path to TOML configuration file
- `--host`: Server host address (default: 127.0.0.1)
- `--port`: Server port (default: 9328)
- `--log-level`: Logging verbosity (debug/info/warning/error/critical)

### Environment Variables

Configuration can also be provided via environment variables:

**Repository Configuration:**
- `CODEWEAVER_REPO_PATH`: Repository path
- `CODEWEAVER_CONFIG`: Config file path

**Provider Selection:**
- `CODEWEAVER_EMBEDDING_PROVIDER`: Provider name (voyage/cohere/openai/etc.)
- `CODEWEAVER_EMBEDDING_MODEL`: Specific model to use
- `CODEWEAVER_VECTOR_STORE`: Vector store backend (qdrant/inmemory)

**API Keys** (marked as secret):
- `VOYAGE_API_KEY`: Voyage AI
- `COHERE_API_KEY`: Cohere
- `OPENAI_API_KEY`: OpenAI
- `MISTRAL_API_KEY`: Mistral AI
- `GOOGLE_API_KEY`: Google AI
- `HUGGINGFACE_API_KEY`: HuggingFace

**Vector Store:**
- `QDRANT_URL`: Qdrant server URL
- `QDRANT_API_KEY`: Qdrant authentication

**System:**
- `LOG_LEVEL`: Logging level
- `CODEWEAVER_TELEMETRY_ENABLED`: Enable/disable telemetry (default: true)

## Testing Before Submission

### Local Validation

```bash
# Validate JSON syntax
python -c "import json; json.load(open('server.json'))"

# Run validation workflow locally (requires act)
act -j validate -W .github/workflows/mcp-registry-validate.yml
```

### Test with MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) allows testing servers locally:

```bash
# Install inspector
npx @modelcontextprotocol/inspector

# Test CodeWeaver
uvx codeweaver --repo-path /path/to/repo
```

### Verify Package on PyPI

```bash
# Check package exists
curl https://pypi.org/pypi/codeweaver/json | jq .info.version

# Check specific version
curl https://pypi.org/pypi/codeweaver/0.1.0/json

# Verify README contains mcp-name
curl https://pypi.org/pypi/codeweaver/json | jq -r .info.description | grep -i "mcp-name"
```

## Troubleshooting

### Submission Fails: "Package not found"

**Problem**: PyPI package doesn't exist or hasn't propagated yet

**Solution**: 
- Verify package exists: `pip index versions codeweaver`
- Wait 5-10 minutes after PyPI publication for CDN propagation
- Check PyPI URL directly: https://pypi.org/project/codeweaver/

### Validation Error: "Invalid namespace format"

**Problem**: Name doesn't follow `namespace/server-name` pattern

**Solution**: Ensure `name` field is exactly `io.github.knitli/codeweaver`

### Validation Error: "Version contains range"

**Problem**: Version includes `^`, `~`, `>=`, etc.

**Solution**: Use exact version: `0.1.0` not `^0.1.0`

### Validation Error: "stdio transport cannot have URL"

**Problem**: Transport configuration includes URL field for stdio

**Solution**: Remove `url` field from transport object for stdio type

### Authentication Fails

**Problem**: GitHub authentication rejected

**Solution**:
- Ensure you have push access to `knitli/codeweaver` repository
- Re-authenticate with `mcp-publisher`: `mcp-publisher auth`
- Verify token has required scopes (repo access)

## Registry Update Process

### For New Releases

1. **Create Release**: Tag and publish release on GitHub (e.g., `v0.2.0`)
2. **PyPI Publication**: Automated via `release.yml` workflow
3. **Wait for Propagation**: 5-10 minutes for PyPI availability
4. **Automatic Submission**: `mcp-registry-submit.yml` triggers automatically
5. **Verify Listing**: Check https://registry.modelcontextprotocol.io/servers/io.github.knitli/codeweaver

### For Metadata Updates

If only `server.json` needs updating (description, arguments, etc.):

1. Update `server.json` in repository
2. Create PR with changes
3. Validation runs automatically
4. After merge, manually trigger submission:
   - Go to Actions → "Submit to MCP Registry"
   - Click "Run workflow"
   - Specify version to update
   - Submit

## Additional Resources

- [MCP Registry Documentation](https://github.com/modelcontextprotocol/registry)
- [Server Schema Specification](https://modelcontextprotocol.io/specification/)
- [Publishing Guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/guides/publishing/publish-server.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification/)
- [Registry API Documentation](https://registry.modelcontextprotocol.io/v0/swagger)

## Other Distribution Channels

Beyond the MCP Registry, CodeWeaver can be submitted to:

### Alpha-Friendly Directories (Submit Immediately)

1. **awesome-mcp-servers** (GitHub)
2. **mcp-get package manager** 
3. **AI tool marketplaces** (Phind, Perplexity)
4. **Developer communities** (Hacker News, Reddit)

### Production-Ready Directories (Wait for Beta/Stable)

1. **Awesome lists** (awesome-python, awesome-ai-tools)
2. **Package discovery** (libraries.io, pepy.tech)
3. **Developer platforms** (Product Hunt, OpenTools)

See the full registry submission guide provided by @bashandbone for complete details on all submission opportunities.
