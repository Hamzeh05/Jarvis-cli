import json

import uuid

from datetime import (
    datetime,
    timezone,
)

from harness.config import LOG_DIR


LOG_FILE = LOG_DIR / "runs.jsonl"


def log_event(
    event_type: str,
    run_id: str,
    **data,
):

    event = {

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "event":
            event_type,

        "run_id":
            run_id,

        "trace_id":
            data.pop(
                "trace_id",
                uuid.uuid4().hex[:12],
            ),

        **data,
    }

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            json.dumps(
                event,
                default=str,
            )
            + "\n"
        )
