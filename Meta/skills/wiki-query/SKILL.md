---
name: wiki-query
description: >-
  Queries the compiled LLM Wiki to answer questions, perform comparative analyses,
  and synthesize research briefs. Use this skill when the user asks a domain
  question, requests a synthesis across vault knowledge, or invokes /wiki-query.
---

# `/wiki-query` — Knowledge Retrieval & Synthesis

Answers complex queries by traversing the compiled knowledge graph in `wiki/` first (Compilation over RAG), reading raw sources only when deep verification is required, and archiving high-value syntheses back into the vault.

## Execution Workflow

### 1. Fast Index & Graph Lookup
1. Read `wiki/index.md` to locate relevant concepts, entities, topics, and past query archives.
2. Perform fast keyword/regex search across `wiki/` using available search tools (`qmd`, `rg`, or `grep -rn` over `wiki/`).
3. Prioritize reading compiled notes in `wiki/concepts/`, `wiki/entities/`, `wiki/topics/`, and `wiki/archives/`.

### 2. Selective Deep Verification
- Do **not** scan `raw/` in bulk.
- Only open a specific file in `raw/YYYY-MM-DD/` if a compiled `wiki/` page references it and the query requires exact verbatim quotes, raw figures, or resolution of a `[!WARNING] Contradiction Flag`.

### 3. Synthesize Sourced Response
1. Formulate a structured answer grounded strictly in vault notes.
2. Cite all referenced `wiki/` nodes using the **Dual Linking Standard**:
   - When writing inside `wiki/archives/`: `[[node-slug|Display Title]] ([Display Title](../concepts/node-slug.md))`
   - When replying in chat: include clickable links to the vault files.
3. Explicitly flag any inference or gap not covered by existing `wiki/` pages with `> [!WARNING] Unverified / Knowledge Gap`.

### 4. Archive High-Value Syntheses
If the query produces a durable comparative analysis, literature review, or research brief:
1. Save the synthesis to `wiki/archives/YYYY-MM-DD-<query-slug>.md`:
   ```markdown
   ---
   title: "<Query / Synthesis Title>"
   category: archive
   created: YYYY-MM-DD
   sources:
     - "wiki/concepts/<slug>.md"
   tags:
     - wiki/archive
   ---

   # <Query / Synthesis Title>

   ## Executive Synthesis
   ...

   ## Detailed Analysis
   ...

   ## Referenced Wiki Nodes
   - `[[<slug>|<Display Title>]] ([<Display Title>](../concepts/<slug>.md))`
   ```
2. Add the archived brief under `## Archives` in `wiki/index.md`:
   `- [[YYYY-MM-DD-<query-slug>|<Query Title>]] ([<Query Title>](archives/YYYY-MM-DD-<query-slug>.md)) — <1-line summary>`
3. Append an entry to `wiki/log.md`:
   ```markdown
   ## [YYYY-MM-DD] query | <Query Title>
   - Archived synthesis to `[[YYYY-MM-DD-<query-slug>|<Query Title>]] ([<Query Title>](archives/YYYY-MM-DD-<query-slug>.md))`.
   ```
