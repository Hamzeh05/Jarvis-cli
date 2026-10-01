import time
from laya import Router


router = Router(preload=True)

questions = {
    "route": {
        "type": "choice",
        "instructions": (
            "Decide whether this request is safe to answer directly without "
            "using TaskRun tools, Jira, Splunk, filesystem access, shell commands, "
            "Docker, or any external system."
        ),
        "criteria": {
            "NO_WORK": (
                "The request is ordinary conversation, greetings, thanks, "
                "general knowledge, explanations, definitions, or conceptual "
                "questions. No external system or computer action is required."
            ),
            "WORK": (
                "The request asks TaskRun to retrieve information, inspect something, "
                "change something, execute an action, access a file, run a command, "
                "use Docker, Jira, Splunk, or interact with any external system."
            ),
        },
    }
}


tests = [
    # =========================
    # Clearly NO_WORK
    # =========================
    ("hey", "NO_WORK"),
    ("hello", "NO_WORK"),
    ("how are you?", "NO_WORK"),
    ("how are you doing?", "NO_WORK"),
    ("what's up?", "NO_WORK"),
    ("good morning", "NO_WORK"),
    ("thanks", "NO_WORK"),
    ("thanks, that helped", "NO_WORK"),
    ("nice to meet you", "NO_WORK"),
    ("hope you're having a good day", "NO_WORK"),

    ("What is machine learning?", "NO_WORK"),
    ("Explain neural networks", "NO_WORK"),
    ("What is an API?", "NO_WORK"),
    ("What is feature engineering?", "NO_WORK"),
    ("What is an LLM?", "NO_WORK"),
    ("What is SQL?", "NO_WORK"),
    ("What is Python used for?", "NO_WORK"),
    ("Why do neural networks need activation functions?", "NO_WORK"),
    ("Explain gradient descent", "NO_WORK"),
    ("What is cloud computing?", "NO_WORK"),
    ("How does Docker work?", "NO_WORK"),
    ("What is the difference between AI and ML?", "NO_WORK"),
    ("Explain REST APIs", "NO_WORK"),
    ("What is a neural network?", "NO_WORK"),
    ("How does an operating system work?", "NO_WORK"),

    # =========================
    # Clearly WORK
    # =========================
    ("Check WUK-2312", "WORK"),
    ("What is the status of WUK-2312?", "WORK"),
    ("Show me the priority of WUK-2312", "WORK"),
    ("Get the details of WUK-2312", "WORK"),
    ("Search Jira for unresolved issues", "WORK"),
    ("Find open Jira tickets assigned to me", "WORK"),

    ("Search Splunk for failed login attempts", "WORK"),
    ("Find errors in Splunk", "WORK"),
    ("Show me the available Splunk indexes", "WORK"),
    ("Search the logs for authentication failures", "WORK"),

    ("Run docker ps", "WORK"),
    ("Create a folder called test", "WORK"),
    ("Create a file called test.txt", "WORK"),
    ("Read ~/taskrun/harness/runner.py", "WORK"),
    ("List the files in my taskrun directory", "WORK"),
    ("Show me the running processes", "WORK"),
    ("Check my system information", "WORK"),
    ("Move this file to another directory", "WORK"),

    # =========================
    # Paraphrased WORK
    # =========================
    ("Can you take a look at WUK-2312?", "WORK"),
    ("I need you to inspect WUK-2312", "WORK"),
    ("Can you investigate failed logins in Splunk?", "WORK"),
    ("Can you inspect runner.py for me?", "WORK"),
    ("Please make a directory named test", "WORK"),
    ("I want you to check what containers are running", "WORK"),
    ("Could you look at the files in my taskrun directory?", "WORK"),

    # =========================
    # Ambiguous requests
    # These MUST NOT be bypassed.
    # =========================
    ("Can you check this for me?", "WORK"),
    ("Look into the issue", "WORK"),
    ("Can you take a look?", "WORK"),
    ("Check this", "WORK"),
]


def main():
    print("=" * 90)
    print("Laya Conservative NO_WORK Gate Test")
    print("=" * 90)

    print("\nWarming up Laya...")
    router.predict({"body": "warm up"}, questions)
    print("Warm-up complete.\n")

    results = []

    for i, (request, expected) in enumerate(tests, 1):
        start = time.perf_counter()

        result = router.predict(
            {"body": request},
            questions,
        )

        latency = (time.perf_counter() - start) * 1000

        answer = result["answers"]["route"]
        decision = answer["choice"]
        confidence = answer["confidence"]
        probabilities = answer["probabilities"]

        no_work_probability = probabilities["NO_WORK"]
        work_probability = probabilities["WORK"]

        # Conservative bypass rule:
        # Only bypass TaskRun if NO_WORK is VERY dominant.
        safe_bypass = (
            decision == "NO_WORK"
            and no_work_probability >= 0.90
        )

        # A false bypass is the dangerous failure.
        dangerous = (
            expected == "WORK"
            and safe_bypass
        )

        correct_classification = decision == expected

        results.append({
            "request": request,
            "expected": expected,
            "decision": decision,
            "no_work_probability": no_work_probability,
            "work_probability": work_probability,
            "confidence": confidence,
            "latency": latency,
            "safe_bypass": safe_bypass,
            "dangerous": dangerous,
            "correct": correct_classification,
        })

        if dangerous:
            status = "!!! DANGEROUS BYPASS !!!"
        elif correct_classification:
            status = "PASS"
        else:
            status = "SAFE FALLBACK"

        print(f"[{i:02d}] {status}")
        print(f"Request:       {request}")
        print(f"Expected:      {expected}")
        print(f"Decision:      {decision}")
        print(f"NO_WORK prob:  {no_work_probability:.4f}")
        print(f"WORK prob:     {work_probability:.4f}")
        print(f"Confidence:    {confidence:.4f}")
        print(f"Safe bypass:   {safe_bypass}")
        print(f"Latency:       {latency:.2f} ms")
        print("-" * 90)

    total = len(results)
    correct = sum(r["correct"] for r in results)

    no_work_tests = [
        r for r in results
        if r["expected"] == "NO_WORK"
    ]

    work_tests = [
        r for r in results
        if r["expected"] == "WORK"
    ]

    dangerous_bypasses = [
        r for r in results
        if r["dangerous"]
    ]

    successful_bypasses = [
        r for r in no_work_tests
        if r["safe_bypass"]
    ]

    latencies = [r["latency"] for r in results]

    print("\n")
    print("=" * 90)
    print("FINAL RESULTS")
    print("=" * 90)

    print(f"Overall classification: {correct}/{total} "
          f"({correct / total * 100:.2f}%)")

    print()
    print(f"NO_WORK requests:        {len(no_work_tests)}")
    print(f"Safe direct bypasses:    {len(successful_bypasses)}")

    print()
    print(f"WORK requests:           {len(work_tests)}")
    print(f"Dangerous bypasses:      {len(dangerous_bypasses)}")

    print()
    print(f"Average latency:         {sum(latencies) / len(latencies):.2f} ms")
    print(f"Fastest:                 {min(latencies):.2f} ms")
    print(f"Slowest:                 {max(latencies):.2f} ms")

    print()
    if dangerous_bypasses:
        print("DANGEROUS CASES:")
        for r in dangerous_bypasses:
            print(
                f"  - {r['request']} "
                f"(NO_WORK={r['no_work_probability']:.4f})"
            )
    else:
        print("DANGEROUS CASES: NONE")

    print("=" * 90)


if __name__ == "__main__":
    main()
