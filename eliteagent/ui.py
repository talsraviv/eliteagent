"""UI utilities built with rich for pretty terminal output."""
from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme


THEME = Theme(
    {
        "user": "bold cyan",
        "model": "bold magenta",
        "tool": "bold yellow",
        "tool_out": "bright_yellow",
        "sys": "dim white",
        "info": "green",
        "error": "bold red",
    }
)


@dataclass
class UI:
    console: Console

    @classmethod
    def make(cls) -> "UI":
        return cls(console=Console(theme=THEME))

    def box(self, title: str, content: str, style: str) -> None:
        panel = Panel.fit(Text.from_markup(content), title=title, border_style=style)
        self.console.print(panel)

    def user_box(self, content: str) -> None:
        self.box("User", content, "user")

    def model_box(self, content: str) -> None:
        self.box("Model", content, "model")

    def tool_call_box(self, content: str) -> None:
        self.box("Tool Call", content, "tool")

    def tool_output_box(self, content: str) -> None:
        self.box("Tool Output", content, "tool_out")

    def info(self, content: str) -> None:
        self.console.print(Text.from_markup(content, style="info"))

    def error(self, content: str) -> None:
        self.console.print(Text.from_markup(content, style="error"))

    def thinking(self):
        return self.console.status("[model]Thinking...[/]", spinner="dots")
