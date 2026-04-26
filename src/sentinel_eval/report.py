from __future__ import annotations
from .core import EvalReport

def to_markdown(report: EvalReport) -> str:
    lines = [
        "# Sentinel Evaluation Report",
        "",
        f"Suite: `{report.suite_path}`",
        f"Total cases: **{report.total_cases}**",
        f"Pass rate: **{report.pass_rate:.2%}**",
        "",
        "## Aggregate scores",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for k, v in report.aggregate_scores.items():
        lines.append(f"| {k} | {v:.4f} |")
    lines += ["", "## Safety summary", "", "| Signal | Count |", "|---|---:|"]
    for k, v in report.safety_summary.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Case results", "", "| Case | Category | Passed | Token F1 | Groundedness |", "|---|---|---:|---:|---:|"]
    for r in report.results:
        lines.append(f"| {r.case_id} | {r.category} | {r.passed} | {r.scores['token_f1']:.3f} | {r.scores['groundedness']:.3f} |")
    return "\n".join(lines) + "\n"
