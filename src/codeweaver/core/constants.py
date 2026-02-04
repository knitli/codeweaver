# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Constants used throughout the CodeWeaver codebase."""

from __future__ import annotations

from textwrap import dedent


# ===========================================================================
# *                           Find_Code and CodeWeaver Constants
# ===========================================================================


CODEWEAVER_DESCRIPTION = "CodeWeaver advanced code search and understanding server."

CODEWEAVER_ICON = (
    "https://raw.githubusercontent.com/knitli/codeweaver/main/docs/assets/codeweaver-primary.svg"
)

FIND_CODE_TITLE = "CodeWeaver find_code Tool"

FIND_CODE_DESCRIPTION = dedent("""
        CodeWeaver's `find_code` tool is an advanced code search function that leverages context and task-aware semantic search to identify and retrieve relevant code snippets from a codebase using natural language queries. `find_code` uses advanced sparse and dense embedding models, and reranking models to provide the best possible results, which are continuously updated. `find_code` is purpose-built to assist AI coding agents with getting exactly the information they need for any coding or repository task.

        # Using `find_code`

        **One Required Argument:**
            - query: Provide a natural language query describing what you are looking for.

        **Optional Arguments:**
            - intent: Specify an intent to help narrow down the search results. Choose from: `understand`, `implement`, `debug`, `optimize`, `test`, `configure`, `document`.
            - token_limit: Set a maximum number of tokens to return (default is 30000).
            - focus_languages: Filter results by programming language(s). A list of languages using their common names (like "python", "javascript", etc.). CodeWeaver supports over 166 programming languages.

        RETURNS:
            A detailed summary of ranked matches and metadata. Including:
            - matches: A list of code or documentation snippets *in ranked order by relevance* to the query. Each match includes:
                - content: An object representing the code or documentation snippet or its syntax tree representation. These objects carry substantial metadata about the snippet depending on how it was retrieved. Metadata may include: language, size, importance, symbol, semantic role and relationships to other code snippets and symbols.
                - file: The file and associated metadata where the snippet was found.
                - span: A span object indicating the exact location of the snippet within the file.
                - relevance_score: A numerical score indicating how relevant the snippet is to the query, normalized between 0 and 1. If all results have the same score, this is because they are ranked using reciprocal rank fusion and their scores are not directly comparable.
        """)

FIND_CODE_INSTRUCTION = ""

USER_AGENT_TAGS = {"user", "external"}

CONTEXT_AGENT_TAGS = {"context", "internal", "data"}

MCP_ENDPOINT = "/mcp"

DEFAULT_DENSE_WEIGHT = 0.65

DEFAULT_SPARSE_WEIGHT = 0.35


# ===========================================================================
# *                           TIME Constants
# ===========================================================================

ONE_SECOND = 1
"""One second in seconds."""

ONE_MINUTE = 60 * ONE_SECOND
"""One minute in seconds."""

FIVE_MINUTES = 5 * ONE_MINUTE
"""Five minutes in seconds."""

TEN_MINUTES = 10 * ONE_MINUTE
"""Ten minutes in seconds."""

ONE_HOUR = 60 * ONE_MINUTE
"""One hour in seconds."""

ONE_DAY = 24 * ONE_HOUR
"""One day in seconds."""

ONE_MILLISECOND_IN_MICROSECONDS = 1000
"""One millisecond in microseconds."""

# ===========================================================================
# *                            SIZE Constants
# ===========================================================================

ONE_KILOBYTE = 1024
"""One kilobyte in bytes."""

ONE_MEGABYTE = 1024 * ONE_KILOBYTE
"""One megabyte in bytes."""

ONE_HUNDRED_MEGABYTES = 100 * ONE_MEGABYTE
"""One hundred megabytes in bytes."""

ONE_GIGABYTE = 1024 * ONE_MEGABYTE
"""One gigabyte in bytes."""

# ===========================================================================
# *                            Other Magic Number Constants
# ===========================================================================

