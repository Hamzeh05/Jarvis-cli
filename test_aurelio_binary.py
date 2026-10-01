import time

from benchmark_router import TEST_CASES

from semantic_router import Route, RouteLayer
from semantic_router.encoders import FastEmbedEncoder


# ============================================================
# AURELIO BINARY GATE BENCHMARK
# ============================================================
#
# Question:
#
#   Does this request require TaskRun to perform work?
#
# Routes:
#
#   NO_WORK
#       Casual conversation or general knowledge.
#
#   WORK
#       Jira, Splunk, MCP, or multi-system work.
#
# This is the routing decision TaskRun actually cares about.
# ============================================================


# ============================================================
# ROUTES
# ============================================================

routes = [

    Route(
        name="NO_WORK",
        utterances=[
            "hi",
            "hello",
            "hey",
            "hiya",
            "how are you",
            "how are you doing",
            "what's up",
            "good morning",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "nice to meet you",
            "goodbye",
            "see you",
            "bye",

            "what is machine learning",
            "explain machine learning",
            "explain neural networks",
            "what is feature engineering",
            "what is an API",
            "explain Docker",
            "what is a REST API",
            "what is artificial intelligence",
            "explain what an LLM is",
            "what is cloud computing",
            "explain cloud computing",
        ],
    ),

    Route(
        name="WORK",
        utterances=[
            "search Jira",
            "find Jira issues",
            "check Jira",
            "get Jira issue details",
            "check a Jira ticket",
            "show Jira issues",

            "search Splunk",
            "find errors in Splunk",
            "search Splunk logs",
            "show Splunk events",
            "investigate Splunk",

            "create a folder",
            "run docker ps",
            "read a file",
            "list files",
            "create a file",
            "check system information",
            "show running processes",
            "run a command",
            "execute a command",

            "check Jira and search Splunk",
            "check multiple systems",
            "find a Jira issue and check Splunk",
            "check Jira and run docker",
            "investigate Jira and Splunk",
        ],
    ),
]


# ============================================================
# INITIALIZATION
# ============================================================

print("=" * 70)
print("AURELIO BINARY GATE BENCHMARK")
print("=" * 70)

print()
print("Initializing encoder...")

cold_start_begin = time.perf_counter()

encoder = FastEmbedEncoder()

cold_start_seconds = (
    time.perf_counter()
    - cold_start_begin
)

print(
    f"Encoder cold start: "
    f"{cold_start_seconds:.3f}s"
)

print()
print("Building RouteLayer...")

router_start = time.perf_counter()

router = RouteLayer(
    routes=routes,
    encoder=encoder,
)

router_setup_seconds = (
    time.perf_counter()
    - router_start
)

print(
    f"RouteLayer setup: "
    f"{router_setup_seconds:.3f}s"
)


# ============================================================
# WARM-UP
# ============================================================

print()
print("Warming up...")

for request in [
    "hello",
    "What is machine learning?",
    "Search Jira for issues",
    "Search Splunk for errors",
    "Run docker ps",
]:

    router(request)

print("Warm-up complete.")


# ============================================================
# RUN BENCHMARK
# ============================================================

print()
print("=" * 70)
print("RUNNING 54-REQUEST BINARY BENCHMARK")
print("=" * 70)

results = []


for index, (category, request) in enumerate(
    TEST_CASES,
    start=1,
):

    expected = (
        "NO_WORK"
        if category in {"CASUAL", "GENERAL"}
        else "WORK"
    )

    start = time.perf_counter()

    try:

        response = router(request)

        predicted = response.name

        if predicted is None:
            predicted = "UNKNOWN"

        error = None

    except Exception as exc:

        predicted = "ERROR"
        error = str(exc)

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    correct = (
        predicted == expected
    )

    dangerous = (
        expected == "WORK"
        and predicted == "NO_WORK"
    )

    safe_bypass = (
        expected == "NO_WORK"
        and predicted == "NO_WORK"
    )

    results.append(
        {
            "index": index,
            "category": category,
            "request": request,
            "expected": expected,
            "predicted": predicted,
            "correct": correct,
            "dangerous": dangerous,
            "safe_bypass": safe_bypass,
            "latency_ms": latency_ms,
            "error": error,
        }
    )

    status = (
        "OK"
        if correct
        else "WRONG"
    )

    print(
        f"[{index:02d}/54] "
        f"{status:5} "
        f"{latency_ms:7.2f} ms | "
        f"{expected:7} -> {predicted:7} | "
        f"{request}"
    )


