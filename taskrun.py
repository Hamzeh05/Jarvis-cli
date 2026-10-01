import asyncio
import sys

from harness.runner import TaskRunSession
from harness.context import is_approval_waiting

from harness.model_selector import (
    format_model_status,
    set_auto_mode,
    set_manual_model,
)

from harness.model_registry import (
    list_models,
)


# ============================================================
# COLORS
# ============================================================

RESET = "\033[0m"
BOLD = "\033[1m"

BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
GRAY = "\033[90m"


# ============================================================
# TERMINAL HELPERS
# ============================================================

def supports_color():

    return sys.stdout.isatty()


def color(
    text,
    code,
):

    if not supports_color():

        return text

    return (
        f"{code}{text}{RESET}"
    )


def clear_screen():

    print(
        "\033[2J\033[H",
        end="",
    )


def line(
    width=78,
):

    print(
        color(
            "─" * width,
            BLUE,
        )
    )


def double_line(
    width=78,
):

    print(
        color(
            "═" * width,
            BLUE,
        )
    )


# ============================================================
# HEADER
# ============================================================

def print_header(
    session,
):

    print()

    double_line()

    print(
        color(
            "  TASKRUN",
            BOLD + BLUE,
        )
    )

    print(
        color(
            "  Agent Harness",
            CYAN,
        )
    )

    line()

    print(
        f"  Session      : "
        f"{color(session.session_id, CYAN)}"
    )

    print(
        f"  Dry Run      : "
        f"{color(str(session.dry_run), YELLOW if session.dry_run else GREEN)}"
    )

    print(
        f"  Queue Mode   : "
        f"{color(str(session.queue_mode), YELLOW if session.queue_mode else GREEN)}"
    )

    try:

        jobs = session.list_jobs()

        running = sum(
            1
            for job in jobs
            if job.status() == "running"
        )

        print(
            f"  Background   : "
            f"{color(str(len(jobs)), CYAN)} jobs "
            f"({color(str(running), YELLOW)} running)"
        )

    except Exception:

        print(
            "  Background   : unavailable"
        )

    double_line()

    print()


# ============================================================
# HELP
# ============================================================

def print_help():

    print()

    double_line()

    print(
        color(
            "  TASKRUN COMMANDS",
            BOLD + BLUE,
        )
    )

    line()

    commands = [

        (
            "/help",
            "Show all commands",
        ),

        (
            "/status",
            "Show current TaskRun status",
        ),

        (
            "/clear",
            "Clear the terminal screen",
        ),

        (
            "/model",
            "Show model configuration",
        ),

        (
            "/model <model>",
            "Manually select a model",
        ),

        (
            "/model_change on",
            "Enable automatic model selection",
        ),

        (
            "/model_change off",
            "Disable automatic model selection",
        ),

        (
            "/dryrun on",
            "Enable dry-run mode",
        ),

        (
            "/dryrun off",
            "Disable dry-run mode",
        ),

        (
            "/queue on",
            "Enable command queue mode",
        ),

        (
            "/queue off",
            "Disable command queue mode",
        ),

        (
            "/queue",
            "Show queued commands",
        ),

        (
            "/memory",
            "Show stored memory",
        ),

        (
            "/memory set <scope> <key> <value>",
            "Store a memory value",
        ),

        (
            "/memory clear <scope> <key>",
            "Clear a memory value",
        ),

        (
            "/undo",
            "Undo the last reversible operation",
        ),

        (
            "/bg <request>",
            "Run a request in the background",
        ),

        (
            "/jobs",
            "List background jobs",
        ),

        (
            "/job <id>",
            "Show background job details",
        ),

        (
            "/cancel <id>",
            "Cancel a background job",
        ),

        (
            "/exit",
            "Exit TaskRun",
        ),
    ]

    for command, description in commands:

        print(
            f"  {command:45}"
            f"{color(description, WHITE)}"
        )

    line()

    print(
        color(
            "  You can also type a normal request to the agent.",
            GRAY,
        )
    )

    print()

    double_line()

    print()


