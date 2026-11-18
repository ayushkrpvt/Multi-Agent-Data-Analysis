"""
Run the sample questions through the full pipeline and save the reports
(with charts) into docs/samples/ - the "Sample Questions and Outputs" deliverable.

    python -m scripts.generate_samples            # all questions
    python -m scripts.generate_samples 1 3        # only questions 1 and 3
"""

import json
import re
import shutil
import sys
import time
from pathlib import Path

from graph.workflow import run_analysis
from tools.config import BASE_DIR, llm_description

QUESTIONS = [
    "Show monthly sales trends for 1997",
    "Compare sales by product category",
    "Who are the top 10 customers by revenue?",
    "Why did beverage sales decline in 1998?",
    "Are there any unusual spikes or drops in monthly sales?",
    "Which countries generate the most revenue?",
    "Which employees generated the highest sales in 1997?",
    "How has the number of orders changed per quarter?",
]

OUT = BASE_DIR / "docs" / "samples"


def save(i, question, result):
    folder = OUT / f"{i:02d}_{re.sub(r'[^a-z0-9]+', '_', question.lower()).strip('_')[:40]}"
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "charts").mkdir(parents=True)

    md = result.get("report_markdown") or f"# Failed\n\n{result.get('error')}"
    for c in result.get("charts") or []:
        src = Path(c["path"])
        dst = folder / "charts" / src.name.replace(result["run_id"] + "_", "")
        shutil.copy(src, dst)
        md = md.replace(f"../charts/{src.name}", f"charts/{dst.name}")

    (folder / "report.md").write_text(md, encoding="utf-8")
    summary = {
        "question": question,
        "analysis_type": result.get("analysis_route"),
        "error": result.get("error"),
        "sql_attempts": len(result.get("sql_attempts") or []),
        "queries": list((result.get("query_results") or {}).keys()),
        "failed_queries": result.get("failed_queries"),
        "seconds": round(sum(t["seconds"] for t in result.get("trace") or []), 1),
        "trace": result.get("trace"),
    }
    (folder / "run.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return folder, summary


def main():
    picks = [int(a) for a in sys.argv[1:]] or range(1, len(QUESTIONS) + 1)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in picks:
        q = QUESTIONS[i - 1]
        print(f"\n{'#' * 80}\n# [{i}] {q}\n{'#' * 80}")
        try:
            result = run_analysis(q)
        except Exception as e:
            result = {"error": str(e), "run_id": "failed"}
        folder, s = save(i, q, result)
        rows.append((i, q, s, folder))
        print(f"-> {folder.name}: type={s['analysis_type']} attempts={s['sql_attempts']} error={s['error']}")
        time.sleep(3)

    index = OUT / "README.md"
    existing = {}
    if index.exists():
        for line in index.read_text().splitlines():
            m = re.match(r"\| (\d+) \|", line)
            if m:
                existing[int(m.group(1))] = line
    for i, q, s, folder in rows:
        status = "✅" if not s["error"] else "❌"
        existing[i] = (f"| {i} | [{q}]({folder.name}/report.md) | {s['analysis_type']} | "
                       f"{len(s['queries'])} | {s['sql_attempts']} | {s['seconds']} | {status} |")
    lines = [
        "# Sample Questions and Outputs", "",
        f"Generated with **{llm_description()}** on the Northwind database. "
        "Each folder contains the full executive report (`report.md`), its charts and the agent trace (`run.json`).", "",
        "| # | Question | Analysis type | Data queries | SQL attempts (all queries) | Time (s) | Status |",
        "|---|---|---|---|---|---|---|",
        *[existing[k] for k in sorted(existing)], "",
    ]
    index.write_text("\n".join(lines), encoding="utf-8")
    print("\nIndex:", index)


if __name__ == "__main__":
    main()
