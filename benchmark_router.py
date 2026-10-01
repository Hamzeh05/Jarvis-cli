import time


# ============================================================
# CANONICAL TASKRUN ROUTER BENCHMARK
# ============================================================
#
# 54 requests total:
#   CASUAL   = 14
#   GENERAL  = 9
#   JIRA     = 8
#   SPLUNK   = 8
#   MCP      = 8
#   MULTI    = 7
#
# NO_WORK:
#   CASUAL + GENERAL = 23
#
# WORK:
#   JIRA + SPLUNK + MCP + MULTI = 31
#
# IMPORTANT:
# Every router must be tested against these exact requests.
# ============================================================


TEST_CASES = [

    # ========================================================
    # CASUAL — 14
    # ========================================================

    ("CASUAL", "hi"),
    ("CASUAL", "hello"),
    ("CASUAL", "hey"),
    ("CASUAL", "hiya"),
    ("CASUAL", "how are you?"),
    ("CASUAL", "how are you doing?"),
    ("CASUAL", "what's up?"),
    ("CASUAL", "good morning"),
    ("CASUAL", "good afternoon"),
    ("CASUAL", "good evening"),
    ("CASUAL", "thanks"),
    ("CASUAL", "thank you"),
    ("CASUAL", "nice to meet you"),
    ("CASUAL", "goodbye"),

    # ========================================================
    # GENERAL — 9
    # ========================================================

    ("GENERAL", "What is machine learning?"),
    ("GENERAL", "Explain neural networks"),
    ("GENERAL", "What is feature engineering?"),
    ("GENERAL", "What is an API?"),
    ("GENERAL", "Explain Docker"),
    ("GENERAL", "What is a REST API?"),
    ("GENERAL", "What is artificial intelligence?"),
    ("GENERAL", "Explain what an LLM is"),
    ("GENERAL", "What is cloud computing?"),

    # ========================================================
    # JIRA — 8
    # ========================================================

    ("JIRA", "Search Jira for unresolved high priority issues"),
    ("JIRA", "Find open Jira tickets"),
    ("JIRA", "Check WUK-2312"),
    ("JIRA", "What is the status of WUK-2312?"),
    ("JIRA", "Show me WUK-2312"),
    ("JIRA", "What is the priority of WUK-2312?"),
    ("JIRA", "Get the details for WUK-2312"),
    ("JIRA", "Show me the highest priority Jira issues"),

    # ========================================================
    # SPLUNK — 8
    # ========================================================

    ("SPLUNK", "Search Splunk for failed login attempts"),
    ("SPLUNK", "Find errors in Splunk"),
    ("SPLUNK", "Search Splunk for HTTP 500 errors"),
    ("SPLUNK", "Show me recent Splunk events"),
    ("SPLUNK", "Search Splunk for authentication failures"),
    ("SPLUNK", "What indexes are available in Splunk?"),
    ("SPLUNK", "Find network errors in Splunk"),
    ("SPLUNK", "Search Splunk for application errors"),

    # ========================================================
    # MCP — 8
    # ========================================================

    ("MCP", "Create a folder called test"),
    ("MCP", "Run docker ps"),
    ("MCP", "Read the file runner.py"),
    ("MCP", "List the files in this directory"),
    ("MCP", "Create a file called test.txt"),
    ("MCP", "Check system information"),
    ("MCP", "Show the running processes"),
    ("MCP", "Run the command pwd"),

    # ========================================================
    # MULTI — 7
    # ========================================================

    (
        "MULTI",
        "Check WUK-2312 and then search Splunk for related errors",
    ),
    (
        "MULTI",
        "Find the Jira issue WUK-2312 and check Splunk for errors",
    ),
    (
        "MULTI",
        "Check Jira for open issues and then search Splunk",
    ),
    (
        "MULTI",
        "Get the status of WUK-2312 and search Splunk for related logs",
    ),
    (
        "MULTI",
        "Search Jira for high priority issues and check the system files",
    ),
    (
        "MULTI",
        "Check a Jira ticket and then run docker ps",
    ),
    (
        "MULTI",
        "Find Jira errors and investigate the related Splunk logs",
    ),
]


# ============================================================
# VALIDATION
# ============================================================

EXPECTED_COUNTS = {
    "CASUAL": 14,
    "GENERAL": 9,
    "JIRA": 8,
    "SPLUNK": 8,
    "MCP": 8,
    "MULTI": 7,
}


def validate_benchmark():
    total = len(TEST_CASES)

    if total != 54:
        raise ValueError(
            f"Benchmark must contain exactly 54 requests, "
            f"but contains {total}"
        )

    actual_counts = {}

    for category, request in TEST_CASES:
        actual_counts[category] = actual_counts.get(category, 0) + 1

    for category, expected in EXPECTED_COUNTS.items():
        actual = actual_counts.get(category, 0)

        if actual != expected:
            raise ValueError(
                f"{category}: expected {expected}, got {actual}"
            )

    print("Benchmark validation passed.")
    print(f"Total requests: {total}")
    print()

    for category in EXPECTED_COUNTS:
        print(f"{category:<10} {actual_counts[category]}")


