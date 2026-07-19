"""
scanner.py — RepoPilot CLI: Workspace Scanning Module
--------------------------------------------------------
Strictly handles parsing the local workspace directory. Scans for
multi-language configuration files, reads them safely, and returns a
clean file mapping dictionary for downstream AI processing.
"""

import os

# Multi-language configuration files RepoPilot understands. Covers Python,
# Node.js, Docker, Go, and Java/Maven ecosystems, plus general project docs.
TARGET_FILES = [
    'package.json',
    'requirements.txt',
    'Dockerfile',
    '.env.example',
    'README.md',
    'go.mod',
    'pom.xml',
    'README test setup.md'
]

# How many characters to safely read from each file. Kept small so the
# local LLM's context window isn't overwhelmed by huge files (e.g. a
# massive README or a lockfile-like requirements.txt).
READ_CHAR_LIMIT = 1000


def scan_repository(directory='.'):
    """Scans the given directory (defaults to current folder) for standard
    setup/configuration files and returns a dict mapping filename -> content.

    Each file's content is safely read as UTF-8, truncated to
    READ_CHAR_LIMIT characters, so downstream prompts stay small and
    focused (this is what prevents local LLM context overwhelm when
    combined with the Split-and-Merge execution strategy in repopilot.py).
    """
    important_files = {}

    print("🔍 Scanning current directory for blueprints...")
    try:
        entries = os.listdir(directory)
    except Exception as e:
        print(f"❌ Could not list directory '{directory}': {e}")
        return important_files

    for filename in entries:
        if filename in TARGET_FILES:
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    important_files[filename] = f.read(READ_CHAR_LIMIT)
            except Exception as e:
                print(f"⚠️ Could not read {filename}: {e}")

    return important_files


if __name__ == "__main__":
    # Quick standalone test: run `python scanner.py` inside any project
    # folder to see exactly what RepoPilot would pick up.
    result = scan_repository()
    if not result:
        print("❌ No standard setup files found in this directory!")
    else:
        print(f"\n✅ Found {len(result)} blueprint file(s):")
        for name, content in result.items():
            print(f"  - {name} ({len(content)} chars read)")
