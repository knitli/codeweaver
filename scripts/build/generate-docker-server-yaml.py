# sourcery skip: no-complex-if-expressions
#!/usr/bin/env -S uv run -s
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ///script
# python-version = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Generate server.yaml for Docker MCP Registry submission.

This script creates the server.yaml configuration file needed for submitting
CodeWeaver to the Docker MCP Registry (github.com/docker/mcp-registry).

Docker will build and maintain the image with enhanced security features including
cryptographic signatures, provenance tracking, and SBOMs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from codeweaver import __version__
from codeweaver.config.envs import environment_variables


def get_git_commit() -> str:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def generate_server_yaml() -> dict:
    """Generate the server.yaml configuration for Docker MCP Registry."""
    # Get critical environment variables (secrets)
    env_vars = environment_variables()

    # Separate secrets from regular env vars
    secrets = []
    regular_env = []
    parameters_props = {}
    parameters_required = []

    # Key environment variables that should be exposed
    important_vars = [
        "CODEWEAVER_PROJECT_PATH",
        "CODEWEAVER_EMBEDDING_PROVIDER",
        "CODEWEAVER_EMBEDDING_MODEL",
        "CODEWEAVER_EMBEDDING_API_KEY",
        "CODEWEAVER_VECTOR_STORE_PROVIDER",
        "CODEWEAVER_VECTOR_STORE_URL",
        "CODEWEAVER_VECTOR_STORE_API_KEY",
        "CODEWEAVER_RERANKING_PROVIDER",
        "CODEWEAVER_RERANKING_MODEL",
        "CODEWEAVER_RERANKING_API_KEY",
    ]

    for var_name in important_vars:
        if var_name not in env_vars:
            continue

        var_info = env_vars[var_name]
        env_name = var_info.env

        # Extract parameter name from env var (e.g., CODEWEAVER_EMBEDDING_PROVIDER -> embedding_provider)
        param_name = env_name.replace("CODEWEAVER_", "").lower()

        if var_info.is_secret:
            # Add to secrets
            secrets.append({
                "name": f"codeweaver.{param_name}",
                "env": env_name,
                "example": f"<{env_name}>",
            })
            # Secrets also get added to parameters as required strings
            parameters_props[param_name] = {"type": "string"}
        else:
            # Add to regular environment variables
            example = var_info.default or f"<{env_name}>"
            regular_env.append({
                "name": env_name,
                "example": example,
                "value": f"{{{{codeweaver.{param_name}}}}}",
            })
            # Add to parameters
            param_type = "string"
            if var_info.fmt and "NUMBER" in str(var_info.fmt):
                param_type = "integer"
            elif var_info.fmt and "BOOLEAN" in str(var_info.fmt):
                param_type = "boolean"

            param_def = {"type": param_type}
            if var_info.choices:
                param_def["enum"] = sorted(var_info.choices)
            if var_info.default:
                param_def["default"] = var_info.default

            parameters_props[param_name] = param_def

        if var_info.is_required:
            parameters_required.append(param_name)
    return {
        "name": "codeweaver",
        "image": "mcp/codeweaver",  # Docker will build and publish to mcp/ namespace
        "type": "server",
        "meta": {
            "category": "developer-tools",
            "tags": [
                "code-search",
                "semantic-search",
                "embeddings",
                "ai",
                "developer-tools",
                "ast",
                "hybrid-search",
                "rag",
            ],
        },
        "about": {
            "title": "CodeWeaver - Semantic Code Search",
            "description": "Semantic code search built for AI agents. Hybrid AST-aware embeddings for 170+ languages with intelligent chunking, intent detection, and multi-provider support.",
            "icon": "https://avatars.githubusercontent.com/u/182288589?s=200&v=4",
        },
        "source": {
            "project": "https://github.com/knitli/codeweaver",
            "commit": get_git_commit(),
        },
        "config": {
            "description": "Configure CodeWeaver with your project path, embedding provider, and optional vector store settings. Supports 17+ embedding providers and 170+ programming languages.",
            "secrets": secrets or None,
            "env": regular_env or None,
            "parameters": {
                "type": "object",
                "properties": parameters_props,
                "required": parameters_required or None,
            } if parameters_props else None,
        },
    }


def save_server_yaml(config: dict | None = None) -> Path:
    """Save the server.yaml configuration."""
    if config is None:
        config = generate_server_yaml()

    file_path = Path(__file__).parent.parent.parent / "server.yaml"

    # Clean None values for cleaner YAML output
    def clean_dict(d: dict) -> dict:
        """Recursively remove None values from dict."""
        return {
            k: clean_dict(v) if isinstance(v, dict) else v
            for k, v in d.items()
            if v is not None
        }

    cleaned_config = clean_dict(config)

    # Write with proper YAML formatting
    with file_path.open("w") as f:
        yaml.dump(
            cleaned_config,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    return file_path


if __name__ == "__main__":
    import sys

    print("🔄 Generating server.yaml for Docker MCP Registry...")
    try:
        config = generate_server_yaml()
        file_path = save_server_yaml(config)

        print(f"✅ Successfully generated server.yaml at {file_path}")
        print(f"📦 Version: {__version__}")
        print(f"📝 Commit: {config['source']['commit'][:8]}")
        print(f"🏷️  Category: {config['meta']['category']}")
        print(f"🔖 Tags: {', '.join(config['meta']['tags'])}")
        print(f"\n📋 Next steps:")
        print("   1. Review server.yaml and adjust descriptions if needed")
        print("   2. Ensure Dockerfile is at repository root")
        print("   3. Fork github.com/docker/mcp-registry")
        print("   4. Add server.yaml to servers/codeweaver/")
        print("   5. Submit PR to Docker MCP Registry")

    except Exception as e:
        print(f"❌ Error generating server.yaml: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
