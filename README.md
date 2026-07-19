# RepoPilot CLI 🚀

An autonomous DevOps CLI agent built for the OpenAI 2026 Build Week series.
RepoPilot scans messy codebases, extracts dependency blueprints, and uses an
offline-resilient local AI engine to generate — and, on confirmation, execute
— clean terminal setup commands. No cloud API keys, no manual dependency
hunting, no stale README guesswork.

## 🎯 The Problem

Onboarding onto an unfamiliar repo almost always means the same tedious
ritual: hunting through `requirements.txt`, `package.json`, and a half-outdated
`README.md`, then manually typing out install commands one by one — often
getting a few wrong along the way. RepoPilot automates that entire loop.

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **SDK framework:** OpenAI Python SDK
- **Inference bridge:** Ollama (local engine)
- **Core LLM:** Llama3 / Qwen2.5-Coder (code-optimized models)

## 🏗️ Architecture

RepoPilot is split into three focused modules, each with a single
responsibility — this keeps every local-LLM prompt small and targeted,
which is what actually prevents the model from hallucinating or drifting
off-format on larger projects.

```
repopilot-cli/
├── scanner.py     # Workspace scanning — finds & reads config files
├── parser.py      # Text cleaning, validation & command extraction
└── repopilot.py   # Main executive — orchestrates the pipeline & runs commands
```

### `scanner.py`

Scans the current workspace for standard configuration files
(`requirements.txt`, `package.json`, `Dockerfile`, `.env.example`,
`README.md`, `go.mod`, `pom.xml`), safely reads each as UTF-8, and returns
a clean `{filename: content}` mapping — nothing else touches the filesystem.

### `parser.py`

The safety layer. Takes raw local-LLM output and runs it through a full
validation pipeline before anything is ever shown to the user:

- Strict delimiter-based extraction (with typo tolerance)
- A `forbidden_keywords` filter to strip conversational noise
- A command whitelist covering 15+ ecosystems (pip, npm, cargo, mvn,
  dotnet, docker, and more)
- OS-awareness — commands meant for a different OS (e.g. `brew` on
  Windows) are automatically filtered out, `sudo`-aware
- Repairs for common model mistakes: bare package specs missing their
  installer prefix, multi-package lines that should be one-per-line,
  and packages wrongly attributed to a system package manager
- Final de-duplication using dictionary compression

### `repopilot.py`

The orchestrator. Implements a **Split-and-Merge execution strategy**:
instead of dumping every scanned file into one giant prompt, it queries
the local Ollama model once _per file_, collects the raw responses, and
hands them all to `parser.py` for a single unified cleaning and
cross-file deduplication pass. The final, verified command list is then
shown to the user and executed via `subprocess.run()` only after explicit
confirmation.

## 🚀 How It Works

1. **Repository Scan** (`scanner.py`) — locates development dependencies
   across the workspace.
2. **Split-and-Merge Inference** (`repopilot.py`) — sends one focused
   prompt per file to the local Ollama instance, entirely offline —
   nothing leaves the machine.
3. **Safe Extraction & Repair** (`parser.py`) — parses every response,
   discards conversational text, fixes common formatting mistakes, and
   filters out anything unsafe or OS-incompatible.
4. **Confirmed Execution** (`repopilot.py`) — prints the full, deduplicated
   command list for review, then executes each one locally only after
   explicit user confirmation.

## 💻 Setup and Installation

### 1. Initialize the Local AI Server

Download and install [Ollama](https://ollama.com/). Then pull a model:

```bash
ollama pull llama3
```

### 2. Set Up the Project Workspace

Clone this repository and create a virtual environment:

```bash
git clone https://github.com/yashtripathi1517/repopilot-cli.git
cd repopilot-cli
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate   # On macOS/Linux
```

Install the one dependency RepoPilot itself needs:

```bash
pip install openai
```

### 3. Run RepoPilot

From inside any project you want to set up (with `scanner.py`, `parser.py`,
and `repopilot.py` all in the same folder):

```bash
python repopilot.py
```

RepoPilot will scan the current directory, query the local model once per
detected file, merge and verify the results, show you the full command
list, and ask for confirmation before running anything.

## ✅ Key Design Choices

- **Fully offline inference** — no API keys, no cloud dependency, no data
  leaves your machine.
- **Split-and-Merge prompting** — one file, one focused prompt, every
  time. Keeps the local model's context small and prevents the format
  drift that a single giant prompt causes.
- **Human-in-the-loop execution** — commands are always shown and
  confirmed before running.
- **Defense-in-depth parsing** — a strict output contract (delimiter
  markers) paired with a multi-stage repair-and-validation pipeline means
  the agent's mistakes get caught and fixed, not blindly executed.

## 🔭 What's Next

- Expand ecosystem coverage further (Rust, Java/Gradle, .NET, PowerShell
  already supported).
- Add rollback support if a command in the sequence fails.
- Optional cloud-model fallback for machines without a local GPU.
