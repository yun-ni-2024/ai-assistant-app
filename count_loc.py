#!/usr/bin/env python3
"""
Count lines of code in this repository.

Reports totals for:
- total_lines: all lines
- code_lines: lines excluding comments and blanks
- comment_lines: comment-only lines
- blank_lines: empty/whitespace-only lines

Ignores common build/cache/vendor directories and files like __init__.py.
Understands basic comment styles for Python, TypeScript/JavaScript, and HTML.
This is a lightweight counter; it won't perfectly parse every edge case.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable, Tuple


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Directories to ignore anywhere in the tree
IGNORE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

# Files to ignore by exact name
IGNORE_FILE_NAMES = {
    "__init__.py",
}

# File extensions to include and their language type
LANG_BY_EXT = {
    ".py": "python",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "js",
    ".jsx": "js",
    ".html": "html",
}


@dataclass
class Tally:
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0

    def add(self, other: "Tally") -> None:
        self.total_lines += other.total_lines
        self.code_lines += other.code_lines
        self.comment_lines += other.comment_lines
        self.blank_lines += other.blank_lines


def iter_files(root: str) -> Iterable[Tuple[str, str]]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored dirs in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for name in filenames:
            if name in IGNORE_FILE_NAMES:
                continue
            _, ext = os.path.splitext(name)
            lang = LANG_BY_EXT.get(ext.lower())
            if not lang:
                continue
            yield os.path.join(dirpath, name), lang


def count_file(path: str, lang: str) -> Tally:
    tally = Tally()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return tally

    # Determine comment delimiters
    if lang == "python":
        line_comment = "#"
        block_start = ("\"\"\"", "'''")
        block_end = block_start
    elif lang in {"ts", "js"}:
        line_comment = "//"
        block_start = ("/*",)
        block_end = ("*/",)
    elif lang == "html":
        line_comment = None
        block_start = ("<!--",)
        block_end = ("-->",)
    else:
        line_comment = None
        block_start = tuple()
        block_end = tuple()

    in_block = False
    block_end_token = None

    for raw_line in content.splitlines():
        tally.total_lines += 1
        line = raw_line.strip()
        if not line:
            tally.blank_lines += 1
            continue

        if in_block:
            # inside block comment until we see the end token
            if block_end_token and block_end_token in line:
                in_block = False
            tally.comment_lines += 1
            continue

        # check block start
        started = False
        for start_tok, end_tok in zip(block_start, block_end):
            if start_tok in line:
                in_block = True
                block_end_token = end_tok
                tally.comment_lines += 1
                started = True
                # handle same-line end
                if end_tok in line and line.find(end_tok) > line.find(start_tok):
                    in_block = False
                break
        if started:
            continue

        # line comment
        if line_comment and line.startswith(line_comment):
            tally.comment_lines += 1
            continue

        tally.code_lines += 1

    return tally


def main() -> int:
    overall = Tally()
    per_lang: dict[str, Tally] = {}
    file_count = 0

    for path, lang in iter_files(REPO_ROOT):
        t = count_file(path, lang)
        overall.add(t)
        per_lang.setdefault(lang, Tally()).add(t)
        file_count += 1

    # Print summary
    print(f"Files counted: {file_count}")
    print("Totals (all languages):")
    print(f"  total_lines:  {overall.total_lines}")
    print(f"  code_lines:   {overall.code_lines}")
    print(f"  comment_lines:{overall.comment_lines}")
    print(f"  blank_lines:  {overall.blank_lines}")

    if per_lang:
        print("\nBy language:")
        for lang, t in sorted(per_lang.items()):
            print(f"  [{lang}] total={t.total_lines} code={t.code_lines} comments={t.comment_lines} blanks={t.blank_lines}")

    return 0


if __name__ == "__main__":
    sys.exit(main())


