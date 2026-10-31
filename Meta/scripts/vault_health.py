#!/usr/bin/env python3
"""Deterministic Vault Health & Link Auditor for Obsidian + LLM-Wiki Second Brain.

Scans markdown files for [[wikilinks]] and relative markdown links, verifies target
existence, detects orphan nodes in wiki/, checks wiki/index.md synchronization,
and outputs a JSON payload + optional Markdown report (Meta/health-report.md).
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\[\]]+)\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[([^\[\]]+)\]\(([^()\s]+)\)")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

WIKI_SECTIONS = {
    "concepts": "## Concepts",
    "entities": "## Entities",
    "topics": "## Topics",
    "archives": "## Archives",
}

IGNORED_DIRS = {
    ".git",
    ".obsidian",
    ".agents",
    ".gemini",
    "node_modules",
    "__pycache__",
    "Templates",
}


def strip_code_and_comments(text: str) -> str:
    """Remove HTML comments, fenced code blocks, and inline code before link parsing."""
    text = HTML_COMMENT_RE.sub("", text)
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract lightweight key-value metadata from YAML frontmatter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta: dict[str, Any] = {"_present": True}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


def collect_markdown_files(vault_root: Path) -> list[Path]:
    """Return all non-ignored Markdown files in the vault."""
    md_files: list[Path] = []
    for path in sorted(vault_root.rglob("*.md")):
        rel_parts = path.relative_to(vault_root).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        md_files.append(path)
    return md_files


def resolve_wikilink(
    raw_target: str,
    source_file: Path,
    vault_root: Path,
    by_stem: dict[str, list[Path]],
    by_rel_no_ext: dict[str, Path],
) -> Path | None:
    """Resolve an Obsidian [[target|alias]] or [[path/target#heading|alias]] to a Path."""
    target = raw_target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return source_file

    target_norm = target.removesuffix(".md")

    # 1. Try relative to source file directory
    rel_candidate = (source_file.parent / f"{target_norm}.md").resolve()
    if rel_candidate.is_file() and vault_root in rel_candidate.parents:
        return rel_candidate

    # 2. Try vault-root relative path
    if target_norm in by_rel_no_ext:
        return by_rel_no_ext[target_norm]

    # 3. Try Obsidian shortest-filename stem lookup
    stem = Path(target_norm).name
    matches = by_stem.get(stem, [])
    if matches:
        return matches[0]

    return None


def resolve_mdlink(raw_url: str, source_file: Path, vault_root: Path) -> Path | None:
    """Resolve a relative markdown link to a file inside the vault."""
    if raw_url.startswith(("http://", "https://", "mailto:", "obsidian://", "sidecar://", "#")):
        return source_file
    clean_url = raw_url.split("#", 1)[0].strip()
    if not clean_url:
        return source_file
    candidate = (source_file.parent / clean_url).resolve()
    if candidate.exists():
        return candidate
    root_candidate = (vault_root / clean_url).resolve()
    if root_candidate.exists():
        return root_candidate
    return None


def sync_wiki_index(vault_root: Path, missing_from_index: list[dict[str, str]]) -> int:
    """Insert missing wiki nodes into wiki/index.md under their section header."""
    index_path = vault_root / "wiki" / "index.md"
    if not index_path.is_file() or not missing_from_index:
        return 0

    content = index_path.read_text(encoding="utf-8")
    added = 0
    for item in missing_from_index:
        category = item["category"]
        slug = item["slug"]
        title = item["title"]
        rel_from_wiki = f"{category}/{slug}.md"
        header = WIKI_SECTIONS.get(category)
        if not header or header not in content:
            continue
        entry_line = f"- [[{slug}|{title}]] ([{title}]({rel_from_wiki}))"
        if f"[[{slug}" in content or f"]({rel_from_wiki})" in content:
            continue
        pattern = re.compile(rf"(^{re.escape(header)}\s*\n(?:<!--.*?-->\s*\n)?)", re.MULTILINE)
        content, count = pattern.subn(rf"\1{entry_line}\n", content, count=1)
        if count > 0:
            added += 1

    if added > 0:
        index_path.write_text(content, encoding="utf-8")
    return added


def analyze_vault(vault_root: Path, fix_index: bool = False) -> dict[str, Any]:
    """Perform full structural analysis of the Second Brain vault."""
    md_files = collect_markdown_files(vault_root)

    by_stem: dict[str, list[Path]] = {}
    by_rel_no_ext: dict[str, Path] = {}
    for f in md_files:
        rel_no_ext = f.relative_to(vault_root).with_suffix("").as_posix()
        by_rel_no_ext[rel_no_ext] = f
        by_stem.setdefault(f.stem, []).append(f)

    broken_wikilinks: list[dict[str, str]] = []
    broken_mdlinks: list[dict[str, str]] = []
    missing_frontmatter: list[str] = []
    inbound_links: dict[str, set[str]] = {
        f.relative_to(vault_root).as_posix(): set() for f in md_files
    }

    system_Exclude_for_inbound = {
        "wiki/index.md",
        "wiki/log.md",
        "GEMINI.md",
        "AGENTS.md",
        "Meta/GEMINI.md",
        "Meta/health-report.md",
    }

    for f in md_files:
        rel_src = f.relative_to(vault_root).as_posix()
        if rel_src in ("GEMINI.md", "AGENTS.md", "Meta/GEMINI.md", "Meta/health-report.md"):
            continue

        raw_text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(raw_text)
        if rel_src.startswith(("wiki/", "raw/")) and not fm.get("_present"):
            missing_frontmatter.append(rel_src)

        clean_text = strip_code_and_comments(raw_text)

        for match in WIKILINK_RE.finditer(clean_text):
            token = match.group(1)
            resolved = resolve_wikilink(token, f, vault_root, by_stem, by_rel_no_ext)
            if resolved is None:
                broken_wikilinks.append({"source": rel_src, "link": f"[[{token}]]"})
            elif resolved != f and resolved in md_files:
                target_rel = resolved.relative_to(vault_root).as_posix()
                if rel_src not in system_Exclude_for_inbound:
                    inbound_links.setdefault(target_rel, set()).add(rel_src)

        for match in MDLINK_RE.finditer(clean_text):
            label, url = match.group(1), match.group(2)
            resolved = resolve_mdlink(url, f, vault_root)
            if resolved is None:
                broken_mdlinks.append({"source": rel_src, "link": f"[{label}]({url})"})
            elif resolved != f and resolved in md_files:
                target_rel = resolved.relative_to(vault_root).as_posix()
                if rel_src not in system_Exclude_for_inbound:
                    inbound_links.setdefault(target_rel, set()).add(rel_src)

    # Check wiki nodes (concepts, entities, topics, archives)
    wiki_root = vault_root / "wiki"
    index_path = wiki_root / "index.md"
    index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""

    orphan_pages: list[str] = []
    missing_from_index: list[dict[str, str]] = []
    wiki_counts: dict[str, int] = {k: 0 for k in WIKI_SECTIONS}

    for category in WIKI_SECTIONS:
        cat_dir = wiki_root / category
        if not cat_dir.is_dir():
            continue
        for note in sorted(cat_dir.glob("*.md")):
            wiki_counts[category] += 1
            rel_note = note.relative_to(vault_root).as_posix()
            fm = parse_frontmatter(note.read_text(encoding="utf-8"))
            title = fm.get("title") or note.stem.replace("-", " ").title()

            if category in ("concepts", "entities", "topics"):
                if not inbound_links.get(rel_note):
                    orphan_pages.append(rel_note)

            rel_from_wiki = f"{category}/{note.name}"
            if f"[[{note.stem}" not in index_text and rel_from_wiki not in index_text:
                missing_from_index.append(
                    {
                        "path": rel_note,
                        "category": category,
                        "slug": note.stem,
                        "title": title,
                    }
                )

    auto_indexed_count = 0
    if fix_index and missing_from_index:
        auto_indexed_count = sync_wiki_index(vault_root, missing_from_index)
        if auto_indexed_count:
            missing_from_index = []

    healthy = not (
        broken_wikilinks or broken_mdlinks or orphan_pages or missing_from_index or missing_frontmatter
    )

    return {
        "date": date.today().isoformat(),
        "vault_root": str(vault_root),
        "healthy": healthy,
        "summary": {
            "total_markdown_files": len(md_files),
            "wiki_counts": wiki_counts,
            "broken_wikilinks_count": len(broken_wikilinks),
            "broken_mdlinks_count": len(broken_mdlinks),
            "orphan_pages_count": len(orphan_pages),
            "missing_from_index_count": len(missing_from_index),
            "missing_frontmatter_count": len(missing_frontmatter),
            "auto_indexed_count": auto_indexed_count,
        },
        "issues": {
            "broken_wikilinks": broken_wikilinks,
            "broken_mdlinks": broken_mdlinks,
            "orphan_pages": orphan_pages,
            "missing_from_index": missing_from_index,
            "missing_frontmatter": missing_frontmatter,
        },
    }


def render_markdown_report(payload: dict[str, Any]) -> str:
    """Format the health check payload as a Markdown audit report."""
    s = payload["summary"]
    issues = payload["issues"]
    status_badge = "HEALTHY" if payload["healthy"] else "ACTION REQUIRED"

    lines = [
        "---",
        "title: Vault Health Report",
        f"updated: {payload['date']}",
        f"status: {status_badge.lower()}",
        "tags:",
        "  - meta/health",
        "---",
        "",
        f"# Vault Health Report ({payload['date']})",
        "",
        f"**Overall Status**: `{status_badge}`",
        "",
        "## Metrics Summary",
        "",
        "| Metric | Count |",
        "| :--- | ---: |",
        f"| Total Markdown Files | {s['total_markdown_files']} |",
        f"| Wiki Concepts (`wiki/concepts/`) | {s['wiki_counts']['concepts']} |",
        f"| Wiki Entities (`wiki/entities/`) | {s['wiki_counts']['entities']} |",
        f"| Wiki Topics (`wiki/topics/`) | {s['wiki_counts']['topics']} |",
        f"| Wiki Archives (`wiki/archives/`) | {s['wiki_counts']['archives']} |",
        f"| Broken `[[Wikilinks]]` | {s['broken_wikilinks_count']} |",
        f"| Broken Markdown Links | {s['broken_mdlinks_count']} |",
        f"| Orphan Wiki Pages | {s['orphan_pages_count']} |",
        f"| Unindexed Wiki Pages | {s['missing_from_index_count']} |",
        f"| Missing YAML Frontmatter | {s['missing_frontmatter_count']} |",
        "",
    ]

    if issues["broken_wikilinks"]:
        lines.append("## Broken Wikilinks")
        for item in issues["broken_wikilinks"]:
            lines.append(f"- `{item['source']}` -> `{item['link']}`")
        lines.append("")

    if issues["broken_mdlinks"]:
        lines.append("## Broken Markdown Links")
        for item in issues["broken_mdlinks"]:
            lines.append(f"- `{item['source']}` -> `{item['link']}`")
        lines.append("")

    if issues["orphan_pages"]:
        lines.append("## Orphan Wiki Pages (No Inbound Links)")
        for path in issues["orphan_pages"]:
            lines.append(f"- `{path}`")
        lines.append("")

    if issues["missing_from_index"]:
        lines.append("## Out-of-Sync `wiki/index.md` Entries")
        for item in issues["missing_from_index"]:
            lines.append(f"- `{item['path']}` (`{item['title']}`)")
        lines.append("")

    if issues["missing_frontmatter"]:
        lines.append("## Missing YAML Frontmatter")
        for path in issues["missing_frontmatter"]:
            lines.append(f"- `{path}`")
        lines.append("")

    if payload["healthy"]:
        lines.append("> [!TIP] All Structural Checks Passed")
        lines.append("> Zero broken links, zero orphans, and `wiki/index.md` is fully synchronized.")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Obsidian + LLM-Wiki vault health.")
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to the Obsidian vault root.",
    )
    parser.add_argument(
        "--fix-index",
        action="store_true",
        help="Automatically add unindexed wiki notes to wiki/index.md.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write a Markdown health report to the specified path (e.g. Meta/health-report.md).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON payload to stdout (default if --report is not set).",
    )
    args = parser.parse_args()

    vault_root = args.vault_root.resolve()
    payload = analyze_vault(vault_root, fix_index=args.fix_index)

    if args.report:
        report_path = args.report if args.report.is_absolute() else (vault_root / args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown_report(payload), encoding="utf-8")

    if args.json or not args.report:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Report written to {args.report} (healthy={payload['healthy']})")

    return 0 if payload["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
