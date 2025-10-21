"""Custom tools for the agent.

We expose a single `shell` tool that executes a shell command and returns
combined stdout+stderr. The tool accepts one string argument which is the
full command line including pipes or redirections.

Approval gating is implemented via dependencies (`ctx.deps`) so the CLI can
approve or deny each tool call before execution when in Approval mode.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

from pydantic_ai import RunContext

if TYPE_CHECKING:
    from .logger import SessionLogger


def run_shell_command(command: str, timeout: Optional[int] = None) -> str:
    """Run a shell command and return combined stdout+stderr as text.

    We use `bash -lc` to allow complex commands with pipes and redirection.
    A timeout may be specified to avoid long-running commands.
    """
    try:
        # On macOS, /bin/bash is available; -l ensures login env, -c runs the command
        proc = subprocess.run(
            ["/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        return output
    except subprocess.TimeoutExpired as e:
        return f"[timeout] Command exceeded {e.timeout} seconds. Partial output: {e.output or ''}{e.stderr or ''}"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"

class ApprovalDenied(Exception):
    """Raised by tools when a user denies a tool call in Approval mode."""


@dataclass
class Deps:
    """Dependencies passed to tool functions via RunContext.

    The CLI populates these so tools can render UI, request approval, and
    optionally set a timeout for command execution.
    """

    # Whether approval is required before running tools
    approval_mode: bool
    # Callback to ask for approval: returns True to proceed, False to cancel
    approve: Callable[[str, dict], bool]
    # UI object with printing helpers
    ui: any  # duck-typed UI
    # Optional timeout for shell commands (seconds)
    timeout: Optional[int] = None
    # Session logger for transparent debugging
    logger: Optional['SessionLogger'] = None


def shell(ctx: RunContext[Deps], command: str) -> str:
    """Execute a shell command with optional approval and return combined output.

    Parameters
    - command: Full shell command string (supports pipes and redirection).
    """
    # Always show the tool call to the user
    ctx.deps.ui.tool_call_box(f"shell(command={command!r})")

    # Approval gating when enabled
    allowed = True
    if ctx.deps.approval_mode:
        allowed = ctx.deps.approve("shell", {"command": command})
        if not allowed:
            ctx.deps.ui.error("Denied. Tool call cancelled.")
            # Log the denied tool call
            if ctx.deps.logger:
                interaction_num = ctx.deps.logger.log_tool_request(
                    tool_name="shell",
                    args={"command": command},
                    approval_mode=ctx.deps.approval_mode,
                    approved=False,
                )
                ctx.deps.logger.log_tool_response(
                    interaction_num=interaction_num,
                    output="",
                    error="User denied tool call",
                )
            raise ApprovalDenied("User denied shell tool call")
    
    # Log tool request
    interaction_num = None
    if ctx.deps.logger:
        interaction_num = ctx.deps.logger.log_tool_request(
            tool_name="shell",
            args={"command": command},
            approval_mode=ctx.deps.approval_mode,
            approved=allowed,
        )

    # Execute and show output
    output = run_shell_command(command, timeout=ctx.deps.timeout)
    ctx.deps.ui.tool_output_box(output if output else "<no output>")
    
    # Log tool response
    if ctx.deps.logger and interaction_num is not None:
        ctx.deps.logger.log_tool_response(
            interaction_num=interaction_num,
            output=output if output else "<no output>",
        )
    
    return output
