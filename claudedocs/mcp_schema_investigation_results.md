<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# MCP Schema URL Investigation Results

**Investigation Date**: 2025-11-24
**Subject**: Validity of MCP schema URLs, specifically tools.schema.json

---

## Executive Summary

**Critical Finding**: `tools.schema.json` **NEVER existed** in the MCP specification. Only `server.schema.json` is valid for the static hosting URL.

---

## HTTP Status Code Results

### Primary Investigation: tools.schema.json
```
❌ https://static.modelcontextprotocol.io/schemas/2025-09-16/tools.schema.json
   Status: 404 NOT FOUND

✅ https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json
   Status: 200 OK

✅ https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json
   Status: 200 OK
```

### Comprehensive Version Testing

| Version | schema.json | server.schema.json | tools.schema.json |
|---------|-------------|-------------------|------------------|
| 2024-11-05 | ❌ 404 | ❌ 404 | ❌ 404 |
| 2025-03-26 | ❌ 404 | ❌ 404 | ❌ 404 |
| 2025-06-18 | ❌ 404 | ❌ 404 | ❌ 404 |
| **2025-09-16** | ❌ 404 | ✅ **200** | ❌ 404 |
| **2025-09-29** | ❌ 404 | ✅ **200** | ❌ 404 |

---

## Available Schemas on Static Server

### ✅ Valid URLs (HTTP 200)
```
https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json
https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json
```

### ❌ Invalid URLs (HTTP 404)
- All `tools.schema.json` URLs (all versions)
- All `schema.json` URLs (all versions)
- Root directory listing (`/schemas/`)
- Versions before 2025-09-16

---

## GitHub Repository Structure

### Specification Repository
**URL**: https://github.com/modelcontextprotocol/specification

**Schema Versions in Repository** (as of 2025-11-24):
```
schema/
├── 2024-11-05/
│   ├── schema.json
│   └── schema.ts
├── 2025-03-26/
│   ├── schema.json
│   └── schema.ts
├── 2025-06-18/
│   ├── schema.json
│   └── schema.ts
└── draft/
    ├── schema.json
    └── schema.ts
```

**Key Observations**:
1. ❌ No `2025-09-16` directory exists in GitHub
2. ❌ No `2025-09-29` directory exists in GitHub
3. ❌ No `tools.schema.json` in ANY version directory
4. ❌ No `server.schema.json` in ANY version directory
5. ✅ Only `schema.json` and `schema.ts` exist in repository

---

## Schema Naming Discrepancy Analysis

### GitHub Repository
- **File Name**: `schema.json`
- **Purpose**: Defines the entire MCP protocol (JSON-RPC 2.0 based)
- **Versions**: 2024-11-05, 2025-03-26, 2025-06-18, draft

### Static Hosting (CDN)
- **File Name**: `server.schema.json`
- **Purpose**: Defines MCP server metadata format
- **Versions**: 2025-09-16, 2025-09-29 (not in GitHub!)
- **URL Pattern**: `https://static.modelcontextprotocol.io/schemas/{version}/server.schema.json`

### Conclusions
1. **Different Schemas**: GitHub's `schema.json` (protocol) ≠ CDN's `server.schema.json` (server metadata)
2. **Version Mismatch**: CDN versions (2025-09-16, 2025-09-29) don't exist in GitHub
3. **Separate Purpose**:
   - `schema.json` = MCP protocol specification
   - `server.schema.json` = MCP server registry metadata format

---

## What is server.schema.json?

### Purpose
Defines metadata format for MCP server registry entries (not the protocol itself).

