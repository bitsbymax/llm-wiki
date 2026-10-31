---
name: inbox-triage
description: >-
  Triages and routes raw notes and clips from 00-Inbox/ into Tiago Forte's PARA
  hierarchy (01-Projects, 02-Areas, 03-Resources, 04-Archive) or raw/ for wiki
  ingestion. Use this skill during daily review, inbox zero cleanup, or when the
  user invokes /inbox-triage.
---

# `/inbox-triage` — CODE & PARA Inbox Triage

Processes unstructured captures in `00-Inbox/` and routes each item to its proper home in Tiago Forte's **PARA** hierarchy or into `raw/` for **LLM Wiki** compilation.

## Execution Workflow

### 1. Scan `00-Inbox/`
List all `.md` and media files in `00-Inbox/` (ignoring `.gitkeep`). If `00-Inbox/` is empty, report Inbox Zero.

### 2. Classify Each Item (PARA + Raw Router)
Evaluate the content and intent of each item:

| Target Folder | Routing Criteria | Action |
| :--- | :--- | :--- |
| `01-Projects/` | Actionable, time-bound effort with a specific goal or deadline. | Standardize YAML (`status: active`, `deadline:`) & move. |
| `02-Areas/` | Ongoing sphere of responsibility (health, finances, engineering standards, daily logs). | Standardize YAML (`status: ongoing`) & move. |
| `03-Resources/` | Personal reference checklists, snippets, or static topic repositories not meant for wiki synthesis. | Standardize YAML (`status: reference`) & move. |
| `04-Archive/` | Completed, cancelled, or inactive actionable items. | Standardize YAML (`status: archived`) & move. |
| `raw/YYYY-MM-DD/` | External articles, research papers, transcripts, web clips, or domain knowledge dumps. | Hand off to **`/wiki-ingest`** (`Meta/skills/wiki-ingest/SKILL.md`). |

### 3. Standardize Metadata & Slugify Filename
For items routed to `01-Projects/`, `02-Areas/`, `03-Resources/`, or `04-Archive/`:
1. Rename the file to lowercase `kebab-case.md` (e.g., `q4-product-launch.md`).
2. Ensure the note starts with standardized YAML frontmatter (preserving existing user tags/fields):
   ```yaml
   ---
   title: "<Human-Readable Title>"
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   category: project | area | resource | archive
   status: active | ongoing | reference | archived
   tags:
     - para/<category>
   ---
   ```
3. Move any embedded media attachments from `00-Inbox/` to `raw/assets/` and update attachment links.
4. Move the note to the selected PARA directory.

### 4. Trigger `/wiki-ingest` for Research Sources
For items classified as external sources or domain knowledge dumps:
- Execute the **`/wiki-ingest`** workflow (`Meta/skills/wiki-ingest/SKILL.md`) to archive the raw file in `raw/YYYY-MM-DD/`, compile concepts/entities into `wiki/`, and update `wiki/index.md`.

### 5. Log Triage Summary
Append an operational summary to `wiki/log.md`:
```markdown
## [YYYY-MM-DD] triage | Inbox Processing
- Processed <N> items from `00-Inbox/`.
- Routed: <summary of destinations>.
```
