#!/usr/bin/env python3
"""
Pre-publish guard for public sharing.

Checks:
1) Tracked files do not include forbidden sensitive paths.
2) Tracked text files do not include common secret patterns.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


FORBIDDEN_EXACT = {
    ".env",
}

FORBIDDEN_PREFIXES = (
    "documents/",
    "data/",
    "logs/",
    "archives/",
    "temp-pdf-训练用/",
)

SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style Key", re.compile(r"\b(?:sk|rk)-[A-Za-z0-9]{20,}\b")),
    (
        "Private Key Block",
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    ),
    (
        "Azure API Key Literal",
        re.compile(r"AZURE_OPENAI_API_KEY\s*=\s*(?!your-|<)[A-Za-z0-9_\-]{16,}"),
    ),
]

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".env",
    ".tsv",
}


def git_tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=False,
        check=True,
    )
    raw = result.stdout.decode("utf-8", errors="replace")
    items = [x for x in raw.split("\x00") if x]
    return [repo_root / item for item in items]


def is_text_like(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(2048)
        return b"\x00" not in chunk
    except Exception:
        return False


def find_forbidden_paths(repo_root: Path, files: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        if rel in FORBIDDEN_EXACT:
            issues.append(f"Tracked forbidden file: {rel}")
            continue
        if any(rel.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            issues.append(f"Tracked forbidden path: {rel}")
    return issues


def find_secret_patterns(repo_root: Path, files: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in files:
        if not path.exists() or not is_text_like(path):
            continue
        rel = path.relative_to(repo_root).as_posix()
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pattern in SECRET_PATTERNS:
            match = pattern.search(content)
            if not match:
                continue
            line_no = content.count("\n", 0, match.start()) + 1
            issues.append(f"{label} in {rel}:{line_no}")
    return issues


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        files = git_tracked_files(repo_root)
    except subprocess.CalledProcessError as exc:
        print(f"Failed to list git files: {exc}", file=sys.stderr)
        return 2

    issues = []
    issues.extend(find_forbidden_paths(repo_root, files))
    issues.extend(find_secret_patterns(repo_root, files))

    if issues:
        print("Pre-publish guard: FAILED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Pre-publish guard: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
