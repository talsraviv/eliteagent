"""EliteAgent: Terminal AI coding agent using pydantic-ai, rich, prompt-toolkit.

Features
- Multiple models: OpenAI GPT-5, Anthropic Claude 4.5 Sonnet, OpenRouter Grok Code Fast
- Rich UI: boxed messages, color-coding, thinking spinner
- prompt-toolkit: history, basic autocompletion
- Tool: shell (single string command), outputs stdout+stderr
- Modes: Approval vs YOLO for tool execution
- Ctrl+C handling: abort generation or exit gracefully
- .env loading for API keys
- Conversation history persisted in-memory per session
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings  # noqa: F401 (reserved for future)

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from .models import build_model, ModelName, SYSTEM_PROMPT
from .tools import Deps, shell, ApprovalDenied
from .ui import UI
from .logger import SessionLogger


HISTORY_PATH = os.path.expanduser("~/.eliteagent_history")
DEFAULT_MODEL: ModelName = "gpt-5"


@dataclass
class AppState:
    model_name: ModelName = DEFAULT_MODEL
    approval_mode: bool = True  # True=Approval, False=YOLO
    history: List[ModelMessage] | None = None


class AbortGeneration(Exception):
    pass


def _make_agent(state: AppState) -> Agent:
    model = build_model(state.model_name)
    # Register shell tool at construction; deps will be provided at run time
    return Agent(model, system_prompt=SYSTEM_PROMPT, tools=[shell], deps_type=Deps)


def _available_models_from_env() -> list[ModelName]:
    """Check env for available API keys and return usable models."""
    avail: list[ModelName] = []
    if os.environ.get("OPENAI_API_KEY"):
        avail.append("gpt-5")
    if os.environ.get("ANTHROPIC_API_KEY"):
        avail.append("claude-4.5-sonnet")
    if os.environ.get("OPENROUTER_API_KEY"):
        avail.append("grok-code-fast-1")
    return avail


def _prompt_model_selection(ui: UI, current: ModelName) -> ModelName | None:
    """Prompt the user to select a model, preferring ones with keys set."""
    avail = _available_models_from_env()
    ui.info("[info]Select model: 1) GPT-5  2) Claude 4.5 Sonnet  3) Grok Code Fast")
    if not avail:
        ui.error(
            "No API keys found. Set at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY in .env"
        )
    else:
        ui.info(
            "[info]Available with keys: "
            + ", ".join(
                [
                    m
                    for m in ["gpt-5", "claude-4.5-sonnet", "grok-code-fast-1"]
                    if m in avail
                ]
            )
        )
    sel = input().strip()
    mapping: dict[str, ModelName] = {
        "1": "gpt-5",
        "2": "claude-4.5-sonnet",
        "3": "grok-code-fast-1",
    }
    chosen = mapping.get(sel)
    if chosen is None:
        ui.error("Invalid selection.")
        return None
    return chosen


async def ask_model(agent: Agent, prompt: str, history: list[ModelMessage] | None, ui: UI):
    # Stream text to display thoughts progressively; collect messages afterwards
    try:
        async with agent.run_stream(prompt, message_history=history) as result:
            # There is no way to intercept tool calls here with custom approval,
            # so we run models without registering shell tool directly. We'll mediate
            # tool execution by instructing the model to propose shell commands in a
            # special format and let the CLI execute them. However, the requirement
            # says we must use provided tools. Therefore, we'll run non-streaming
            # to intercept tool calls using agent.run and tool decorators instead.
            async for text in result.stream_text():
                ui.model_box(text)
            return result.all_messages()
    except KeyboardInterrupt as e:
        raise AbortGeneration from e



def _handle_slash_command(text: str, state: AppState, ui: UI) -> Optional[str]:
    if text == "/new":
        state.history = None
        ui.info("[info]Session cleared.")
        return None
    if text.startswith("/model"):
        ui.info("[info]Select model: 1) GPT-5  2) Claude 4.5 Sonnet  3) Grok Code Fast")
        sel = input().strip()
        mapping = {"1": "gpt-5", "2": "claude-4.5-sonnet", "3": "grok-code-fast-1"}
        chosen = mapping.get(sel)
        if chosen is None:
            ui.error("Invalid selection.")
        else:
            state.model_name = chosen  # type: ignore[assignment]
            ui.info(f"[info]Model set to {state.model_name}")
        return None
    if text == "/approval":
        state.approval_mode = not state.approval_mode
        mode = "Approval" if state.approval_mode else "YOLO"
        ui.info(f"[info]Mode switched to {mode} mode.")
        return None
    return text


def main() -> None:
    # Load env
    load_dotenv()

    # UI
    ui = UI.make()
    
    # Initialize session logger for transparent debugging
    logger = SessionLogger.create_new_session()
    ui.info(f"[info]Session logging to: {logger.session_dir}")

    # Choose a sensible default model if the current one lacks an API key
    def _auto_pick_model() -> ModelName:
        env_avail = _available_models_from_env()
        if not env_avail:
            return DEFAULT_MODEL
        # Prefer current if available, otherwise first available
        if DEFAULT_MODEL in env_avail:
            return DEFAULT_MODEL
        return env_avail[0]

    # Prompt session
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    session = PromptSession(
        history=FileHistory(HISTORY_PATH),
        completer=WordCompleter(["/new", "/model", "/approval"], ignore_case=True),
    )

    state = AppState()
    # Auto-pick available model at startup
    state.model_name = _auto_pick_model()
    if state.model_name != DEFAULT_MODEL:
        ui.info(f"[info]Using available model: {state.model_name}")

    # Ctrl+C behavior handled by catching KeyboardInterrupt in loops
    ui.info("[info]EliteAgent ready. Type your request. Use /model, /approval, /new.")

    while True:
        try:
            text = session.prompt("› ")
        except KeyboardInterrupt:
            # Ctrl+C at prompt exits
            ui.info("[info]Exiting. Bye.")
            break
        except EOFError:
            ui.info("[info]EOF. Bye.")
            break

        if not text.strip():
            continue

        # Slash commands
        if text.startswith("/"):
            res = _handle_slash_command(text.strip(), state, ui)
            if res is None:
                continue
            else:
                text = res

        # Log user input
        logger.log_user_input(text)
        
        # Show user box
        ui.user_box(text)

        # Build agent per current model
        try:
            agent = _make_agent(state)
        except Exception as e:
            ui.error(f"[error]Failed to initialize model '{state.model_name}': {e}")
            ui.info("[info]Tip: create a .env with the appropriate API key(s).")
            try:
                chosen = _prompt_model_selection(ui, state.model_name)
            except KeyboardInterrupt:
                ui.info("[info]Cancelled. Back to prompt.")
                continue
            if chosen is None:
                continue
            state.model_name = chosen
            try:
                agent = _make_agent(state)
            except Exception as e2:
                ui.error(f"[error]Still failed to initialize: {e2}")
                continue

        # We will run non-streaming and let pydantic-ai handle tool calls via our shell tool.
        try:
            with ui.thinking():
                # Prepare deps for tools
                def approve(name: str, args: dict) -> bool:
                    if not state.approval_mode:
                        return True
                    ui.info("[info]Approval required. Execute this tool call? [y/N]")
                    try:
                        choice = input().strip().lower()
                    except KeyboardInterrupt:
                        return False
                    return choice in {"y", "yes"}

                deps = Deps(
                    approval_mode=state.approval_mode,
                    approve=approve,
                    ui=ui,
                    timeout=None,
                    logger=logger,
                )
                
                result = agent.run_sync(text, message_history=state.history, deps=deps)
        except KeyboardInterrupt:
            # Abort generation and return to idle
            ui.error("Generation aborted.")
            continue
        except ApprovalDenied:
            # Tool call denied in Approval mode, continue loop
            state.history = result.all_messages() if 'result' in locals() else state.history
            continue

        # Get all messages from this run
        messages = result.all_messages()
        
        # Log each LLM request/response pair by parsing the message history
        # Messages come in pairs: request (with user/tool parts) followed by response
        logger.log_conversation_turn(
            messages=messages,
            model_name=state.model_name,
            system_prompt=SYSTEM_PROMPT,
        )
        
        # Display model text parts to user
        model_texts: list[str] = []
        for m in messages:
            if getattr(m, "kind", None) == "response":
                for p in m.parts:
                    if getattr(p, "part_kind", None) == "text" and p.content:
                        model_texts.append(p.content)
        if model_texts:
            ui.model_box("\n\n".join(model_texts))

        # Tools were executed automatically by pydantic-ai; nothing to intercept here.
        # Maintain full history for session continuity by appending new messages
        if state.history:
            try:
                state.history = state.history + result.new_messages()
            except Exception:
                # Fallback to full messages if new_messages unavailable
                state.history = messages
        else:
            state.history = messages

        # Loop continues


if __name__ == "__main__":
    main()
