import shlex

from pathlib import Path

from harness.config import PROTECTED_PATHS

from harness.safety import (
    SafetyResult,
    classify_command,
)


READ_ONLY_TOOLS = {

    "list_directory",

    "read_file",

    "search_files",

    "system_info",

    "process_list",

    "docker_ps",
}


MUTATING_TOOLS = {

    "write_file",

    "make_directory",

    "copy_path",

    "move_path",

    "delete_path",

    "execute_command",
}


def _resolve(
    path_text: str,
) -> Path:

    return (
        Path(path_text)
        .expanduser()
        .resolve(strict=False)
    )


def protected_reason(
    path_text: str,
):

    try:

        path = _resolve(
            path_text
        )

    except Exception:

        return (
            "The path could not be safely resolved."
        )

    for protected in PROTECTED_PATHS:

        protected = protected.resolve(
            strict=False
        )

        try:

            path.relative_to(
                protected
            )

            return (
                f"Protected resource: {protected}"
            )

        except ValueError:

            pass

    # --------------------------------------------------------
    # Secret files
    # --------------------------------------------------------

    if path.name in {
        ".env",
        ".env.local",
        ".env.production",
    }:

        return (
            f"Protected secret file: {path.name}"
        )

    return None


def operation_command(
    tool_name: str,
    kwargs: dict,
) -> str:

    if tool_name == "execute_command":

        return str(
            kwargs.get(
                "command",
                "",
            )
        )

    if tool_name == "list_directory":

        return (
            "ls -la "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        ".",
                    )
                )
            )
        )

    if tool_name == "read_file":

        return (
            "cat "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        "",
                    )
                )
            )
        )

    if tool_name == "search_files":

        return (
            "search_files "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        ".",
                    )
                )
            )
            + " "
            + shlex.quote(
                str(
                    kwargs.get(
                        "pattern",
                        "*",
                    )
                )
            )
        )

    if tool_name == "write_file":

        return (
            "write_file "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        "",
                    )
                )
            )
        )

    if tool_name == "make_directory":

        return (
            "mkdir -p "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        "",
                    )
                )
            )
        )

    if tool_name == "copy_path":

        return (
            "cp "
            + shlex.quote(
                str(
                    kwargs.get(
                        "source",
                        "",
                    )
                )
            )
            + " "
            + shlex.quote(
                str(
                    kwargs.get(
                        "destination",
                        "",
                    )
                )
            )
        )

    if tool_name == "move_path":

        return (
            "mv "
            + shlex.quote(
                str(
                    kwargs.get(
                        "source",
                        "",
                    )
                )
            )
            + " "
            + shlex.quote(
                str(
                    kwargs.get(
                        "destination",
                        "",
                    )
                )
            )
        )

    if tool_name == "delete_path":

        return (
            "delete_path "
            + shlex.quote(
                str(
                    kwargs.get(
                        "path",
                        "",
                    )
                )
            )
        )

    if tool_name == "system_info":

        return "system_info"

    if tool_name == "process_list":

        return "ps"

    if tool_name == "docker_ps":

        return "docker ps"

    return tool_name


def classify_operation(
    tool_name: str,
    kwargs: dict,
) -> SafetyResult:

    command = operation_command(
        tool_name,
        kwargs,
    )

    result = classify_command(
        command
    )

    if result.level == "BLOCKED":

        return result

    paths = []

    if "path" in kwargs:

        paths.append(
            kwargs["path"]
        )

    if "source" in kwargs:

        paths.append(
            kwargs["source"]
        )

    if "destination" in kwargs:

        paths.append(
            kwargs["destination"]
        )

    if tool_name in MUTATING_TOOLS:

        for path in paths:

            reason = protected_reason(
                str(path)
            )

            if reason:

                return SafetyResult(
                    level="BLOCKED",
                    reason=reason,
                )

    return result


def requires_approval(
    tool_name: str,
    safety: SafetyResult,
) -> bool:

    if safety.level == "BLOCKED":

        return False

    return tool_name in MUTATING_TOOLS
