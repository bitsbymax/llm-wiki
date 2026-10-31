#!/usr/bin/env python3
"""Deterministic Git Auto-Sync & Diff Safety Helper for AI Second Brain.

Provides structured Conventional Commits (`feat(wiki): ingest <title>`,
`fix(lint): repair broken links`, etc.), pre-commit diff verification,
and optional remote push.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command inside the vault root."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def build_commit_message(action: str, title: str | None) -> str:
    """Create a structured Conventional Commit message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_title = (title or "").strip()

    if action == "ingest":
        subject = clean_title or "new source material"
        return f"feat(wiki): ingest {subject}"
    if action == "lint":
        subject = clean_title or "repair broken links and sync index"
        return f"fix(lint): {subject}"
    if action == "triage":
        subject = clean_title or f"process inbox items ({timestamp})"
        return f"chore(triage): {subject}"
    if action == "query":
        subject = clean_title or f"archive research synthesis ({timestamp})"
        return f"docs(wiki): {subject}"
    if action == "init":
        return "feat(vault): initialize AI Second Brain (Obsidian + LLM-Wiki + PARA)"
    subject = clean_title or f"sync knowledge base ({timestamp})"
    return f"chore(vault): {subject}"


def sync_vault(
    vault_root: Path,
    action: str,
    title: str | None = None,
    dry_run: bool = False,
    push: bool = False,
) -> dict[str, Any]:
    """Verify git status/diff, stage changes, commit with structured message, and optionally push."""
    git_dir = vault_root / ".git"
    if not git_dir.exists():
        return {
            "ok": False,
            "error": "Git repository not initialized in vault root. Run `git init` first.",
        }

    status_proc = run_git(["status", "--porcelain"], vault_root)
    if status_proc.returncode != 0:
        return {"ok": False, "error": status_proc.stderr.strip()}

    changed_lines = [line for line in status_proc.stdout.splitlines() if line.strip()]
    if not changed_lines:
        return {
            "ok": True,
            "committed": False,
            "message": "Working tree clean — nothing to commit.",
            "changed_files": [],
        }

    diff_stat_proc = run_git(["diff", "--stat"], vault_root)
    commit_msg = build_commit_message(action, title)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "committed": False,
            "commit_message": commit_msg,
            "changed_files": changed_lines,
            "diff_stat": diff_stat_proc.stdout.strip(),
        }

    add_proc = run_git(["add", "-A"], vault_root)
    if add_proc.returncode != 0:
        return {"ok": False, "error": add_proc.stderr.strip()}

    staged_diff_proc = run_git(["diff", "--cached", "--stat"], vault_root)
    commit_proc = run_git(["commit", "-m", commit_msg], vault_root)
    if commit_proc.returncode != 0:
        return {"ok": False, "error": commit_proc.stderr.strip()}

    rev_proc = run_git(["rev-parse", "--short", "HEAD"], vault_root)
    result: dict[str, Any] = {
        "ok": True,
        "committed": True,
        "commit_hash": rev_proc.stdout.strip(),
        "commit_message": commit_msg,
        "changed_files": changed_lines,
        "diff_stat": staged_diff_proc.stdout.strip(),
    }

    if push:
        push_proc = run_git(["push", "-u", "origin", "HEAD"], vault_root)
        result["pushed"] = push_proc.returncode == 0
        if push_proc.returncode != 0:
            result["push_error"] = push_proc.stderr.strip()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Git auto-sync helper for Second Brain vault.")
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to the Obsidian vault root.",
    )
    parser.add_argument(
        "--action",
        choices=["ingest", "lint", "triage", "query", "init", "sync"],
        default="sync",
        help="Workflow action type for Conventional Commit message.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Source title or description for the commit message.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview git diff and commit message without committing.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push committed changes to origin remote.",
    )
    args = parser.parse_args()

    payload = sync_vault(
        vault_root=args.vault_root.resolve(),
        action=args.action,
        title=args.title,
        dry_run=args.dry_run,
        push=args.push,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