# ============================================================
# METRICS
# ============================================================

total = len(results)

correct = sum(
    result["correct"]
    for result in results
)

accuracy = (
    correct / total
    if total
    else 0
)

safe_bypasses = sum(
    result["safe_bypass"]
    for result in results
)

dangerous_bypasses = sum(
    result["dangerous"]
    for result in results
)

latencies = sorted(
    result["latency_ms"]
    for result in results
    if result["predicted"] != "ERROR"
)


def percentile(values, percentile_value):

    if not values:
        return 0

    if len(values) == 1:
        return values[0]

    position = (
        len(values) - 1
    ) * percentile_value

    lower = int(position)

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = position - lower

    return (
        values[lower]
        + (
            values[upper]
            - values[lower]
        ) * fraction
    )


average_latency = (
    sum(latencies) / len(latencies)
    if latencies
    else 0
)

p50_latency = percentile(
    latencies,
    0.50,
)

p95_latency = percentile(
    latencies,
    0.95,
)


# ============================================================
# RESULTS
# ============================================================

print()
print("=" * 70)
print("RESULTS")
print("=" * 70)

print()
print(
    f"Total requests:       {total}"
)

print(
    f"Correct:              "
    f"{correct}/{total}"
)

print(
    f"Accuracy:             "
    f"{accuracy * 100:.2f}%"
)

print()
print(
    f"Safe bypasses:        "
    f"{safe_bypasses}/23"
)

print(
    f"Dangerous bypasses:   "
    f"{dangerous_bypasses}"
)

print()
print("Latency:")

print(
    f"  Average:            "
    f"{average_latency:.2f} ms"
)

print(
    f"  P50:                "
    f"{p50_latency:.2f} ms"
)

print(
    f"  P95:                "
    f"{p95_latency:.2f} ms"
)

print(
    f"  Fastest:            "
    f"{min(latencies):.2f} ms"
)

print(
    f"  Slowest:            "
    f"{max(latencies):.2f} ms"
)

print()
print("Initialization:")

print(
    f"  Cold start:         "
    f"{cold_start_seconds:.3f}s"
)

print(
    f"  RouteLayer setup:   "
    f"{router_setup_seconds:.3f}s"
)


# ============================================================
# CONFUSION
# ============================================================

print()
print("=" * 70)
print("BINARY CONFUSION")
print("=" * 70)

true_no_work = sum(
    result["expected"] == "NO_WORK"
    for result in results
)

true_work = sum(
    result["expected"] == "WORK"
    for result in results
)

correct_no_work = sum(
    result["expected"] == "NO_WORK"
    and result["predicted"] == "NO_WORK"
    for result in results
)

correct_work = sum(
    result["expected"] == "WORK"
    and result["predicted"] == "WORK"
    for result in results
)

print()
print(
    f"NO_WORK correct:      "
    f"{correct_no_work}/{true_no_work}"
)

print(
    f"WORK correct:         "
    f"{correct_work}/{true_work}"
)


# ============================================================
# WRONG PREDICTIONS
# ============================================================

print()
print("=" * 70)
print("WRONG PREDICTIONS")
print("=" * 70)

wrong = [
    result
    for result in results
    if not result["correct"]
]

if not wrong:

    print()
    print("None")

else:

    for result in wrong:

        print()
        print(
            f"Original category: "
            f"{result['category']}"
        )

        print(
            f"Expected:           "
            f"{result['expected']}"
        )

        print(
            f"Predicted:          "
            f"{result['predicted']}"
        )

        print(
            f"Request:            "
            f"{result['request']}"
        )


# ============================================================
# SAFETY
# ============================================================

print()
print("=" * 70)
print("TASKRUN SAFETY")
print("=" * 70)

if dangerous_bypasses == 0:

    print()
    print(
        "SAFE: Zero dangerous NO_WORK bypasses."
    )

else:

    print()
    print(
        "WARNING: Dangerous bypasses detected."
    )

print()
print(
    "Aurelio is NOT connected to TaskRun."
)