# ============================================================
# STATUS
# ============================================================

def print_status(
    session,
):

    print()

    double_line()

    print(
        color(
            "  STATUS",
            BOLD + BLUE,
        )
    )

    line()

    print(
        f"  Session ID   : "
        f"{color(session.session_id, CYAN)}"
    )

    print(
        f"  Dry Run      : "
        f"{color(str(session.dry_run), YELLOW if session.dry_run else GREEN)}"
    )

    print(
        f"  Queue Mode   : "
        f"{color(str(session.queue_mode), YELLOW if session.queue_mode else GREEN)}"
    )

    try:

        items = session.queue.recent(
            10
        )

        print(
            f"  Queue Items  : "
            f"{color(str(len(items)), CYAN)}"
        )

    except Exception:

        print(
            "  Queue Items  : unavailable"
        )

    try:

        jobs = session.list_jobs()

        running = sum(
            1
            for job in jobs
            if job.status() == "running"
        )

        print(
            f"  Jobs         : "
            f"{color(str(len(jobs)), CYAN)} total / "
            f"{color(str(running), YELLOW)} running"
        )

    except Exception:

        print(
            "  Jobs         : unavailable"
        )

    line()

    print()


# ============================================================
# QUEUE
# ============================================================

def print_queue(
    session,
):

    print()

    double_line()

    print(
        color(
            "  COMMAND QUEUE",
            BOLD + BLUE,
        )
    )

    line()

    items = session.queue.recent(
        10
    )

    if not items:

        print(
            color(
                "  Queue is empty.",
                GRAY,
            )
        )

        print()

        return

    for item in items:

        status_color = CYAN

        if item.status == "completed":

            status_color = GREEN

        elif item.status == "failed":

            status_color = RED

        elif item.status == "running":

            status_color = YELLOW

        print(
            f"  [{color(item.id, CYAN)}] "
            f"{color(item.status, status_color)} "
            f"{item.tool}"
        )

        print(
            f"      {item.operation}"
        )

        if item.result:

            print(
                color(
                    f"      Result: {item.result}",
                    GRAY,
                )
            )

        if item.error:

            print(
                color(
                    f"      Error: {item.error}",
                    RED,
                )
            )

        print()

    line()

    print()


# ============================================================
# MEMORY
# ============================================================

def print_memory(
    session,
):

    print()

    double_line()

    print(
        color(
            "  MEMORY",
            BOLD + BLUE,
        )
    )

    line()

    try:

        summary = session.memory.summary()

        if not summary:

            print(
                color(
                    "  Memory is empty.",
                    GRAY,
                )
            )

        else:

            print(
                summary
            )

    except Exception as exc:

        print(
            color(
                f"  Memory error: {exc}",
                RED,
            )
        )

    print()

    line()

    print()


# ============================================================
# BACKGROUND JOBS
# ============================================================

def print_jobs(
    session,
):

    print()

    double_line()

    print(
        color(
            "  BACKGROUND JOBS",
            BOLD + BLUE,
        )
    )

    line()

    jobs = session.list_jobs()

    if not jobs:

        print(
            color(
                "  No background jobs.",
                GRAY,
            )
        )

        print()

        return

    for job in jobs:

        status = job.status()

        if status == "completed":

            status_color = GREEN

        elif status == "failed":

            status_color = RED

        elif status == "cancelled":

            status_color = YELLOW

        else:

            status_color = CYAN

        print(
            f"  [{color(job.job_id, CYAN)}] "
            f"{color(status, status_color)}"
        )

        print(
            f"      {job.request}"
        )

        if job.model_id:

            print(
                f"      Model: "
                f"{color(job.model_id, CYAN)}"
            )

        print()


    line()

    print()


# ============================================================
# SINGLE JOB
# ============================================================

