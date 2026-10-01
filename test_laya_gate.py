import time
from laya import Router


router = Router(preload=True)

questions = {
    "route": {
        "type": "choice",
        "instructions": "Does this request require TaskRun to perform work using Jira, Splunk, computer tools, files, shell commands, Docker, or other external systems?",
        "criteria": {
            "NO_WORK": (
                "The request can be answered conversationally or with general knowledge. "
                "It does not require TaskRun to access external systems, files, the computer, "
                "Jira, Splunk, Docker, or execute an action."
            ),
            "WORK": (
                "The request asks TaskRun to perform an action, retrieve information from "
                "Jira or Splunk, interact with the computer or filesystem, run commands, "
                "use Docker, or access an external system."
            ),
        },
    }
}


tests = [
    # -------------------------
    # NO_WORK: casual
    # -------------------------
    ("hey, how are you doing?", "NO_WORK"),
    ("what's up?", "NO_WORK"),
    ("hope you're having a good day", "NO_WORK"),
    ("thanks, that helped", "NO_WORK"),
    ("nice to meet you", "NO_WORK"),
    ("good morning", "NO_WORK"),
    ("can you help me understand something?", "NO_WORK"),

    # -------------------------
    # NO_WORK: general knowledge
    # -------------------------
    ("What is machine learning?", "NO_WORK"),
    ("Explain neural networks to me", "NO_WORK"),
    ("What is the difference between SQL and NoSQL?", "NO_WORK"),
    ("What is Python used for?", "NO_WORK"),
    ("How does Docker work?", "NO_WORK"),
    ("What is an API?", "NO_WORK"),
    ("Explain what an LLM is", "NO_WORK"),
    ("What is feature engineering?", "NO_WORK"),
    ("Why do neural networks need activation functions?", "NO_WORK"),

    # -------------------------
    # WORK: Jira
    # -------------------------
    ("Check WUK-2312", "WORK"),
    ("What is the status of WUK-2312?", "WORK"),
    ("Show me the priority of WUK-2312", "WORK"),
    ("Search Jira for unresolved high priority issues", "WORK"),
    ("Find all open Jira tickets assigned to me", "WORK"),
    ("Get the details of WUK-2312", "WORK"),

    # -------------------------
    # WORK: Splunk
    # -------------------------
    ("Search Splunk for failed login attempts", "WORK"),
    ("Show me the available Splunk indexes", "WORK"),
    ("Find errors in Splunk from today", "WORK"),
    ("Search the logs for authentication failures", "WORK"),
    ("Look for HTTP 500 errors in Splunk", "WORK"),

    # -------------------------
    # WORK: computer / MCP
    # -------------------------
    ("Create a folder called test", "WORK"),
    ("Run docker ps", "WORK"),
    ("Read the file ~/taskrun/harness/runner.py", "WORK"),
    ("List the files in my taskrun directory", "WORK"),
    ("Show me the running processes", "WORK"),
    ("Create a file called test.txt", "WORK"),
    ("Move this file to another directory", "WORK"),
    ("Check my system information", "WORK"),

    # -------------------------
    # WORK: paraphrased requests
    # -------------------------
    ("Can you take a look at WUK-2312?", "WORK"),
    ("I need you to inspect the Jira ticket WUK-2312", "WORK"),
    ("Can you investigate failed logins in Splunk?", "WORK"),
    ("I want you to check what containers are running", "WORK"),
    ("Can you inspect the runner.py file for me?", "WORK"),
    ("Please make a directory named test", "WORK"),

    # -------------------------
    # WORK: multi-system
    # -------------------------
    (
        "Check WUK-2312 and then search Splunk for related errors",
        "WORK",
    ),
    (
        "Look at the Jira issue and then inspect the logs",
        "WORK",
    ),

    # -------------------------
    # Ambiguous but should still be WORK
    # -------------------------
    ("Can you check this for me?", "WORK"),
    ("Look into the issue", "WORK"),
]


def main():
    results = []

    print("=" * 90)
    print("Laya NO_WORK vs WORK Gate Test")
    print("=" * 90)
    print()

    # Warm-up
    print("Warming up Laya...")
    router.predict({"body": "hello"}, questions)
    print("Warm-up complete.")
    print()

    for index, (request, expected) in enumerate(tests, start=1):
        start = time.perf_counter()

        result = router.predict(
            {"body": request},
            questions,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        answer = result["answers"]["route"]
        decision = answer["choice"]
        confidence = answer["confidence"]
        probabilities = answer["probabilities"]

        passed = decision == expected

        results.append({
            "passed": passed,
            "latency": elapsed_ms,
        })

        status = "PASS" if passed else "FAIL"

        print(f"[{index:02d}] {status}")
        print(f"Request:     {request}")
        print(f"Expected:    {expected}")
        print(f"Decision:    {decision}")
        print(f"Confidence:  {confidence:.4f}")
        print(f"Probabilities:")
        for label, probability in probabilities.items():
            print(f"  {label:10s} {probability:.4f}")
        print(f"Latency:     {elapsed_ms:.2f} ms")
        print("-" * 90)

    total = len(results)
    correct = sum(r["passed"] for r in results)
    accuracy = correct / total * 100

    latencies = [r["latency"] for r in results]
    average_latency = sum(latencies) / len(latencies)

    print()
    print("=" * 90)
    print("FINAL RESULTS")
    print("=" * 90)
    print(f"Correct:          {correct}/{total}")
    print(f"Accuracy:         {accuracy:.2f}%")
    print(f"Average latency:  {average_latency:.2f} ms")
    print("=" * 90)


if __name__ == "__main__":
    main()
