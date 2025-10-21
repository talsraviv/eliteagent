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
    - NNN-request.txt/json (the input/request)
    - NNN-response.txt/json (the output/response, if applicable)
    """
    
    session_dir: Path
    interaction_counter: int = 0
    turn_number: int = 0
    all_turns: list = None
    
    def __post_init__(self):
        """Initialize the turns list."""
        if self.all_turns is None:
            self.all_turns = []
    
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
    
    def _create_validation_file(self, messages: list[Any]) -> None:
        """Create a cumulative source-of-truth validation file.
        
        Tracks all turns in the session, not just the current one.
        """
        # Increment turn number
        self.turn_number += 1
        
        # Track the starting interaction for this turn
        turn_start_interaction = self.interaction_counter + 1
        
        # Build validation for this turn
        turn_validation = {
            "turn_number": self.turn_number,
            "start_interaction": turn_start_interaction,
            "total_messages": len(messages),
            "message_sequence": [],
            "expected_log_files": []
        }
        
        interaction_num = self.interaction_counter  # Current counter position
        
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            msg_info = {
                "index": i,
                "type": msg_type,
                "parts": []
            }
            
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    part_type = type(part).__name__
                    part_info = {"type": part_type}
                    
                    # Add relevant details
                    if part_type == 'UserPromptPart' and hasattr(part, 'content'):
                        part_info["content_preview"] = part.content[:50] + "..." if len(part.content) > 50 else part.content
                    elif part_type == 'ToolCallPart':
                        if hasattr(part, 'tool_name'):
                            part_info["tool_name"] = part.tool_name
                        if hasattr(part, 'tool_call_id'):
                            part_info["tool_call_id"] = part.tool_call_id
                    elif part_type == 'ToolReturnPart':
                        if hasattr(part, 'tool_call_id'):
                            part_info["tool_call_id"] = part.tool_call_id
                    elif part_type == 'TextPart' and hasattr(part, 'content'):
                        part_info["content_preview"] = part.content[:50] + "..." if len(part.content) > 50 else part.content
                    
                    msg_info["parts"].append(part_info)
            
            turn_validation["message_sequence"].append(msg_info)
            
            # Track expected log files
            if msg_type == 'ModelRequest':
                # Check if next message is a response
                if i + 1 < len(messages) and type(messages[i + 1]).__name__ == 'ModelResponse':
                    interaction_num += 1
                    turn_validation["expected_log_files"].append({
                        "interaction": f"{interaction_num:03d}-llm",
                        "files": [
                            f"{interaction_num:03d}-request.json",
                            f"{interaction_num + 1:03d}-response.json"
                        ]
                    })
                    
                    # Check if response has tool calls
                    next_msg = messages[i + 1]
                    if hasattr(next_msg, 'parts'):
                        for part in next_msg.parts:
                            if type(part).__name__ == 'ToolCallPart':
                                interaction_num += 1
                                turn_validation["expected_log_files"].append({
                                    "interaction": f"{interaction_num:03d}-tool",
                                    "files": [
                                        f"{interaction_num:03d}-request.txt",
                                        f"{interaction_num + 1:03d}-response.txt"
                                    ]
                                })
                                break
        
        # Add end interaction for this turn
        turn_validation["end_interaction"] = interaction_num
        
        # Add this turn to the session's turn list
        self.all_turns.append(turn_validation)
        
        # Write cumulative validation file
        session_validation = {
            "session_directory": str(self.session_dir.name),
            "total_turns": len(self.all_turns),
            "total_interactions": self.interaction_counter,
            "turns": self.all_turns
        }
        
        validation_content = json.dumps(session_validation, indent=2, ensure_ascii=False)
        validation_file = self.session_dir / "VALIDATION.json"
        validation_file.write_text(validation_content)
        
        # Create cumulative human-readable summary
        summary_lines = [
            "# Session Validation - Source of Truth",
            "",
            f"## Session Overview",
            f"- Total Turns: {len(self.all_turns)}",
            f"- Total Interactions: {interaction_num}",
            "",
        ]
        
        for turn in self.all_turns:
            summary_lines.extend([
                f"## Turn {turn['turn_number']} (Interactions {turn['start_interaction']:03d}-{turn['end_interaction']:03d})",
                f"Messages: {turn['total_messages']}",
                ""
            ])
            
            for msg_info in turn["message_sequence"]:
                summary_lines.append(f"{msg_info['index']}. {msg_info['type']}")
                for part in msg_info['parts']:
                    summary_lines.append(f"   - {part['type']}")
                    if 'content_preview' in part:
                        summary_lines.append(f"     Preview: {part['content_preview']}")
                    if 'tool_name' in part:
                        summary_lines.append(f"     Tool: {part['tool_name']}")
            
            summary_lines.extend([
                "",
                "### Expected Log Files",
                ""
            ])
            
            for expected in turn["expected_log_files"]:
                summary_lines.append(f"- {expected['interaction']}/")
                for file in expected['files']:
                    summary_lines.append(f"  - {file}")
            
            summary_lines.append("")
        
        summary_content = "\n".join(summary_lines)
        summary_file = self.session_dir / "VALIDATION.md"
        summary_file.write_text(summary_content)
    
    def log_conversation_turn(
        self,
        messages: list[Any],
        model_name: str,
        system_prompt: str,
    ) -> None:
        """Log all LLM request/response pairs from a conversation turn.
        
        Builds the FULL conversation context for each LLM call, exactly as
        it's sent to the API. Handles pydantic-ai ModelRequest/ModelResponse objects.
        """
        # Create source of truth validation file
        self._create_validation_file(messages)
        
        # Process messages and log each request/response pair
        i = 0
        conversation_history = []
        
        while i < len(messages):
            msg = messages[i]
            msg_type = type(msg).__name__
            
            if msg_type == 'ModelRequest':
                # Extract request data from pydantic-ai object
                parts = msg.parts if hasattr(msg, 'parts') else []
                
                # Check if this includes system prompt (first request)
                has_system = any(type(p).__name__ == 'SystemPromptPart' for p in parts)
                
                # Build the complete messages array for this API call
                current_request = []
                
                if has_system:
                    # First request: add system prompt and save to history
                    system_msg = {
                        "role": "system",
                        "content": system_prompt
                    }
                    current_request.append(system_msg)
                    conversation_history.append(system_msg)
                else:
                    # Subsequent requests: include full history
                    current_request.extend(conversation_history)
                
                # Add the new parts from this request
                for part in parts:
                    part_type = type(part).__name__
                    if part_type == 'UserPromptPart':
                        msg_obj = {
                            "role": "user",
                            "content": part.content if hasattr(part, 'content') else ''
                        }
                        current_request.append(msg_obj)
                        # Add to history for next round (only on first request)
                        if has_system:
                            conversation_history.append(msg_obj)
                    elif part_type == 'ToolReturnPart':
                        # Tool returns come after we've already added assistant message
                        current_request.append({
                            "role": "tool",
                            "tool_call_id": part.tool_call_id if hasattr(part, 'tool_call_id') else '',
                            "content": part.content if hasattr(part, 'content') else ''
                        })
                
                # Look ahead for the response
                if i + 1 < len(messages):
                    next_msg = messages[i + 1]
                    if type(next_msg).__name__ == 'ModelResponse':
                        # Log this LLM request/response pair
                        self._log_llm_pair(
                            request_messages=current_request,
                            response_obj=next_msg,
                            model_name=model_name,
                            conversation_history=conversation_history
                        )
                        
                        # Check if response has tool calls - if so, log the tool execution
                        response_parts = next_msg.parts if hasattr(next_msg, 'parts') else []
                        for part in response_parts:
                            if type(part).__name__ == 'ToolCallPart':
                                # This is a tool call - extract the command
                                tool_name = part.tool_name if hasattr(part, 'tool_name') else ''
                                tool_call_id = part.tool_call_id if hasattr(part, 'tool_call_id') else ''
                                
                                # Get the command from args
                                command = ''
                                if hasattr(part, 'args'):
                                    if isinstance(part.args, str):
                                        try:
                                            args_dict = json.loads(part.args)
                                            command = args_dict.get('command', '')
                                        except:
                                            command = part.args
                                    elif isinstance(part.args, dict):
                                        command = part.args.get('command', '')
                                
                                # Look ahead for the tool return in the next request
                                tool_output = ''
                                if i + 2 < len(messages):
                                    tool_return_msg = messages[i + 2]
                                    if type(tool_return_msg).__name__ == 'ModelRequest':
                                        return_parts = tool_return_msg.parts if hasattr(tool_return_msg, 'parts') else []
                                        for return_part in return_parts:
                                            if type(return_part).__name__ == 'ToolReturnPart':
                                                if hasattr(return_part, 'tool_call_id') and return_part.tool_call_id == tool_call_id:
                                                    tool_output = return_part.content if hasattr(return_part, 'content') else ''
                                                    break
                                
                                # Log the tool execution
                                self._log_tool_execution(
                                    tool_name=tool_name,
                                    command=command,
                                    output=tool_output
                                )
                        
                        i += 2  # Skip both request and response
                        continue
                
                i += 1
            else:
                i += 1
    
    def _log_llm_pair(
        self,
        request_messages: list[dict],
        response_obj: Any,
        model_name: str,
        conversation_history: list[dict]
    ) -> None:
        """Log a single LLM request/response pair from pydantic-ai objects."""
        # Log request
        num, interaction_dir = self._next_interaction("llm")
        
        request_payload = {
            "model": model_name,
            "messages": request_messages
        }
        
        json_content = json.dumps(request_payload, indent=2, ensure_ascii=False)
        self._write_file(interaction_dir, f"{num:03d}-request.json", json_content)
        
        # Log response - extract from pydantic-ai ModelResponse object
        parts = response_obj.parts if hasattr(response_obj, 'parts') else []
        content_parts = []
        tool_calls = []
        
        for part in parts:
            part_type = type(part).__name__
            if part_type == 'TextPart':
                if hasattr(part, 'content'):
                    content_parts.append(part.content)
            elif part_type == 'ToolCallPart':
                tool_call = {
                    "id": part.tool_call_id if hasattr(part, 'tool_call_id') else '',
                    "type": "function",
                    "function": {
                        "name": part.tool_name if hasattr(part, 'tool_name') else '',
                        "arguments": {}
                    }
                }
                # Parse args if it's JSON string
                if hasattr(part, 'args'):
                    if isinstance(part.args, str):
                        try:
                            tool_call["function"]["arguments"] = json.loads(part.args)
                        except:
                            tool_call["function"]["arguments"] = {"raw": part.args}
                    else:
                        tool_call["function"]["arguments"] = part.args
                tool_calls.append(tool_call)
        
        message = {"role": "assistant"}
        if content_parts:
            message["content"] = "\n".join(content_parts)
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        choice = {
            "index": 0,
            "message": message,
            "finish_reason": response_obj.finish_reason if hasattr(response_obj, 'finish_reason') else 'stop'
        }
        
        response_payload = {
            "choices": [choice],
            "model": model_name
        }
        
        # Add usage if available
        if hasattr(response_obj, 'usage'):
            usage_obj = response_obj.usage
            if hasattr(usage_obj, 'input_tokens'):
                response_payload["usage"] = {
                    "input_tokens": usage_obj.input_tokens,
                    "output_tokens": usage_obj.output_tokens,
                    "total_tokens": usage_obj.total_tokens if hasattr(usage_obj, 'total_tokens') else usage_obj.input_tokens + usage_obj.output_tokens
                }
        
        json_content = json.dumps(response_payload, indent=2, ensure_ascii=False, default=str)
        response_num = num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.json", json_content)
        
        # Add the assistant response to conversation history
        conversation_history.append(message)
    
    def _log_tool_execution(
        self,
        tool_name: str,
        command: str,
        output: str
    ) -> None:
        """Log a tool execution (request + response) from message history."""
        # Log tool request
        num, interaction_dir = self._next_interaction("tool")
        self._write_file(interaction_dir, f"{num:03d}-request.txt", command)
        
        # Log tool response
        response_num = num + 1
        self._write_file(interaction_dir, f"{response_num:03d}-response.txt", output if output else "<no output>")
    
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
