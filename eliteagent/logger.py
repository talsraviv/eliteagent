"""Session logger for transparent glass-box debugging.

Creates numbered session directories and logs every interaction (user input,
LLM calls, tool executions) as raw, unadulterated data files.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
        """Log user input as raw text."""
        num, interaction_dir = self._next_interaction("user")
        # Pure raw input, no decoration
        self._write_file(interaction_dir, f"{num:03d}-request.txt", user_input)
    
    def log_llm_request(
        self,
        prompt: str,
        model_name: str,
        message_history: list[Any] | None,
        system_prompt: str,
    ) -> int:
        """Log LLM request as OpenAI-style JSON.
        
        Returns:
            interaction_num to use when logging the response
        """
        num, interaction_dir = self._next_interaction("llm")
        
        # Build OpenAI-style messages array
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add message history if present
        if message_history:
            for msg in message_history:
                # Convert pydantic message to dict
                if hasattr(msg, 'model_dump'):
                    msg_dict = msg.model_dump()
                    # Extract role and content from pydantic-ai format
                    kind = msg_dict.get('kind')
                    if kind == 'request':
                        # User message
                        for part in msg_dict.get('parts', []):
                            if part.get('part_kind') == 'user-prompt':
                                messages.append({
                                    "role": "user",
                                    "content": part.get('content', '')
                                })
                    elif kind == 'response':
                        # Assistant message
                        content_parts = []
                        tool_calls = []
                        for part in msg_dict.get('parts', []):
                            part_kind = part.get('part_kind')
                            if part_kind == 'text':
                                content_parts.append(part.get('content', ''))
                            elif part_kind == 'tool-call':
                                tool_calls.append({
                                    "id": part.get('tool_call_id'),
                                    "type": "function",
                                    "function": {
                                        "name": part.get('tool_name'),
                                        "arguments": part.get('args', {})
                                    }
                                })
                        
                        assistant_msg = {"role": "assistant"}
                        if content_parts:
                            assistant_msg["content"] = "\n".join(content_parts)
                        if tool_calls:
                            assistant_msg["tool_calls"] = tool_calls
                        messages.append(assistant_msg)
        
        # Add current user prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Create request payload
        request_payload = {
            "model": model_name,
            "messages": messages
        }
        
        # Write as pure JSON
        json_content = json.dumps(request_payload, indent=2, ensure_ascii=False)
        self._write_file(interaction_dir, f"{num:03d}-request.json", json_content)
        return num
    
    def log_llm_response(
        self,
        interaction_num: int,
        messages: list[Any],
        text_parts: list[str],
    ) -> None:
        """Log LLM response as OpenAI-style JSON."""
        interaction_dir = self.session_dir / f"{interaction_num:03d}-llm"
        
        # Build OpenAI-style response
        choices = []
        
        # Find the last response message
        for msg in messages:
            if hasattr(msg, 'model_dump'):
                msg_dict = msg.model_dump()
                if msg_dict.get('kind') == 'response':
                    # Extract message content
                    content_parts = []
                    tool_calls = []
                    
                    for part in msg_dict.get('parts', []):
                        part_kind = part.get('part_kind')
                        if part_kind == 'text':
                            content_parts.append(part.get('content', ''))
                        elif part_kind == 'tool-call':
                            tool_calls.append({
                                "id": part.get('tool_call_id'),
                                "type": "function",
                                "function": {
                                    "name": part.get('tool_name'),
                                    "arguments": part.get('args', {})
                                }
                            })
                    
                    message = {"role": "assistant"}
                    if content_parts:
                        message["content"] = "\n".join(content_parts)
                    if tool_calls:
                        message["tool_calls"] = tool_calls
                    
                    choices.append({
                        "index": 0,
                        "message": message,
                        "finish_reason": msg_dict.get('finish_reason', 'stop')
                    })
                    
                    # Also extract usage if available
                    usage = msg_dict.get('usage')
                    if usage:
                        response_payload = {
                            "choices": choices,
                            "usage": usage,
                            "model": msg_dict.get('model_name', 'unknown')
                        }
                    else:
                        response_payload = {
                            "choices": choices,
                            "model": msg_dict.get('model_name', 'unknown')
                        }
                    
                    # Write as pure JSON
                    json_content = json.dumps(response_payload, indent=2, ensure_ascii=False, default=str)
                    response_num = interaction_num + 1
                    self._write_file(interaction_dir, f"{response_num:03d}-response.json", json_content)
                    return
        
        # Fallback: if we couldn't parse, write what we have
        fallback = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else ""
                }
            }]
        }
        json_content = json.dumps(fallback, indent=2, ensure_ascii=False)
        response_num = interaction_num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.json", json_content)
    
    def log_tool_request(
        self,
        tool_name: str,
        args: dict[str, Any],
        approval_mode: bool,
        approved: bool,
    ) -> int:
        """Log tool execution request as raw command.
        
        Returns:
            interaction_num to use when logging the response
        """
        num, interaction_dir = self._next_interaction("tool")
        
        # For shell tool, just log the raw command
        if tool_name == "shell" and "command" in args:
            self._write_file(interaction_dir, f"{num:03d}-request.txt", args["command"])
        else:
            # For other tools, log as JSON
            json_content = json.dumps({"tool": tool_name, **args}, indent=2, ensure_ascii=False)
            self._write_file(interaction_dir, f"{num:03d}-request.json", json_content)
        
        return num
    
    def log_tool_response(
        self,
        interaction_num: int,
        output: str,
        error: str | None = None,
    ) -> None:
        """Log tool execution response as raw output."""
        interaction_dir = self.session_dir / f"{interaction_num:03d}-tool"
        
        # Pure raw output, no decoration
        content = output
        if error:
            content = f"{output}\n\n[ERROR]\n{error}"
        
        response_num = interaction_num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.txt", content)

