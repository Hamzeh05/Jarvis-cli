from __future__ import annotations

from typing import Optional

from pyfiglet import Figlet
from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .theme import console


def show_banner() -> None:
    """Display the JARVIS startup banner."""

    figlet = Figlet(font="slant")
    banner = figlet.renderText("JARVIS")

    text = Text(banner, style="jarvis")

    panel = Panel(
        Align.center(text),
        box=ROUNDED,
        border_style="jarvis",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print(
        Align.center(
            Text(
                "LOCAL AI AGENT HARNESS",
                style="jarvis_dim",
            )
        )
    )
    console.print()


def show_system_status(
    *,
    model: Optional[str] = None,
    agent_count: int = 0,
    mcp_status: str = "READY",
    session_status: str = "ACTIVE",
) -> None:
    """Display the current JARVIS system status."""

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=True,
    )

    table.add_column("Component", style="system")
    table.add_column("Status")
    table.add_column("Component", style="system")
    table.add_column("Status")

    model_name = model or "DEFAULT"

    table.add_row(
        "● CORE",
        Text("ONLINE", style="online"),
        "● ROUTER",
        Text("READY", style="online"),
    )

    table.add_row(
        "● AGENTS",
        Text(f"{agent_count} ACTIVE", style="online"),
        "● MCP",
        Text(mcp_status, style="online"),
    )

    table.add_row(
        "● MODEL",
        Text(model_name, style="accent"),
        "● SESSION",
        Text(session_status, style="online"),
    )

    panel = Panel(
        table,
        title="[jarvis]SYSTEM[/jarvis]",
        border_style="jarvis_dim",
        box=ROUNDED,
    )

    console.print(panel)


def show_assistant(message: str) -> None:
    """Display a JARVIS response."""

    panel = Panel(
        message,
        title="[assistant]JARVIS[/assistant]",
        border_style="jarvis",
        box=ROUNDED,
        padding=(1, 2),
    )

    console.print(panel)


def show_user(message: str) -> None:
    """Display the user's submitted request."""

    console.print()
    console.print(
        Text.assemble(
            ("You  ", "user"),
            (message, "user"),
        )
    )


def show_processing() -> None:
    """Display a simple processing indicator."""

    console.print(
        Text(
            "◉ ANALYZING REQUEST",
            style="jarvis_dim",
        )
    )


def show_routing(agent_name: str) -> None:
    """Display the selected routing destination."""

    console.print(
        Text(
            f"◉ ROUTING → {agent_name.upper()}",
            style="jarvis_dim",
        )
    )


def show_success(message: str = "Request completed") -> None:
    """Display a successful completion message."""

    console.print(
        Text(
            f"✓ {message}",
            style="online",
        )
    )


def show_error(message: str) -> None:
    """Display an error message."""

    console.print(
        Text(
            f"✗ {message}",
            style="error",
        )
    )


def show_separator() -> None:
    """Display a subtle visual separator."""

    console.print(
        Text(
            "─" * 64,
            style="jarvis_dim",
        )
    )


def show_welcome() -> None:
    """Display the initial JARVIS welcome message."""

    content = Group(
        Text(
            "Good day. JARVIS is ready.",
            style="assistant",
        ),
        Text(
            "How may I assist you?",
            style="muted",
        ),
    )

    panel = Panel(
        content,
        title="[jarvis]JARVIS[/jarvis]",
        border_style="jarvis",
        box=ROUNDED,
        padding=(1, 2),
    )

    console.print(panel)
