import os
import time

import requests

from langchain.agents import create_agent
from langchain.tools import tool

from harness.context import current_model_id
from harness.model_registry import create_llm


SPLUNK_URL = "http://10.100.100.5:65535"

SPLUNK_USER = "hamzeh"

SPLUNK_PASSWORD = os.getenv(
    "SPLUNK_PASSWORD"
)

DEBUG = False


# ============================================================
# AGENT METADATA
# ============================================================

AGENT_NAME = "splunk_agent"

AGENT_DESCRIPTION = """
Handles Splunk-related tasks.

Can search Splunk events and logs using SPL and can list
available Splunk indexes.

Use this agent when the user needs information from Splunk,
including logs, events, authentication activity, hosts,
users, errors, tickets, or other indexed data.
"""

SPLUNK_SYSTEM_PROMPT = """
You are a Splunk security/log analysis assistant.

When the user asks about logs, events, errors, users, hosts,
authentication, tickets, or other information that may exist
in Splunk, use the appropriate Splunk tool.

Use search_splunk when you need to search Splunk events.

Use list_indexes when the user asks for available Splunk indexes.

Generate valid SPL queries when using search_splunk.

When searching for tickets, use index=mail instead of index=*.

Always set the time range through the earliest and latest arguments
of search_splunk.

Never filter time inside the SPL.

For normal ticket searches, limit results with:

| head 20

If a search returns no events or an error, say exactly that and state
the query and time range you used.

Never conclude that the system is healthy or normal just because a
search returned nothing.

Do not invent Splunk results.

After receiving the results, explain them clearly to the user.
"""

# Required by TaskRun's dynamic agent registry.
AGENT_SYSTEM_PROMPT = SPLUNK_SYSTEM_PROMPT


# ============================================================
# DEBUG LOGGING
# ============================================================

def log(*args):

    if DEBUG:

        print(*args)


# ============================================================
# SPLUNK TOOLS
# ============================================================

@tool
def search_splunk(
    spl_query: str,
    earliest: str = "-7h",
    latest: str = "now",
) -> str:

    """Search Splunk with an SPL query."""

    spl_query = spl_query.strip()

    if not spl_query.startswith("search "):

        spl_query = (
            "search " + spl_query
        )

    log(
        f"\nSPL query: {spl_query}"
        f" [{earliest} -> {latest}]"
    )

    start = time.time()

    response = requests.get(
        f"{SPLUNK_URL}"
        "/services/search/jobs/export",
        params={
            "search": spl_query,
            "earliest_time": earliest,
            "latest_time": latest,
            "output_mode": "json",
        },
        auth=(
            SPLUNK_USER,
            SPLUNK_PASSWORD,
        ),
        verify=False,
        timeout=60,
    )

    log(
        "Splunk request took "
        f"{time.time() - start:.2f}s"
    )

    response.raise_for_status()

    if not response.text.strip():

        return (
            "The search ran but returned "
            f"NO events for {earliest} "
            f"to {latest}. "
            "This does not prove the "
            "system is healthy."
        )

    return response.text[:8000]


@tool
def list_indexes() -> str:

    """List the indexes available in Splunk."""

    start = time.time()

    response = requests.get(
        f"{SPLUNK_URL}"
        "/services/data/indexes",
        params={
            "output_mode": "json"
        },
        auth=(
            SPLUNK_USER,
            SPLUNK_PASSWORD,
        ),
        timeout=60,
    )

    log(
        f"Index request took "
        f"{time.time() - start:.2f}s"
    )

    response.raise_for_status()

    data = response.json()

    indexes = []

    for entry in data.get(
        "entry",
        [],
    ):

        name = entry.get("name")

        if name:

            indexes.append(name)

    return "\n".join(indexes)


# ============================================================
# DYNAMIC SPLUNK AGENT
# ============================================================

_AGENT_CACHE = {}


def get_agent(model_id: str | None = None):

    if not model_id:

        model_id = current_model_id()

    if model_id == "unknown":

        raise RuntimeError(
            "No active main model is set."
        )

    if model_id not in _AGENT_CACHE:

        llm = create_llm(model_id)

        _AGENT_CACHE[model_id] = create_agent(
            model=llm,
            tools=[
                search_splunk,
                list_indexes,
            ],
            system_prompt=SPLUNK_SYSTEM_PROMPT,
        )

    return _AGENT_CACHE[model_id]


if __name__ == "__main__":

    print(
        "Splunk Agent is intended to "
        "run through TaskRun."
    )
