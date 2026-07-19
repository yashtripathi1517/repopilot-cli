"""
repopilot.py — RepoPilot CLI: Main Executive Entry File
------------------------------------------------------------
Orchestrates scanner.py and parser.py using a "Split-and-Merge Execution
Strategy": instead of dumping every scanned file into ONE giant prompt
(which was causing local LLM context overwhelm and format drift), this
script loops through the scanned files ONE FILE AT A TIME, makes an
individual prompt call to the local Ollama backend for each, collects
the raw responses into an array, then hands the entire array to the
parser module for cleaning, repair, deduplication, and OS-filtering in
a single unified pass. The final verified command list is then executed
via subprocess.run().
"""

import sys
import subprocess

# ── Fix for Windows cp1252 encoding crash ──────────────────────────
# Windows terminals default to cp1252 which cannot handle emoji/unicode
# characters used throughout RepoPilot's output. Force UTF-8 so emojis
# either render properly (Windows Terminal, VS Code) or get replaced
# gracefully ('?') on legacy consoles — instead of crashing outright.
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from openai import OpenAI

from scanner import scan_repository
from parser import clean_and_extract_commands, get_current_os

# Which local model to target on the Ollama backend. 'llama3' is the
# default; 'qwen2.5-coder' tends to follow strict formatting instructions
# more reliably for code/command generation tasks if available.
OLLAMA_MODEL = "llama3"
# OLLAMA_MODEL = "qwen2.5-coder"  # uncomment to use instead

OLLAMA_BASE_URL = "http://localhost:11434/v1"


def build_system_instruction(current_os):
    """Builds the strict, delimiter-based system prompt. Kept identical in
    spirit to the single-file version's hardened prompt — every rule below
    maps directly to a real bug discovered during development."""
    return (
        "You are RepoPilot, an elite autonomous DevOps engineer tool. "
        "Analyze the SINGLE project file provided and determine the "
        "environment requirements it implies.\n\n"

        f"The user's operating system is: {current_os}. "
        "Only output commands that make sense on THIS operating system. "
        "Do NOT output commands for other operating systems at all — not even as "
        "alternatives, notes, or comments. If a dependency needs a system package "
        "manager, use the one appropriate for the user's OS only "
        "(apt-get/yum/dnf for Linux, brew for macOS, choco/winget for Windows).\n\n"

        "OUTPUT FORMAT — follow this exactly:\n"
        "<<<COMMANDS>>>\n"
        "command1\n"
        "command2\n"
        "<<<END>>>\n\n"

        "STRICT RULES (each one below has caused real bugs before — follow all of them):\n"
        "1. Output ONLY the block above. Nothing before <<<COMMANDS>>> and nothing "
        "after <<<END>>>. No greeting, no explanation, no closing remarks.\n"
        "2. Every line inside the block must be exactly ONE complete, directly "
        "executable terminal command. Never write just a package name or version "
        "on its own line — always include the full installer command "
        "(e.g. write 'pip install pytest==8.1.1', never just 'pytest==8.1.1' alone).\n"
        "3. ONE PACKAGE PER LINE — this is critical. Never list multiple packages "
        "after a single install command, even if they belong to the same tool. "
        "   - WRONG: 'pip install fastapi==0.110.0 numpy==1.26.4 pandas>=2.1.0'\n"
        "   - WRONG: 'npm install vite eslint prettier axios'\n"
        "   - RIGHT: 'pip install fastapi==0.110.0' on one line, then "
        "'pip install numpy==1.26.4' on the next line, then "
        "'pip install pandas>=2.1.0' on the line after that (one full command per "
        "package, repeated as many times as there are packages).\n"
        "4. Never combine two different commands into one line. Never use '&&' to chain commands.\n"
        "5. Never write alternatives on the same line, in any form. This means:\n"
        "   - WRONG: 'sudo apt-get install postgresql (or brew install postgresql for macOS)'\n"
        "   - WRONG: 'sudo apt-get install postgresql  # macOS users: brew install postgresql'\n"
        "   - WRONG: 'brew install postgresql if on macOS'\n"
        "   - RIGHT: just 'sudo apt-get install postgresql' (since the user is on "
        f"{current_os}, only include the one command that applies to them, nothing else).\n"
        "6. Do not include comments (anything starting with '#') on command lines.\n"
        "7. Do not include numbering (e.g. '1.'), bullets ('-', '*'), or markdown "
        "code fences (```) anywhere in the block.\n"
        "8. Do not include commands to run this script itself, activate/create a "
        "virtual environment, or navigate directories with 'cd' — assume the user "
        "is already in the correct directory with their environment active.\n"
        "9. NEVER include commands that install a language runtime or package "
        "manager itself (e.g. 'choco install python', 'choco install node', "
        "'choco install pip', 'brew install python'). Assume Python, pip, Node, "
        "npm, and any other language runtimes mentioned in the project files are "
        "ALREADY installed on the user's machine — the user is already running "
        "this tool from inside an active environment. Only output commands that "
        "install the project's actual DEPENDENCIES, never the runtime itself.\n"
        "10. Choose exactly ONE strategy for installing Python dependencies from "
        "requirements.txt — either (a) a single 'pip install -r requirements.txt' "
        "line, OR (b) one 'pip install <package>' line per package — never both. "
        "Prefer strategy (a), the single '-r requirements.txt' command, whenever "
        "a requirements.txt file is present, since it is simpler and less error-prone.\n"
        "11. Always close the block with the exact marker '<<<END>>>' — never omit it.\n\n"

        "Before responding, mentally check every line against rules 1-11, especially "
        "rule 3 (one package per line). If a line violates any rule, fix it or omit it."
    )


