---
name: wiki-lint
description: >-
  Audits and repairs the Obsidian + LLM-Wiki vault health. Use this skill when
  the user requests a vault health check, link validation, orphan detection,
  index synchronization, contradiction audit, or invokes /wiki-lint.
---

# `/wiki-lint` — Vault Health Check & Automated Repair

Combines deterministic link/index verification (`Meta/scripts/vault_health.py`) with an LLM semantic audit for contradictions, missing citations, and stale claims.

## Execution Workflow

### 1. Deterministic Structural Scan
Execute the local zero-token health script:
```bash
python3 Meta/scripts/vault_health.py --report Meta/health-report.md
```
To automatically synchronize missing `wiki/` pages into `wiki/index.md` and get the machine-readable payload:
```bash
python3 Meta/scripts/vault_health.py --fix-index --report Meta/health-report.md --json
```

The script inspects the vault for:
- **Broken `[[wikilinks]]`** and broken relative markdown links `([Title](path.md))`.
- **Dual-Link Violations** in `wiki/` (wikilinks missing a companion markdown link or vice versa).
- **Orphan Pages** in `wiki/concepts/`, `wiki/entities/`, and `wiki/topics/` with zero inbound links outside `wiki/index.md` and `wiki/log.md`.
- **Index Drift**: Pages in `wiki/` missing from `wiki/index.md`, or dead links in `wiki/index.md`.
- **Missing Frontmatter**: `wiki/` or `raw/` notes lacking required YAML frontmatter (`title`, `tags`, `sources` / `ingest_date`).

### 2. Semantic LLM Audit Pass
Inspect the JSON payload from `vault_health.py` and review modified or flagged `wiki/` pages to detect:
1. **Factual Contradictions**: Conflicting claims across two or more `wiki/` pages that lack a `[!WARNING] Contradiction Flag`.
2. **Unsourced Claims**: Assertions in `wiki/` that do not cite a source in `sources:` frontmatter or inline text.
3. **Orphan Integration**: Add cross-references from related `wiki/topics/`, `wiki/concepts/`, or `wiki/entities/` pages to connect orphan nodes into the knowledge graph using the dual-link standard:
   `[[target-page|Display Title]] ([Display Title](../path/target-page.md))`

### 3. Apply Automated Repairs & Update Report
1. Fix broken links, dual-link formatting, and missing frontmatter in `wiki/` (never edit files in `raw/`).
2. Re-run `python3 Meta/scripts/vault_health.py --fix-index --report Meta/health-report.md` to confirm a clean health score and update `Meta/health-report.md` with any semantic findings.
3. Append a maintenance entry to `wiki/log.md`:
   ```markdown
   ## [YYYY-MM-DD] lint | Vault Health Audit
   - Executed `vault_health.py` and semantic consistency pass.
   - Report written to `Meta/health-report.md`.
   ```
4. If Git auto-sync is requested, run:
   `python3 Meta/scripts/git_auto_sync.py --action lint`
