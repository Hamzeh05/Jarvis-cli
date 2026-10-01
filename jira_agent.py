import requests

from langchain.agents import create_agent

from harness.model_registry import create_llm
from harness.context import current_model_id


JIRA_BASE_URL = "http://10.100.100.5:65534"


# ============================================================
# AGENT METADATA
# ============================================================

AGENT_NAME = "jira_agent"

AGENT_DESCRIPTION = """
Handles Jira-related tasks.

Can retrieve individual Jira issues by issue key and search Jira
using JQL.

Can return issue summaries, status, priority, assignee, and
search results.

Use this agent whenever the user needs information from Jira.
"""

AGENT_SYSTEM_PROMPT = """
You are TaskRun's Jira Agent.

Your purpose is to handle Jira-related requests.

Use the provided Jira tools to retrieve real Jira information.

Do not invent Jira data.

Do not claim information that was not returned by a Jira tool.

Be concise and factual.

When searching Jira, use the appropriate Jira tool rather than
guessing information.
"""


# ============================================================
# JIRA TOOLS
# ============================================================

def get_jira_issue(key: str) -> dict:

    """Retrieves a single Jira issue by its key, e.g. WUK-4351."""

    url = (
        f"{JIRA_BASE_URL}"
        f"/rest/api/2/issue/{key}"
    )

    response = requests.get(
        url,
        headers={
            "Accept": "application/json"
        },
        timeout=10,
        verify=False,
    )

    response.raise_for_status()

    data = response.json()

    fields = data.get("fields") or {}

    return {
        "key": data.get(
            "key",
            key,
        ),
        "summary": fields.get(
            "summary",
            "No summary",
        ),
        "status": (
            fields.get("status") or {}
        ).get(
            "name",
            "Unknown",
        ),
        "priority": (
            fields.get("priority") or {}
        ).get(
            "name",
            "Unknown",
        ),
        "assignee": (
            fields.get("assignee") or {}
        ).get(
            "displayName",
            "Unassigned",
        ),
    }


def search_jira_jql(
    jql: str,
    max_results: int = 10,
) -> dict:

    """Searches for Jira issues using JQL."""

    url = (
        f"{JIRA_BASE_URL}"
        "/rest/api/2/search"
    )

    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": (
            "summary,status,"
            "assignee,priority,created"
        ),
    }

    response = requests.get(
        url,
        headers={
            "Accept": "application/json"
        },
        params=params,
        timeout=10,
        verify=False,
    )

    response.raise_for_status()

    data = response.json()

    issues = []

    for issue in data.get("issues") or []:

        fields = issue.get("fields") or {}

        issues.append(
            {
                "key": issue.get(
                    "key",
                    "Unknown",
                ),
                "summary": fields.get(
                    "summary",
                    "No summary",
                ),
                "status": (
                    fields.get("status") or {}
                ).get(
                    "name",
                    "Unknown",
                ),
                "priority": (
                    fields.get("priority") or {}
                ).get(
                    "name",
                    "Unknown",
                ),
                "assignee": (
                    fields.get("assignee") or {}
                ).get(
                    "displayName",
                    "Unassigned",
                ),
            }
        )

    return {
        "total": data.get(
            "total",
            0,
        ),
        "returned": len(issues),
        "issues": issues,
    }


# ============================================================
# DYNAMIC JIRA AGENT
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
                get_jira_issue,
                search_jira_jql,
            ],
            system_prompt=AGENT_SYSTEM_PROMPT,
        )

    return _AGENT_CACHE[model_id]


# ============================================================
# BACKWARDS COMPATIBILITY
# ============================================================

def get_current_agent():

    return get_agent()


if __name__ == "__main__":

    print(
        "Jira Chatbot ready. "
        "Use TaskRun to select the model."
    )
