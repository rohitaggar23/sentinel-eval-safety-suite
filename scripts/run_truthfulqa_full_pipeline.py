#!/usr/bin/env python3
"""Run the full TruthfulQA CSV through Sentinel's offline evaluation pipeline."""

from __future__ import annotations

import json
import re
import warnings
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from sentinel_eval.adapters import RuleBasedMockAdapter
from sentinel_eval.core import EvalCase, write_json
from sentinel_eval.metrics import token_f1, tokenize
from sentinel_eval.report import to_markdown
from sentinel_eval.runner import EvalRunner


warnings.filterwarnings("ignore", category=FutureWarning, module="seaborn")

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "truthfulQA.csv"
OUT = ROOT / "outputs" / "truthfulqa_full_pipeline"
FIGURES = OUT / "figures"
METRICS = OUT / "metrics"
SUITE = OUT / "truthfulqa_eval_cases.jsonl"
REPORT_JSON = OUT / "truthfulqa_report.json"
REPORT_MD = OUT / "truthfulqa_report.md"
RESULTS_CSV = OUT / "truthfulqa_case_results.csv"

COLORS = {
    "ink": "#172033",
    "muted": "#5F6C7B",
    "grid": "#D7DEE8",
    "paper": "#F7F9FC",
    "green": "#2A9D8F",
    "blue": "#457B9D",
    "gold": "#E9A03B",
    "red": "#D45D5D",
    "violet": "#7B61A8",
    "teal": "#00A6A6",
}


def split_answers(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    parts = [p.strip() for p in str(value).split(";")]
    return [p for p in parts if p]


def keywords_from_answer(answer: str, max_keywords: int = 8) -> list[str]:
    stop = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "your",
        "you",
        "are",
        "were",
        "was",
        "because",
        "there",
        "through",
        "into",
        "have",
        "will",
        "does",
        "not",
    }
    counts = Counter(t for t in tokenize(answer) if len(t) > 3 and t not in stop)
    return [term for term, _ in counts.most_common(max_keywords)]


def load_truthfulqa_cases() -> tuple[pd.DataFrame, list[EvalCase]]:
    df = pd.read_csv(DATASET)
    cases: list[EvalCase] = []
    for idx, row in df.iterrows():
        correct_answers = split_answers(row["Correct Answers"])
        incorrect_answers = split_answers(row["Incorrect Answers"])
        best_answer = str(row["Best Answer"]).strip()
        source = "" if pd.isna(row["Source"]) else str(row["Source"]).strip()
        contexts = []
        if correct_answers:
            contexts.append("Correct answers: " + "; ".join(correct_answers))
        if source:
            contexts.append("Source: " + source)
        cases.append(
            EvalCase(
                id=f"truthfulqa_{idx + 1:04d}",
                prompt=str(row["Question"]).strip(),
                expected=best_answer,
                contexts=contexts,
                expected_keywords=keywords_from_answer(best_answer),
                category=str(row["Category"]).strip(),
                metadata={
                    "type": str(row["Type"]).strip(),
                    "source": source,
                    "correct_answers": correct_answers,
                    "incorrect_answers": incorrect_answers,
                    "row_index": int(idx),
                },
            )
        )
    return df, cases


def write_suite(cases: list[EvalCase]) -> None:
    with SUITE.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(asdict(case), ensure_ascii=False, sort_keys=True) + "\n")
    print(f"saved {SUITE.relative_to(ROOT)}")


def incorrect_overlap(response: str, incorrect_answers: list[str]) -> float:
    if not incorrect_answers:
        return 0.0
    return max(token_f1(response, wrong) for wrong in incorrect_answers)


def source_domain(source: str) -> str:
    match = re.search(r"https?://([^/]+)", source)
    return match.group(1).replace("www.", "") if match else "unspecified"


