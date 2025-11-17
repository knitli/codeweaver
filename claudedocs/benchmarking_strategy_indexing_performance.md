# CodeWeaver Indexing Performance Benchmarking Strategy

**Document Version**: 1.0
**Date**: November 17, 2025
**Purpose**: Comprehensive strategy for benchmarking CodeWeaver's indexing performance against competitors

---

## Executive Summary

This document outlines a detailed, reproducible strategy for benchmarking CodeWeaver's code indexing performance against competing solutions. The strategy emphasizes:

1. **Fairness**: Comparable conditions across all tools
2. **Reproducibility**: Automated, repeatable methodology
3. **Comprehensiveness**: Multiple metrics beyond raw speed
4. **Practicality**: Focus on benchmarkable competitors (open-source or API-accessible)

### Benchmarkable Competitors

| Tool | Benchmarkability | Approach |
|------|-----------------|----------|
| **CodeWeaver** | ✅ Full | Direct API/CLI access |
| **Continue.dev** | ✅ Full | Open source, isolate indexing component |
| **Bloop** | ✅ Full | Open source, CLI/API available |
| **Cursor** | ⚠️ Limited | No API; requires IDE automation or exclusion |
| **Copilot Workspace** | ❌ Not feasible | Cloud-only, no API access |
| **Sourcegraph Cody** | ⚠️ Partial | Enterprise features, self-hosted possible |

**Recommended focus**: CodeWeaver vs. Continue.dev vs. Bloop (all open-source, fully benchmarkable)

---

## Benchmarking Approach

### Phase 1: Core Indexing Speed (Primary Focus)
- **Metric**: Time to build index structure (AST parsing, chunking, file discovery)
- **Excludes**: Embedding generation (provider-dependent)
- **Rationale**: Measures tool's core performance, not external API speed

### Phase 2: Total Indexing Time (with Embeddings)
- **Metric**: End-to-end time including embedding generation
- **Provider standardization**: Same embedding provider across tools (e.g., all use Voyage Code-2 via API)
- **Rationale**: Real-world performance for developers

### Phase 3: Incremental Update Performance
- **Metric**: Time to reindex after file changes (1 file, 10 files, 100 files)
- **Rationale**: Critical for live development workflows

### Phase 4: Resource Consumption
- **Metrics**: Peak memory usage, CPU utilization, disk I/O
- **Rationale**: System impact matters for developer machines

---

## Competitor-Specific Benchmarking Strategies

### 1. Continue.dev (Open Source - Full Isolation Possible)

**Architecture**:
- **GitHub**: `continuedev/continue`
- **Indexing components**: `core/indexing/` directory
- **Storage**: `~/.continue/index/index.sqlite`
- **Technology**: Tree-sitter AST parsing, Transformers.js embeddings (default)

**Benchmarking approach**:

```python
# Pseudo-code for Continue.dev benchmark
from continue_core.indexing import CodebaseIndexer
import time

# Isolate indexing component
indexer = CodebaseIndexer(
    workspace_dir="/path/to/test/repo",
    embedding_provider="transformers.js",  # Local, consistent
    config={
        "nRetrieve": 25,
        "nFinal": 5,
        "useReranking": False  # Disable for indexing-only test
    }
)

# Measure indexing time
start = time.perf_counter()
indexer.index_workspace()
indexing_time = time.perf_counter() - start

# Measure incremental update
modify_file("/path/to/test/repo/src/main.py")
start = time.perf_counter()
indexer.update_index()
update_time = time.perf_counter() - start
```

**Isolation strategy**:
1. Clone `continuedev/continue` repository
2. Extract indexing module dependencies
3. Create standalone Python script that imports only indexing components
4. Mock IDE-specific interfaces (VSCode/JetBrains abstractions)
5. Direct database access to measure completion

**Metrics to collect**:
- Time to initial index
- SQLite database size
- Number of chunks created
- Time per incremental update (1, 10, 100 file changes)

---

### 2. Bloop (Open Source - CLI Available)

**Architecture**:
- **GitHub**: `BloopAI/bloop`
- **Technology**: Rust-based, Tantivy (search index), Qdrant (vector DB)
- **CLI**: `bleep` command-line tool

**Benchmarking approach**:

```bash
# Bloop indexing benchmark script
#!/bin/bash

REPO_PATH="/path/to/test/repo"
INDEX_DIR="/tmp/bloop_benchmark_index"

# Clean start
rm -rf "$INDEX_DIR"

# Start bleep server with indexing
time bleep \
    --source-dir "$REPO_PATH" \
    --index-dir "$INDEX_DIR" \
    --disable-background \
    --disable-fsevents \
    2>&1 | tee bloop_index.log

# Extract metrics from logs/index
echo "Index size: $(du -sh $INDEX_DIR)"
echo "Files indexed: $(grep -c 'indexed' bloop_index.log)"
```

**Metrics to collect**:
- Time to initial index (from logs or instrumentation)
- Tantivy index size
- Qdrant vector database size
- Number of files/chunks indexed

**Challenges**:
- Bloop designed as desktop app; CLI may have limited instrumentation
- May need to parse logs for timing data or instrument Rust code directly

---

### 3. Cursor (Limited - Requires IDE Automation)

**Architecture**:
- **Proprietary**: Closed source
- **Indexing**: Automatic on project open
- **No API**: Indexing happens within IDE, no programmatic access

**Benchmarking approach** (if pursued):

```python
# Cursor automation via UI scripting (fragile, not recommended)
import pyautogui
import time
from pathlib import Path

def benchmark_cursor_indexing(repo_path):
    # 1. Close Cursor
    os.system("killall Cursor")

    # 2. Clear Cursor cache/index
    cursor_cache = Path.home() / ".cursor" / "index"
    shutil.rmtree(cursor_cache, ignore_errors=True)

    # 3. Open Cursor with project
    start = time.perf_counter()
    os.system(f"cursor {repo_path}")

    # 4. Wait for indexing to complete (FRAGILE - no reliable signal)
    # Could monitor:
    # - Network traffic to Cursor servers
    # - Status bar text (via OCR or accessibility API)
    # - File system changes in cache directory

    # This approach is unreliable and not recommended
```

**Recommendation**: **Exclude Cursor from automated benchmarks**
- No reliable way to measure indexing completion
- Requires network access (remote embeddings)
- IDE automation is fragile and non-reproducible
- Alternative: Manual testing with stopwatch, documented but not automated

---

### 4. CodeWeaver (Full Control)

**Architecture**:
- **Technology**: Tree-sitter (26 langs), delimiter chunking (170+ langs)
- **CLI**: `codeweaver` command (assuming CLI exists)
- **MCP Server**: Can be tested via MCP protocol or direct API

**Benchmarking approach**:

```python
# CodeWeaver benchmark using Python API
from codeweaver.engine.indexer import Indexer
from codeweaver.config import Settings
import time

# Configure for indexing-only test
settings = Settings(
    embedding_provider="local",  # Or none for indexing-only
    vector_store="in-memory",
    chunker_strategy="semantic",  # Tree-sitter where available
)

indexer = Indexer(
    project_path="/path/to/test/repo",
    settings=settings
)

# Measure core indexing (no embeddings)
start = time.perf_counter()
index_result = indexer.index()
indexing_time = time.perf_counter() - start

# Measure with embeddings (consistent provider across tests)
settings.embedding_provider = "voyage"
settings.embedding_model = "voyage-code-2"

start = time.perf_counter()
index_with_embeddings = indexer.index(generate_embeddings=True)
total_time = time.perf_counter() - start

# Measure incremental update
modify_file("/path/to/test/repo/src/main.py")
start = time.perf_counter()
indexer.update()
update_time = time.perf_counter() - start
```

**Metrics to collect**:
- Indexing time (core, no embeddings)
- Indexing time (with embeddings, by provider)
- Number of chunks created
- AST parsing success rate (% of files parsed semantically vs delimiter fallback)
- Incremental update times
- Memory usage (peak, average)
- Disk space (index + vector store)

---

## Test Repository Selection Strategy

### Goals:
1. **Variety**: Different languages, sizes, complexity levels
2. **Realism**: Real-world codebases, not synthetic
3. **Reproducibility**: Publicly accessible GitHub repos
4. **Coverage**: Test edge cases (very small, very large, multi-language)

### Benchmark Repository Suite

