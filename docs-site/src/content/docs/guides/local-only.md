# Local-Only Operation

> **TL;DR:** CodeWeaver Alpha 6 can run 100% locally with zero internet dependencies. Use it for airgapped environments or sensitive codebases where privacy is paramount. It saves your data from leaving your network while still providing high-quality semantic search.

Many of our users work on proprietary or sensitive projects that cannot be shared with cloud-based AI providers. CodeWeaver is built with a **Privacy-First** architecture, allowing you to run all indexing, search, and storage locally on your own hardware.

---

## 1. Fast Setup: The `quickstart` Profile

The easiest way to go local is by using the `quickstart` profile during initialization. This profile configures CodeWeaver to use local-only embedding and vector store providers.

```bash
cw init --profile quickstart
```

**What this profile enables:**
- **Local Embedding:** [FastEmbed](https://qdrant.github.io/fastembed/) (highly optimized for CPU/GPU).
- **Local Search:** [Sentence-Transformers](https://sbert.net/) for high-precision local semantics.
- **Local Storage:** An embedded [Qdrant](https://qdrant.tech) instance running as a background service or in-memory.

---

## 2. Airgapped Environments

CodeWeaver is fully functional in completely airgapped environments (no internet access).

### Model Pre-loading
In a standard `quickstart` setup, CodeWeaver will attempt to download its local models once during the first run. For a true airgapped setup, you can pre-load these models into your environment:

1.  **Download on an internet-connected machine:**
    ```bash
    cw models download --all
    ```
2.  **Transfer to your airgapped machine:** Move the contents of `~/.cache/huggingface` and `~/.cache/fastembed` to the corresponding directories on your local machine.

---

## 3. High Performance on Local Hardware

Local-only operation doesn't mean slow search. CodeWeaver leverages specialized runtimes to ensure your queries are fast:

- **ONNX Runtime:** FastEmbed uses ONNX for blazing-fast inference on almost any CPU.
- **Quantization:** Local models are automatically quantized to reduce memory usage without sacrificing accuracy.
- **Hybrid Search:** Even in local mode, CodeWeaver uses its "Hybrid Search" pipeline (Keyword + Semantic) to provide "Exquisite Context."

---

## 4. Why Go Local?

- **Privacy & Security:** Your source code never leaves your local network or machine.
- **Zero API Costs:** No monthly bills or rate limits from cloud providers.
- **Offline Reliability:** Search your code in the air, on a train, or in a high-security bunker.
- **Predictable Performance:** No network latency means consistent, ultra-fast search results.

---

## Summary: Industrial-Grade Privacy

CodeWeaver Alpha 6 ensures that privacy doesn't have to come at the cost of intelligence. By using its local-only mode, you can give your AI agents deep structural and semantic context without compromising your most sensitive data.