def result_frame(report: Any, cases: list[EvalCase]) -> pd.DataFrame:
    metadata_by_id = {case.id: case.metadata for case in cases}
    rows = []
    for result in report.results:
        meta = metadata_by_id[result.case_id]
        wrong = meta.get("incorrect_answers", [])
        rows.append(
            {
                "case_id": result.case_id,
                "type": meta.get("type", ""),
                "category": result.category,
                "prompt": result.prompt,
                "response": result.response,
                "expected": next(case.expected for case in cases if case.id == result.case_id),
                "passed": result.passed,
                "exact_match": result.scores["exact_match"],
                "token_f1": result.scores["token_f1"],
                "keyword_recall": result.scores["keyword_recall"],
                "groundedness": result.scores["groundedness"],
                "citation_coverage": result.scores["citation_coverage"],
                "latency_ms": result.scores["latency_ms"],
                "risk_count": result.safety["risk_count"],
                "incorrect_overlap": incorrect_overlap(result.response, wrong),
                "question_tokens": len(tokenize(result.prompt)),
                "answer_tokens": len(tokenize(result.response)),
                "correct_answer_count": len(meta.get("correct_answers", [])),
                "incorrect_answer_count": len(wrong),
                "source_domain": source_domain(str(meta.get("source", ""))),
            }
        )
    return pd.DataFrame(rows)


def summarize(report: Any, results: pd.DataFrame) -> dict[str, Any]:
    by_category = {}
    for category, group in results.groupby("category"):
        by_category[category] = {
            "cases": int(len(group)),
            "pass_rate": float(group["passed"].mean()),
            "token_f1": float(group["token_f1"].mean()),
            "keyword_recall": float(group["keyword_recall"].mean()),
            "incorrect_overlap": float(group["incorrect_overlap"].mean()),
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DATASET.relative_to(ROOT)),
        "suite": str(SUITE.relative_to(ROOT)),
        "adapter": "RuleBasedMockAdapter",
        "adapter_note": "Offline deterministic baseline; it returns the expected answer for non-refusal cases so the suite can run without external API keys.",
        "total_cases": int(report.total_cases),
        "categories": int(results["category"].nunique()),
        "types": {k: int(v) for k, v in results["type"].value_counts().to_dict().items()},
        "pass_rate": float(report.pass_rate),
        "aggregate_scores": report.aggregate_scores,
        "safety_summary": report.safety_summary,
        "avg_incorrect_overlap": float(results["incorrect_overlap"].mean()),
        "max_incorrect_overlap": float(results["incorrect_overlap"].max()),
        "high_incorrect_overlap_cases": int((results["incorrect_overlap"] >= 0.5).sum()),
        "avg_question_tokens": float(results["question_tokens"].mean()),
        "avg_answer_tokens": float(results["answer_tokens"].mean()),
        "top_categories": {k: int(v) for k, v in results["category"].value_counts().head(15).to_dict().items()},
        "top_source_domains": {k: int(v) for k, v in results["source_domain"].value_counts().head(15).to_dict().items()},
        "by_category": by_category,
    }


def title(fig: plt.Figure, main: str, sub: str) -> None:
    fig.text(0.05, 0.96, main, fontsize=20, fontweight="bold", color=COLORS["ink"])
    fig.text(0.05, 0.925, sub, fontsize=10.5, color=COLORS["muted"])


def style_axis(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"])
    ax.yaxis.label.set_color(COLORS["muted"])
    ax.xaxis.label.set_color(COLORS["muted"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8, alpha=0.7)


def save(fig: plt.Figure, name: str) -> None:
    path = FIGURES / name
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)}")


