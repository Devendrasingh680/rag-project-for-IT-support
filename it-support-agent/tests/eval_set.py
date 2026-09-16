"""
Small evaluation set for checking that the sufficiency routing logic works.
Each case specifies whether we EXPECT the agent to answer from KB alone,
or to fall back to web search (because it's outside the internal docs' scope
by construction — e.g. references a specific software version not in our KB).

Run: python -m tests.eval_set
This does NOT check answer quality (that's subjective) — it checks that the
routing decision matches expectations, which is the part the assignment
spec actually asks you to build ("if internal search fails, trigger web tool").
"""
from app.agent import run_agent

EVAL_CASES = [
    {
        "query": "My VPN says connection timed out, what do I do?",
        "expected_source": "kb",
        "reason": "Directly covered in vpn__runbook doc",
    },
    {
        "query": "How do I reset a locked out account?",
        "expected_source": "kb",
        "reason": "Directly covered in accounts__policy doc",
    },
    {
        "query": "Outlook won't connect to the server, what's wrong?",
        "expected_source": "kb",
        "reason": "Directly covered in email__setup doc",
    },
    {
        "query": "What's the latest CVE affecting Cisco AnyConnect VPN clients in 2025?",
        "expected_source": "web",
        "reason": "Recent CVE info is not in static internal docs — must fall back to web",
    },
    {
        "query": "Is there a new zero-day exploit for Windows print spooler this month?",
        "expected_source": "web",
        "reason": "Time-sensitive security info not in internal runbooks",
    },
    {
        "query": "What's the current stock price of the company?",
        "expected_source": "web",
        "reason": "Completely outside IT support KB scope, should fall back",
    },
]


def run_eval():
    correct = 0
    for case in EVAL_CASES:
        result = run_agent(case["query"])
        actual = result["used_source"]
        # "kb+web" counts as using web if expected is web, and as using kb if expected is kb+kb-was-sufficient
        matched = (
            (case["expected_source"] == "kb" and actual == "kb")
            or (case["expected_source"] == "web" and actual in ("web", "kb+web"))
        )
        correct += matched
        status = "PASS" if matched else "FAIL"
        print(f"[{status}] '{case['query'][:50]}...' "
              f"expected={case['expected_source']} actual={actual} "
              f"top_score={result['kb_top_score']:.3f}")

    print(f"\n{correct}/{len(EVAL_CASES)} routing decisions correct")


if __name__ == "__main__":
    run_eval()
