import json

from typing import Any

from harness.config import MEMORY_FILE


class MemoryStore:

    """
    TaskRun memory has three scopes.

    session
        Current conversation only.

    project
        Persistent TaskRun project memory.

    global
        Persistent memory across TaskRun sessions.
    """

    def __init__(self):

        self.data = {

            "global": {},

            "project": {},

            "sessions": {},
        }

        self._load()

    def _load(self):

        if not MEMORY_FILE.exists():

            return

        try:

            self.data.update(
                json.loads(
                    MEMORY_FILE.read_text(
                        encoding="utf-8"
                    )
                )
            )

        except Exception:

            pass

    def _save(self):

        MEMORY_FILE.parent.mkdir(
            exist_ok=True
        )

        MEMORY_FILE.write_text(
            json.dumps(
                self.data,
                indent=2,
            ),
            encoding="utf-8",
        )

    def set(
        self,
        scope: str,
        key: str,
        value: Any,
        session_id: str,
    ):

        scope = scope.lower()

        if scope == "session":

            bucket = (
                self.data["sessions"]
                .setdefault(
                    session_id,
                    {},
                )
            )

        elif scope in {
            "project",
            "global",
        }:

            bucket = self.data[
                scope
            ]

        else:

            raise ValueError(
                "Scope must be session, project, or global."
            )

        bucket[key] = value

        self._save()

    def clear(
        self,
        scope: str,
        session_id: str,
    ):

        scope = scope.lower()

        if scope == "session":

            self.data[
                "sessions"
            ].pop(
                session_id,
                None,
            )

        elif scope in {
            "project",
            "global",
        }:

            self.data[
                scope
            ] = {}

        else:

            raise ValueError(
                "Scope must be session, project, or global."
            )

        self._save()

    def get_context(
        self,
        session_id: str,
    ) -> str:

        pieces = []

        global_memory = (
            self.data.get(
                "global",
                {},
            )
        )

        project_memory = (
            self.data.get(
                "project",
                {},
            )
        )

        session_memory = (
            self.data
            .get(
                "sessions",
                {},
            )
            .get(
                session_id,
                {},
            )
        )

        if global_memory:

            pieces.append(
                "GLOBAL MEMORY:\n"
                +
                json.dumps(
                    global_memory,
                    indent=2,
                )
            )

        if project_memory:

            pieces.append(
                "PROJECT MEMORY:\n"
                +
                json.dumps(
                    project_memory,
                    indent=2,
                )
            )

        if session_memory:

            pieces.append(
                "SESSION MEMORY:\n"
                +
                json.dumps(
                    session_memory,
                    indent=2,
                )
            )

        return "\n\n".join(
            pieces
        )

    def summary(
        self,
        session_id: str,
    ):

        return {

            "global":
                self.data.get(
                    "global",
                    {},
                ),

            "project":
                self.data.get(
                    "project",
                    {},
                ),

            "session":
                self.data
                .get(
                    "sessions",
                    {},
                )
                .get(
                    session_id,
                    {},
                ),
        }