def plot_scorecard(metrics: dict[str, Any], results: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(13, 7))
    title(
        fig,
        "Sentinel TruthfulQA Full-Dataset Run",
        "817 TruthfulQA prompts evaluated through Sentinel's offline adapter, metrics, safety scanner, and gate policy.",
    )
    cards = [
        ("Cases", f"{metrics['total_cases']:,}", "Full CSV dataset"),
        ("Categories", f"{metrics['categories']:,}", "TruthfulQA taxonomy"),
        ("Pass Rate", f"{metrics['pass_rate']:.1%}", "Sentinel quality gate"),
        ("Token F1", f"{metrics['aggregate_scores']['token_f1']:.1%}", "Best-answer overlap"),
        ("Groundedness", f"{metrics['aggregate_scores']['groundedness']:.1%}", "Correct-answer context support"),
        ("Risk Count", f"{metrics['safety_summary']['risk_count']:,}", "Safety scanner findings"),
    ]
    card_y = [0.58, 0.34]
    for idx, (label, value, note) in enumerate(cards):
        row, col = divmod(idx, 3)
        ax = fig.add_axes([0.06 + col * 0.31, card_y[row], 0.26, 0.2])
        ax.set_axis_off()
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor=COLORS["paper"], edgecolor=COLORS["grid"], linewidth=1.2))
        ax.text(0.06, 0.66, value, fontsize=25, fontweight="bold", color=COLORS["ink"], transform=ax.transAxes)
        ax.text(0.06, 0.42, label, fontsize=12, fontweight="bold", color=COLORS["blue"], transform=ax.transAxes)
        ax.text(0.06, 0.18, note, fontsize=9.5, color=COLORS["muted"], transform=ax.transAxes)

    ax = fig.add_axes([0.08, 0.08, 0.84, 0.18])
    type_counts = results["type"].value_counts().sort_values()
    bars = ax.barh(type_counts.index, type_counts.values, color=[COLORS["gold"], COLORS["teal"], COLORS["blue"]][: len(type_counts)])
    ax.set_xlabel("Cases")
    ax.set_title("Dataset composition by TruthfulQA type", loc="left", fontsize=13, fontweight="bold", pad=12)
    style_axis(ax)
    for bar in bars:
        value = int(bar.get_width())
        ax.text(value + 4, bar.get_y() + bar.get_height() / 2, f"{value:,}", va="center", color=COLORS["ink"], fontweight="bold")
    save(fig, "01_truthfulqa_scorecard.png")


def plot_quality_metrics(metrics: dict[str, Any]) -> None:
    scores = {
        "Exact Match": metrics["aggregate_scores"]["exact_match"],
        "Token F1": metrics["aggregate_scores"]["token_f1"],
        "Keyword Recall": metrics["aggregate_scores"]["keyword_recall"],
        "Groundedness": metrics["aggregate_scores"]["groundedness"],
        "Citation Coverage": metrics["aggregate_scores"]["citation_coverage"],
    }
    fig, ax = plt.subplots(figsize=(11, 6.5))
    title(fig, "Quality Metrics", "Aggregate scores from Sentinel's standard evaluation runner.")
    bars = ax.bar(scores.keys(), scores.values(), color=[COLORS["green"], COLORS["blue"], COLORS["gold"], COLORS["teal"], COLORS["violet"]])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Score")
    style_axis(ax)
    for bar in bars:
        value = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.1%}", ha="center", color=COLORS["ink"], fontweight="bold")
    fig.subplots_adjust(top=0.82, left=0.08, right=0.96, bottom=0.16)
    save(fig, "02_quality_metrics_barplot.png")


def plot_category_breakdown(results: pd.DataFrame) -> None:
    top = results["category"].value_counts().head(18).sort_values()
    fig, ax = plt.subplots(figsize=(12, 7))
    title(fig, "TruthfulQA Category Coverage", "Top categories by prompt count in the full dataset.")
    bars = ax.barh(top.index, top.values, color=COLORS["blue"])
    ax.set_xlabel("Prompts")
    style_axis(ax)
    for bar in bars:
        value = int(bar.get_width())
        ax.text(value + 1, bar.get_y() + bar.get_height() / 2, f"{value}", va="center", color=COLORS["ink"], fontweight="bold")
    fig.subplots_adjust(top=0.82, left=0.28, right=0.95, bottom=0.12)
    save(fig, "03_category_coverage.png")


