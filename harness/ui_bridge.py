import asyncio


_approval_handler = None


def set_approval_handler(handler):
    global _approval_handler
    _approval_handler = handler


def clear_approval_handler():
    global _approval_handler
    _approval_handler = None


async def request_approval(details: dict) -> bool:
    """
    Ask the active UI for approval.

    If TaskRun is running in the normal CLI, fall back to
    the traditional terminal prompt.
    """

    if _approval_handler is not None:
        return await _approval_handler(details)

    command = details.get("command", "Unknown operation")
    reason = details.get("reason", "")

    print()
    print("APPROVAL REQUIRED")
    print("-" * 50)
    print(command)

    if reason:
        print()
        print(reason)

    approval = await asyncio.to_thread(
        input,
        "Allow this operation? [y/N]: ",
    )

    return approval.strip().lower() in {
        "y",
        "yes",
    }
