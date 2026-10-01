from contextvars import ContextVar


_dry_run = ContextVar(
    "taskrun_dry_run",
    default=False,
)

_session_id = ContextVar(
    "taskrun_session_id",
    default="unknown",
)

_queue_mode = ContextVar(
    "taskrun_queue_mode",
    default=False,
)

_active_model = ContextVar(
    "taskrun_active_model",
    default="unknown",
)


def set_runtime_context(
    session_id: str,
    dry_run: bool,
    queue_mode: bool,
    model_id: str = "unknown",
):

    tokens = (
        _session_id.set(session_id),
        _dry_run.set(dry_run),
        _queue_mode.set(queue_mode),
        _active_model.set(model_id),
    )

    return tokens


def reset_runtime_context(tokens):

    _session_id.reset(tokens[0])
    _dry_run.reset(tokens[1])
    _queue_mode.reset(tokens[2])
    _active_model.reset(tokens[3])


def is_dry_run() -> bool:

    return _dry_run.get()


def is_queue_mode() -> bool:

    return _queue_mode.get()


def current_session_id() -> str:

    return _session_id.get()


def current_model_id() -> str:

    return _active_model.get()


# ============================================================
# APPROVAL STATE
# ============================================================

_approval_waiting = False


def set_approval_waiting(value: bool):

    global _approval_waiting

    _approval_waiting = value


def is_approval_waiting() -> bool:

    return _approval_waiting
