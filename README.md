# EliteAgent

Terminal AI coding agent powered by pydantic-ai, rich, and prompt-toolkit.

Features
- Multiple models: OpenAI GPT-5, Anthropic Claude 4.5 Sonnet, OpenRouter Grok Code Fast
- Rich UI: boxed messages, color-coding, spinner
- Tool: `shell` for executing commands (stdout+stderr)
- Modes: Approval vs YOLO
- Ctrl+C handling & session history

## Requirements
- Python 3.10+
- API keys set in `.env` (see `example.env`)

## Quick start

```bash
# Install uv (optional but recommended)
# macOS: brew install uv

# Create env and run
uv sync
# Run via module to avoid PATH script resolution issues
uv run -m eliteagent.cli
```

If not using `uv`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# If `eliteagent` is not on PATH in your shell, run via module:
python -m eliteagent.cli
```

## Environment
Create a `.env` in the project root from `example.env` and set:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
# Optional OpenRouter endpoint override
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Usage
- Type your request at the prompt.
- Slash commands:
  - `/new` — new session (clears history)
  - `/model` — switch models
  - `/approval` — toggle Approval vs YOLO for tool execution

## Notes
- The `shell` tool executes via `/bin/bash -lc` to support pipes and redirection.
- All model text messages are displayed; tool calls and outputs are boxed and color-coded.

