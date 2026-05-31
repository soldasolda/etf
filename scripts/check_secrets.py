from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", "data", "logs"}
SKIP_FILES = {".env", ".env.example"}
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".env",
    ".example",
    ".gitignore",
}

PATTERNS = {
    "telegram_bot_token": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "github_pat": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "nonempty_secret_assignment": re.compile(
        r"(?m)^[ \t]*(?:TOSS_SECRETKEY|TOSS_APPKEY|TELEGRAM_BOT_TOKEN)[ \t]*=[ \t]*"
        r"(?!\s*(?:$|<|\.\.\.|your_|example|changeme))[^\s#]+"
    ),
}


def main() -> int:
    findings: list[str] = []
    for path in iter_files(ROOT):
        text = read_text(path)
        if text is None:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                rel = path.relative_to(ROOT)
                findings.append(f"{rel}:{line_no}: potential {name}")

    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("No obvious secrets found.")
    return 0


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.name.startswith(".env."):
            continue
        if path.name == ".gitignore" or path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


if __name__ == "__main__":
    sys.exit(main())
