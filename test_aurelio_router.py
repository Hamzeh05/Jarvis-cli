import time

from benchmark_router import TEST_CASES

from semantic_router import Route, RouteLayer
from semantic_router.encoders import FastEmbedEncoder


# ============================================================
# AURELIO SEMANTIC ROUTER BENCHMARK
# ============================================================
#
# Uses the canonical 54-request benchmark from:
#
#     benchmark_router.py
#
# DO NOT add test cases here.
#
# ============================================================


# ============================================================
# ROUTE DEFINITIONS
# ============================================================

routes = [

    Route(
        name="CASUAL",
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
            "see you later",
            "bye",
        ],
    ),

    Route(
        name="GENERAL",
        utterances=[
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
            "what are neural networks",
        ],
    ),

    Route(
        name="JIRA",
        utterances=[
            "search Jira for unresolved high priority issues",
            "find open Jira tickets",
            "check a Jira issue",
            "what is the status of a Jira issue",
            "show me a Jira issue",
            "what is the priority of a Jira issue",
            "get the details for a Jira issue",
            "show me the highest priority Jira issues",
            "get Jira issue details",
            "check the status of a Jira ticket",
            "find high priority Jira issues",
            "search Jira",
        ],
    ),

    Route(
        name="SPLUNK",
        utterances=[
            "search Splunk for failed login attempts",
            "find errors in Splunk",
            "search Splunk for HTTP 500 errors",
            "show me recent Splunk events",
            "search Splunk for authentication failures",
            "what indexes are available in Splunk",
            "find network errors in Splunk",
            "search Splunk for application errors",
            "search Splunk logs",
            "find errors in Splunk logs",
            "investigate Splunk logs",
            "search logs in Splunk",
        ],
    ),

    Route(
        name="MCP",
        utterances=[
            "create a folder",
            "run docker ps",
            "read a file",
            "list files",
            "create a file",
            "check system information",
            "show running processes",
            "run the command pwd",
            "execute a command",
            "run a shell command",
            "work with files",
            "perform a computer operation",
        ],
    ),

    Route(
        name="MULTI",
        utterances=[
            "check Jira and then search Splunk",
            "find a Jira issue and check Splunk",
            "check Jira and Splunk",
            "get Jira status and search Splunk logs",
            "search Jira and check system files",
            "check Jira and run docker",
            "find Jira errors and investigate Splunk logs",
            "perform multiple tasks",
            "check multiple systems",
            "investigate Jira and Splunk together",
            "use Jira and Splunk",
        ],
    ),
]


# ============================================================
# INITIALIZATION
# ============================================================

print("=" * 70)
print("AURELIO SEMANTIC ROUTER — CANONICAL BENCHMARK")
print("=" * 70)

print()
print("Canonical benchmark:")
print(f"  Total requests: {len(TEST_CASES)}")

print()
print("Initializing encoder...")

cold_start_begin = time.perf_counter()

encoder = FastEmbedEncoder()

cold_start_end = time.perf_counter()

cold_start_seconds = cold_start_end - cold_start_begin

print(
    f"Encoder initialization: "
    f"{cold_start_seconds:.3f}s"
)

print()
print("Building RouteLayer...")

route_layer_begin = time.perf_counter()

router = RouteLayer(
    routes=routes,
    encoder=encoder,
)

route_layer_end = time.perf_counter()

route_layer_seconds = (
    route_layer_end - route_layer_begin
)

print(
    f"RouteLayer initialization: "
    f"{route_layer_seconds:.3f}s"
)


# ============================================================
# WARM-UP
# ============================================================

print()
print("Warming up router...")

warmup_requests = [
    "hello",
    "What is machine learning?",
    "Search Jira for unresolved issues",
    "Search Splunk for errors",
    "Run docker ps",
    "Check Jira and search Splunk",
]

for request in warmup_requests:
    router(request)

print("Warm-up complete.")


# ============================================================
# BENCHMARK
# ============================================================

print()
print("=" * 70)
print("RUNNING 54-REQUEST BENCHMARK")
print("=" * 70)

results = []


