# CodeWeaver CLI Reference

CodeWeaver: Powerful code search and understanding for humans and agents.

## Table of Contents

- [`config`](#codeweaver-config)
- [`search`](#codeweaver-search)
- [`server`](#codeweaver-server)
- [`index`](#codeweaver-index)
- [`doctor`](#codeweaver-doctor)
- [`list`](#codeweaver-list)
  - [`providers`](#codeweaver-list-providers)
  - [`models`](#codeweaver-list-models)
  - [`embedding`](#codeweaver-list-embedding)
  - [`embed`](#codeweaver-list-embed)
  - [`sparse-embedding`](#codeweaver-list-sparse-embedding)
  - [`vector-store`](#codeweaver-list-vector-store)
  - [`reranking`](#codeweaver-list-reranking)
  - [`rerank`](#codeweaver-list-rerank)
  - [`agent`](#codeweaver-list-agent)
  - [`data`](#codeweaver-list-data)
- [`ls`](#codeweaver-ls)
  - [`providers`](#codeweaver-ls-providers)
  - [`models`](#codeweaver-ls-models)
  - [`embedding`](#codeweaver-ls-embedding)
  - [`embed`](#codeweaver-ls-embed)
  - [`sparse-embedding`](#codeweaver-ls-sparse-embedding)
  - [`vector-store`](#codeweaver-ls-vector-store)
  - [`reranking`](#codeweaver-ls-reranking)
  - [`rerank`](#codeweaver-ls-rerank)
  - [`agent`](#codeweaver-ls-agent)
  - [`data`](#codeweaver-ls-data)
- [`init`](#codeweaver-init)
  - [`config`](#codeweaver-init-config)
  - [`mcp`](#codeweaver-init-mcp)
- [`status`](#codeweaver-status)

**Usage**:

```console
$ codeweaver COMMAND
```

**Commands**:

* `config`: Manage and view your CodeWeaver config.
* `doctor`: Validate prerequisites and configuration for CodeWeaver.
* `index`: Index codebase for semantic search.
* `init`: Initialize CodeWeaver configuration and MCP client setup.
* `list`: List available CodeWeaver resources.
* `search`: Search your codebase from the command line.
* `server`: Start CodeWeaver MCP server.
* `status`: Show CodeWeaver runtime status.

## `codeweaver config`

Manage and view your CodeWeaver config.

**Usage**:

```console
$ codeweaver config [OPTIONS]
```

**Options**:

### Options

* `-p, --project`: Path to project directory
* `-c, --config-file`: Path to a specific config file to use
* `-v, --verbose, --no-verbose`: Enable verbose logging  *[default: --no-verbose]*
* `-d, --debug, --no-debug`: Enable debug logging  *[default: --no-debug]*

## `codeweaver search`

Search your codebase from the command line.

**Usage**:

```console
$ codeweaver search [OPTIONS] QUERY
```

**Arguments**:

### Arguments

* `QUERY`:   **[required]**

**Options**:

### Options

* `--intent`:   *[choices: understand, implement, debug, optimize, test, configure, document]*
* `--limit`:   *[default: 10]*
* `-p, --project`: 
* `-c, --config-file`: Path to a specific config file to use
* `--output-format`:   *[choices: json, table, markdown]*  *[default: table]*

## `codeweaver server`

Start CodeWeaver MCP server.

**Usage**:

```console
$ codeweaver server [OPTIONS]
```

**Options**:

### Options

* `-c, --config`: 
* `-p, --project`: 
* `--host`:   *[default: 127.0.0.1]*
* `--port`:   *[default: 9328]*
* `-t, --transport`: Transport type for MCP communication (streamable-http or stdio)  *[choices: streamable-http, stdio]*  *[default: streamable-http]*
* `-v, --verbose, --no-verbose`: Enable verbose logging with timestamps  *[default: --no-verbose]*
* `-d, --debug, --no-debug`: Enable debug logging  *[default: --no-debug]*

## `codeweaver index`

Index codebase for semantic search.

**Usage**:

```console
$ codeweaver index [OPTIONS]
```

**Options**:

### Options

* `-c, --config`: Optional path to CodeWeaver configuration file
* `-p, --project`: Optional path to project root directory
* `-f, --force, --no-force`: Force full reindex  *[default: --no-force]*
* `-s, --standalone, --no-standalone`: Run indexing without server  *[default: --no-standalone]*
* `--clear, --no-clear`: Clear vector store and checkpoints before indexing (requires confirmation)  *[default: --no-clear]*
* `-y, --yes, --no-yes`: Skip confirmation prompts (use with --clear)  *[default: --no-yes]*

## `codeweaver doctor`

Validate prerequisites and configuration for CodeWeaver.

**Usage**:

```console
$ codeweaver doctor [OPTIONS]
```

**Options**:

### Options

* `--verbose, --no-verbose`: Show detailed information for all checks  *[default: --no-verbose]*
* `--display.console.color-system`: The color system supported by your terminal, either "standard", "256" or "truecolor". Leave as "auto" to autodetect.  *[choices: auto, standard, 256, truecolor, windows]*  *[default: auto]*
* `--display.console.force-terminal, --display.console.no-force-terminal`: Enable/disable terminal control codes, or None to auto-detect terminal. Defaults to None.
* `--display.console.force-jupyter, --display.console.no-force-jupyter`: Enable/disable Jupyter rendering, or None to auto-detect Jupyter. Defaults to None.
* `--display.console.force-interactive, --display.console.no-force-interactive`: Enable/disable interactive mode, or None to auto detect. Defaults to None.
* `--display.console.soft-wrap, --display.console.no-soft-wrap`: Set soft wrap default on print method. Defaults to False.
* `--display.console.theme.styles`: A mapping of style names on to styles. Defaults to None for a theme with no styles.
* `--display.console.theme.inherit, --display.console.theme.no-inherit`: Inherit default styles. Defaults to True.  *[default: --display.console.theme.inherit]*
* `--display.console.stderr, --display.console.no-stderr`: Use stderr rather than stdout if file is not specified. Defaults to False.
* `--display.console.file`: A file object where the console should write to. Defaults to stdout.
* `--display.console.quiet, --display.console.no-quiet`: Boolean to suppress all output. Defaults to False.
* `--display.console.width`: The width of the terminal. Leave as default to auto-detect width.
* `--display.console.height`: The height of the terminal. Leave as default to auto-detect height.
* `--display.console.style.color.name`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.color.type`: Style to apply to all output, or None for no style. Defaults to None.  *[choices: default, standard, eight-bit, truecolor, windows]*
* `--display.console.style.color.number`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.color.triplet.red`: Red component in 0 to 255 range.
* `--display.console.style.color.triplet.green`: Green component in 0 to 255 range.
* `--display.console.style.color.triplet.blue`: Blue component in 0 to 255 range.
* `--display.console.style.bgcolor.name`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.bgcolor.type`: Style to apply to all output, or None for no style. Defaults to None.  *[choices: default, standard, eight-bit, truecolor, windows]*
* `--display.console.style.bgcolor.number`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.bgcolor.triplet.red`: Red component in 0 to 255 range.
* `--display.console.style.bgcolor.triplet.green`: Green component in 0 to 255 range.
* `--display.console.style.bgcolor.triplet.blue`: Blue component in 0 to 255 range.
* `--display.console.style.bold, --display.console.style.no-bold`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.dim, --display.console.style.no-dim`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.italic, --display.console.style.no-italic`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.underline, --display.console.style.no-underline`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.blink, --display.console.style.no-blink`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.blink2, --display.console.style.no-blink2`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.reverse, --display.console.style.no-reverse`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.conceal, --display.console.style.no-conceal`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.strike, --display.console.style.no-strike`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.underline2, --display.console.style.no-underline2`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.frame, --display.console.style.no-frame`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.encircle, --display.console.style.no-encircle`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.overline, --display.console.style.no-overline`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.link`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.style.meta`: Style to apply to all output, or None for no style. Defaults to None.
* `--display.console.no-color, --display.console.no-no-color`: Enabled no color mode, or None to auto detect. Defaults to None.
* `--display.console.tab-size`: Number of spaces used to replace a tab character. Defaults to 8.  *[default: 8]*
* `--display.console.record, --display.console.no-record`: Boolean to enable recording of terminal output, required to call export_html, export_svg, and export_text. Defaults to 
False.
* `--display.console.markup, --display.console.no-markup`: Boolean to enable :ref:`console_markup`. Defaults to True.  *[default: --display.console.markup]*
* `--display.console.emoji, --display.console.no-emoji`: Enable emoji code. Defaults to True.  *[default: --display.console.emoji]*
* `--display.console.emoji-variant`: Optional emoji variant, either "text" or "emoji". Defaults to None.  *[choices: emoji, text]*
* `--display.console.highlight, --display.console.no-highlight`: Enable automatic highlighting. Defaults to True.  *[default: --display.console.highlight]*
* `--display.console.log-time, --display.console.no-log-time`: Boolean to enable logging of time by log methods. Defaults to True.  *[default: --display.console.log-time]*
* `--display.console.log-path, --display.console.no-log-path`: Boolean to enable the logging of the caller by log. Defaults to True.  *[default: --display.console.log-path]*
* `--display.console.log-time-format`: If log_time is enabled, either string for strftime or callable that formats the time. Defaults to "[%X] ".  *[default: [%X]]*
* `--display.console.highlighter`: Default highlighter.  *[default: <rich.highlighter.ReprHighlighter object at 0x76857d629550>]*
* `--display.console.legacy-windows, --display.console.no-legacy-windows`: Enable legacy Windows mode, or None to auto detect. Defaults to None.
* `--display.console.safe-box, --display.console.no-safe-box`: Restrict box options that don't render on legacy Windows.  *[default: --display.console.safe-box]*
* `--display.console.get-datetime`: Callable that gets the current time as a datetime.datetime object (used by Console.log), or None for datetime.now.
* `--display.console.get-time`: Callable that gets the current time in seconds, default uses time.monotonic.
* `--display.console.environ`: StatusDisplay instance for output
* `-c, --config-file`: Path to a specific config file to use
* `-p, --project`: Path to project directory

## `codeweaver list`

List available CodeWeaver resources.

**Usage**:

```console
$ codeweaver list COMMAND
```

**Commands**:

* `agent`: List all agent providers (shortcut).
* `data`: List all data providers (shortcut).
* `embedding`: List all embedding providers (shortcut).
* `models`: List available models for a specific provider.
* `providers`: List all available providers.
* `reranking`: List all reranking providers (shortcut).
* `sparse-embedding`: List all sparse-embedding providers (shortcut).
* `vector-store`: List all vector-store providers (shortcut).

## `codeweaver list providers`

List all available providers.

Shows provider name, capabilities, and status (ready or needs configuration).

**Usage**:

```console
$ codeweaver list providers [ARGS]
```

**Options**:

* `-k, --kind`: Filter by provider kind  *[choices: data, embedding, sparse-embedding, reranking, vector-store, agent, unset]*  *[default: embedding]*


## `codeweaver list models`

List available models for a specific provider.

Shows model name, dimensions, and other capabilities.

**Usage**:

```console
$ codeweaver list models PROVIDER-NAME
```

**Arguments**:

* `PROVIDER-NAME`: Provider name to list models for (voyage, fastembed, cohere, etc.)  **[required]**  *[choices: voyage, fastembed, qdrant, memory, anthropic, bedrock, cohere, google, x-ai, huggingface-inference, sentence-transformers, mistral, openai, azure, cerebras, deepseek, fireworks, github, groq, heroku, litellm, moonshot, ollama, openrouter, perplexity, together, vercel, duckduckgo, tavily, not-set]*


## `codeweaver list embedding`

List all embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind embedding

**Usage**:

```console
$ codeweaver list embedding
```


## `codeweaver list embed`

List all embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind embedding

**Usage**:

```console
$ codeweaver list embed
```


## `codeweaver list sparse-embedding`

List all sparse-embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind sparse-embedding

**Usage**:

```console
$ codeweaver list sparse-embedding
```


## `codeweaver list vector-store`

List all vector-store providers (shortcut).

Equivalent to: codeweaver list providers --kind vector-store

**Usage**:

```console
$ codeweaver list vector-store [ARGS]
```

**Options**:

* `ALIAS, --alias`:   *[default: vec]*


## `codeweaver list reranking`

List all reranking providers (shortcut).

Equivalent to: codeweaver list providers --kind reranking

**Usage**:

```console
$ codeweaver list reranking
```


## `codeweaver list rerank`

List all reranking providers (shortcut).

Equivalent to: codeweaver list providers --kind reranking

**Usage**:

```console
$ codeweaver list rerank
```


## `codeweaver list agent`

List all agent providers (shortcut).

Equivalent to: codeweaver list providers --kind agent

**Usage**:

```console
$ codeweaver list agent
```


## `codeweaver list data`

List all data providers (shortcut).

Equivalent to: codeweaver list providers --kind data

**Usage**:

```console
$ codeweaver list data
```


## `codeweaver ls`

List available CodeWeaver resources.

**Usage**:

```console
$ codeweaver ls COMMAND
```

**Commands**:

* `agent`: List all agent providers (shortcut).
* `data`: List all data providers (shortcut).
* `embedding`: List all embedding providers (shortcut).
* `models`: List available models for a specific provider.
* `providers`: List all available providers.
* `reranking`: List all reranking providers (shortcut).
* `sparse-embedding`: List all sparse-embedding providers (shortcut).
* `vector-store`: List all vector-store providers (shortcut).

## `codeweaver ls providers`

List all available providers.

Shows provider name, capabilities, and status (ready or needs configuration).

**Usage**:

```console
$ codeweaver ls providers [ARGS]
```

**Options**:

* `-k, --kind`: Filter by provider kind  *[choices: data, embedding, sparse-embedding, reranking, vector-store, agent, unset]*  *[default: embedding]*


## `codeweaver ls models`

List available models for a specific provider.

Shows model name, dimensions, and other capabilities.

**Usage**:

```console
$ codeweaver ls models PROVIDER-NAME
```

**Arguments**:

* `PROVIDER-NAME`: Provider name to list models for (voyage, fastembed, cohere, etc.)  **[required]**  *[choices: voyage, fastembed, qdrant, memory, anthropic, bedrock, cohere, google, x-ai, huggingface-inference, sentence-transformers, mistral, openai, azure, cerebras, deepseek, fireworks, github, groq, heroku, litellm, moonshot, ollama, openrouter, perplexity, together, vercel, duckduckgo, tavily, not-set]*


## `codeweaver ls embedding`

List all embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind embedding

**Usage**:

```console
$ codeweaver ls embedding
```


## `codeweaver ls embed`

List all embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind embedding

**Usage**:

```console
$ codeweaver ls embed
```


## `codeweaver ls sparse-embedding`

List all sparse-embedding providers (shortcut).

Equivalent to: codeweaver list providers --kind sparse-embedding

**Usage**:

```console
$ codeweaver ls sparse-embedding
```


## `codeweaver ls vector-store`

List all vector-store providers (shortcut).

Equivalent to: codeweaver list providers --kind vector-store

**Usage**:

```console
$ codeweaver ls vector-store [ARGS]
```

**Options**:

* `ALIAS, --alias`:   *[default: vec]*


## `codeweaver ls reranking`

List all reranking providers (shortcut).

Equivalent to: codeweaver list providers --kind reranking

**Usage**:

```console
$ codeweaver ls reranking
```


## `codeweaver ls rerank`

List all reranking providers (shortcut).

Equivalent to: codeweaver list providers --kind reranking

**Usage**:

```console
$ codeweaver ls rerank
```


## `codeweaver ls agent`

List all agent providers (shortcut).

Equivalent to: codeweaver list providers --kind agent

**Usage**:

```console
$ codeweaver ls agent
```


## `codeweaver ls data`

List all data providers (shortcut).

Equivalent to: codeweaver list providers --kind data

**Usage**:

```console
$ codeweaver ls data
```


## `codeweaver init`

Initialize CodeWeaver configuration and MCP client setup.

**Usage**:

```console
$ codeweaver init COMMAND [OPTIONS]
```

**Options**:

### Options

* `-p, --project`: Path to project directory (defaults to current directory)
* `--config-only, --no-config-only`: Only create CodeWeaver config file  *[default: --no-config-only]*
* `--mcp-only, --no-mcp-only`: Only create MCP client config  *[default: --no-mcp-only]*
* `-q, --quickstart, --no-quickstart`:   *[default: --no-quickstart]*
* `--profile`: Configuration profile to use (recommended, quickstart, or test). Defaults to 'recommended' with --recommended.  *[choices: recommended, quickstart, test]*  *[default: recommended]*
* `--vector-deployment`: Vector store deployment type  *[choices: local, cloud]*  *[default: local]*
* `--vector-url`: URL for cloud vector deployment (required if --vector-deployment=cloud)
* `-c, --client, --empty-client`: MCP clients to configure. Defaults to 'mcpjson' if none specified. You can provide multiple clients by repeating this 
flag.  *[choices: claude_code, claude_desktop, cursor, gemini_cli, vscode, mcpjson]*
* `--host`: CodeWeaver server host  *[default: http://127.0.0.1]*
* `--port`: CodeWeaver server port  *[default: 9328]*
* `-f, --force, --no-force`: Force overwrite existing config  *[default: --no-force]*
* `-t, --transport`: Transport type (streamable-http or stdio). Streamable default and recommended.  *[choices: streamable-http, stdio]*  *[default: streamable-http]*
* `--config-extension`:   *[choices: toml, yaml, yml, json]*  *[default: toml]*
* `--config-path`: Custom path for CodeWeaver configuration file
* `--mcp-config-level`: The level of mcp configuration to write to (project or user)  *[choices: project, user]*  *[default: project]*
* `--config-level`: Configuration level for CodeWeaver config (local, project, or user)  *[choices: local, project, user]*  *[default: project]*

**Commands**:

* `config`: Set up CodeWeaver configuration file.
* `mcp`: Set up MCP client configuration for CodeWeaver.

## `codeweaver init config`

Set up CodeWeaver configuration file.

**Usage**:

```console
$ codeweaver init config [OPTIONS]
```

**Options**:

* `-p, --project`: Path to project directory (defaults to current directory)
* `--profile`: Configuration profile to use (recommended, quickstart, or test)  *[choices: recommended, quickstart, test]*  *[default: recommended]*
* `--quickstart, --no-quickstart`: Use the quickstart local-only profile instead of the recommended profile.  *[default: --no-quickstart]*
* `--vector-deployment`: Vector store deployment type  *[choices: local, cloud]*  *[default: local]*
* `--vector-url`: URL for cloud vector deployment (required if --vector-deployment=cloud)
* `--config-path`: Custom path for configuration file (defaults to codeweaver.toml in project root)
* `--config-extension`:   *[choices: toml, yaml, yml, json]*  *[default: toml]*
* `--config-level`: Configuration level. Local configs (which end in 'local') should be gitignored and are for personal use. Project-level 
are for shared configuration in a repository and should not be gitignored. User-level are for personal configurations 
across multiple projects.  *[choices: local, project, user]*  *[default: project]*
* `-f, --force, --no-force`: Overwrite existing configuration file  *[default: --no-force]*


## `codeweaver init mcp`

Set up MCP client configuration for CodeWeaver.

This command generates MCP client configuration that allows AI assistants like Claude Code, Cursor, or VSCode to connect
to CodeWeaver's MCP server.

Transport Types: - streamable-http (default): HTTP-based transport for persistent server connections - stdio: Standard 
input/output transport that launches CodeWeaver per-session

Tip: Set a default MCP config in your CodeWeaver config, then just run cw init mcp --client your_client --client 
another_client to generate the config for those clients.

**Usage**:

```console
$ codeweaver init mcp [OPTIONS]
```

**Options**:

* `-o, --output`: Output method for MCP client configuration. 'write' to file, 'print' to stdout, 'copy' to clipboard.  *[choices: write, print, copy]*  *[default: write]*
* `-p, --project`: Path to project directory (auto-detected if not provided)
* `-l, --config-level`: Configuration level to write to.  *[choices: project, user]*  *[default: project]*
* `-f, --file-path`: Custom path to MCP client configuration file.
* `-c, --client, --empty-client`: MCP client to configure, you can provide multiple clients by repeating this flag. Defaults to 'mcpjson' if none 
specified.  *[choices: claude_code, claude_desktop, cursor, gemini_cli, vscode, mcpjson]*
* `--host`: [http-only] Server host address (default: http://127.0.0.1)  *[default: http://127.0.0.1]*
* `--port`: [http-only] Server port (default: 9328)  *[default: 9328]*
* `-t, --transport`: Transport type for MCP communication  *[choices: streamable-http, stdio]*  *[default: streamable-http]*
* `--timeout`: Timeout in seconds for MCP client connections  *[default: 120]*
* `--auth`: Authentication method for MCP client (bearer token, 'oauth', an httpx.Auth object, or None)  *[choices: oauth]*
* `--cmd`: [stdio-only] Command to start MCP client process
* `--args`: [stdio-only] Arguments for MCP client process command
* `--env`: stdio-only Environment variables for MCP client process
* `--authentication`: Authentication configuration for MCP client


## `codeweaver status`

Show CodeWeaver runtime status.

**Usage**:

```console
$ codeweaver status [OPTIONS]
```

**Options**:

### Options

* `--verbose, --no-verbose`: Show detailed status information  *[default: --no-verbose]*
* `--watch, --no-watch`: Continuously watch status (refresh every watch_interval seconds)  *[default: --no-watch]*
* `--watch-interval`: Seconds between updates in watch mode (default: 5)  *[default: 5]*