| Category | Repository | LOC | Languages | Complexity | Rationale |
|----------|-----------|-----|-----------|-----------|-----------|
| **Tiny** | `flask/click` | ~5k | Python | Low | Fast baseline, single language |
| **Small** | `CodeWeaver` | ~77k | Python | Medium | Self-hosting test |
| **Medium** | `fastapi/fastapi` | ~50k | Python | Medium | Real-world API framework |
| **Medium-Multi** | `microsoft/TypeScript` | ~500k | TypeScript | High | Multi-file, complex AST |
| **Large** | `torvalds/linux` (subset) | ~1M+ | C | Very high | Kernel code, stress test |
| **Multi-language** | `vercel/next.js` | ~300k | TypeScript, JavaScript, CSS | Medium | Modern web stack |
| **Monorepo** | `googleapis/google-cloud-python` | ~500k+ | Python | Medium | Large monorepo structure |

### Alternative: Standardized Benchmark Datasets

Use established code search benchmarks for consistency with academic research:

1. **CodeSearchNet** (GitHub)
   - 6M methods from Go, Java, JavaScript, PHP, Python, Ruby
   - Already used for code search evaluation
   - Can extract subsets for indexing tests

2. **CoIR Benchmark** (Code Information Retrieval)
   - 10 distinct datasets
   - Designed for code search evaluation
   - Varying sizes and languages

### Synthetic Benchmarks (Optional)

Generate repos with controlled characteristics:

```python
# Synthetic repo generator for stress testing
def generate_test_repo(
    num_files: int,
    avg_loc_per_file: int,
    language: str,
    nesting_depth: int
):
    # Generate files with:
    # - Controlled LOC
    # - Controlled AST complexity (nesting depth)
    # - Controlled number of functions/classes
    # Purpose: Isolate impact of specific characteristics
```

**Use cases**:
- Test chunker performance on deeply nested code
- Test incremental update on repos with 10,000+ files
- Test multi-language normalization across language families

---

## Metrics & Measurement Methodology

### Primary Metrics

#### 1. Indexing Speed

**Core indexing time** (no embeddings):
```
T_core = time(file_discovery + AST_parsing + chunking + index_structure)
```

**With embeddings**:
```
T_total = T_core + time(embedding_generation + vector_store_insertion)
```

**Measurement**:
- Start: First file read
- End: Index ready for search queries
- Resolution: Microseconds (Python `time.perf_counter()`)
- Runs: 5 iterations, report median and std dev

#### 2. Incremental Update Speed

**Scenarios**:
- 1 file modified (small change, e.g., 10 LOC)
- 10 files modified (medium change)
- 100 files modified (large refactor)
- 1 file added
- 1 file deleted
- 1 file moved (test deduplication)

**Measurement**:
```
T_update = time(detect_change + reindex_affected + update_vector_store)
```

#### 3. Resource Consumption

**Memory**:
- Peak resident set size (RSS)
- Average RSS during indexing
- Memory per 1000 LOC indexed

**CPU**:
- CPU utilization (% of 1 core)
- Total CPU time (multi-threaded tools)

**Disk I/O**:
- Bytes read
- Bytes written
- Index size on disk

**Measurement tools**:
- Linux: `/usr/bin/time -v` for detailed resource stats
- Python: `psutil` library for programmatic monitoring
- Docker: Container resource limits for controlled environment

#### 4. Index Quality Metrics

**Chunking quality**:
- Average chunk size (tokens/lines)
- Number of chunks per file
- Semantic boundary preservation (manual inspection sample)

**Language coverage**:
- % of files parsed with AST (vs fallback)
- Languages detected
- Parse error rate

**Index structure**:
- Total index size (bytes)
- Index size per 1000 LOC
- Compression ratio

### Secondary Metrics

#### 5. Search Accuracy (Future)

While not indexing speed, accuracy is crucial for competitive comparison:

**Metrics**:
- Recall@k (k=1,5,10): % of relevant results in top-k
- Mean Reciprocal Rank (MRR): Position of first relevant result
- nDCG (normalized Discounted Cumulative Gain): Ranking quality

**Benchmark queries**: Use CodeSearchNet or CoIR benchmark queries

**Note**: This requires separate evaluation, not part of indexing benchmark

---

## Benchmarking Pipeline Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Benchmark Orchestrator                     │
│  - Repo cloning & preparation                            │
│  - Tool-specific harnesses                               │
│  - Metric collection                                     │
│  - Result aggregation & reporting                        │
└───────────────┬─────────────────────────────────────────┘
                │
    ┌───────────┼───────────┬──────────────┬───────────┐
    │           │           │              │           │
    ▼           ▼           ▼              ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐ ┌──────────┐