### Schema Structure
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json",
  "title": "MCP Server Detail",
  "$ref": "#/definitions/ServerDetail"
}
```

### Key Properties Defined
- **Server**: name, description, version (reverse-DNS format)
- **Repository**: URL, source, ID, subfolder (for transparency)
- **Package**: registry type (npm, pypi, oci, nuget, mcpb)
- **Transport**: stdio, streamable-http, SSE
- **Arguments**: Positional and named command-line arguments
- **Variables**: Environment variable substitution

### Use Case
Used by MCP server registries (like the servers repository) to catalog available servers with installation metadata.

---

## Official MCP Schema Documentation

### Documentation URLs
- **Main Site**: https://modelcontextprotocol.io
- **Specification**: https://github.com/modelcontextprotocol/specification
- **Servers Registry**: https://github.com/modelcontextprotocol/servers

### Latest Schema Version
**GitHub Repository**: 2025-06-18 (as of investigation date)
**CDN Hosting**: 2025-09-29 (server.schema.json only)

### Schema Evolution
- **2024-11-05**: Initial schema version
- **2025-03-26**: Intermediate update
- **2025-06-18**: Latest in GitHub repository
- **2025-09-16**: First CDN-hosted server.schema.json
- **2025-09-29**: Latest CDN-hosted server.schema.json

---

## Tools Specification in MCP

### Where are "Tools" Defined?

**In the Protocol Schema** (`schema.json`):
```json
Tools are defined within the main protocol schema under:
- tools/list: Request to list available tools
- tools/call: Request to invoke a tool
- Tool definitions: Inline within protocol specification
```

**Not as Separate Schema**:
- ❌ There is NO separate `tools.schema.json`
- ❌ There was NEVER a `tools.schema.json` in any version
- ✅ Tools are part of the core protocol schema

### MCP Protocol Capabilities
The main `schema.json` defines:
1. **Resources** - Servers expose readable content
2. **Prompts** - Template and prompt management
3. **Tools** - Callable functions (defined inline)
4. **Sampling** - LLM invocation

---

## Commit History Analysis

### Recent Schema Changes (Nov 2025)
- Task-related enhancements (execution.task → execution.taskSupport)
- Elicitation backwards compatibility
- Automated schema regeneration (`npm run generate:schema`)

### Key Finding
❌ **No evidence of `tools.schema.json` in commit history**

The schema appears to use automated generation from TypeScript definitions, making the TypeScript source (`schema.ts`) the source of truth.

---

## Related Repositories

### MCP Servers Repository
**URL**: https://github.com/modelcontextprotocol/servers

**Purpose**: Reference implementations and third-party server catalog

**Reference Servers**:
- Everything (prompts, resources, tools)
- Fetch (web content)
- Filesystem (secure file operations)
- Git (repository tools)
- Memory (knowledge graph)
- Sequential Thinking (problem-solving)
- Time (timezone conversion)

**Integration Partners**: 100+ third-party integrations (AWS, Azure, Atlassian, Auth0, etc.)

---

## Conclusions

### ✅ Valid Schema URLs
```
https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json
https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json
```

### ❌ Invalid Schema URLs
```
https://static.modelcontextprotocol.io/schemas/{any-version}/tools.schema.json
https://static.modelcontextprotocol.io/schemas/{any-version}/schema.json
https://static.modelcontextprotocol.io/schemas/ (directory listing)
```

### 🎯 Recommendations

1. **For Protocol Validation**: Use GitHub repository schemas
   ```
   https://raw.githubusercontent.com/modelcontextprotocol/specification/main/schema/2025-06-18/schema.json
   ```

2. **For Server Registry Metadata**: Use CDN-hosted server.schema.json
   ```
   https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json
   ```

3. **For Tool Definitions**: Reference the main protocol schema, not a separate tools schema

4. **Schema Version Selection**:
   - Use latest version: 2025-09-29 for server metadata
   - Use 2025-06-18 from GitHub for protocol specification
   - Expect automated schema updates (regeneration via npm scripts)

### 🔍 Investigation Methodology
- HTTP HEAD requests to test URL validity
- WebFetch for content analysis
- GitHub repository structure analysis
- Commit history review
- Documentation crawling
- Systematic version testing

---

## Appendix: HTTP Headers

### tools.schema.json (404)
```
HTTP/2 404
server: GitHub.com
content-type: text/html; charset=utf-8
```

### server.schema.json (200)
```
HTTP/2 200
server: GitHub.com
content-type: application/json; charset=utf-8
last-modified: Tue, 21 Oct 2025 19:10:53 GMT
cache-control: max-age=600
```

### Schema ID Fields
```json
2025-09-16: "https://static.modelcontextprotocol.io/schemas/2025-09-16/server.schema.json"
2025-09-29: "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json"
```

---

**Investigation Complete**: 2025-11-24
