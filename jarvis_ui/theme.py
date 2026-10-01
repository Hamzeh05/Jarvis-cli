from rich.console import Console
from rich.theme import Theme


JARVIS_THEME = Theme(
    {
        "jarvis": "bold cyan",
        "jarvis_dim": "dim cyan",
        "system": "bold white",
        "online": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "user": "bold white",
        "assistant": "cyan",
        "muted": "dim white",
        "accent": "bold bright_cyan",
    }
)


console = Console(theme=JARVIS_THEME)
