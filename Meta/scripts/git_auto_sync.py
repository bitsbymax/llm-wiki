#!/usr/bin/env python3
"""Deterministic Git Auto-Sync & Diff Safety Helper for AI Second Brain.

Provides structured Conventional Commits (`feat(wiki): ingest <title>`,
`fix(lint): repair broken links`, etc.), pre-commit diff verification,
GitHub repository creation (`--create-repo`), and remote push (`--push`).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.request


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command inside the vault root."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def load_env_var(name: str, vault_root: Path) -> str | None:
    """Safely load a credential from environment or ~/.env without printing it."""
    if os.environ.get(name):
        return os.environ[name].strip()
    for env_path in (vault_root / ".env", Path.home() / ".env"):
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return None


def create_github_repo(
    vault_root: Path,
    repo_name: str = "llm-wiki",
    private: bool = True,
) -> dict[str, Any]:
    """Create the GitHub repository via GITHUB_TOKEN API or `gh` CLI and push main."""
    token = load_env_var("GITHUB_TOKEN", vault_root)
    if token:
        payload = json.dumps(
            {
                "name": repo_name,
                "private": private,
                "description": "AI Second Brain (Obsidian + Karpathy LLM-Wiki + Forte PARA)",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.github.com/user/repos",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "llm-wiki-git-auto-sync",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ssh_url = data.get("ssh_url") or f"git@github.com:bitsbymax/{repo_name}.git"
                html_url = data.get("html_url")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code != 422:  # 422 = repository already exists
                return {
                    "ok": False,
                    "error": f"GitHub API error ({exc.code}): {err_body}",
                }
            ssh_url = f"git@github.com:bitsbymax/{repo_name}.git"
            html_url = f"https://github.com/bitsbymax/{repo_name}"

        run_git(["remote", "set-url", "origin", ssh_url], vault_root)
        push_proc = run_git(["push", "-u", "origin", "HEAD"], vault_root)
        return {
            "ok": push_proc.returncode == 0,
            "repo_url": html_url,
            "ssh_url": ssh_url,
            "pushed": push_proc.returncode == 0,
            "push_error": push_proc.stderr.strip() if push_proc.returncode != 0 else None,
        }

    gh_bin = shutil.which("gh")
    if gh_bin:
        visibility = "--private" if private else "--public"
        proc = subprocess.run(
            [
                gh_bin,
                "repo",
                "create",
                repo_name,
                visibility,
                "--source=.",
                "--remote=origin",
                "--push",
            ],
            cwd=str(vault_root),
            text=True,
            capture_output=True,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "pushed": proc.returncode == 0,
            "output": proc.stdout.strip(),
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
        }

    return {
        "ok": False,
        "error": "Neither GITHUB_TOKEN (in ~/.env) nor `gh` CLI is configured.",
    }


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
        result: dict[str, Any] = {
            "ok": True,
            "committed": False,
            "message": "Working tree clean — nothing to commit.",
            "changed_files": [],
        }
        if push:
            push_proc = run_git(["push", "-u", "origin", "HEAD"], vault_root)
            result["pushed"] = push_proc.returncode == 0
            if push_proc.returncode != 0:
                result["ok"] = False
                result["push_error"] = push_proc.stderr.strip()
        return result

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
    result = {
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
            result["ok"] = False
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
    parser.add_argument(
        "--create-repo",
        type=str,
        nargs="?",
        const="llm-wiki",
        default=None,
        help="Create the GitHub repository (default: llm-wiki) and push main.",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create the GitHub repository as public (defaults to private).",
    )
    args = parser.parse_args()

    vault_root = args.vault_root.resolve()
    payload = sync_vault(
        vault_root=vault_root,
        action=args.action,
        title=args.title,
        dry_run=args.dry_run,
        push=args.push and not args.create_repo,
    )

    if args.create_repo:
        repo_res = create_github_repo(
            vault_root=vault_root,
            repo_name=args.create_repo,
            private=not args.public,
        )
        payload["github_repo"] = repo_res
        if not repo_res.get("ok"):
            payload["ok"] = False

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