ONE: int = 1
"""One (1)."""

ONE_LINE = 1
"""One line (1)."""

ZERO: int = 0
"""Zero (0). Or, Zed for our British friends."""

ZERO_POINT_ZERO: float = 0.0
"""Floating point zero (0.0)."""

ONE_POINT_ZERO: float = 1.0
"""Floating point one (1.0)."""

ONE_HUNDRED: int = 100
"""One hundred (100)."""


# ===========================================================================
# *                            TEXT Constants
# ===========================================================================

ELLIPSIS = "..."
"""Ellipsis string."""

POSIX_NEWLINE = "\n"
"""Newline character."""

WINDOWS_NEWLINE = "\r\n"
"""Windows newline character."""

SPACE = " "
"""Space character."""

TAB = "\t"
"""Tab character."""

WHITESPACES = {
    SPACE,
    TAB,
    POSIX_NEWLINE,
    "\r",
    "\v",
    "\f",
    "\u00a0",
    "\u1680",
    "\u2000",
    "\u2001",
    WINDOWS_NEWLINE,
}
"""Set of whitespace characters."""

# ===========================================================================

SHEBANG = "#!"
"""Shebang string."""

PYTHON_SHEBANG = f"{SHEBANG}/usr/bin/env python3"
"""Python shebang string."""

# ===========================================================================
# *                            Default Settings Constants
# ===========================================================================

BASE_RETRYABLE_EXCEPTIONS = {ConnectionError, TimeoutError, OSError}

# ======== Backup Defaults

BACKUP_EMBEDDING_MODEL_PRIMARY = "minishlab/potion-base-8M"
"""Primary backup embedding model. If Sentence Transformers is available, we use 'potion-base-8M', which is a static vector model -- making it very lightweight and fast at the expense of some accuracy and semantic richness."""

BACKUP_EMBEDDING_MODEL_FALLBACK = "jinaai/jina-embeddings-v2-small-en"
"""Fallback backup embedding model. If Sentence Transformers is not available, we use 'jina-embeddings-v2-small-en' with FastEmbed. This is a traditional embedding model, but still very small and efficient."""

BACKUP_RERANKING_MODEL = "jinaai/jina-reranker-v1-tiny-en"
"""Backup reranking model used when the primary model is unavailable. This is a very small and fast model, and has the added bonus of being available with both Sentence Transformers and FastEmbed, and a large context window (8096 tokens). Its context window is larger than our maximum chunk size (~1000 tokens), so we can safely use it for reranking without worrying about truncation or re-chunking."""

# ======== Logging Defaults

LOGGERS_TO_SUPPRESS = {
    "anthropic",
    "aws",
    "azure",
    "boto3",
    "botocore",
    "cohere",
    "ddgs",
    "fastapi",
    "fastmcp",
    "fastmcp.server",
    "google",
    "google.api_core",
    "google.genai",
    "groq",
    "hf",
    "httpcore",
    "httpx",
    "httpx._client",
    "huggingface_hub",
    "mcp",
    "mcp.server",
    "mistral",
    "ollama",
    "openai",
    "qdrant_client",
    "sentence_transformers",
    "tavily",
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "voyage",
}

DEFAULT_LOG_LEVEL = 30
"""Default logging level (`logging.WARNING`)."""

DEFAULT_RICH_HANDLER_OPTIONS = {
    "show_time": True,
    "show_level": True,
    "show_path": True,
    "rich_tracebacks": False,
}
"""Default options for Rich logging handler."""

# ======== Language Model Defaults

DEFAULT_MAX_TOKENS = 20_000
"""Default maximum number of tokens for language models."""

DEFAULT_AGENT_TEMPERATURE = 0.2
"""Default temperature setting for language models."""

DEFAULT_AGENT_TOP_P = 1.0
"""Default top-p setting for language models."""

# ======= HTTPX Defaults

