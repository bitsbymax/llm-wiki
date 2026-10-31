---
name: wiki-ingest
description: >-
  Ingests raw sources from 00-Inbox/ or raw/ into the LLM-compiled wiki. Use this
  skill when new articles, notes, clips, or documents arrive in 00-Inbox/ or raw/,
  or when the user invokes /wiki-ingest to compile source material into
  interlinked concept, entity, and topic pages.
---

# `/wiki-ingest` — Source Ingestion & Knowledge Compilation

Compiles raw source documents into structured, interlinked knowledge nodes in `wiki/` following Andrej Karpathy's LLM Wiki pattern.

## Execution Workflow

### 1. Archive & Normalize Raw Source
1. Determine today's date (`YYYY-MM-DD`).
2. Create directory `raw/YYYY-MM-DD/` if it does not exist.
3. If the source file is in `00-Inbox/` (or unarchived at the root of `raw/`), move it to `raw/YYYY-MM-DD/<slug>.md` and prepend standard YAML frontmatter if missing:
   ```yaml
   ---
   title: "<Source Title>"
   source_url: "<URL or local origin>"
   ingest_date: YYYY-MM-DD
   tags:
     - raw/source
   ---
   ```
4. **Immutability Rule**: Once placed in `raw/YYYY-MM-DD/`, treat the file as strictly **read-only**. Never modify or delete it on subsequent runs.

### 2. Extract Knowledge Units
Read the source document and extract:
- **Concepts** (`wiki/concepts/<slug>.md`): Domain theories, mental models, algorithms, architectures, or methodologies.
- **Entities** (`wiki/entities/<slug>.md`): Specific people, tools, companies, libraries, datasets, or products.
- **Topics** (`wiki/topics/<slug>.md`): High-level macro research areas grouping multiple concepts and entities.
- **Empirical Claims & Quotes**: Verifiable facts, metrics, and dates tied to the source.

### 3. Compile Into `wiki/` (Create or Merge)
Inspect `wiki/index.md` and existing files in `wiki/concepts/`, `wiki/entities/`, and `wiki/topics/`:

- **If node already exists**:
  1. Integrate new facts and claims into the relevant sections without erasing prior sourced knowledge.
  2. Append the new raw source path (`raw/YYYY-MM-DD/<slug>.md`) to the `sources:` array in YAML frontmatter.
  3. Update `updated: YYYY-MM-DD` in YAML frontmatter.
  4. **Contradiction Handling**: If the new source contradicts an existing claim, do not silently overwrite. Insert an explicit warning callout:
     ```markdown
     > [!WARNING] Contradiction Flag
     > **Source A** (`raw/...`) states X, whereas **Source B** (`raw/YYYY-MM-DD/<slug>.md`) states Y.
     ```

- **If node is new**:
  Create `wiki/<category>/<slug>.md` (refer to `Templates/Wiki-Concept.md` or `Templates/Wiki-Entity.md`):
  ```markdown
  ---
  title: "<Display Title>"
  category: concept | entity | topic
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  sources:
    - "raw/YYYY-MM-DD/<source-slug>.md"
  tags:
    - wiki/<category>
  ---

  # <Display Title>

  ## Summary
  Concise 2-3 sentence synthesis of the concept or entity.

  ## Key Claims & Breakdown
  - Detailed point citing `[[<source-slug>|Source Title]] ([Source Title](../../raw/YYYY-MM-DD/<source-slug>.md))`.

  ## Related Nodes
  - `[[related-slug|Related Title]] ([Related Title](../concepts/related-slug.md))`
  ```

### 4. Enforce Dual Linking Standard
Every cross-reference inside `wiki/` MUST use dual syntax:
`[[target-slug|Display Title]] ([Display Title](../<category>/target-slug.md))`

### 5. Synchronize Index & Activity Log
1. **Update `wiki/index.md`**:
   Add any newly created notes in alphabetical order under `## Concepts`, `## Entities`, or `## Topics` using dual links:
   `- [[<slug>|<Display Title>]] ([<Display Title>](<category>/<slug>.md)) — <1-line summary>`
2. **Append to `wiki/log.md`**:
   Append a chronological entry at the bottom of `wiki/log.md`:
   ```markdown
   ## [YYYY-MM-DD] ingest | <source_title>
   - **Source**: `[[<source-slug>|<source_title>]] ([<source_title>](../raw/YYYY-MM-DD/<source-slug>.md))`
   - **Created**: <list of new wiki nodes>
   - **Updated**: <list of updated wiki nodes>
   ```

### 6. Validate & Optional Git Sync
1. Run `python3 Meta/scripts/vault_health.py` to confirm zero broken links or index drift.
2. When auto-sync is desired, run:
   `python3 Meta/scripts/git_auto_sync.py --action ingest --title "<source_title>"`
