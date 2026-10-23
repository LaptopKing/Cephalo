# Cephalo System Architecture

Cephalo strictly decouples **high-order agent reasoning** (Antigravity, Claude Code, Cursor) from **sovereign local data storage, multi-tier privacy scrubbing, and cognitive reflex execution**.

## High-Level Execution Topology

```mermaid
flowchart TD
    User["User / Agent Prompt"] --> Harness["AI Agent Harness
(Antigravity / Claude Code / Cursor)"]
    
    subgraph SovereignCore ["Cephalo Sovereign Core (Local Hardware)"]
        Harness --> CLI["Universal CLI (brain.py)"]
        
        CLI --> Sanitizer["Multi-Tier Privacy Shield
(Regex + Entropy + AST + GLiNER)"]
        
        Sanitizer --> FastEmbed["FastEmbed Local ONNX
(Qwen 1024d / Zero Cloud API)"]
        FastEmbed --> LanceDB[("LanceDB Columnar Vector Store
(Native Dense + BM25 FTS)")]
        
        CLI --> Patterns["Cognitive Patterns Engine
(extract_wisdom, review_code, etc.)"]
        CLI --> WebCrawler["Dynamic Web & YouTube Crawler
(Playwright Chromium / Transcript API)"]
        CLI --> Context["Dynamic Context Assembler
(USER_PROFILE.md + Specialties)"]
        
        WebCrawler --> Sanitizer
    end
    
    LanceDB -->|"Injected Context / JSON"| Harness
```

## Key Architectural Principles

1. **Local-First Sovereignty:**
   All vector computations (FastEmbed Qwen 1024d) and tabular storage (LanceDB) execute directly in-process via ONNX Runtime and Apache Arrow zero-copy memory. Zero monthly bills, zero per-token embedding costs, zero data leaving your machine.

2. **Zero-Leak Privacy Shield:**
   Every string ingested into Cephalo passes through a deterministic regex filter (tax IDs, IBANs, Hungarian PII), Shannon entropy guards (stripping high-entropy API tokens), and local named-entity masking before writing to disk.

3. **Unix-Philosophy Ergonomics:**
   All commands support `stdin` streaming (`cat file | cephalo record`), Windows clipboard reading/writing (`--clip`, `--copy`), and structured output (`--json`).