DEFAULT_HTTPX_MAX_CONNECTIONS = 100
"""Default maximum number of HTTPX connections."""

DEFAULT_HTTPX_MAX_KEEPALIVE_CONNECTIONS = 20
"""Default maximum number of HTTPX keep-alive connections."""

DEFAULT_HTTPX_KEEPALIVE_EXPIRY = 5 * ONE_POINT_ZERO
"""Default keep-alive expiry time in seconds for HTTPX connections."""

# HTTP pool defaults

DEFAULT_OPEN_BREAKER_DURATION = 30 * ONE_POINT_ZERO
"""Default duration in seconds to keep the circuit breaker open."""

DEFAULT_POOL_CONNECTION_TIMEOUT = 10 * ONE_POINT_ZERO
"""Default connection timeout in seconds for HTTP pools."""

DEFAULT_POOL_READ_TIMEOUT = 60 * ONE_POINT_ZERO
"""Default read timeout in seconds for HTTP pools. This is high to account for long-running embedding requests and agent operations."""

DEFAULT_POOL_WRITE_TIMEOUT = 10 * ONE_POINT_ZERO
"""Default write timeout in seconds for HTTP pools."""

DEFAULT_POOL_ACQUIRE_TIMEOUT = 5 * ONE_POINT_ZERO
"""Default acquire timeout in seconds for HTTP pools."""

# ======== Timeout Defaults

DEFAULT_AGENT_TIMEOUT = 2 * ONE_MINUTE
"""Default timeout in seconds for agent operations."""

DEFAULT_EMBEDDING_TIMEOUT = 45 * ONE_SECOND
"""Default timeout in seconds for embedding operations."""

DEFAULT_EMBEDDING_BATCH_SIZE = 64
"""Default batch size for embedding operations."""

DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE = 32
"""Default batch size for local embedding operations."""

DEFAULT_RERANKING_TIMEOUT = 30 * ONE_SECOND
"""Default timeout in seconds for reranking operations."""

# ======== Store Defaults

DEFAULT_BLAKE_STORE_MAX_SIZE = 256 * ONE_KILOBYTE
"""Default maximum size for Blake3 hash store cache. Blake stores are used for deduping, but only contain mappings of file hashes to UUIDs. As such, they are very small."""

DEFAULT_EMBEDDING_REGISTRY_MAX_SIZE = ONE_HUNDRED_MEGABYTES
"""Default maximum size for embedding registry cache. The embedding registry is a special UUID store used for storing embeddings, and plays an important role in deduping for embedding decisions."""

DEFAULT_UUID_STORE_MAX_SIZE = 3 * ONE_MEGABYTE
"""Default maximum size for UUID store cache. UUID stores are used for caching and temporary storage, usually mapping UUIDs to results or file content from an operation."""

# ======== Retry Defaults

MAX_RETRY_ATTEMPTS = 3
"""Maximum number of retry attempts for operations."""

# ======== Vector Database Defaults

DEFAULT_HNSW_M = 24
"""Default HNSW M parameter for vector databases."""

DEFAULT_HNSW_EF_CONSTRUCTION = 130
"""Default HNSW EF construction parameter for vector databases."""

DEFAULT_HNSW_PAYLOAD_M = 120
"""Default HNSW payload M parameter for vector databases."""

DEFAULT_HNSW_FULL_SCAN_THRESHOLD = 10_000
"""Default HNSW full scan threshold for vector databases."""

DEFAULT_PERSIST_INTERVAL = 10 * ONE_MINUTE
"""Default interval in seconds for persisting vector database changes to disk."""

DEFAULT_COLLECTION_NAME_PREFIX = "codeweaver_"
"""Default prefix for vector database collection names. The full default collection name is this prefix followed by the project name and a hash of the absolute path to the project. This ensures uniqueness across different projects, even when sharing directory names. The downside is this forces reindexing if you change or move the project. A `cw migrate` command is on the roadmap to help with this."""