def print_job(
    session,
    job_id,
):

    print()

    double_line()

    print(
        color(
            "  BACKGROUND JOB",
            BOLD + BLUE,
        )
    )

    line()

    job = session.get_job(
        job_id
    )

    if job is None:

        print(
            color(
                f"  Job '{job_id}' was not found.",
                RED,
            )
        )

        print()

        return

    print(
        f"  ID        : "
        f"{color(job.job_id, CYAN)}"
    )

    print(
        f"  Status    : "
        f"{color(job.status(), GREEN)}"
    )

    print(
        f"  Request   : "
        f"{job.request}"
    )

    if job.model_id:

        print(
            f"  Model     : "
            f"{color(job.model_id, CYAN)}"
        )

    print(
        f"  Created   : "
        f"{job.created_at}"
    )

    if job.completed_at:

        print(
            f"  Completed : "
            f"{job.completed_at}"
        )

    if job.result is not None:

        print()

        print(
            color(
                "  RESULT",
                BOLD + CYAN,
            )
        )

        line()

        print(
            job.result
        )

    if job.error:

        print()

        print(
            color(
                "  ERROR",
                BOLD + RED,
            )
        )

        line()

        print(
            job.error
        )

    print()

    double_line()

    print()


# ============================================================
# AGENT RESPONSE
# ============================================================

def print_agent_response(
    answer,
):

    print()

    line()

    print(
        color(
            "  TASKRUN",
            BOLD + BLUE,
        )
    )

    line()

    if answer is None:

        print(
            color(
                "  No response.",
                GRAY,
            )
        )

    else:

        print(
            answer
        )

    print()

    double_line()

    print()


# ============================================================
# RUN FOREGROUND REQUEST
# ============================================================

async def run_agent(
    session,
    request,
):

    # --------------------------------------------------------
    # MODEL SELECTION HAPPENS BEFORE THE SPINNER
    # --------------------------------------------------------

    selection = await session.prepare_model(
        request
    )

    selected_model_id = (
        selection["model"]
    )

    print(
        color(
            "  TaskRun is working...",
            CYAN,
        )
    )

    task = asyncio.create_task(
        session.send(
            request,
            selected_model_id=
                selected_model_id,
        )
    )

    spinner = [
        "⠋",
        "⠙",
        "⠹",
        "⠸",
        "⠼",
        "⠴",
        "⠦",
        "⠧",
        "⠇",
        "⠏",
    ]

    index = 0

    while not task.done():

        if not is_approval_waiting():

            print(
                f"\r  "
                f"{color(spinner[index % len(spinner)], BLUE)}",
                end="",
                flush=True,
            )

            index += 1

        await asyncio.sleep(
            0.1
        )

    print(
        "\r  ",
        end="",
        flush=True,
    )

    try:

        result = await task

        return result

    except asyncio.CancelledError:

        print()

        print(
            color(
                "  Request cancelled.",
                YELLOW,
            )
        )

        return None

    except Exception as exc:

        print()

        print(
            color(
                f"  TaskRun error: {exc}",
                RED,
            )
        )

        return None


# ============================================================
# MODEL COMMANDS
# ============================================================

def print_models():

    print()

    double_line()

    print(
        color(
            "  AVAILABLE MODELS",
            BOLD + BLUE,
        )
    )

    line()

    for model in list_models():

        capabilities = ", ".join(
            model.capabilities
        )

        print(
            f"  {color(model.model_id, CYAN)}"
        )

        print(
            f"      Provider: "
            f"{model.provider}"
        )

        print(
            f"      {model.description}"
        )

        print(
            f"      Capabilities: "
            f"{capabilities}"
        )

        print()

    double_line()

    print()


# ============================================================
# MAIN
# ============================================================

