from dataclasses import (
    dataclass,
    asdict,
    field,
)

import json
import uuid

from harness.config import QUEUE_FILE


@dataclass
class QueueItem:

    id: str

    session_id: str

    tool: str

    operation: str

    status: str = "proposed"

    kwargs: dict = field(default_factory=dict)

    result: str = ""

    error: str = ""


class CommandQueue:

    def __init__(self):

        self.items = []

        self._load()

    # ========================================================
    # LOAD
    # ========================================================

    def _load(self):

        if not QUEUE_FILE.exists():

            return

        try:

            raw = json.loads(
                QUEUE_FILE.read_text(
                    encoding="utf-8"
                )
            )

            self.items = []

            for item in raw:

                # Backward compatibility with old queue files.
                item.setdefault(
                    "kwargs",
                    {},
                )

                item.setdefault(
                    "result",
                    "",
                )

                item.setdefault(
                    "error",
                    "",
                )

                self.items.append(
                    QueueItem(**item)
                )

        except Exception:

            self.items = []

    # ========================================================
    # REFRESH
    # ========================================================

    def refresh(self):

        self._load()

    # ========================================================
    # SAVE
    # ========================================================

    def _save(self):

        QUEUE_FILE.parent.mkdir(
            exist_ok=True
        )

        QUEUE_FILE.write_text(
            json.dumps(
                [
                    asdict(item)
                    for item in self.items
                ],
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    # ========================================================
    # ADD
    # ========================================================

    def add(
        self,
        session_id: str,
        tool: str,
        operation: str,
        kwargs: dict | None = None,
    ):

        item = QueueItem(

            id=uuid.uuid4().hex[:8],

            session_id=session_id,

            tool=tool,

            operation=operation,

            kwargs=dict(kwargs or {}),
        )

        self.items.append(
            item
        )

        self._save()

        return item

    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        item_id: str,
        status: str,
        result: str = "",
        error: str = "",
    ):

        self.refresh()

        for item in self.items:

            if item.id == item_id:

                item.status = status

                if result:
                    item.result = result

                if error:
                    item.error = error

                break

        self._save()

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        item_id: str,
    ):

        self.refresh()

        for item in self.items:

            if item.id == item_id:

                return item

        return None

    # ========================================================
    # RECENT
    # ========================================================

    def recent(
        self,
        limit: int = 10,
    ):

        self.refresh()

        return self.items[
            -limit:
        ]

    # ========================================================
    # SESSION ITEMS
    # ========================================================

    def session_items(
        self,
        session_id: str,
    ):

        self.refresh()

        return [
            item
            for item in self.items
            if item.session_id == session_id
        ]

    # ========================================================
    # CLEAR SESSION
    # ========================================================

    def clear_session(
        self,
        session_id: str,
    ):

        self.refresh()

        self.items = [
            item
            for item in self.items
            if item.session_id
            != session_id
        ]

        self._save()