PRIMARY_VECTOR_NAME = "primary"
"""Default name for the primary vector in vector databases."""

PRIMARY_SPARSE_VECTOR_NAME = "sparse"

BACKUP_DENSE_VECTOR_NAME = "backup"

DEFAULT_SNAPSHOT_RETENTION_COUNT = 5
"""Default number of snapshots to retain for vector database disaster recovery."""

DEFAULT_VECTOR_STORE_MAX_RESULTS = 30
"""Default maximum number of results to return from vector store queries."""

DEFAULT_VECTOR_STORE_BATCH_SIZE = 64
"""Default batch size for vector store operations."""

# ======= Server Defaults

DEFAULT_HOST = "127.0.0.1"
"""Default host address for the server."""

DEFAULT_MANAGEMENT_PORT = 9329
"""Default management port for the server."""

DEFAULT_MCP_PORT = 9328
"""Default MCP port for the server."""

HEALTH_ENDPOINT = "/health"
"""Health check endpoint path."""

STATUS_ENDPOINT = "/status"
"""Status endpoint path."""

METRICS_ENDPOINT = "/metrics"
"""Metrics endpoint path."""

SHUTDOWN_ENDPOINT = "/shutdown"
"""Shutdown endpoint path."""

VERSION_ENDPOINT = "/version"
"""Version endpoint path."""

SETTINGS_ENDPOINT = "/settings"
"""Settings endpoint path."""

STATE_ENDPOINT = "/state"
"""State endpoint path."""

INDEXER_WINDDOWN_TIMEOUT = 7.5 * ONE_SECOND
"""Default timeout in seconds for indexer wind-down during shutdown."""

WATCHER_WINDDOWN_TIMEOUT = 2.5 * ONE_SECOND
"""Default timeout in seconds for file watcher wind-down during shutdown."""

DEFAULT_MCP_TIMEOUT = 2 * ONE_MINUTE
"""Default timeout in seconds for MCP server operations."""

DEFAULT_DAEMON_STARTUP_WAIT = 30.0
"""Default maximum wait time in seconds for the daemon to start up."""

DEFAULT_DAEMON_STARTUP_CHECK_INTERVAL = 0.5
"""Default interval to check on the daemon during start up."""

DEFAULT_SERVER_SHUTDOWN_TIMEOUT = 10.0
"""Default timeout in seconds for server shutdown operations."""

# ======= File Path Defaults

DEFAULT_USER_DIR_NAME = "codeweaver"
"""Default directory name for user-level configuration and data storage. CodeWeaver follows the XDG Base Directory Specification on Unix-like systems, and uses idiomatic equivalent directories on Windows and macOS."""

DEFAULT_CHECKPOINT_SUBPATH = f"{DEFAULT_USER_DIR_NAME}/.checkpoints"

DEFAULT_MANIFEST_SUBPATH = f"{DEFAULT_USER_DIR_NAME}/.manifests"

# ======= Semantic analysis Defaults

DEFAULT_SEMANTIC_IDENTIFICATION_CONFIDENCE_THRESHOLD = 0.75
"""Default confidence threshold for semantic identification tasks. Ranges from 0.0 to 1.0."""

# ======= Find_Code Defaults

DEFAULT_MAX_RESULTS = 10
"""Default maximum number of results to return from `find_code`."""

DEFAULT_RERANKING_MAX_RESULTS = 15
"""Default maximum number of results to consider for reranking in `find_code`."""

# ===========================================================================
# *                   MCP Middleware Defaults
# ===========================================================================

DEFAULT_MCP_MAX_RETRY_ATTEMPTS = 5
"""Default maximum number of retry attempts for MCP middleware operations."""

DEFAULT_MCP_RETRY_BASE_DELAY = ONE_POINT_ZERO
"""Default base delay in seconds for MCP middleware retry operations."""