for index, (expected, request) in enumerate(
    TEST_CASES,
    start=1,
):

    start = time.perf_counter()

    try:

        result = router(request)

        predicted = result.name

        if predicted is None:
            predicted = "UNKNOWN"

        error = None

    except Exception as exc:

        predicted = "ERROR"
        error = str(exc)

    end = time.perf_counter()

    latency_ms = (end - start) * 1000

    correct = predicted == expected

    results.append(
        {
            "index": index,
            "expected": expected,
            "predicted": predicted,
            "request": request,
            "latency_ms": latency_ms,
            "correct": correct,
            "error": error,
        }
    )

    status = "OK" if correct else "WRONG"

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


no_work_categories = {
    "CASUAL",
    "GENERAL",
}

work_categories = {
    "JIRA",
    "SPLUNK",
    "MCP",
    "MULTI",
}


safe_bypasses = sum(
    result["expected"] in no_work_categories
    and result["predicted"] in no_work_categories
    for result in results
)


dangerous_bypasses = sum(
    result["expected"] in work_categories
    and result["predicted"] in no_work_categories
    for result in results
)


latencies = [
    result["latency_ms"]
    for result in results
    if result["predicted"] != "ERROR"
]


latencies_sorted = sorted(latencies)


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
        )
        * fraction
    )


average_latency = (
    sum(latencies) / len(latencies)
    if latencies
    else 0
)

p50_latency = percentile(
    latencies_sorted,
    0.50,
)

p95_latency = percentile(
    latencies_sorted,
    0.95,
)

fastest_latency = (
    min(latencies)
    if latencies
    else 0
)

slowest_latency = (
    max(latencies)
    if latencies
    else 0
)


# ============================================================
# RESULTS
# ============================================================

print()
print("=" * 70)
print("RESULTS")
print("=" * 70)

print()
print(f"Total requests:       {total}")
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
    f"{safe_bypasses}"
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
    f"{fastest_latency:.2f} ms"
)
print(
    f"  Slowest:            "
    f"{slowest_latency:.2f} ms"
)

print()
print("Initialization:")
print(
    f"  Encoder cold start: "
    f"{cold_start_seconds:.3f}s"
)
print(
    f"  RouteLayer setup:    "
    f"{route_layer_seconds:.3f}s"
)


# ============================================================
# CATEGORY ACCURACY
# ============================================================

print()
print("=" * 70)
print("CATEGORY ACCURACY")
print("=" * 70)

categories = [
    "CASUAL",
    "GENERAL",
    "JIRA",
    "SPLUNK",
    "MCP",
    "MULTI",
]

for category in categories:

    category_results = [
        result
        for result in results
        if result["expected"] == category
    ]

    category_correct = sum(
        result["correct"]
        for result in category_results
    )

    category_total = len(
        category_results
    )

    category_accuracy = (
        category_correct / category_total
        if category_total
        else 0
    )

    print(
        f"{category:<10} "
        f"{category_correct}/"
        f"{category_total:<3} "
        f"({category_accuracy * 100:.2f}%)"
    )


# ============================================================
# WRONG PREDICTIONS
# ============================================================

print()
print("=" * 70)
print("WRONG PREDICTIONS")
print("=" * 70)

wrong_predictions = [
    result
    for result in results
    if not result["correct"]
]


if not wrong_predictions:

    print()
    print("None")

else:

    for result in wrong_predictions:

        print()
        print(
            f"Expected:  "
            f"{result['expected']}"
        )

        print(
            f"Predicted: "
            f"{result['predicted']}"
        )

        print(
            f"Latency:   "
            f"{result['latency_ms']:.2f} ms"
        )

        print(
            f"Request:   "
            f"{result['request']}"
        )

        if result["error"]:

            print(
                f"Error:     "
                f"{result['error']}"
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
        "No dangerous NO_WORK bypasses detected."
    )

else:

    print()
    print(
        "WARNING: Dangerous NO_WORK bypasses detected!"
    )


print()
print(
    "This is ONLY a benchmark."
)

print(
    "Aurelio has NOT been connected to TaskRun."
)
