from semantic_router import Route, RouteLayer
from semantic_router.encoders import FastEmbedEncoder


encoder = FastEmbedEncoder()


NO_WORK = Route(
    name="NO_WORK",
    utterances=[
        "hi",
        "hello",
        "hey",
        "hiya",
        "how are you?",
        "how are you doing?",
        "what's up?",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "nice to meet you",
        "goodbye",
        "What is machine learning?",
        "Explain neural networks",
        "What is feature engineering?",
        "What is an API?",
        "Explain Docker",
        "What is a REST API?",
        "What is artificial intelligence?",
        "Explain what an LLM is",
        "What is cloud computing?",
    ],
)


WORK = Route(
    name="WORK",
    utterances=[
        "Search Jira for unresolved high priority issues",
        "Find open Jira tickets",
        "Check WUK-2312",
        "What is the status of WUK-2312?",
        "Show me WUK-2312",
        "What is the priority of WUK-2312?",
        "Get the details for WUK-2312",
        "Show me the highest priority Jira issues",

        "Search Splunk for failed login attempts",
        "Find errors in Splunk",
        "Search Splunk for HTTP 500 errors",
        "Show me recent Splunk events",
        "Search Splunk for authentication failures",
        "What indexes are available in Splunk?",
        "Find network errors in Splunk",
        "Search Splunk for application errors",

        "Create a folder called test",
        "Run docker ps",
        "Read the file runner.py",
        "List the files in this directory",
        "Create a file called test.txt",
        "Check system information",
        "Show the running processes",
        "Run the command pwd",

        "Check WUK-2312 and then search Splunk for related errors",
        "Find the Jira issue WUK-2312 and check Splunk for errors",
        "Check Jira for open issues and then search Splunk",
        "Get the status of WUK-2312 and search Splunk for related logs",
        "Search Jira for high priority issues and check the system files",
        "Check a Jira ticket and then run docker ps",
        "Find Jira errors and investigate the related Splunk logs",
    ],
)


router = RouteLayer(
    encoder=encoder,
    routes=[NO_WORK, WORK],
)


def classify_request(request: str) -> str:
    """
    Classify a TaskRun request as NO_WORK or WORK.
    """

    if not isinstance(request, str):
        raise TypeError("request must be a string")

    request = request.strip()

    if not request:
        raise ValueError("request cannot be empty")

    result = router(request)

    # Fail closed.
    # If classification is uncertain, use the normal
    # TaskRun work pipeline.
    if result is None or result.name is None:
        return "WORK"

    if result.name == "NO_WORK":
        return "NO_WORK"

    return "WORK"


def needs_work(request: str) -> bool:
    """
    Returns True if the request should go through
    TaskRun's normal work pipeline.
    """

    return classify_request(request) == "WORK"


if __name__ == "__main__":
    test_requests = [
        "hi",
        "how are you?",
        "What is machine learning?",
        "Check WUK-2312",
        "Search Splunk for errors",
        "Run docker ps",
        "Check WUK-2312 and then search Splunk for related errors",
    ]

    for request in test_requests:
        print(f"{request!r} -> {classify_request(request)}")