DEFAULT_MCP_RETRY_MAX_DELAY = ONE_MINUTE * ONE_POINT_ZERO
"""Default maximum delay in seconds for MCP middleware retry operations."""

DEFAULT_MCP_RETRY_BACKOFF_MULTIPLIER = 2.0
"""Default backoff multiplier for MCP middleware retry operations."""

DEFAULT_MCP_RATE_LIMIT_MAX_REQUESTS_PER_SECOND = 75
"""Default maximum number of requests per second for MCP middleware rate limiting."""

DEFAULT_MCP_RATE_LIMIT_BURST_CAPACITY = 150
"""Default burst capacity for MCP middleware rate limiting."""

# ===========================================================================
# *                   Cost Estimates
# ===========================================================================
# *  The cloud embedding cost is based on the current flagship Voyage model
# *  Voyage-4-large at $0.12 per million tokens which is $0.000_12 per 1k.
#
# *  Cloud reranking cost is based on voyage-rerank-2.5 at
# *  $0.05 per million tokens

CLOUD_EMBEDDING_COST_PER_1K_TOKENS = 0.000_12
"""Estimated cost per 1,000 tokens for cloud embedding models."""

CLOUD_RERANKING_COST_PER_1K_TOKENS = 0.000_05
"""Estimated cost per 1,000 tokens for cloud reranking models."""

LOCAL_EMBEDDING_COST_PER_1K_TOKENS = 0.000_005
"""Estimated cost per 1,000 tokens for local embedding models.

Based on average hardware (25-70W power draw, 200-1K tokens/sec) at $0.15/kWh.
Actual costs vary 5-10x by hardware and model size but remain negligible
(roughly ~$0.001-0.015 per million tokens -- a 1/10th cent to 1.5 cents).
We assume 1/2 cent/million as a reasonable average for local embedding inference.

You can calculate a better number for your situation with:
TDP×inference_time×electricity_rate
Regardless, your cost is ~$1/year give or take 50 cents.

This number applies to dense and sparse embeddings alike since our default sparse model
is a Splade model, which is just a dense model with a different training objective.
It is much cheaper at inference, but that's not where the costs are in embedding for a code base.

We also use this same estimate for local reranking models, though in practice reranking models
are larger and more expensive to run (usually). However, reranking is a smaller portion of overall costs.
"""  # noqa: RUF001

CONTEXT_AGENT_COST_PER_1K_TOKENS = 0.0018
"""Estimated cost per 1,000 tokens for context agent operations.

The context agent is the agent *inside* CodeWeaver that responds to `find_code` queries.

The model used depends on a number of factors we don't control. When responding to
an MCP request (from your agent), we request fast, low cost, but quality models. Your client,
however, can -- and probably does -- ignore our request and choose whatever model it wants.

If responding outside of an MCP request (or if your client doesn't support MCP sampling), CodeWeaver uses whatever you configured it to use. Our current recommended default is `claude-haiku-4.5`, which currently costs $1/million tokens input and $5/million tokens output. We assume 80% of tokens are input and 20% output for a blended cost of $1.80/million or $0.0018/1k.
"""

USER_AGENT_COST_PER_1K_TOKENS = 0.0045
"""Estimated cost per 1,000 tokens for user agent operations.

The user agent is your agent that is using CodeWeaver to help with coding tasks -- the agent you interact with.

The model of course depends completely on what you choose to use, and we have no visibility on
what that is. By far the most common model used by developers today is `claude-sonnet-4.5`, though
many also use `claude-opus-4.5`. Also common currently are `gpt-5.2-codex`
and `gemini-3-pro`. Costs as of 2 Feb 2026 and usage assumptions are:
 - `claude-sonnet-4.5`: $3/million input, $6/million output - 60% (1.8/3.2)
 - `claude-opus-4.5`: $5/million input, $25/million output - 10% (0.5/2.5)
 - `gpt-5.2-codex`: $1.75/million input, $14/million output - 10% (0.175/1.4)
 - `gemini-3-pro`: $3/million input, $15/million output (varies by context length, splitting the difference evenly for this estimate) - 20% (0.6/3.0)

Again we assume 80% of tokens are input and 20% output for a blended cost and round a few cents to $4.50/million or $0.0045/1k.
"""