async def main():

    session = TaskRunSession()

    clear_screen()

    print_header(
        session
    )

    print(
        color(
            "  Type /help to see all available commands.",
            GRAY,
        )
    )

    print()

    try:

        while True:

            try:

                request = input(
                    color(
                        "  You > ",
                        BOLD + BLUE,
                    )
                ).strip()

            except EOFError:

                break

            except KeyboardInterrupt:

                print()

                print(
                    color(
                        "  Use /exit to quit TaskRun.",
                        YELLOW,
                    )
                )

                continue

            if not request:

                continue

            lower = request.lower()

            # ==================================================
            # HELP
            # ==================================================

            if lower == "/help":

                print_help()

                continue

            # ==================================================
            # STATUS
            # ==================================================

            if lower == "/status":

                print_status(
                    session
                )

                continue

            # ==================================================
            # MODEL
            # ==================================================

            if lower == "/model":

                print(
                    format_model_status()
                )

                continue

            # ==================================================
            # MODEL CHANGE
            # ==================================================

            if lower.startswith(
                "/model_change"
            ):

                parts = request.split()

                if len(parts) == 1:

                    print(
                        format_model_status()
                    )

                    continue

                mode = parts[1].lower()

                if mode == "on":

                    set_auto_mode(
                        True
                    )

                    print()

                    print(
                        color(
                            "  ✓ Automatic model selection enabled.",
                            GREEN,
                        )
                    )

                    print()

                    continue

                if mode == "off":

                    set_auto_mode(
                        False
                    )

                    print()

                    print(
                        color(
                            "  ✓ Automatic model selection disabled.",
                            YELLOW,
                        )
                    )

                    print()

                    continue

                print()

                print(
                    color(
                        "  Usage: /model_change on|off",
                        YELLOW,
                    )
                )

                print()

                continue

            # ==================================================
            # MANUAL MODEL
            # ==================================================

            if lower.startswith(
                "/model "
            ):

                model_id = request[
                    len("/model "):
                ].strip()

                try:

                    set_manual_model(
                        model_id
                    )

                    print()

                    print(
                        color(
                            f"  ✓ Model set to {model_id}",
                            GREEN,
                        )
                    )

                    print(
                        color(
                            "  Automatic selection is now OFF.",
                            YELLOW,
                        )
                    )

                    print()

                except ValueError as exc:

                    print()

                    print(
                        color(
                            f"  {exc}",
                            RED,
                        )
                    )

                    print()

                continue

            # ==================================================
            # AVAILABLE MODELS
            # ==================================================

            if lower == "/models":

                print_models()

                continue

            # ==================================================
            # CLEAR
            # ==================================================

            if lower == "/clear":

                clear_screen()

                print_header(
                    session
                )

                continue

            # ==================================================
            # EXIT
            # ==================================================

            if lower in {
                "/exit",
                "/quit",
            }:

                print()

                print(
                    color(
                        "  Goodbye.",
                        BLUE,
                    )
                )

                break

            # ==================================================
            # DRY RUN
            # ==================================================

            if lower == "/dryrun on":

                session.set_dry_run(
                    True
                )

                print()

                print(
                    color(
                        "  ✓ Dry-run mode enabled.",
                        YELLOW,
                    )
                )

                print()

                continue

            if lower == "/dryrun off":

                session.set_dry_run(
                    False
                )

                print()

                print(
                    color(
                        "  ✓ Dry-run mode disabled.",
                        GREEN,
                    )
                )

                print()

                continue

            # ==================================================
            # QUEUE
            # ==================================================

            if lower == "/queue on":

                session.set_queue_mode(
                    True
                )

                print()

                print(
                    color(
                        "  ✓ Queue mode enabled.",
                        YELLOW,
                    )
                )

                print()

                continue

            if lower == "/queue off":

                session.set_queue_mode(
                    False
                )

                print()

                print(
                    color(
                        "  ✓ Queue mode disabled.",
                        GREEN,
                    )
                )

                print()

                continue

            if lower == "/queue":

                print_queue(
                    session
                )

                continue

            # ==================================================
            # MEMORY
            # ==================================================

            if lower == "/memory":

                print_memory(
                    session
                )

                continue

            if lower.startswith(
                "/memory set "
            ):

                parts = request.split(
                    " ",
                    4,
                )

                if len(parts) < 5:

                    print(
                        color(
                            "  Usage: /memory set <scope> <key> <value>",
                            YELLOW,
                        )
                    )

                    continue

                _, _, scope, key, value = parts

                try:

                    session.memory.set(
                        scope,
                        key,
                        value,
                    )

                    print()

                    print(
                        color(
                            "  ✓ Memory updated.",
                            GREEN,
                        )
                    )

                    print()

                except Exception as exc:

                    print(
                        color(
                            f"  Memory error: {exc}",
                            RED,
                        )
                    )

                continue

            if lower.startswith(
                "/memory clear "
            ):

                parts = request.split(
                    " ",
                    3,
                )

                if len(parts) < 4:

                    print(
                        color(
                            "  Usage: /memory clear <scope> <key>",
                            YELLOW,
                        )
                    )

                    continue

                _, _, scope, key = parts

                try:

                    session.memory.clear(
                        scope,
                        key,
                    )

                    print()

                    print(
                        color(
                            "  ✓ Memory cleared.",
                            GREEN,
                        )
                    )

                    print()

                except Exception as exc:

                    print(
                        color(
                            f"  Memory error: {exc}",
                            RED,
                        )
                    )

                continue

            # ==================================================
            # UNDO
            # ==================================================

            if lower == "/undo":

                success, message = (
                    session.undo.undo_last(
                        session.session_id
                    )
                )

                print()

                if success:

                    print(
                        color(
                            f"  ✓ {message}",
                            GREEN,
                        )
                    )

                else:

                    print(
                        color(
                            f"  {message}",
                            YELLOW,
                        )
                    )

                print()

                continue

            # ==================================================
            # BACKGROUND JOB
            # ==================================================

            if lower.startswith(
                "/bg "
            ):

                background_request = (
                    request[4:].strip()
                )

                if not background_request:

                    print(
                        color(
                            "  Usage: /bg <request>",
                            YELLOW,
                        )
                    )

                    continue

                try:

                    job = session.start_background(
                        background_request
                    )

                    print()

                    print(
                        color(
                            "  ✓ Background job started.",
                            GREEN,
                        )
                    )

                    print(
                        f"  Job ID : "
                        f"{color(job.job_id, CYAN)}"
                    )

                    print(
                        f"  Request: "
                        f"{job.request}"
                    )

                    print()

                except Exception as exc:

                    print(
                        color(
                            f"  Could not start job: {exc}",
                            RED,
                        )
                    )

                continue

            # ==================================================
            # JOB LIST
            # ==================================================

            if lower == "/jobs":

                print_jobs(
                    session
                )

                continue

            # ==================================================
            # SINGLE JOB
            # ==================================================

            if lower.startswith(
                "/job "
            ):

                job_id = request[
                    5:
                ].strip()

                if not job_id:

                    print(
                        color(
                            "  Usage: /job <id>",
                            YELLOW,
                        )
                    )

                    continue

                print_job(
                    session,
                    job_id,
                )

                continue

            # ==================================================
            # CANCEL JOB
            # ==================================================

            if lower.startswith(
                "/cancel "
            ):

                job_id = request[
                    8:
                ].strip()

                if not job_id:

                    print(
                        color(
                            "  Usage: /cancel <id>",
                            YELLOW,
                        )
                    )

                    continue

                try:

                    success, message = (
                        session.cancel_job(
                            job_id
                        )
                    )

                    print()

                    if success:

                        print(
                            color(
                                f"  ✓ {message}",
                                GREEN,
                            )
                        )

                    else:

                        print(
                            color(
                                f"  {message}",
                                YELLOW,
                            )
                        )

                    print()

                except Exception as exc:

                    print(
                        color(
                            f"  Could not cancel job: {exc}",
                            RED,
                        )
                    )

                continue

            # ==================================================
            # NORMAL AGENT REQUEST
            # ==================================================

            answer = await run_agent(
                session,
                request,
            )

            print_agent_response(
                answer
            )

    finally:

        try:

            await session.close()

        except Exception as exc:

            print(
                color(
                    f"  Shutdown warning: {exc}",
                    YELLOW,
                )
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
