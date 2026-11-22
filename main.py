"""
Command-line runner.

    python main.py "Compare sales by product category"
"""

import sys

from graph.workflow import run_analysis


def main():
    question = " ".join(sys.argv[1:]).strip() or input("Business question: ").strip()
    result = run_analysis(question)

    print("\n" + "=" * 80)
    if (result.get("guardrail") or {}).get("blocked"):
        print(result["guardrail"]["message"])
        return
    if result.get("error"):
        print("ERROR:", result["error"])
        sys.exit(1)

    report = result["report"]
    print(report["title"].upper())
    print("=" * 80)
    print("\n" + report["business_summary"])
    print("\nKEY FINDINGS")
    for f in report["key_findings"]:
        print(" -", f)
    print("\nRECOMMENDATIONS")
    for r in report["recommendations"]:
        print(f" - [{r['priority']}] {r['action']}")
    print("\nCharts:")
    for c in result.get("charts", []):
        print(" -", c["path"])
    print("\nFull report:", result["report_path"])


if __name__ == "__main__":
    main()
