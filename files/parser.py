"""
parser.py — RepoPilot CLI: Text Cleaning & Command Extraction Module
------------------------------------------------------------------------
Handles all text cleaning and command extraction from raw local-LLM
output. This module is the safety layer: it assumes the model WILL
occasionally violate formatting rules, and defends against every failure
mode discovered during RepoPilot's development (conversational noise,
bundled multi-OS commands, bare package specs, multi-package lines,
runtime-install commands, redundant bulk-vs-individual installs, etc.)
"""

import re
import platform

# ---------------------------------------------------------------------
# OS DETECTION
# ---------------------------------------------------------------------

# Kuch package managers OS-specific hote hain — agar in me se koi command
# current OS ke liye galat hai, to use skip kar denge (jaise Linux pe 'brew').
OS_SPECIFIC_PREFIXES = {
    'brew': 'Darwin',                                        # macOS only
    'choco': 'Windows', 'winget': 'Windows', 'scoop': 'Windows',
    'install-package': 'Windows', 'install-module': 'Windows',
    'set-executionpolicy': 'Windows',
    'apt': 'Linux', 'apt-get': 'Linux', 'yum': 'Linux', 'dnf': 'Linux',
    'pacman': 'Linux', 'snap': 'Linux', 'flatpak': 'Linux',
    'apk': 'Linux', 'zypper': 'Linux',
}


def get_current_os():
    """Returns 'Windows', 'Darwin' (macOS), or 'Linux'."""
    return platform.system()


def get_effective_command_word(line):
    """Returns the word that identifies the actual tool being invoked,
    skipping past 'sudo' if present — e.g. 'sudo apt-get install X' -> 'apt-get'.
    Without this, OS-restriction checks would miss sudo-prefixed commands,
    since 'sudo' itself has no OS restriction."""
    words = line.split()
    if not words:
        return ""
    first = words[0].lower()
    if first == "sudo" and len(words) > 1:
        return words[1].lower()
    return first


def is_command_for_current_os(line, current_os):
    """Agar command ka effective word kisi specific OS ke liye hai aur wo current
    OS se match nahi karta, to False return karega (skip karne ke liye)."""
    effective_word = get_effective_command_word(line)
    required_os = OS_SPECIFIC_PREFIXES.get(effective_word)
    if required_os is None:
        return True  # OS-agnostic command, hamesha allow karo
    return required_os == current_os


# ---------------------------------------------------------------------
# COMMAND WHITELIST
# ---------------------------------------------------------------------

# Commands ke known prefixes — fallback whitelist filter ke liye.
# Ye "kya ye line ek real command hai" ka final safety net hai.
KNOWN_COMMAND_PREFIXES = (
    # Python
    'pip', 'pip3', 'python', 'python3', 'py', 'conda', 'mamba',
    'poetry', 'pipenv', 'virtualenv', 'venv', 'pyenv', 'uv',

    # Node.js / JavaScript
    'npm', 'yarn', 'pnpm', 'npx', 'node', 'bun', 'deno',

    # Rust
    'cargo', 'rustup',

    # Java / JVM
    'mvn', 'mvnw', 'gradle', 'gradlew', 'java', 'javac', 'sdk',

    # .NET / C#
    'dotnet', 'nuget',

    # Ruby
    'bundle', 'bundler', 'gem', 'rails', 'rake', 'rbenv', 'rvm',

    # PHP
    'composer', 'php', 'artisan',

    # Go
    'go',

    # Windows / PowerShell
    'choco', 'winget', 'scoop', 'install-package', 'install-module',
    'set-executionpolicy',

    # macOS
    'brew',

    # Linux package managers
    'apt', 'apt-get', 'yum', 'dnf', 'pacman', 'snap', 'flatpak',
    'apk', 'zypper',

    # Containers / orchestration
    'docker', 'docker-compose', 'podman', 'kubectl', 'helm',

    # Shell / env / filesystem
    'sudo', 'export', 'set', 'source', 'mkdir', 'touch', 'chmod',
    'chown', 'curl', 'wget', 'unzip', 'tar', 'git',

    # Misc build tools / other ecosystems
    'make', 'cmake', 'ninja', 'terraform', 'ansible-playbook',
    'flutter', 'dart', 'swift', 'pod', 'cocoapods',
)

# Strict "forbidden_keywords" filter — lines containing any of these are
# dropped as conversational noise, not real commands.
FORBIDDEN_KEYWORDS = (
    "here is",
    "based on",
    "step",
    "dependencies:",
    "```",
)


def contains_forbidden_keyword(line):
    """Returns True if the line looks like conversational noise rather
    than an executable command, based on the forbidden_keywords filter."""
    lowered = line.lower()
    return any(keyword in lowered for keyword in FORBIDDEN_KEYWORDS)


def looks_like_command(line):
    """Heuristic fallback check: kya ye line actually ek terminal command jaisi dikhti hai?"""
    if not line:
        return False
    first_word = line.split()[0].lower() if line.split() else ""
    # Agar first word known command prefix hai, to ise command maano —
    # chahe wo '.' pe end ho (e.g. 'pip install -e .' ya 'npm install .')
    if first_word in KNOWN_COMMAND_PREFIXES:
        return True
    # Warna agar sentence-jaisa punctuation hai, to reject karo
    if line.endswith(('.', ':', '!', '?')):
        return False
    return False


# ---------------------------------------------------------------------
# DELIMITER EXTRACTION
# ---------------------------------------------------------------------

def extract_commands_block(commands_text):
    """Primary extraction: delimiter markers ke beech ka content nikalta hai.
    Thoda tolerant hai agar model ne '<' ya '>' ki exact count me typo kar di
    ho (e.g. '<<<END>>' ya '<<<<COMMANDS>>>>')."""
    match = re.search(r"<{2,4}\s*COMMANDS\s*>{2,4}(.*?)<{2,4}\s*END\s*>{2,4}",
                       commands_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip().split('\n')

    # Partial match: opening marker mila par closing '<<<END>>>' model bhool
    # gaya. Poore text pe fallback lagane ke bajaye, sirf opening marker ke
    # baad ka content lo — usme trailing conversational text kam hone ka
    # chance zyada hai.
    open_match = re.search(r"<{2,4}\s*COMMANDS\s*>{2,4}", commands_text, re.IGNORECASE)
    if open_match:
        print("⚠️ Closing delimiter (<<<END>>>) nahi mila — opening ke baad ka content use kar rahe hain.")
        return commands_text[open_match.end():].strip().split('\n')

    # Fallback: agar model delimiter bhool gaya, to poore text pe line-by-line filtering try karo
    print("⚠️ Delimiter markers nahi mile — fallback filtering use kar rahe hain.")
    return commands_text.strip().split('\n')


# ---------------------------------------------------------------------
# BARE PACKAGE SPEC REPAIR
# ---------------------------------------------------------------------

def looks_like_bare_package_spec(line):
    """Detects a standalone package name/version the model forgot to prefix
    with an installer command — e.g. 'pytest==8.1.1', 'vite@5.2.0'.
    Only matches specs WITH a version marker — a bare word like 'postgresql'
    or 'black' is too ambiguous (could be a system service, not a package)
    to safely auto-repair, so those are intentionally excluded."""
    if not line or ' ' in line.strip():
        return False  # real commands have spaces (e.g. "pip install X")
    # Require an explicit version/pin marker to reduce false positives
    return bool(re.match(r'^[a-zA-Z0-9_.\-]+[=<>~^!]{1,2}[\w.\-]+$', line.strip()) or
                re.match(r'^[a-zA-Z0-9_.\-]+@[\w.\-]+$', line.strip()))


# Maps an installer command's leading words to the prefix used to repair
# a bare package spec that follows it (e.g. after "pip install X", a bare
# "Y" on the next line becomes "pip install Y").
INSTALLER_PREFIX_MAP = {
    'pip': 'pip install', 'pip3': 'pip3 install',
    'npm': 'npm install', 'yarn': 'yarn add', 'pnpm': 'pnpm add',
    'cargo': 'cargo add', 'gem': 'gem install', 'composer': 'composer require',
}


def infer_installer_prefix_from_syntax(bare_spec):
    """Looks at the VERSION SYNTAX of the bare spec itself to guess its
    ecosystem, before ever considering 'the last command seen'. This is
    more reliable than context-guessing because the syntax is unambiguous:
      - 'name@version'  (e.g. 'vite@5.2.0')      -> npm-style, always 'npm install'
      - 'name==version' / '>=' / '~=' / '<' etc. -> pip-style, always 'pip install'
    Returns None if the syntax doesn't clearly indicate one ecosystem,
    in which case the caller should fall back to context (last command)."""
    spec = bare_spec.strip()
    if '@' in spec:
        return 'npm install'
    if re.search(r'[=<>~^!]{1,2}', spec):
        return 'pip install'
    return None


def infer_installer_prefix(bare_spec, previous_command):
    """Determines the installer prefix for a bare package spec.
    Priority: 1) unambiguous syntax of the spec itself, 2) the last valid
    command seen (context fallback, only used when syntax is ambiguous)."""
    from_syntax = infer_installer_prefix_from_syntax(bare_spec)
    if from_syntax:
        return from_syntax
    if not previous_command:
        return None
    first_word = previous_command.split()[0].lower()
    return INSTALLER_PREFIX_MAP.get(first_word)


# ---------------------------------------------------------------------
# MULTI-PACKAGE LINE SPLITTING
# ---------------------------------------------------------------------

# Installer commands jinke baad "install"/"add" keyword ke turant baad
# multiple package names ek saath aa sakte hain — inhe split karne ke liye.
MULTI_PACKAGE_INSTALLERS = {
    'pip': ('install',), 'pip3': ('install',),
    'npm': ('install', 'i'), 'yarn': ('add',), 'pnpm': ('add', 'install'),
}


def split_multi_package_command(clean_line):
    """Agar model ne galti se ek hi line me multiple packages daal diye
    (e.g. 'pip install fastapi numpy pandas' ya 'npm install vite eslint axios'),
    to isse multiple individual commands me split karta hai — chahe system
    prompt ne mana kiya ho, ye code-level safety net hai jo hamesha sahi
    behavior guarantee karta hai. Returns a list of one or more commands."""
    words = clean_line.split()
    if len(words) < 2:
        return [clean_line]

    tool = words[0].lower()
    subcommands = MULTI_PACKAGE_INSTALLERS.get(tool)
    if not subcommands or words[1].lower() not in subcommands:
        return [clean_line]

    verb = words[1]
    packages = words[2:]
    if len(packages) <= 1:
        return [clean_line]  # already a single package, nothing to split

    # Flags (words starting with '-', e.g. --save-dev, --upgrade) apply to
    # every package, so keep them attached to each generated command.
    flags = [p for p in packages if p.startswith('-')]
    package_names = [p for p in packages if not p.startswith('-')]

    if len(package_names) <= 1:
        return [clean_line]

    return [f"{tool} {verb} {' '.join(flags + [pkg])}" for pkg in package_names]


# ---------------------------------------------------------------------
# RUNTIME-INSTALL BLOCKING
# ---------------------------------------------------------------------

# Language runtimes / package managers that should NEVER be targeted by
# an install command — the user is already running this tool from inside
# an active environment, so these are always wrong.
RUNTIME_INSTALL_TARGETS = (
    'python', 'python3', 'node', 'nodejs', 'pip', 'pip3', 'npm',
)

RUNTIME_INSTALLERS = (
    'choco', 'winget', 'scoop', 'brew', 'apt', 'apt-get', 'yum', 'dnf', 'pacman',
)


def is_runtime_install_command(clean_line):
    """Detects commands that try to install a language runtime or package
    manager itself (e.g. 'choco install python'). These are always wrong
    since the tool is already running inside an active environment."""
    words_lower = clean_line.lower().split()
    if len(words_lower) < 2:
        return False
    return (words_lower[0] in RUNTIME_INSTALLERS and
            any(target in words_lower[1:] for target in RUNTIME_INSTALL_TARGETS))


# System-level package managers — these NEVER understand pip-style version
# pins (==, >=, ~=) or npm-style (@version). If the model attaches one of
# these installers to a spec with such a version marker, it has confused a
# language-ecosystem package (Python/Node) for a system package.
SYSTEM_PACKAGE_MANAGERS = ('choco', 'winget', 'scoop', 'brew', 'apt', 'apt-get',
                           'yum', 'dnf', 'pacman', 'apk', 'zypper')


# Packages that genuinely ARE installed via a system package manager —
# databases, servers, and other OS-level services. If a system-installer
# command targets one of these, it's legitimate and left alone.
KNOWN_SYSTEM_SERVICES = (
    'postgresql', 'postgres', 'mysql', 'mariadb', 'redis', 'mongodb',
    'nginx', 'apache2', 'httpd', 'docker', 'git', 'curl', 'wget',
    'unzip', 'build-essential', 'openssl', 'sqlite3', 'sqlite',
)


def fix_misattributed_system_install(clean_line, ecosystem_hint=None):
    """Detects a system package manager wrongly paired with one or more
    language-ecosystem packages, and repairs or flags each one. Handles
    BOTH single-package lines ('choco install numpy==1.26.4') AND
    multi-package bundled lines ('choco install python-dotenv sqlalchemy alembic').

    For each package spec found after '<tool> install', applies (in order):
      1. Syntax-based: a pip/npm-style version spec (==, >=, ~=, @version)
         is always a misattribution (system package managers don't use
         this syntax) -> auto-repaired to the correct installer.
      2. Context-based: if we know the source file (ecosystem_hint, e.g.
         'requirements.txt' -> pip), a bare name with NO version marker
         can still be corrected.
      3. Known-service allowlist: bare names matching a real system
         service (postgresql, redis, nginx, ...) are left as system-manager commands.
      4. Otherwise: ambiguous and unsafe to guess — that one package is
         dropped (with a warning) rather than risking the wrong installer.

    Returns: a LIST of zero or more corrected command strings (since one
    bundled input line can expand into several output commands, or shrink
    to zero if every package was ambiguous). If the line isn't a system-
    package-manager command at all, returns [clean_line] unchanged."""
    words = clean_line.split()
    if len(words) < 3:
        return [clean_line]

    tool = words[0].lower()
    if tool not in SYSTEM_PACKAGE_MANAGERS:
        return [clean_line]

    # Everything after "<tool> install" is treated as one or more package
    # specs (handles both single and bundled multi-package lines).
    install_verb = words[1]
    specs = words[2:]
    if not specs:
        return [clean_line]

    # Flags (e.g. '-y', '--upgrade') apply to the whole line, not to any
    # one package — keep them out of the per-package repair logic.
    flags = [s for s in specs if s.startswith('-')]
    package_specs = [s for s in specs if not s.startswith('-')]
    if not package_specs:
        return [clean_line]

    repaired_commands = []
    unresolved_system_specs = []

    for spec in package_specs:
        # Strategy 1: syntax-based (version marker present)
        correct_prefix = infer_installer_prefix_from_syntax(spec)
        if correct_prefix:
            repaired = f"{correct_prefix} {spec}"
            print(f"🔧 Fixed misattributed system-package command: "
                  f"'{tool} {install_verb} {spec}' -> {repaired!r}")
            repaired_commands.append(repaired)
            continue

        # Strategy 2: context-based (no version marker, but source file known)
        if ecosystem_hint:
            repaired = f"{ecosystem_hint} {spec}"
            print(f"🔧 Fixed misattributed system-package command (via source file context): "
                  f"'{tool} {install_verb} {spec}' -> {repaired!r}")
            repaired_commands.append(repaired)
            continue

        # Strategy 3: known system service — legitimate, keep under original tool
        if spec.lower() in KNOWN_SYSTEM_SERVICES:
            unresolved_system_specs.append(spec)
            continue

        # Strategy 4: ambiguous — drop this one package, warn, move on
        print(f"⚠️ Skipped (ambiguous system-package target, cannot verify ecosystem): "
              f"'{tool} {install_verb} {spec}'")

    # Any specs confirmed as real system services get reassembled into a
    # single command under the original tool (preserving any flags).
    if unresolved_system_specs:
        rebuilt = " ".join([tool, install_verb] + flags + unresolved_system_specs)
        repaired_commands.append(rebuilt)

    return repaired_commands


# ---------------------------------------------------------------------
# BUNDLED MULTI-OS INSTRUCTION DETECTION
# ---------------------------------------------------------------------

def strip_bundled_os_instruction(clean_line):
    """Detects and handles lines where the model bundled TWO OS-specific
    commands together in one line, in various styles:
      - Parenthetical: "sudo apt-get install X (or brew install X for macOS)"
      - Hash comment:  "sudo apt-get install X  # macOS users: brew install X"
    Returns (result_line_or_None, was_modified_flag). If result is None,
    the entire line should be dropped."""
    # Parenthetical style — always drop entirely, since extracting the
    # "correct" half reliably from free-form parenthetical text is unsafe.
    if re.search(r'\(\s*(or|use|for)\b.*\)', clean_line.lower()):
        return None, True

    # Hash-comment style — the part before '#' is still a valid, safe
    # command, so keep it and trim the trailing comment.
    if '#' in clean_line:
        before_hash = clean_line.split('#', 1)[0].strip()
        if before_hash:
            return before_hash, True
        return None, True  # line was ONLY a comment

    return clean_line, False


# ---------------------------------------------------------------------
# SELF-REFERENTIAL / NAVIGATION COMMAND DETECTION
# ---------------------------------------------------------------------

def is_navigation_command(clean_line):
    """Directory navigation lines that should be ignored since we're
    already inside the correct workspace folder."""
    lowered = clean_line.lower()
    return (lowered.startswith("cd ") or
            lowered.startswith("git clone") or
            "ollama run" in lowered)


def is_self_referential_command(clean_line):
    """README setup steps sometimes get mistaken for install steps by the
    model (e.g. 'python repopilot.py', re-creating the venv we're already
    running inside)."""
    lowered = clean_line.lower()
    return ("repopilot.py" in lowered or
            bool(re.search(r'\bvenv\b.*\bactivate\b', lowered)) or
            bool(re.search(r'\-m\s+venv\b', lowered)))


# ---------------------------------------------------------------------
# NUMBERING / BULLET / MARKDOWN CLEANUP
# ---------------------------------------------------------------------

def strip_formatting_artifacts(clean_line):
    """Strips accidental markdown symbols or numbering formats that
    sometimes survive around otherwise-valid command lines."""
    if ". " in clean_line[:5]:
        clean_line = clean_line.split(". ", 1)[1]
    if clean_line.startswith("- ") or clean_line.startswith("* "):
        clean_line = clean_line[2:]
    return clean_line.strip()


# ---------------------------------------------------------------------
# BULK vs INDIVIDUAL DEDUPLICATION
# ---------------------------------------------------------------------

def deduplicate_bulk_vs_individual(commands):
    """Agar 'pip install -r requirements.txt' present hai, to individual
    'pip install <package>' commands redundant hain (wahi packages dobara
    install honge) — unhe hata do aur sirf bulk wala rakho."""
    has_bulk_install = any(
        re.search(r'^pip3?\s+install\s+.*-r\s+requirements\.txt', cmd.lower())
        for cmd in commands
    )
    if not has_bulk_install:
        return commands

    deduped = []
    removed_count = 0
    for cmd in commands:
        is_bulk = re.search(r'^pip3?\s+install\s+.*-r\s+requirements\.txt', cmd.lower())
        is_individual_pip = (re.match(r'^pip3?\s+install\s+', cmd.lower()) and not is_bulk)
        if is_individual_pip:
            removed_count += 1
            continue
        deduped.append(cmd)

    if removed_count:
        print(f"🧹 Removed {removed_count} individual pip command(s) — already covered by 'pip install -r requirements.txt'.")
    return deduped


def deduplicate_commands(commands):
    """Removes exact-duplicate commands using dictionary compression
    (dict.fromkeys preserves first-seen order while dropping repeats —
    this can happen naturally when multiple source files, scanned one at
    a time under the Split-and-Merge strategy, produce overlapping
    commands, e.g. two files both mentioning 'pip install python-dotenv')."""
    return list(dict.fromkeys(commands))


# ---------------------------------------------------------------------
# MAIN ENTRY POINT: clean_and_extract_commands
# ---------------------------------------------------------------------

# Maps a source filename to the installer prefix its packages should use.
# This lets us correct system-package-manager misattribution even when the
# package name has no version marker to go on syntactically.
SOURCE_FILE_ECOSYSTEM_HINTS = {
    'requirements.txt': 'pip install',
    'package.json': 'npm install',
    'go.mod': 'go get',
}


def clean_and_extract_commands(raw_responses):
    """Main parser entry point. Accepts a list of raw LLM response strings,
    OR a list of (filename, raw_text) tuples for source-file-aware repair,
    runs every cleaning/filtering/repair stage on each, and returns one
    final, de-duplicated, OS-correct list of commands.

    raw_responses: list[str] or list[tuple[str, str]] — raw text blocks
    from the local LLM, optionally paired with their source filename
    (recommended, enables context-based misattribution fixes).
    Returns: list[str] — final verified commands, ready for execution.
    """
    current_os = get_current_os()
    print(f"🖥️  Detected OS: {current_os}")

    all_commands = []

    for entry in raw_responses:
        # Support both plain strings and (filename, text) tuples
        if isinstance(entry, tuple):
            source_filename, commands_text = entry
        else:
            source_filename, commands_text = None, entry

        ecosystem_hint = SOURCE_FILE_ECOSYSTEM_HINTS.get(source_filename)

        if not commands_text:
            continue

        raw_lines = extract_commands_block(commands_text)

        for line in raw_lines:
            clean_line = line.strip()
            if not clean_line:
                continue

            # Skip conversational text (forbidden_keywords filter)
            if contains_forbidden_keyword(clean_line):
                continue

            # Skip navigation commands since we are already inside the folder!
            if is_navigation_command(clean_line):
                continue

            # Skip self-referential commands
            if is_self_referential_command(clean_line):
                continue

            # Skip commands that try to install the language runtime itself
            if is_runtime_install_command(clean_line):
                print(f"⚠️ Skipped (installs a language runtime, assumed already present): {clean_line}")
                continue

            # Fix system package manager wrongly paired with a language-
            # ecosystem package (via version-syntax OR source-file context).
            # This can expand ONE bundled line into MULTIPLE repaired commands
            # (e.g. 'choco install a b c' -> 'pip install a', 'pip install b', ...),
            # so every candidate below is run through the rest of the pipeline.
            candidate_lines = fix_misattributed_system_install(clean_line, ecosystem_hint)

            for candidate in candidate_lines:
                # Handle bundled multi-OS instructions (parenthetical or '#' comment)
                stripped, was_modified = strip_bundled_os_instruction(candidate)
                if stripped is None:
                    print(f"⚠️ Skipped (bundled multi-OS instruction): {candidate}")
                    continue
                if was_modified:
                    print(f"✂️  Trimmed bundled instruction: {candidate!r} -> {stripped!r}")
                candidate = stripped

                # Clean up accidental numbering or bullets remaining on valid command lines
                candidate = strip_formatting_artifacts(candidate)

                # Whitelist safety net — sirf tabhi add karo jab command jaisa lage
                if not looks_like_command(candidate):
                    # Before giving up, check if this is a bare package spec the
                    # model forgot to prefix (e.g. "pytest==8.1.1" right after a
                    # "pip install X" line). If so, repair it using syntax first,
                    # then the last installer command seen as fallback.
                    if looks_like_bare_package_spec(candidate):
                        prefix = infer_installer_prefix(
                            candidate, all_commands[-1] if all_commands else None
                        )
                        if prefix:
                            repaired = f"{prefix} {candidate}"
                            print(f"🔧 Repaired bare package spec: {candidate!r} -> {repaired!r}")
                            candidate = repaired
                        else:
                            print(f"⚠️ Skipped (not a command): {candidate}")
                            continue
                    else:
                        print(f"⚠️ Skipped (not a command): {candidate}")
                        continue

                # OS filter — dusre OS ke package-manager commands skip karo (sudo-aware)
                if not is_command_for_current_os(candidate, current_os):
                    required = OS_SPECIFIC_PREFIXES.get(get_effective_command_word(candidate))
                    print(f"⏭️  Skipped (needs {required}, you're on {current_os}): {candidate}")
                    continue

                # Split multi-package lines into individual commands
                split_result = split_multi_package_command(candidate)
                if len(split_result) > 1:
                    print(f"✂️  Split multi-package command into {len(split_result)}: {candidate!r}")
                all_commands.extend(split_result)

    # Remove redundant individual pip installs when a bulk -r install exists
    all_commands = deduplicate_bulk_vs_individual(all_commands)

    # Final de-duplication pass using dictionary compression
    all_commands = deduplicate_commands(all_commands)

    return all_commands