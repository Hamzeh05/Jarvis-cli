import json

import shutil

from pathlib import Path

from harness.config import UNDO_FILE


class UndoManager:

    """
    Rollback journal for supported filesystem operations.
    """

    def __init__(self):

        self.entries = []

        self._load()

    def _load(self):

        if not UNDO_FILE.exists():

            return

        try:

            self.entries = json.loads(
                UNDO_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            self.entries = []

    def _save(self):

        UNDO_FILE.parent.mkdir(
            exist_ok=True
        )

        UNDO_FILE.write_text(
            json.dumps(
                self.entries,
                indent=2,
            ),
            encoding="utf-8",
        )

    def record(
        self,
        tool_name: str,
        kwargs: dict,
        session_id: str,
    ):

        supported = {

            "make_directory",

            "write_file",

            "copy_path",

            "move_path",

            "delete_path",
        }

        if tool_name not in supported:

            return None

        entry = {

            "tool":
                tool_name,

            "kwargs":
                kwargs,

            "session_id":
                session_id,

            "reversible":
                True,
        }

        # ----------------------------------------------------
        # Existing file contents
        # ----------------------------------------------------

        if tool_name == "write_file":

            path = Path(
                kwargs["path"]
            ).expanduser()

            if (
                path.exists()
                and path.is_file()
            ):

                entry[
                    "previous_content"
                ] = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )

            else:

                entry[
                    "previous_content"
                ] = None

        # ----------------------------------------------------
        # Deleted file backup
        # ----------------------------------------------------

        if tool_name == "delete_path":

            path = Path(
                kwargs["path"]
            ).expanduser()

            if (
                path.exists()
                and path.is_file()
            ):

                backup = (
                    UNDO_FILE.parent
                    /
                    f"undo_backup_{len(self.entries)}"
                )

                shutil.copy2(
                    path,
                    backup,
                )

                entry[
                    "backup"
                ] = str(backup)

        self.entries.append(
            entry
        )

        self._save()

        return entry

    def undo_last(
        self,
        session_id: str,
    ):

        for index in range(
            len(self.entries) - 1,
            -1,
            -1,
        ):

            entry = self.entries[index]

            if (
                entry.get(
                    "session_id"
                )
                != session_id
            ):

                continue

            tool = entry["tool"]

            kwargs = entry["kwargs"]

            try:

                # =========================================
                # DIRECTORY
                # =========================================

                if tool == "make_directory":

                    path = Path(
                        kwargs["path"]
                    ).expanduser()

                    if path.is_dir():

                        path.rmdir()

                # =========================================
                # FILE
                # =========================================

                elif tool == "write_file":

                    path = Path(
                        kwargs["path"]
                    ).expanduser()

                    previous = entry.get(
                        "previous_content"
                    )

                    if previous is None:

                        if path.exists():

                            path.unlink()

                    else:

                        path.write_text(
                            previous,
                            encoding="utf-8",
                        )

                # =========================================
                # COPY
                # =========================================

                elif tool == "copy_path":

                    destination = Path(
                        kwargs["destination"]
                    ).expanduser()

                    if (
                        destination.exists()
                        and destination.is_file()
                    ):

                        destination.unlink()

                # =========================================
                # MOVE
                # =========================================

                elif tool == "move_path":

                    source = Path(
                        kwargs["source"]
                    ).expanduser()

                    destination = Path(
                        kwargs["destination"]
                    ).expanduser()

                    if destination.exists():

                        shutil.move(
                            str(destination),
                            str(source),
                        )

                # =========================================
                # DELETE
                # =========================================

                elif tool == "delete_path":

                    backup = entry.get(
                        "backup"
                    )

                    path = Path(
                        kwargs["path"]
                    ).expanduser()

                    if (
                        backup
                        and
                        Path(
                            backup
                        ).exists()
                    ):

                        shutil.copy2(
                            backup,
                            path,
                        )

                    else:

                        return (
                            False,
                            "This delete cannot be automatically restored.",
                        )

                self.entries.pop(
                    index
                )

                self._save()

                return (
                    True,
                    f"Undid: {tool}",
                )

            except Exception as exc:

                return (
                    False,
                    f"Undo failed: {exc}",
                )

        return (
            False,
            "No reversible operation is available for this session.",
        )