# ===========================================================================
# *                   Engine Constants
# ===========================================================================

DEFAULT_RECONCILIATION_SERVICE_BATCH_SIZE = 100
"""Default batch size for the reconciliation service."""

DEFAULT_WATCHER_GRACE_PERIOD = 20.0
"""Default grace period in seconds for the file watcher. This is the time to wait after a file change is detected before processing the change. This helps to avoid processing incomplete or transient file changes."""

DEFAULT_WATCHER_DEBOUNCE_MILLISECONDS = 10 * ONE_SECOND * 1_000
"""Default debounce time in milliseconds for the file watcher. This is the maximum time to wait before grouping file changes and processing them together."""

DEFAULT_WATCHER_STEP_MILLISECONDS = 15 * ONE_SECOND * 1_000
"""Default step time in milliseconds for the file watcher. This is the time to wait for new file changes before yielding grouped changes."""

MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH = 10
"""Maximum recursion depth for the semantic chunker to avoid infinite loops."""

SEMANTIC_CHUNKER_PERFORMANCE_THRESHOLD_MS = 1_000
"""Performance threshold in milliseconds for the semantic chunker to log warnings if exceeded."""

# ===========================================================================
# *                   Miscellaneous Constants
# ===========================================================================

DATATYPE_FIELDS = frozenset({
    "datatype",
    "dtype",
    "embedding_types",
    "encoding_format",
    "output_datatype",
    "output_datatypes",
    "output_dtype",
    "precision",
})

DIMENSION_FIELDS = frozenset({
    "dim",
    "dimension",
    "dimensions",
    "embedding_dimension",
    "embedding_dimensions",
    "output_dimension",
    "output_dimensionality",
    "output_dimensions",
    "truncate_dim",
})

ENV_CI_INDICATORS = {
    "APPVEYOR",
    "BUILDKITE",
    "BUILD_NUMBER",
    "CIRCLECI",
    "CONTINUOUS_INTEGRATION",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "RUN_ID",
    "TF_BUILD",
    "TRAVIS",
}
"""Environment variable names that indicate CI environments."""

ENV_EXPLICIT_TRUE_VALUES = {"1", "true", "yes", "on"}
"""Environment variable values that indicate explicit true."""

# ok, so "" isn't explicit, but it is falsey
ENV_EXPLICIT_FALSE_VALUES = {"0", "false", "no", "off", ""}
"""Environment variable values that indicate explicit false."""

ENV_JETBRAINS_INDICATOR = "TERMINAL_EMULATOR"
"""Environment variable name that indicates JetBrains IDEs."""

ENV_VSCODE_INDICATORS = {"VSCODE_GIT_IPC_HANDLE", "VSCODE_INJECTION", "VSCODE_IPC_HOOK_CLI"}

INTROSPECTION_ATTRIBUTES = frozenset({
    "__annotations__",
    "__class__",
    "__closure__",
    "__code__",
    "__defaults__",
    "__dict__",
    "__doc__",
    "__func__",
    "__globals__",
    "__kwdefaults__",
    "__module__",
    "__name__",
    "__qualname__",
    "__self__",
    "__signature__",
    "__text_signature__",
    "__wrapped__",
})
"""Attributes used for introspection (e.g. in lazy imports, by pydantic, etc.)."""

LOCALHOST = "127.0.0.1"
"""Standard localhost IP address. We avoid DNS lookups by using the IP directly."""

LOCALHOST_URL = f"http://{LOCALHOST}"
"""Localhost URL using HTTP."""

