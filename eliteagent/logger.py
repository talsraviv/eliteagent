"""Session logger for transparent glass-box debugging.

Creates numbered session directories and logs every interaction (user input,
LLM calls, tool executions) as raw markdown files for educational transparency.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionLogger:
    """Logs all agent interactions to numbered session directories.
    
    Each session gets a directory like session_001/, session_002/, etc.
    Within each session, interactions are numbered chronologically:
    - 001-user/, 002-llm/, 003-tool/, etc.
    
    Each interaction directory contains:
    - NNN-request.md (the input/request)
    - NNN-response.md (the output/response, if applicable)
    """
    
    session_dir: Path
    interaction_counter: int = 0
    
    @classmethod
    def create_new_session(cls, base_dir: Path | str = ".") -> SessionLogger:
        """Create a new session with auto-incremented number.
        
        Reads .last_session file to get the next session number,
        creates the session directory, and updates the counter.
        """
        base_path = Path(base_dir)
        counter_file = base_path / ".last_session"
        
        # Read last session number
        if counter_file.exists():
            try:
                last_session = int(counter_file.read_text().strip())
            except (ValueError, OSError):
                last_session = 0
        else:
            last_session = 0
        
        # Increment and create new session
        new_session = last_session + 1
        session_dir = base_path / f"session_{new_session:03d}"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Update counter file
        counter_file.write_text(str(new_session))
        
        return cls(session_dir=session_dir, interaction_counter=0)
    
    def _next_interaction(self, interaction_type: str) -> tuple[int, Path]:
        """Get next interaction number and create its directory.
        
        Returns:
            (interaction_num, interaction_dir)
        """
        self.interaction_counter += 1
        num = self.interaction_counter
        interaction_dir = self.session_dir / f"{num:03d}-{interaction_type}"
        interaction_dir.mkdir(parents=True, exist_ok=True)
        return num, interaction_dir
    
    def _write_file(self, dir_path: Path, filename: str, content: str) -> None:
        """Write content to a file in the given directory."""
        file_path = dir_path / filename
        file_path.write_text(content)
    
    def log_user_input(self, user_input: str) -> None:
        """Log user input as a request-only interaction."""
        num, interaction_dir = self._next_interaction("user")
        
        content = f"""# User Input

**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Interaction**: {num:03d}

## Input
```
{user_input}
```
"""
        self._write_file(interaction_dir, f"{num:03d}-request.md", content)
    
    def log_llm_request(
        self,
        prompt: str,
        model_name: str,
        message_history: list[Any] | None,
        system_prompt: str,
    ) -> int:
        """Log LLM request and return interaction number for later response logging.
        
        Returns:
            interaction_num to use when logging the response
        """
        num, interaction_dir = self._next_interaction("llm")
        
        # Format message history as JSON if present
        history_json = "null"
        if message_history:
            try:
                # Convert pydantic messages to dict for serialization
                history_dicts = []
                for msg in message_history:
                    if hasattr(msg, 'model_dump'):
                        history_dicts.append(msg.model_dump())
                    else:
                        history_dicts.append(str(msg))
                history_json = json.dumps(history_dicts, indent=2)
            except Exception:
                history_json = f"<{len(message_history)} messages - serialization failed>"
        
        content = f"""# LLM Request

**Model**: {model_name}
**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Interaction**: {num:03d}

## User Prompt
```
{prompt}
```

## Message History
```json
{history_json}
```

## System Prompt
```
{system_prompt}
```
"""
        self._write_file(interaction_dir, f"{num:03d}-request.md", content)
        return num
    
    def log_llm_response(
        self,
        interaction_num: int,
        messages: list[Any],
        text_parts: list[str],
    ) -> None:
        """Log LLM response to the same interaction directory as the request."""
        interaction_dir = self.session_dir / f"{interaction_num:03d}-llm"
        
        # Serialize all messages
        messages_json = "[]"
        try:
            msg_dicts = []
            for msg in messages:
                if hasattr(msg, 'model_dump'):
                    msg_dicts.append(msg.model_dump())
                else:
                    msg_dicts.append(str(msg))
            messages_json = json.dumps(msg_dicts, indent=2)
        except Exception as e:
            messages_json = f"<serialization failed: {e}>"
        
        # Extract text content
        text_content = "\n\n".join(text_parts) if text_parts else "<no text response>"
        
        content = f"""# LLM Response

**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Interaction**: {interaction_num:03d}

## Text Output
```
{text_content}
```

## All Messages (Raw)
```json
{messages_json}
```
"""
        response_num = interaction_num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.md", content)
    
    def log_tool_request(
        self,
        tool_name: str,
        args: dict[str, Any],
        approval_mode: bool,
        approved: bool,
    ) -> int:
        """Log tool execution request.
        
        Returns:
            interaction_num to use when logging the response
        """
        num, interaction_dir = self._next_interaction("tool")
        
        # Format args nicely
        args_str = "\n".join(f"**{k}**: {v}" for k, v in args.items())
        
        content = f"""# Tool Call: {tool_name}

**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Interaction**: {num:03d}
**Approval Mode**: {approval_mode}
**Approved**: {approved}

## Arguments
{args_str}

## Command
```bash
{args.get('command', '<no command>')}
```
"""
        self._write_file(interaction_dir, f"{num:03d}-request.md", content)
        return num
    
    def log_tool_response(
        self,
        interaction_num: int,
        output: str,
        error: str | None = None,
    ) -> None:
        """Log tool execution response."""
        interaction_dir = self.session_dir / f"{interaction_num:03d}-tool"
        
        content = f"""# Tool Response

**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Interaction**: {interaction_num:03d}

## Output
```
{output}
```
"""
        
        if error:
            content += f"""
## Error
```
{error}
```
"""
        
        response_num = interaction_num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.md", content)

