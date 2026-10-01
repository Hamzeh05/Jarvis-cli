import hashlib

from pathlib import Path


def _hash_file(
    path: Path,
) -> str:

    h = hashlib.sha256()

    with path.open("rb") as f:

        for chunk in iter(
            lambda:
                f.read(
                    1024 * 1024
                ),
            b"",
        ):

            h.update(chunk)

    return h.hexdigest()


def verify_operation(
    tool_name: str,
    kwargs: dict,
    result: str,
):

    """
    Deterministic post-operation verification.

    This function never executes a shell command.
    """

    try:

        # ====================================================
        # DIRECTORY
        # ====================================================

        if tool_name == "make_directory":

            path = Path(
                kwargs["path"]
            ).expanduser()

            ok = path.is_dir()

            return (
                ok,
                (
                    "Directory exists."
                    if ok
                    else
                    "Directory was not created."
                ),
            )

        # ====================================================
        # WRITE FILE
        # ====================================================

        if tool_name == "write_file":

            path = Path(
                kwargs["path"]
            ).expanduser()

            content = str(
                kwargs.get(
                    "content",
                    "",
                )
            )

            ok = (
                path.is_file()
                and
                path.read_text(
                    encoding="utf-8"
                )
                == content
            )

            return (
                ok,
                (
                    "File content verified."
                    if ok
                    else
                    "File content could not be verified."
                ),
            )

        # ====================================================
        # DELETE
        # ====================================================

        if tool_name == "delete_path":

            path = Path(
                kwargs["path"]
            ).expanduser()

            ok = not path.exists()

            return (
                ok,
                (
                    "Path no longer exists."
                    if ok
                    else
                    "Path still exists."
                ),
            )

        # ====================================================
        # COPY
        # ====================================================

        if tool_name == "copy_path":

            source = Path(
                kwargs["source"]
            ).expanduser()

            destination = Path(
                kwargs["destination"]
            ).expanduser()

            ok = destination.exists()

            if (
                ok
                and source.is_file()
                and destination.is_file()
            ):

                ok = (
                    _hash_file(source)
                    ==
                    _hash_file(destination)
                )

            return (
                ok,
                (
                    "Copy verified."
                    if ok
                    else
                    "Copy could not be verified."
                ),
            )

        # ====================================================
        # MOVE
        # ====================================================

        if tool_name == "move_path":

            source = Path(
                kwargs["source"]
            ).expanduser()

            destination = Path(
                kwargs["destination"]
            ).expanduser()

            ok = (
                not source.exists()
                and destination.exists()
            )

            return (
                ok,
                (
                    "Move verified."
                    if ok
                    else
                    "Move could not be verified."
                ),
            )

        # ====================================================
        # RAW COMMAND
        # ====================================================

        if tool_name == "execute_command":

            ok = (
                "Exit code: 0"
                in str(result)
            )

            return (
                ok,
                (
                    "Command returned exit code 0."
                    if ok
                    else
                    "Command returned a non-zero exit code."
                ),
            )

        return (
            True,
            "No specialized verification rule was required.",
        )

    except Exception as exc:

        return (
            False,
            f"Verification error: {exc}",
        )