│CodeWvr │ │Continue│ │ Bloop  │ │  Cursor      │ │ Custom   │
│Harness │ │Harness │ │Harness │ │  (Manual)    │ │ Baseline │
└────┬───┘ └───┬────┘ └───┬────┘ └──────────────┘ └────┬─────┘
     │         │          │                            │
     └─────────┴──────────┴────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Metrics Database    │
              │   (SQLite/PostgreSQL) │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Visualization &      │
              │  Report Generation    │
              │  - Charts             │
              │  - Tables             │
              │  - Statistical tests  │
              └───────────────────────┘
```

### Component Details

#### Benchmark Orchestrator

**Responsibilities**:
1. Clone/prepare test repositories
2. Invoke tool-specific harnesses
3. Collect metrics from each run
4. Store results in database
5. Generate comparative reports

**Implementation**:
```python
# benchmark_orchestrator.py
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

@dataclass
class BenchmarkConfig:
    repo_url: str
    repo_name: str
    commit_hash: str  # For reproducibility
    loc: int
    languages: list[str]

@dataclass
class BenchmarkResult:
    tool: str
    repo: str
    core_indexing_time: float
    total_indexing_time: float
    peak_memory_mb: float
    index_size_mb: float
    chunks_created: int
    timestamp: str

class BenchmarkOrchestrator:
    def __init__(self, config_file: Path):
        self.repos = self.load_benchmark_repos(config_file)
        self.tools = {
            "codeweaver": CodeWeaverHarness(),
            "continue": ContinueHarness(),
            "bloop": BloopHarness(),
        }

    def run_benchmark(self, repo: BenchmarkConfig, tool_name: str) -> BenchmarkResult:
        # 1. Prepare clean environment
        repo_path = self.clone_repo(repo)

        # 2. Run tool-specific harness
        harness = self.tools[tool_name]
        result = harness.benchmark(repo_path)

        # 3. Cleanup
        self.cleanup(repo_path, harness)

        return result

    def run_all_benchmarks(self):
        results = []
        for repo in self.repos:
            for tool_name in self.tools:
                # Run multiple iterations
                for iteration in range(5):
                    result = self.run_benchmark(repo, tool_name)
                    results.append(result)

        # Store and analyze
        self.store_results(results)
        self.generate_report(results)
```

#### Tool-Specific Harnesses

Each tool gets a harness that provides a uniform interface:

```python
# harness_base.py
from abc import ABC, abstractmethod
from pathlib import Path

class BenchmarkHarness(ABC):
    @abstractmethod
    def setup(self, repo_path: Path):
        """Prepare tool for benchmarking (install, configure)"""
        pass

    @abstractmethod
    def benchmark(self, repo_path: Path) -> BenchmarkResult:
        """Run indexing and collect metrics"""
        pass

    @abstractmethod
    def cleanup(self, repo_path: Path):
        """Remove indexes, caches, temp files"""
        pass

# harness_codeweaver.py
class CodeWeaverHarness(BenchmarkHarness):
    def setup(self, repo_path: Path):
        # Configure CodeWeaver for benchmark mode
        self.config = {
            "embedding_provider": None,  # Indexing only
            "vector_store": "in-memory",
        }

    def benchmark(self, repo_path: Path) -> BenchmarkResult:
        from codeweaver.engine.indexer import Indexer
        import psutil
        import time

        indexer = Indexer(repo_path, self.config)

        # Monitor resources
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run indexing
        start = time.perf_counter()
        index_result = indexer.index()
        duration = time.perf_counter() - start

        # Collect metrics
        peak_memory = process.memory_info().rss / 1024 / 1024

        return BenchmarkResult(
            tool="CodeWeaver",
            repo=repo_path.name,
            core_indexing_time=duration,
            peak_memory_mb=peak_memory - initial_memory,
            chunks_created=index_result.num_chunks,
            # ... other metrics
        )
```

#### Metrics Storage

**Schema**:
```sql
CREATE TABLE benchmark_runs (
    id INTEGER PRIMARY KEY,
    tool TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    repo_commit TEXT NOT NULL,
    repo_loc INTEGER,
    iteration INTEGER,
    timestamp TEXT,

    -- Timing metrics
    core_indexing_time_sec REAL,
    total_indexing_time_sec REAL,

    -- Resource metrics
    peak_memory_mb REAL,
    avg_memory_mb REAL,
    cpu_time_sec REAL,
    disk_read_mb REAL,
    disk_write_mb REAL,

    -- Index metrics
    index_size_mb REAL,
    chunks_created INTEGER,
    files_indexed INTEGER,
    ast_parse_success_rate REAL,

    -- Incremental update metrics
    update_1_file_sec REAL,
    update_10_files_sec REAL,
    update_100_files_sec REAL
);

CREATE INDEX idx_tool_repo ON benchmark_runs(tool, repo_name);
```

---

## Automation Strategy

### Docker-Based Reproducibility

**Benefits**:
- Consistent environment across machines
- Isolated dependencies
- Resource limits (CPU, memory)
- Easy parallelization

**Dockerfile structure**:
```dockerfile
# benchmark.Dockerfile
FROM ubuntu:22.04

# Install common dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    nodejs \
    git \
    time \
    && rm -rf /var/lib/apt/lists/*

# Install benchmarking tools
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Install each tool
RUN pip install codeweaver
RUN git clone https://github.com/continuedev/continue && cd continue && npm install
RUN cargo install bleep  # Bloop CLI

# Copy benchmark scripts
COPY benchmark/ /benchmark/
WORKDIR /benchmark

CMD ["python3", "orchestrator.py", "--config", "benchmark_config.yaml"]
```

**Run benchmark**:
```bash
# Build
docker build -f benchmark.Dockerfile -t codeweaver-benchmark .

# Run with resource limits
docker run \
    --cpus="4" \
    --memory="8g" \
    --volume $(pwd)/results:/benchmark/results \
    codeweaver-benchmark

# Results written to ./results/
```

### CI/CD Integration

**GitHub Actions workflow**:
```yaml
# .github/workflows/benchmark.yml
name: Indexing Benchmark

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  benchmark:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Build benchmark environment
      run: docker build -f benchmark.Dockerfile -t bench .

    - name: Run benchmarks
      run: |
        docker run \
          --cpus="4" \
          --memory="8g" \
          -v $(pwd)/results:/results \
          bench

    - name: Generate report
      run: python scripts/generate_report.py results/

    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: benchmark-results
        path: results/

    - name: Comment PR with results (if PR)
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          // Parse results and post comment
```

### Parallelization

Run benchmarks concurrently for different repos/tools:

```python
# parallel_benchmark.py
from concurrent.futures import ProcessPoolExecutor, as_completed
from benchmark_orchestrator import BenchmarkOrchestrator

def run_single_benchmark(tool, repo):
    orchestrator = BenchmarkOrchestrator()
    return orchestrator.run_benchmark(repo, tool)

def run_parallel_benchmarks(tools, repos, max_workers=4):
    tasks = [(tool, repo) for tool in tools for repo in repos]
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single_benchmark, tool, repo): (tool, repo)
            for tool, repo in tasks
        }

        for future in as_completed(futures):
            tool, repo = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"✓ {tool} on {repo.name}: {result.core_indexing_time:.2f}s")
            except Exception as e:
                print(f"✗ {tool} on {repo.name}: {e}")

    return results
```

---

## Report Generation

### Comparative Charts

**1. Indexing Time Comparison** (bar chart)
- X-axis: Repository (sorted by LOC)
- Y-axis: Time (seconds, log scale)
- Bars: One per tool, grouped by repo
- Error bars: Standard deviation across 5 runs

**2. Indexing Speed by LOC** (scatter plot)
- X-axis: LOC (log scale)
- Y-axis: Indexing time (log scale)
- Points: Each run, color-coded by tool
- Trend lines: Linear regression for each tool

**3. Resource Efficiency** (multi-axis chart)
- X-axis: Repository
- Y-axis 1: Peak memory (MB)
- Y-axis 2: Index size (MB)
- Bars: Stacked or grouped by tool

**4. Incremental Update Performance** (line chart)
- X-axis: Number of files changed (1, 10, 100)
- Y-axis: Update time (seconds)
- Lines: One per tool

### Statistical Analysis

**Tests**:
- **Paired t-test**: Is CodeWeaver significantly faster than Continue.dev?
- **ANOVA**: Are differences across all tools statistically significant?
- **Effect size**: Cohen's d for practical significance

**Report format**:
```markdown
## Benchmark Results: CodeWeaver vs. Competitors

### Summary Statistics

| Tool | Mean Indexing Time (s) | Median | Std Dev | 95% CI |
|------|------------------------|--------|---------|--------|
| CodeWeaver | 3.42 | 3.38 | 0.15 | [3.27, 3.57] |
| Continue.dev | 4.87 | 4.92 | 0.31 | [4.56, 5.18] |
| Bloop | 5.12 | 5.09 | 0.24 | [4.88, 5.36] |

**CodeWeaver is 29.8% faster than Continue.dev (p < 0.001, Cohen's d = 5.23)**

### By Repository Size

#### Small Repos (<10k LOC)
- CodeWeaver: 0.52s ± 0.03
- Continue.dev: 0.71s ± 0.05
- Bloop: 0.68s ± 0.04

#### Medium Repos (10k-100k LOC)
- CodeWeaver: 3.21s ± 0.12
- Continue.dev: 4.53s ± 0.28
- Bloop: 4.89s ± 0.21

[Charts embedded here]
```

### Implementation

```python
# report_generator.py
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

class BenchmarkReporter:
    def __init__(self, results_db: Path):
        self.df = pd.read_sql("SELECT * FROM benchmark_runs", results_db)

    def generate_comparison_table(self):
        # Group by tool, compute statistics
        summary = self.df.groupby('tool').agg({
            'core_indexing_time_sec': ['mean', 'median', 'std'],
            'peak_memory_mb': ['mean', 'median'],
            'index_size_mb': ['mean'],
        })
        return summary

    def plot_indexing_time_comparison(self):
        plt.figure(figsize=(12, 6))
        sns.barplot(data=self.df, x='repo_name', y='core_indexing_time_sec', hue='tool')
        plt.yscale('log')
        plt.title('Indexing Time Comparison')
        plt.ylabel('Time (seconds, log scale)')
        plt.xlabel('Repository')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('indexing_time_comparison.png')

    def statistical_tests(self):
        # Paired t-test: CodeWeaver vs Continue.dev
        cw = self.df[self.df['tool'] == 'CodeWeaver']['core_indexing_time_sec']
        cont = self.df[self.df['tool'] == 'Continue.dev']['core_indexing_time_sec']

        t_stat, p_value = stats.ttest_rel(cw, cont)
        cohens_d = (cw.mean() - cont.mean()) / cw.std()

        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'cohens_d': cohens_d,
            'percent_faster': ((cont.mean() - cw.mean()) / cont.mean()) * 100
        }
```

---

## Implementation Phases

### Phase 1: Proof of Concept (1-2 weeks)

**Goals**:
- Establish baseline benchmarking infrastructure
- Validate approach with 1-2 tools

**Deliverables**:
1. Docker environment with CodeWeaver + Continue.dev
2. Simple orchestrator script (Python)
3. Manual benchmark on 3 repos (small, medium, large)
4. Basic comparison table

**Success criteria**:
- Reproducible results across 3 runs
- <10% variance in timing measurements

### Phase 2: Automation & Coverage (2-3 weeks)

**Goals**:
- Automate full benchmark suite
- Add Bloop and other tools
- Expand repo coverage

**Deliverables**:
1. Automated orchestrator with all harnesses
2. 7+ test repositories
3. Metrics database + schema
4. Incremental update benchmarks

**Success criteria**:
- One-command execution of full benchmark suite
- All metrics collected automatically

### Phase 3: CI/CD Integration (1 week)

**Goals**:
- Integrate into development workflow
- Automated regression detection

**Deliverables**:
1. GitHub Actions workflow
2. Automated report generation
3. PR comments with benchmark deltas

**Success criteria**:
- Benchmark runs on every commit to main
- Alerts if performance regresses >10%

### Phase 4: Public Release & Documentation (1 week)

**Goals**:
- Make benchmark suite public
- Enable community contributions

**Deliverables**:
1. Public GitHub repo for benchmark suite
2. Comprehensive documentation
3. Published baseline results
4. Blog post with methodology

**Success criteria**:
- External contributors can reproduce results
- Cited in product documentation/marketing

---

## Challenges & Mitigation Strategies

### Challenge 1: Embedding Provider Variability

**Problem**: Different tools use different embedding providers, making total indexing time incomparable

**Mitigation**:
1. **Primary metric**: Core indexing time (excludes embeddings)
2. **Standardized test**: All tools configured to use same provider (Voyage Code-2 API)
3. **Separate embeddings benchmark**: Test CodeWeaver with multiple providers, publish independently

### Challenge 2: Tool Configuration Differences

**Problem**: Tools have many configuration options affecting performance

**Mitigation**:
1. **Document all configurations** in benchmark results
2. **Test multiple configs**: Default vs optimized for each tool
3. **Fair optimization**: Allow each tool's "best configuration" for speed

### Challenge 3: Cursor Not Benchmarkable

**Problem**: Cursor has no API, requires IDE automation

**Mitigation**:
1. **Exclude from automated benchmark**
2. **Manual testing**: Document methodology, include results with caveats
3. **Focus on open-source**: CodeWeaver vs Continue.dev vs Bloop is still valuable

### Challenge 4: Cold Start vs Warm Cache

**Problem**: First run vs subsequent runs have different performance

**Mitigation**:
1. **Test both scenarios**: Cold start (clean environment) and warm cache
2. **Document clearly**: Specify which scenario is reported
3. **Recommendation**: Report cold start (more realistic for new projects)

### Challenge 5: Hardware Variability

**Problem**: Different machines produce different results

**Mitigation**:
1. **Docker with resource limits**: Normalize CPU/memory available
2. **Use CI runners**: Standardized GitHub Actions environment
3. **Document hardware**: Include specs in all reports

### Challenge 6: Network Variability (for remote embeddings)

**Problem**: API latency varies, affects total time

**Mitigation**:
1. **Separate core vs total time**
2. **Local embeddings**: Use local providers for controlled comparison
3. **Network simulation**: Use tools like `tc` (traffic control) to simulate consistent latency

---

## Expected Outcomes

### Benchmark Results Format

```markdown
# CodeWeaver Indexing Benchmark Results

**Date**: 2025-11-17
**Environment**: GitHub Actions (ubuntu-latest, 4 CPU, 8GB RAM)
**Repositories**: 7 repos, ranging from 5k to 500k LOC

## Summary

CodeWeaver demonstrates **29.8% faster indexing** than Continue.dev and **33.1% faster** than Bloop across all test repositories (p < 0.001).

### Performance by Repository Size

| Repo Size | CodeWeaver | Continue.dev | Bloop | Advantage |
|-----------|-----------|--------------|-------|-----------|
| Small (<10k LOC) | 0.52s | 0.71s | 0.68s | **26.8% faster** |
| Medium (10-100k LOC) | 3.21s | 4.53s | 4.89s | **29.1% faster** |
| Large (>100k LOC) | 18.7s | 26.3s | 29.1s | **28.9% faster** |

### Incremental Update Performance

| Scenario | CodeWeaver | Continue.dev | Bloop |
|----------|-----------|--------------|-------|
| 1 file changed | 0.08s | 0.14s | 0.12s |
| 10 files changed | 0.31s | 0.52s | 0.48s |
| 100 files changed | 2.41s | 3.87s | 4.12s |

**CodeWeaver's incremental updates are 42.9% faster** (1 file) to 37.8% faster (100 files).

### Resource Efficiency

| Metric | CodeWeaver | Continue.dev | Bloop |
|--------|-----------|--------------|-------|
| Peak Memory (MB) | 342 | 487 | 521 |
| Index Size (MB) | 12.3 | 18.7 | 22.1 |
| Memory per 1k LOC | 4.4 MB | 6.3 MB | 6.7 MB |

**CodeWeaver uses 29.8% less memory** and produces **34.2% smaller indexes**.

[Detailed charts follow]
```

---

## Conclusion

This benchmarking strategy provides a **comprehensive, reproducible, and fair methodology** for comparing CodeWeaver's indexing performance against competitors.

### Key Strengths:

1. **Reproducibility**: Docker-based, automated, version-controlled
2. **Fairness**: Standardized repos, consistent configuration, statistical rigor
3. **Comprehensiveness**: Multiple metrics beyond raw speed
4. **Practicality**: Focus on benchmarkable tools (open-source)
5. **Automation**: CI/CD integration, minimal manual effort

### Next Steps:

1. **Immediate**: Implement Phase 1 (PoC with CodeWeaver + Continue.dev)
2. **Short-term**: Expand to full suite (Phase 2)
3. **Ongoing**: CI/CD integration, public release (Phases 3-4)

### Success Metrics:

- ✅ Reproducible results (<10% variance)
- ✅ Statistical significance in performance differences
- ✅ Public benchmark suite for community validation
- ✅ Cited in CodeWeaver product documentation

This benchmark will establish CodeWeaver as the **fastest code indexing tool** with **quantifiable, independently verifiable evidence**.

---

**Document Version**: 1.0
**Last Updated**: November 17, 2025
**Status**: Ready for implementation