LOCALHOST_INDICATORS = {
    "localhost",
    LOCALHOST,
    "0.0.0.0",  # noqa: S104
    "::1",
    "0:0:0:0:0:0:0:1",
    "::",  # I guess ruff is ok if we bind to all interfaces in ipv6
    # save the more expensive check for second
    # this checks if the ip range is in private ranges
}
"""Hostnames and IPs that indicate localhost or local network addresses."""

MAX_REGEX_PATTERN_LENGTH = 8192
"""Maximum length for regex patterns to avoid performance issues. This is huge; we can safely say anything over this is likely a mistake or malicious."""

ONNX_CUDA_PROVIDER = "CUDAExecutionProvider"
"""ONNX Runtime CUDA execution provider name."""

QDRANT_MEMORY_LOCATION = ":memory:"
"""Special location string for creating an in-memory Qdrant instance."""


__all__ = (
    "BACKUP_DENSE_VECTOR_NAME",
    "BACKUP_EMBEDDING_MODEL_FALLBACK",
    "BACKUP_EMBEDDING_MODEL_PRIMARY",
    "BACKUP_RERANKING_MODEL",
    "BASE_RETRYABLE_EXCEPTIONS",
    "CLOUD_EMBEDDING_COST_PER_1K_TOKENS",
    "CLOUD_RERANKING_COST_PER_1K_TOKENS",
    "CODEWEAVER_DESCRIPTION",
    "CODEWEAVER_ICON",
    "CONTEXT_AGENT_COST_PER_1K_TOKENS",
    "CONTEXT_AGENT_TAGS",
    "DATATYPE_FIELDS",
    "DEFAULT_AGENT_TEMPERATURE",
    "DEFAULT_AGENT_TIMEOUT",
    "DEFAULT_AGENT_TOP_P",
    "DEFAULT_BLAKE_STORE_MAX_SIZE",
    "DEFAULT_CHECKPOINT_SUBPATH",
    "DEFAULT_COLLECTION_NAME_PREFIX",
    "DEFAULT_DAEMON_STARTUP_CHECK_INTERVAL",
    "DEFAULT_DAEMON_STARTUP_WAIT",
    "DEFAULT_DENSE_WEIGHT",
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "DEFAULT_EMBEDDING_REGISTRY_MAX_SIZE",
    "DEFAULT_EMBEDDING_TIMEOUT",
    "DEFAULT_HNSW_EF_CONSTRUCTION",
    "DEFAULT_HNSW_FULL_SCAN_THRESHOLD",
    "DEFAULT_HNSW_M",
    "DEFAULT_HNSW_PAYLOAD_M",
    "DEFAULT_HOST",
    "DEFAULT_HTTPX_KEEPALIVE_EXPIRY",
    "DEFAULT_HTTPX_MAX_CONNECTIONS",
    "DEFAULT_HTTPX_MAX_KEEPALIVE_CONNECTIONS",
    "DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_MANAGEMENT_PORT",
    "DEFAULT_MANIFEST_SUBPATH",
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MCP_MAX_RETRY_ATTEMPTS",
    "DEFAULT_MCP_PORT",
    "DEFAULT_MCP_RATE_LIMIT_BURST_CAPACITY",
    "DEFAULT_MCP_RATE_LIMIT_MAX_REQUESTS_PER_SECOND",
    "DEFAULT_MCP_RETRY_BACKOFF_MULTIPLIER",
    "DEFAULT_MCP_RETRY_BASE_DELAY",
    "DEFAULT_MCP_RETRY_MAX_DELAY",
    "DEFAULT_MCP_TIMEOUT",
    "DEFAULT_OPEN_BREAKER_DURATION",
    "DEFAULT_PERSIST_INTERVAL",
    "DEFAULT_POOL_ACQUIRE_TIMEOUT",
    "DEFAULT_POOL_CONNECTION_TIMEOUT",
    "DEFAULT_POOL_READ_TIMEOUT",
    "DEFAULT_POOL_WRITE_TIMEOUT",
    "DEFAULT_RECONCILIATION_SERVICE_BATCH_SIZE",
    "DEFAULT_RERANKING_MAX_RESULTS",
    "DEFAULT_RERANKING_MAX_RESULTS",
    "DEFAULT_RERANKING_TIMEOUT",
    "DEFAULT_RICH_HANDLER_OPTIONS",
    "DEFAULT_SEMANTIC_IDENTIFICATION_CONFIDENCE_THRESHOLD",
    "DEFAULT_SERVER_SHUTDOWN_TIMEOUT",
    "DEFAULT_SNAPSHOT_RETENTION_COUNT",
    "DEFAULT_SNAPSHOT_RETENTION_COUNT",
    "DEFAULT_SPARSE_WEIGHT",
    "DEFAULT_USER_DIR_NAME",
    "DEFAULT_UUID_STORE_MAX_SIZE",
    "DEFAULT_VECTOR_STORE_BATCH_SIZE",
    "DEFAULT_VECTOR_STORE_MAX_RESULTS",
    "DEFAULT_VECTOR_STORE_MAX_RESULTS",
    "DEFAULT_WATCHER_DEBOUNCE_MILLISECONDS",
    "DEFAULT_WATCHER_GRACE_PERIOD",
    "DEFAULT_WATCHER_STEP_MILLISECONDS",
    "DIMENSION_FIELDS",
    "ELLIPSIS",
    "ENV_CI_INDICATORS",
    "ENV_EXPLICIT_FALSE_VALUES",
    "ENV_EXPLICIT_TRUE_VALUES",
    "ENV_JETBRAINS_INDICATOR",
    "ENV_VSCODE_INDICATORS",
    "FIND_CODE_DESCRIPTION",
    "FIND_CODE_INSTRUCTION",
    "FIND_CODE_TITLE",
    "FIVE_MINUTES",
    "HEALTH_ENDPOINT",
    "INDEXER_WINDDOWN_TIMEOUT",
    "INTROSPECTION_ATTRIBUTES",
    "LOCALHOST",
    "LOCALHOST_INDICATORS",
    "LOCALHOST_URL",
    "LOCAL_EMBEDDING_COST_PER_1K_TOKENS",
    "LOGGERS_TO_SUPPRESS",
    "MAX_REGEX_PATTERN_LENGTH",
    "MAX_RETRY_ATTEMPTS",
    "MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH",
    "MCP_ENDPOINT",
    "METRICS_ENDPOINT",
    "ONE",
    "ONE_DAY",
    "ONE_GIGABYTE",
    "ONE_HOUR",
    "ONE_HUNDRED",
    "ONE_HUNDRED_MEGABYTES",
    "ONE_KILOBYTE",
    "ONE_LINE",
    "ONE_MEGABYTE",
    "ONE_MILLISECOND_IN_MICROSECONDS",
    "ONE_MINUTE",
    "ONE_POINT_ZERO",
    "ONE_SECOND",
    "ONNX_CUDA_PROVIDER",
    "POSIX_NEWLINE",
    "PRIMARY_SPARSE_VECTOR_NAME",
    "PRIMARY_VECTOR_NAME",
    "PYTHON_SHEBANG",
    "QDRANT_MEMORY_LOCATION",
    "SEMANTIC_CHUNKER_PERFORMANCE_THRESHOLD_MS",
    "SETTINGS_ENDPOINT",
    "SHEBANG",
    "SHUTDOWN_ENDPOINT",
    "SPACE",
    "STATE_ENDPOINT",
    "STATUS_ENDPOINT",
    "TAB",
    "TEN_MINUTES",
    "USER_AGENT_COST_PER_1K_TOKENS",
    "USER_AGENT_TAGS",
    "VERSION_ENDPOINT",
    "WATCHER_WINDDOWN_TIMEOUT",
    "WHITESPACES",
    "WINDOWS_NEWLINE",
    "ZERO",
    "ZERO_POINT_ZERO",
)
