from __future__ import annotations

import asyncio

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from harness.runner import TaskRunSession

from .display import (
    show_assistant,
    show_banner,
    show_error,
    show_processing,
    show_success,
    show_system_status,
    show_user,
    show_welcome,
)
from .theme import console


PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "ansicyan bold",
    }
)


HELP_TEXT = """
[bold cyan]JARVIS COMMANDS[/bold cyan]

[bold white]General[/bold white]
  /help                         Show this help
  /status                       Show system status
  /clear                        Clear the screen
  /exit                         Exit JARVIS
  /quit                         Exit JARVIS

[bold white]Models[/bold white]
  /models                       List available models
  /model                        Show current model
  /model <model>                Change the active model
  /model_change on|off          Enable or disable automatic model selection

[bold white]Execution[/bold white]
  /dryrun on|off                Enable or disable dry-run mode
  /queue on|off                 Enable or disable queue mode
  /queue                        Show queued requests

[bold white]Memory[/bold white]
  /memory                       Show stored memory
  /memory set <scope> <key> <value>
                                Store a memory value
  /memory clear <scope> <key>  Remove a memory value

[bold white]Background Jobs[/bold white]
  /bg <request>                 Run a request in the background
  /jobs                         List background jobs
  /job <id>                     Show a background job
  /cancel <id>                  Cancel a background job

[bold white]Other[/bold white]
  /undo                         Undo the last reversible action

[bold cyan]Normal requests[/bold cyan]
  Type normally and JARVIS will route the request to the
  appropriate specialist agent.

Examples:

  Check Jira ticket WUK-2312
  Search Splunk for failed login events
  Find the status of WUK-2312
"""


def get_prompt_session() -> PromptSession:
    """Create the interactive terminal input session."""

    return PromptSession(
        history=FileHistory(".jarvis_history"),
        style=PROMPT_STYLE,
    )


def show_help() -> None:
    """Display the JARVIS command reference."""

    console.print()
    console.print(HELP_TEXT)
    console.print()


def show_model_info(session: TaskRunSession) -> None:
    """Display the currently selected model when available."""

    model_name = getattr(session, "selected_model_id", None)

    if not model_name:
        model_name = "AUTO"

    console.print(
        f"[system]Current model:[/system] [accent]{model_name}[/accent]"
    )


def show_queue_info(session: TaskRunSession) -> None:
    """Display queue information when available."""

    queue = getattr(session, "queue", None)

    if queue is None:
        console.print("[muted]Queue information unavailable.[/muted]")
        return

    console.print(f"[system]Queue:[/system] {queue}")


def show_memory_info(session: TaskRunSession) -> None:
    """Display memory information when available."""

    memory = getattr(session, "memory", None)

    if memory is None:
        console.print("[muted]Memory information unavailable.[/muted]")
        return

    console.print(f"[system]Memory:[/system] {memory}")


def handle_local_command(
    session: TaskRunSession,
    request: str,
) -> bool:
    """
    Handle commands that belong to the UI itself.

    Returns True when the command was handled locally.
    """

    parts = request.split(maxsplit=2)
    command = parts[0].lower()

    if command in {"/help", "/h"}:
        show_help()
        return True

    if command == "/status":
        show_system_status(
            model="AUTO",
            agent_count=2,
            mcp_status="READY",
            session_status="ACTIVE",
        )
        return True

    if command == "/clear":
        console.clear()
        show_banner()
        show_system_status(
            model="AUTO",
            agent_count=2,
            mcp_status="READY",
            session_status="ACTIVE",
        )
        show_welcome()
        return True

    if command in {"/exit", "/quit"}:
        return True

    if command == "/model":
        show_model_info(session)
        return True

    if command == "/models":
        console.print(
            "[muted]Model listing is handled by the existing JARVIS "
            "model registry. This command will be connected next.[/muted]"
        )
        return True

    if command == "/model_change":
        if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
            show_error("Usage: /model_change on|off")
        else:
            console.print(
                f"[system]Automatic model selection:[/system] "
                f"[accent]{parts[1].upper()}[/accent]"
            )
        return True

    if command == "/dryrun":
        if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
            show_error("Usage: /dryrun on|off")
        else:
            session.dry_run = parts[1].lower() == "on"
            state = "ON" if session.dry_run else "OFF"
            console.print(
                f"[system]Dry-run mode:[/system] [accent]{state}[/accent]"
            )
        return True

    if command == "/queue":
        if len(parts) == 1:
            show_queue_info(session)
            return True

        if parts[1].lower() not in {"on", "off"}:
            show_error("Usage: /queue on|off")
        else:
            session.queue_mode = parts[1].lower() == "on"
            state = "ON" if session.queue_mode else "OFF"
            console.print(
                f"[system]Queue mode:[/system] [accent]{state}[/accent]"
            )
        return True

    if command == "/memory":
        show_memory_info(session)
        return True

    if command == "/undo":
        console.print(
            "[muted]Undo is handled by the existing JARVIS undo manager.[/muted]"
        )
        return True

    if command == "/jobs":
        jobs = getattr(session, "background_jobs", {})

        if not jobs:
            console.print("[muted]No background jobs.[/muted]")
        else:
            for job_id, job in jobs.items():
                console.print(f"[system]{job_id}[/system]  {job}")

        return True

    if command == "/job":
        if len(parts) < 2:
            show_error("Usage: /job <id>")
        else:
            jobs = getattr(session, "background_jobs", {})
            job = jobs.get(parts[1])

            if job is None:
                show_error(f"Background job not found: {parts[1]}")
            else:
                console.print(job)

        return True

    if command == "/cancel":
        if len(parts) < 2:
            show_error("Usage: /cancel <id>")
        else:
            show_error(
                "Background-job cancellation will be connected to "
                "the existing session API next."
            )

        return True

    if command == "/bg":
        if len(parts) < 2:
            show_error("Usage: /bg <request>")
        else:
            show_error(
                "Background-job launching will be connected to "
                "the existing session API next."
            )

        return True

    return False


async def process_request(
    session: TaskRunSession,
    request: str,
) -> None:
    """Send a normal request through the existing JARVIS engine."""

    show_user(request)
    show_processing()

    try:
        answer = await session.send(request)

        if answer:
            show_assistant(str(answer))

        show_success()

    except KeyboardInterrupt:
        show_error("Request interrupted.")

    except Exception as exc:
        show_error(f"Request failed: {exc}")


async def run() -> None:
    """Run the JARVIS interactive interface."""

    console.clear()

    show_banner()

    session = TaskRunSession()

    show_system_status(
        model="AUTO",
        agent_count=2,
        mcp_status="READY",
        session_status="ACTIVE",
    )

    show_welcome()

    prompt_session = get_prompt_session()

    try:
        while True:
            try:
                request = await prompt_session.prompt_async(
                    "❯ ",
                )

            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            request = request.strip()

            if not request:
                continue

            command = request.lower()

            if command in {"/exit", "/quit"}:
                console.print()
                console.print("[jarvis]JARVIS shutting down.[/jarvis]")
                break

            if handle_local_command(session, request):
                continue

            await process_request(session, request)

    finally:
        await session.close()


def main() -> None:
    """Application entry point."""

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print()


if __name__ == "__main__":
    main()
