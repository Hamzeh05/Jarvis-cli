from pathlib import Path

import fnmatch
import os
import platform
import shutil
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

from harness.policy import protected_reason


mcp = FastMCP(
    "TaskRun Computer"
)


# ============================================================
# PATH SAFETY
# ============================================================

def _safe_path(
    path: str,
) -> Path:

    resolved = (
        Path(path)
        .expanduser()
        .resolve(strict=False)
    )

    reason = protected_reason(
        str(resolved)
    )

    if reason:

        raise PermissionError(
            reason
        )

    return resolved


# ============================================================
# RAW COMMAND
# ============================================================

@mcp.tool()
def execute_command(
    command: str,
) -> str:

    """
    Execute a shell command in the TaskRun WSL environment.
    """

    if not command.strip():

        return (
            "Error: command cannot be empty."
        )

    print(
        f"[MCP] $ {command}",
        file=sys.stderr,
        flush=True,
    )

    try:

        result = subprocess.run(

            [
                "bash",
                "-lc",
                command,
            ],

            capture_output=True,

            text=True,

            timeout=60,
        )

        output = (
            f"Exit code: "
            f"{result.returncode}\n"
        )

        if result.stdout.strip():

            output += (
                "\n"
                + result.stdout.strip()
            )

        if result.stderr.strip():

            output += (
                "\n\n[stderr]\n"
                + result.stderr.strip()
            )

        if (
            not result.stdout.strip()
            and
            not result.stderr.strip()
        ):

            output += "\n(no output)"

        return output

    except subprocess.TimeoutExpired:

        return (
            "Command timed out after 60 seconds."
        )

    except Exception as exc:

        return (
            f"Error executing command: {exc}"
        )


# ============================================================
# LIST DIRECTORY
# ============================================================

@mcp.tool()
def list_directory(
    path: str = ".",
) -> str:

    """
    List a directory without modifying it.
    """

    p = (
        Path(path)
        .expanduser()
        .resolve(strict=False)
    )

    if not p.exists():

        return (
            f"Directory does not exist: {p}"
        )

    if not p.is_dir():

        return (
            f"Not a directory: {p}"
        )

    rows = []

    for item in sorted(
        p.iterdir(),
        key=lambda x:
            x.name.lower(),
    ):

        kind = (
            "DIR "
            if item.is_dir()
            else
            "FILE"
        )

        rows.append(
            f"{kind}  {item.name}"
        )

    if not rows:

        return "(empty directory)"

    return "\n".join(rows)


# ============================================================
# READ FILE
# ============================================================

@mcp.tool()
def read_file(
    path: str,
    max_bytes: int = 20000,
) -> str:

    """
    Read a text file.
    """

    p = (
        Path(path)
        .expanduser()
        .resolve(strict=False)
    )

    if not p.exists():

        return (
            f"File does not exist: {p}"
        )

    if not p.is_file():

        return (
            f"Not a file: {p}"
        )

    data = p.read_bytes()[
        :max_bytes
    ]

    return data.decode(
        "utf-8",
        errors="replace",
    )


# ============================================================
# SEARCH FILES
# ============================================================

@mcp.tool()
def search_files(
    path: str = ".",
    pattern: str = "*",
) -> str:

    """
    Recursively search for files.
    """

    root = (
        Path(path)
        .expanduser()
        .resolve(strict=False)
    )

    if not root.exists():

        return (
            f"Path does not exist: {root}"
        )

    matches = []

    for current, dirs, files in os.walk(
        root
    ):

        dirs[:] = [
            d
            for d in dirs
            if d not in {
                ".git",
                ".venv",
                "__pycache__",
            }
        ]

        for name in files:

            if fnmatch.fnmatch(
                name,
                pattern,
            ):

                matches.append(
                    str(
                        Path(current)
                        / name
                    )
                )

                if len(matches) >= 100:

                    return (
                        "\n".join(matches)
                        +
                        "\n[limit: 100 matches]"
                    )

    if not matches:

        return "(no matches)"

    return "\n".join(matches)


# ============================================================
# WRITE FILE
# ============================================================

@mcp.tool()
def write_file(
    path: str,
    content: str,
) -> str:

    """
    Write text to a file.
    """

    p = _safe_path(
        path
    )

    p.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    p.write_text(
        content,
        encoding="utf-8",
    )

    return (
        f"Wrote "
        f"{len(content.encode('utf-8'))} "
        f"bytes to {p}"
    )


# ============================================================
# MAKE DIRECTORY
# ============================================================

@mcp.tool()
def make_directory(
    path: str,
) -> str:

    """
    Create a directory.
    """

    p = _safe_path(
        path
    )

    p.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        f"Created directory: {p}"
    )


# ============================================================
# COPY
# ============================================================

@mcp.tool()
def copy_path(
    source: str,
    destination: str,
) -> str:

    """
    Copy a file or directory.
    """

    src = _safe_path(
        source
    )

    dst = _safe_path(
        destination
    )

    if src.is_dir():

        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
        )

    else:

        dst.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            src,
            dst,
        )

    return (
        f"Copied {src} -> {dst}"
    )


# ============================================================
# MOVE
# ============================================================

@mcp.tool()
def move_path(
    source: str,
    destination: str,
) -> str:

    """
    Move a file or directory.
    """

    src = _safe_path(
        source
    )

    dst = _safe_path(
        destination
    )

    dst.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.move(
        str(src),
        str(dst),
    )

    return (
        f"Moved {src} -> {dst}"
    )


# ============================================================
# DELETE
# ============================================================

@mcp.tool()
def delete_path(
    path: str,
) -> str:

    """
    Delete a single file or empty directory.
    """

    p = _safe_path(
        path
    )

    if p.is_file():

        p.unlink()

        return (
            f"Deleted file: {p}"
        )

    if p.is_dir():

        p.rmdir()

        return (
            f"Deleted directory: {p}"
        )

    return (
        f"Path does not exist: {p}"
    )


# ============================================================
# SYSTEM INFO
# ============================================================

@mcp.tool()
def system_info() -> str:

    """
    Return basic system information.
    """

    usage = shutil.disk_usage(
        Path.home()
    )

    return "\n".join(
        [
            f"OS: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}",
            f"Python: {platform.python_version()}",
            f"CPU count: {os.cpu_count()}",
            f"Disk free: {usage.free} bytes",
        ]
    )


# ============================================================
# PROCESSES
# ============================================================

@mcp.tool()
def process_list() -> str:

    """
    List running processes.
    """

    result = subprocess.run(

        [
            "ps",
            "-eo",
            "pid,comm,%cpu,%mem",
            "--sort=-%cpu",
        ],

        capture_output=True,

        text=True,

        timeout=10,
    )

    return result.stdout[:20000]


# ============================================================
# DOCKER
# ============================================================

@mcp.tool()
def docker_ps() -> str:

    """
    List running Docker containers.
    """

    result = subprocess.run(

        [
            "docker",
            "ps",
        ],

        capture_output=True,

        text=True,

        timeout=20,
    )

    output = result.stdout.strip()

    if result.stderr.strip():

        output += (
            "\n\n[stderr]\n"
            +
            result.stderr.strip()
        )

    return (
        output
        or
        "(no running containers)"
    )


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )
