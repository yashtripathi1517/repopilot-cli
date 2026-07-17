# RepoPilot CLI 🚀

An autonomous DevOps CLI agent built for the OpenAI 2026 Build Week series. RepoPilot automatically scans messy codebases, extracts dependency blueprints, and utilizes an offline-resilient local AI engine to generate and execute local terminal setup commands with a single click.

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **SDK framework:** OpenAI Python SDK
- **Inference Bridge:** Ollama (Local Engine)
- **Core LLM Architecture:** Llama3 (Code Optimized Model)

## 🚀 How It Works

1. **Repository Scan:** The CLI parses structural files (`requirements.txt`, `package.json`, `Dockerfile`, etc.) to locate development dependencies.
2. **Context Packaging:** Formats code snippets into structural blocks without leaking sensitive data or hardcoded keys.
3. **Local AI Execution:** Passes the layout payload straight into the offline local Ollama service using the OpenAI client pipeline format.
4. **Auto-Execution:** Outputs clean terminal instructions and programmatically configures the local system environment after user confirmation.

## 💻 Setup and Installation

### 1. Initialize Local AI Server

Download and install [Ollama](https://ollama.com). Open your terminal and pull the model core:

```bash
ollama run llama3
```

### 2. Configure Local Repository Workspace

Clone this project directory and initialize your virtual environment:

```bash
cd repopilot-cli
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Launch the Agent Sequence

Run the core script execution block:

```bash
python repopilot.py
```