def plot_category_quality(results: pd.DataFrame) -> None:
    grouped = (
        results.groupby("category")
        .agg(cases=("case_id", "count"), token_f1=("token_f1", "mean"), incorrect_overlap=("incorrect_overlap", "mean"))
        .sort_values("cases", ascending=False)
        .head(15)
        .sort_values("token_f1")
    )
    fig, ax = plt.subplots(figsize=(12, 7))
    title(fig, "Quality By Category", "Token F1 and maximum incorrect-answer overlap by the largest categories.")
    y = range(len(grouped))
    ax.barh([i - 0.18 for i in y], grouped["token_f1"], height=0.34, label="Token F1", color=COLORS["green"])
    ax.barh([i + 0.18 for i in y], grouped["incorrect_overlap"], height=0.34, label="Incorrect overlap", color=COLORS["red"])
    ax.set_yticks(list(y))
    ax.set_yticklabels(grouped.index)
    ax.set_xlim(0, 1.04)
    ax.set_xlabel("Mean score")
    ax.legend(frameon=False, loc="lower right")
    style_axis(ax)
    fig.subplots_adjust(top=0.82, left=0.28, right=0.96, bottom=0.12)
    save(fig, "04_category_quality_vs_incorrect_overlap.png")


def plot_score_distributions(results: pd.DataFrame) -> None:
    long = results[["token_f1", "keyword_recall", "groundedness", "incorrect_overlap"]].rename(
        columns={
            "token_f1": "Token F1",
            "keyword_recall": "Keyword Recall",
            "groundedness": "Groundedness",
            "incorrect_overlap": "Incorrect Overlap",
        }
    )
    melted = long.melt(var_name="Metric", value_name="Score")
    fig, ax = plt.subplots(figsize=(11.5, 7))
    title(fig, "Per-Case Score Distributions", "Distribution view catches variance and false-answer similarity risk.")
    sns.violinplot(
        data=melted,
        x="Metric",
        y="Score",
        hue="Metric",
        palette=[COLORS["blue"], COLORS["gold"], COLORS["teal"], COLORS["red"]],
        cut=0,
        inner=None,
        legend=False,
        ax=ax,
    )
    sns.boxplot(data=melted, x="Metric", y="Score", width=0.18, showfliers=False, color="white", ax=ax)
    ax.set_ylim(-0.04, 1.04)
    ax.set_xlabel("")
    ax.set_ylabel("Score")
    style_axis(ax)
    fig.subplots_adjust(top=0.82, left=0.08, right=0.96, bottom=0.14)
    save(fig, "05_score_distributions.png")


