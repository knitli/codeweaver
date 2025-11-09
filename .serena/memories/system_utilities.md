# System Utilities and Environment

## Operating System
**Platform**: Linux (WSL2)
- **Kernel**: Linux 6.6.87.2-microsoft-standard-WSL2
- **Distribution**: Ubuntu/Debian-based (WSL2)

## Development Shell
**Primary Shell**: zsh (configured in mise.toml)
- Tasks default to `zsh -c` for execution
- Shell auto-detection via `ACTIVE_SHELL` environment variable

## System Utilities Available

### Core Development Tools (via mise)
- **ast-grep** - AST-based code search and manipulation
- **gh** - GitHub CLI for repository operations
- **hk** - Housekeeping tool for code quality checks
- **node** - Node.js (v24) for JavaScript tooling
- **pkl** - Configuration language
- **python** - Python 3.13 (primary development version)
- **ripgrep (rg)** - Fast text search (use instead of grep)
- **ruff** - Python linter and formatter
- **shellcheck** - Shell script linter
- **shfmt** - Shell script formatter
- **typos** - Spell checker for code
- **uv** - Fast Python package manager (replaces pip)
- **yamlfmt** - YAML formatter

### Python Tools (via pipx)
- **changesets** - Changelog generation
- **claude-monitor** - Claude API monitoring
- **copychat** - Chat utilities
- **fastmcp** - MCP server development
- **mike** - MkDocs versioning
- **mteb** - Embedding benchmarks
- **reuse** - License compliance tool
- **tombi** - TOML formatter
- **ty** - Type checker (pyright-based)

### Rust Tools (via cargo)
- **rust-parallel** - Parallel command execution
- **tree-sitter-cli** - Tree-sitter grammar tools

## File Operations

### Preferred Tools
✅ **Use these**:
- `rg` (ripgrep) - Fast text search instead of grep
- `ast-grep` - Code-aware search instead of grep for code
- `find` - File discovery (or use Python rignore library)
- `ls` - Directory listing
- Native Python file operations via libraries

❌ **Avoid these in automation**:
- `grep` - Use ripgrep (`rg`) instead
- Manual `sed`/`awk` - Use Python or ruff for code transformations

### Common File Operations
```bash
# List directory contents
ls -la

# Find files by name
find . -name "*.py"

# Search file contents (use ripgrep)
rg "pattern" --type py

# Search code semantically
ast-grep --pattern 'class $NAME'

# Count lines of code
find src -name "*.py" | xargs wc -l
```

## Git Operations

### Standard Commands
```bash
git status              # Check working tree status
git branch              # List branches
git diff                # Show changes
git add .               # Stage all changes
git commit -m "msg"     # Commit changes
git push                # Push to remote
git pull                # Pull from remote
```

### GitHub CLI (gh)
```bash
gh repo view            # View repository info
gh issue list           # List issues
gh pr create            # Create pull request
gh pr view              # View pull request
gh pr list              # List pull requests
```

### Project Git Aliases (auto-configured)
```bash
git root                # Show repository root path
```

## Environment Variables

### Auto-Configured (mise.toml)
- `GH_REPO` - Repository path (config_root)
- `PROJECT_NAME` - "codeweaver-mcp"
- `CODEWEAVER_PROJECT_PATH` - Project root path
- `CODEWEAVER_VERSION` - Current version from _version.py
- `CI` - "true" in GitHub Actions, "false" otherwise
- `VIRTUAL_ENV` - Virtual environment path when activated
- `ACTIVE_SHELL` - Current shell (auto-detected)

### User-Configured (required)
- `VOYAGE_API_KEY` - VoyageAI API key for embeddings

### Path Extensions
Mise automatically adds these to PATH:
```
scripts/dev-env
scripts/code-quality
scripts/build
scripts/language-support
scripts/testing
scripts/utils
.venv/bin
```

## Package Management

### UV (Replaces pip/poetry)
```bash
uv sync                 # Install dependencies from lock file
uv sync --all-groups    # Install all dependency groups
uv sync -U              # Update dependencies
uv add package          # Add new dependency
uv remove package       # Remove dependency
uv run command          # Run command in virtual environment
uvx command             # Run tool without installing
```

### Virtual Environment
```bash
# Create/activate (mise handles this automatically)
mise run venv           # Create virtual environment
mise run source         # Source virtual environment
mise run activate       # Activate environment

# Manual activation (if needed)
source .venv/bin/activate
```

## Process Management

### Background Processes
```bash
# Run process in background
command &

# List background jobs
jobs

# Bring to foreground
fg %1

# Kill process
kill PID
```

### Port Management
```bash
# Check port usage (default MCP port: 9328)
lsof -i :9328

# Kill process on port
kill $(lsof -t -i:9328)
```

## Filesystem Conventions

### Temporary Files
- Use `/tmp/` for temporary files
- Clean up temporary files after use
- Avoid cluttering project directory

### Permissions
```bash
# Make script executable
chmod +x script.sh

# Change ownership (if needed)
chown user:group file
```

### Symbolic Links
```bash
# Create symbolic link
ln -s target link_name

# Show link target
readlink link_name
```

## Common Linux Commands

### File Inspection
```bash
cat file.txt            # Display file contents
head -n 20 file.txt     # First 20 lines
tail -n 20 file.txt     # Last 20 lines
wc -l file.txt          # Count lines
file filename           # Determine file type
```

### Directory Navigation
```bash
pwd                     # Print working directory
cd path                 # Change directory
cd ..                   # Parent directory
cd ~                    # Home directory
```

### File Management
```bash
cp source dest          # Copy file
mv source dest          # Move/rename file
rm file                 # Remove file
rm -rf dir              # Remove directory recursively
mkdir dir               # Create directory
mkdir -p path/to/dir    # Create nested directories
```

### Archive Operations
```bash
tar -czf archive.tar.gz dir/    # Create tar.gz
tar -xzf archive.tar.gz         # Extract tar.gz
zip -r archive.zip dir/         # Create zip
unzip archive.zip               # Extract zip
```

## Network Operations

### HTTP Requests (httpx available)
```bash
# Check server health
curl http://localhost:9328/health/

# With JSON formatting (requires jq)
curl http://localhost:9328/health/ | jq

# POST request
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"test"}' http://localhost:9328/find_code
```

### Python HTTP (httpx)
```python
import httpx

# Synchronous
response = httpx.get("http://localhost:9328/health/")

# Asynchronous
async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:9328/health/")
```

## Monitoring and Debugging

### Process Monitoring
```bash
ps aux | grep python    # Find Python processes
top                     # System resource monitor
htop                    # Enhanced resource monitor (if installed)
```

### Disk Usage
```bash
df -h                   # Disk space
du -sh dir/             # Directory size
du -sh * | sort -h      # Sort by size
```

### Memory Usage
```bash
free -h                 # Memory usage
```

## WSL2-Specific Notes

### Windows Integration
- Can access Windows filesystem: `/mnt/c/`, `/mnt/d/`
- Can run Windows executables from WSL
- Network ports are accessible from Windows (localhost)

### Performance Considerations
- WSL2 filesystem is faster for Linux operations
- Windows filesystem access (`/mnt/c/`) is slower
- Keep development files in WSL filesystem for best performance
- Default project path: `/home/knitli/codeweaver-mcp`

### Resource Limits
- WSL2 defaults: 50% of total memory, 8 logical processors
- Can be configured in `.wslconfig` on Windows