def ask_local_ai_for_single_file(client, filename, content, current_os):
    """Split-and-Merge core: makes ONE individual prompt call to the local
    Ollama backend for a SINGLE scanned file. Keeping each call scoped to
    one file (instead of dumping the whole repo blueprint at once) keeps
    the local LLM's context small and focused, which is what prevents the
    format drift and hallucination errors that a single giant prompt caused.

    Returns the raw response string, or None if the call failed.
    """
    system_instruction = build_system_instruction(current_os)
    user_content = f"--- FILE: {filename} ---\n{content}"

    print(f"🦙 Querying local Ollama engine for: {filename} ...")
    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Connection Failed for {filename}. Please make sure the Ollama "
              f"app is running in your taskbar! Error: {e}")
        return None


def run_split_and_merge(repo_blueprint):
    """Implements the full Split-and-Merge Execution Strategy:
    1. Loop through the scanned files dictionary ONE FILE AT A TIME.
    2. Make an individual prompt call to the local Ollama backend for each.
    3. Append each raw response to an array.
    4. Pass the whole array to parser.clean_and_extract_commands() for a
       single unified cleaning, repair, and deduplication pass.

    Returns the final verified list of commands.
    """
    if not repo_blueprint:
        print("❌ No standard setup files found in this directory!")
        return []

    current_os = get_current_os()
    client = OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama-free-hackathon",  # dummy key, Ollama doesn't check it
    )

    raw_responses = []
    for filename, content in repo_blueprint.items():
        raw_response = ask_local_ai_for_single_file(client, filename, content, current_os)
        if raw_response:
            raw_responses.append(raw_response)

    if not raw_responses:
        print("❌ No responses received from the local AI engine for any file.")
        return []

    # Single unified parsing pass across ALL per-file responses — this is
    # where cross-file deduplication (dictionary compression) happens too.
    final_commands = clean_and_extract_commands(raw_responses)
    return final_commands


def execute_commands(commands):
    """Presents the final verified command list to the user and, upon
    confirmation, runs each one via subprocess.run() in the local terminal."""
    if not commands:
        print("❌ No executable terminal commands were detected after filtering.")
        return

    print("\n📋 --- LOCAL AI GENERATED SETUP STEPS ---")
    for i, cmd in enumerate(commands, 1):
        print(f"Command {i}: {cmd}")

    confirm = input("\n🚀 Do you want RepoPilot to execute these commands automatically? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        for cmd in commands:
            print(f"\n🏃 Running: {cmd}")
            try:
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError:
                print(f"❌ Command failed: {cmd}")
                break
    else:
        print("🛑 Execution cancelled by user.")


if __name__ == "__main__":
    blueprint = scan_repository()
    verified_commands = run_split_and_merge(blueprint)
    execute_commands(verified_commands)