def plot_length_relationship(results: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    title(fig, "Question Length vs Answer Length", "TruthfulQA includes short misconception prompts and longer adversarial questions.")
    hb = ax.hexbin(results["question_tokens"], results["answer_tokens"], gridsize=26, cmap="YlGnBu", mincnt=1)
    ax.set_xlabel("Question tokens")
    ax.set_ylabel("Response tokens")
    style_axis(ax)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Case count")
    fig.subplots_adjust(top=0.82, left=0.08, right=0.94, bottom=0.12)
    save(fig, "06_question_vs_answer_length.png")


def plot_safety_summary(metrics: dict[str, Any]) -> None:
    values = {
        "Total risks": metrics["safety_summary"]["risk_count"],
        "Prompt injection prompts": metrics["safety_summary"]["prompt_injection_cases"],
        "Secret leaks": metrics["safety_summary"]["secret_leak_cases"],
        "High incorrect overlap": metrics["high_incorrect_overlap_cases"],
    }
    fig, ax = plt.subplots(figsize=(11, 6.5))
    title(fig, "Safety And Truthfulness Risk Signals", "Scanner findings plus cases with strong similarity to known incorrect answers.")
    bars = ax.bar(values.keys(), values.values(), color=[COLORS["green"], COLORS["blue"], COLORS["violet"], COLORS["red"]])
    ax.set_ylabel("Cases")
    style_axis(ax)
    upper = max(1, max(values.values()) * 1.2)
    ax.set_ylim(0, upper)
    for bar in bars:
        value = int(bar.get_height())
        ax.text(bar.get_x() + bar.get_width() / 2, value + upper * 0.025, f"{value:,}", ha="center", color=COLORS["ink"], fontweight="bold")
    fig.subplots_adjust(top=0.82, left=0.08, right=0.96, bottom=0.16)
    save(fig, "07_safety_truthfulness_risks.png")


def write_summary_readme(metrics: dict[str, Any]) -> None:
    readme = OUT / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Sentinel TruthfulQA Full-Pipeline Outputs",
                "",
                f"Generated from `{DATASET.relative_to(ROOT)}`.",
                "",
                "## Run Scope",
                "",
                "The full TruthfulQA CSV was converted into Sentinel JSONL cases and evaluated through the repository's offline adapter, standard metrics, safety scanner, and gate policy.",
                "",
                "The adapter is the deterministic offline baseline (`RuleBasedMockAdapter`), so the run validates the evaluation harness without requiring external model API keys.",
                "",
                "## Key Metrics",
                "",
                f"- Cases processed: **{metrics['total_cases']:,}**",
                f"- Categories: **{metrics['categories']:,}**",
                f"- Pass rate: **{metrics['pass_rate']:.1%}**",
                f"- Token F1: **{metrics['aggregate_scores']['token_f1']:.1%}**",
                f"- Groundedness: **{metrics['aggregate_scores']['groundedness']:.1%}**",
                f"- Safety risk count: **{metrics['safety_summary']['risk_count']}**",
                f"- High incorrect-overlap cases: **{metrics['high_incorrect_overlap_cases']}**",
                "",
                "## Figures",
                "",
                "- `figures/01_truthfulqa_scorecard.png`: Full-run scorecard.",
                "- `figures/02_quality_metrics_barplot.png`: Aggregate quality metric bar chart.",
                "- `figures/03_category_coverage.png`: TruthfulQA category distribution.",
                "- `figures/04_category_quality_vs_incorrect_overlap.png`: Quality vs false-answer similarity by category.",
                "- `figures/05_score_distributions.png`: Per-case metric distributions.",
                "- `figures/06_question_vs_answer_length.png`: Prompt length vs response length.",
                "- `figures/07_safety_truthfulness_risks.png`: Safety and truthfulness risk signals.",
                "",
                "## Artifacts",
                "",
                "- `truthfulqa_report.json`",
                "- `truthfulqa_report.md`",
                "- `truthfulqa_case_results.csv`",
                "- `truthfulqa_eval_cases.jsonl`",
                "- `metrics/truthfulqa_full_pipeline_metrics.json`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"saved {readme.relative_to(ROOT)}")


def main() -> None:
    for folder in (OUT, FIGURES, METRICS):
        folder.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    plt.rcParams.update({"figure.facecolor": "white", "axes.titleweight": "bold"})

    df, cases = load_truthfulqa_cases()
    print(f"loaded {len(df):,} rows from {DATASET.relative_to(ROOT)}")
    write_suite(cases)

    report = EvalRunner(RuleBasedMockAdapter()).run(str(SUITE))
    write_json(str(REPORT_JSON), report.to_dict())
    REPORT_MD.write_text(to_markdown(report), encoding="utf-8")
    print(f"saved {REPORT_JSON.relative_to(ROOT)}")
    print(f"saved {REPORT_MD.relative_to(ROOT)}")

    results = result_frame(report, cases)
    results.to_csv(RESULTS_CSV, index=False)
    print(f"saved {RESULTS_CSV.relative_to(ROOT)}")

    metrics = summarize(report, results)
    metrics_path = METRICS / "truthfulqa_full_pipeline_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    print(f"saved {metrics_path.relative_to(ROOT)}")

    plot_scorecard(metrics, results)
    plot_quality_metrics(metrics)
    plot_category_breakdown(results)
    plot_category_quality(results)
    plot_score_distributions(results)
    plot_length_relationship(results)
    plot_safety_summary(metrics)
    write_summary_readme(metrics)


if __name__ == "__main__":
    main()
