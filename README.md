# EliteAgent

Terminal AI coding agent powered by pydantic-ai, rich, and prompt-toolkit.

Features
- Multiple models: OpenAI GPT-5, Anthropic Claude 4.5 Sonnet, OpenRouter Grok Code Fast
- Rich UI: boxed messages, color-coding, spinner
- Tool: `shell` for executing commands (stdout+stderr)
- Modes: Approval vs YOLO
- Ctrl+C handling & session history
- **Transparent session logging**: All interactions logged as raw, unadulterated data files for educational transparency

---

## 🔬 What Makes This Fork Special

This is an **educational "glass box"** fork designed to make AI agent behavior completely transparent and inspectable. Every single interaction—user input, LLM calls, tool executions—is logged as raw, readable data files in chronological order.

### Why This Matters

Most AI agents are "black boxes" where you can't see:
- What prompts actually go to the LLM
- What the full conversation context looks like
- How tool calls are structured
- The exact sequence of events

This fork captures **everything** so you can:
- Learn how agentic loops actually work
- Debug issues by inspecting raw payloads
- Understand token usage and costs
- See how conversation context builds up
- Verify accuracy against source of truth

### What Gets Logged (All Raw & Unadulterated)

Each session creates a numbered directory (`session_001/`, `session_002/`, etc.) with:

1. **User Input** (`.txt`) - Exactly what you typed
2. **LLM Requests** (`.json`) - Complete OpenAI-style request payloads with full conversation history
3. **LLM Responses** (`.json`) - Complete responses including tool_calls, usage stats, finish_reason
4. **Tool Executions** (`.txt`) - Raw commands and their stdout/stderr
5. **Validation Files** - Source of truth for verifying accuracy

All files use proper extensions for IDE syntax highlighting. Zero decoration, just raw data.

### Session Structure

```
session_012/
├── VALIDATION.md              ← Human-readable source of truth
├── VALIDATION.json            ← Machine-readable validation data
├── 001-user/
│   └── 001-request.txt       ← Your input
├── 002-llm/
│   ├── 002-request.json      ← LLM request (system + user)
│   └── 003-response.json     ← LLM response (tool_call)
├── 003-tool/
│   ├── 003-request.txt       ← Command to execute
│   └── 004-response.txt      ← Command output
├── 004-llm/
│   ├── 004-request.json      ← LLM request (full context + tool result)
│   └── 005-response.json     ← LLM response (final answer)
└── ...
```

**Key Features:**
- ✅ Chronological numbering shows exact sequence of events
- ✅ Each LLM request includes FULL conversation context
- ✅ Tool call IDs link responses to executions
- ✅ Token usage tracked for every call
- ✅ Proper file extensions for IDE syntax highlighting

### How to Validate a Session

After running the agent, validate that the logs are accurate:

1. **Open `VALIDATION.md`** in the session directory
   ```bash
   cat session_012/VALIDATION.md
   ```

2. **Check the message flow** - Shows what pydantic-ai actually returned:
   - Total number of messages
   - Sequence of ModelRequest/ModelResponse
   - Parts in each message (SystemPrompt, UserPrompt, ToolCall, ToolReturn, etc.)
   - Tool call IDs for tracing

3. **Verify expected log files** - The validation file lists what files should exist:
   ```
   - 002-llm/
     - 002-request.json
     - 003-response.json
   - 003-tool/
     - 003-request.txt
     - 004-response.txt
   ```

4. **Compare against actual files** - All expected files should exist with correct numbering

5. **Spot check content**:
   - Tool call IDs in responses match tool request IDs
   - Commands in tool requests match arguments in LLM responses
   - Second LLM request includes full conversation history
   - Tool results are properly included in subsequent requests

Example validation:
```bash
# 1. See what pydantic-ai returned
cat session_012/VALIDATION.md

# 2. Check all files exist
ls -R session_012/

# 3. Verify tool call ID matches
grep "tool_call_id" session_012/002-llm/003-response.json
grep "tool_call_id" session_012/004-llm/004-request.json

# 4. Verify full context preservation
cat session_012/004-llm/004-request.json
# Should include: system, user, assistant (with tool_calls), tool
```

**The VALIDATION files are your source of truth** - they show exactly what pydantic-ai returned, so you can verify our logs are 100% accurate.

---

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
- Session logs are automatically created in the project root and can be safely deleted or ignored.

