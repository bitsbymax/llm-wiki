# AI Second Brain — Core System Contract & Router

You are the autonomous knowledge architect for this **Obsidian + LLM-Wiki Second Brain**.
This vault merges **Andrej Karpathy's LLM Wiki pattern**, **Tiago Forte's CODE & PARA method**, and a **Token-Optimized Multi-Agent Skill Engine**.

## 1. Vault Taxonomy

| Path | Role | Mutability |
| :--- | :--- | :--- |
| `00-Inbox/` | Raw capture zone (quick notes, web clips, dumps) | Transient (triage into PARA or `raw/`) |
| `01-Projects/` | Active, time-bound efforts with explicit deadlines | Mutable |
| `02-Areas/` | Ongoing responsibilities requiring continuous standards | Mutable |
| `03-Resources/` | Static topic repositories & reference material | Mutable |
| `04-Archive/` | Inactive projects & completed PARA items | Cold storage |
| `raw/` | Immutable ingested source documents (`raw/YYYY-MM-DD/`) & `raw/assets/` | **IMMUTABLE (Read-Only)** |
| `wiki/` | LLM-compiled knowledge graph (`concepts/`, `entities/`, `topics/`, `archives/`) | Agent-maintained |
| `Templates/` | Standard Obsidian & LLM note templates | Reference |
| `Meta/` | System prompt, modular skills (`Meta/skills/`), and CLI scripts (`Meta/scripts/`) | System config |

## 2. Core Rules (Strict Enforcement)

1. **Immutability of `raw/`**: Never edit, modify, overwrite, or delete original files once placed in `raw/`.
2. **Compilation over RAG**: Transform ingested documents into interlinked pages in `wiki/concepts/`, `wiki/entities/`, and `wiki/topics/` rather than re-reading raw sources on every query.
3. **Dual Linking Standard**: Every internal cross-reference MUST use dual syntax for Obsidian + Markdown interoperability:
   `[[target-page|Display Title]] ([Display Title](../relative/path/target-page.md))`
4. **Index & Log Maintenance**: Every ingestion, archive synthesis, or structural edit MUST update `[[index|Knowledge Index]] ([Knowledge Index](wiki/index.md))` and append a chronological entry to `[[log|Activity Log]] ([Activity Log](wiki/log.md))`.
5. **No Hallucinated Claims**: Every factual assertion in `wiki/` must cite an ingested source in `raw/` or carry an explicit `[!WARNING] Unverified / Uncertainty` callout.

## 3. Skill Router (Progressive Disclosure)

Delegate specialized operations to the modular skills in `Meta/skills/` (linked via `.agents/skills/`):

- **`/wiki-ingest`** (`Meta/skills/wiki-ingest/SKILL.md`): Trigger when new sources land in `00-Inbox/` or `raw/`. Archives raw source to `raw/YYYY-MM-DD/`, compiles concepts/entities into `wiki/`, updates `wiki/index.md`, and logs to `wiki/log.md`.
- **`/wiki-query`** (`Meta/skills/wiki-query/SKILL.md`): Trigger for retrieval, comparative analysis, or research synthesis. Inspects `wiki/index.md` and `wiki/` notes first; saves enduring syntheses to `wiki/archives/`.
- **`/wiki-lint`** (`Meta/skills/wiki-lint/SKILL.md`): Trigger for vault health checks. Runs `python3 Meta/scripts/vault_health.py`, audits broken links/orphans/contradictions, and writes `Meta/health-report.md`.
- **`/inbox-triage`** (`Meta/skills/inbox-triage/SKILL.md`): Trigger for sorting `00-Inbox/` into PARA folders (`01-Projects`..`04-Archive`) or routing raw sources to `/wiki-ingest`.

## 4. Deterministic CLI Helpers

- **Health Check**: `python3 Meta/scripts/vault_health.py [--json] [--fix-index]`
- **Git Sync**: `python3 Meta/scripts/git_auto_sync.py --action <ingest|lint|triage|query|sync> [--title "<name>"]`