# ============================================================
# ROUTER BENCHMARK HELPER
# ============================================================

def benchmark_router(router_function):
    """
    router_function(request) must return the predicted category.

    Example:

        prediction = router_function("hello")

    Valid predictions:

        CASUAL
        GENERAL
        JIRA
        SPLUNK
        MCP
        MULTI
    """

    validate_benchmark()

    results = []

    print()
    print("=" * 70)
    print("RUNNING ROUTER BENCHMARK")
    print("=" * 70)

    for index, (expected, request) in enumerate(TEST_CASES, start=1):

        start = time.perf_counter()

        try:
            predicted = router_function(request)
            error = None

        except Exception as exc:
            predicted = "ERROR"
            error = str(exc)

        latency_ms = (time.perf_counter() - start) * 1000

        correct = predicted == expected

        results.append({
            "index": index,
            "request": request,
            "expected": expected,
            "predicted": predicted,
            "correct": correct,
            "latency_ms": latency_ms,
            "error": error,
        })

        print(
            f"[{index:02d}/54] "
            f"{'OK' if correct else 'WRONG':5} "
            f"{latency_ms:7.2f} ms | "
            f"{expected:7} -> {predicted:7} | "
            f"{request}"
        )

    return results


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(results):

    total = len(results)

    correct = sum(
        result["correct"]
        for result in results
    )

    accuracy = correct / total if total else 0

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

    def percentile(values, percentile):

        if not values:
            return 0

        if len(values) == 1:
            return values[0]

        index = (len(values) - 1) * percentile

        lower = int(index)
        upper = min(lower + 1, len(values) - 1)

        fraction = index - lower

        return (
            values[lower]
            + (values[upper] - values[lower]) * fraction
        )

    metrics = {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "safe_bypasses": safe_bypasses,
        "dangerous_bypasses": dangerous_bypasses,
        "average_latency_ms": (
            sum(latencies) / len(latencies)
            if latencies
            else 0
        ),
        "p50_latency_ms": percentile(
            latencies_sorted,
            0.50,
        ),
        "p95_latency_ms": percentile(
            latencies_sorted,
            0.95,
        ),
        "fastest_latency_ms": (
            min(latencies)
            if latencies
            else 0
        ),
        "slowest_latency_ms": (
            max(latencies)
            if latencies
            else 0
        ),
    }

    return metrics


# ============================================================
# PRINT RESULTS
# ============================================================

def print_results(results):

    metrics = calculate_metrics(results)

    print()
    print("=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)

    print()
    print(f"Total requests:       {metrics['total']}")
    print(
        f"Correct:              "
        f"{metrics['correct']}/{metrics['total']}"
    )
    print(
        f"Accuracy:             "
        f"{metrics['accuracy'] * 100:.2f}%"
    )

    print()
    print(
        f"Safe bypasses:        "
        f"{metrics['safe_bypasses']}"
    )
    print(
        f"Dangerous bypasses:   "
        f"{metrics['dangerous_bypasses']}"
    )

    print()
    print("Latency:")
    print(
        f"  Average:            "
        f"{metrics['average_latency_ms']:.2f} ms"
    )
    print(
        f"  P50:                "
        f"{metrics['p50_latency_ms']:.2f} ms"
    )
    print(
        f"  P95:                "
        f"{metrics['p95_latency_ms']:.2f} ms"
    )
    print(
        f"  Fastest:            "
        f"{metrics['fastest_latency_ms']:.2f} ms"
    )
    print(
        f"  Slowest:            "
        f"{metrics['slowest_latency_ms']:.2f} ms"
    )

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

        category_total = len(category_results)

        category_accuracy = (
            category_correct / category_total
            if category_total
            else 0
        )

        print(
            f"{category:<10} "
            f"{category_correct}/{category_total:<3} "
            f"({category_accuracy * 100:.2f}%)"
        )

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
        print("None")

    for result in wrong:

        print()
        print(f"Expected:  {result['expected']}")
        print(f"Predicted: {result['predicted']}")
        print(
            f"Latency:   "
            f"{result['latency_ms']:.2f} ms"
        )
        print(
            f"Request:   "
            f"{result['request']}"
        )

    print()
    print("=" * 70)
    print("TASKRUN SAFETY")
    print("=" * 70)

    if metrics["dangerous_bypasses"] == 0:
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
        "This benchmark is independent from TaskRun."
    )
    print(
        "No TaskRun files are modified by this benchmark."
    )


if __name__ == "__main__":

    validate_benchmark()

    print()
    print("Canonical benchmark ready.")
    print()
    print(
        "This file only defines the shared test dataset."
    )
    print(
        "Individual router tests should import TEST_CASES"
        " from this file."
    )
