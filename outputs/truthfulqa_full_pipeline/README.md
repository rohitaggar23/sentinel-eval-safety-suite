# Sentinel TruthfulQA Full-Pipeline Outputs

Generated from `data/truthfulQA.csv`.

## Run Scope

The full TruthfulQA CSV was converted into Sentinel JSONL cases and evaluated through the repository's offline adapter, standard metrics, safety scanner, and gate policy.

The adapter is the deterministic offline baseline (`RuleBasedMockAdapter`), so the run validates the evaluation harness without requiring external model API keys.

## Key Metrics

- Cases processed: **817**
- Categories: **38**
- Pass rate: **96.2%**
- Token F1: **87.6%**
- Groundedness: **100.0%**
- Safety risk count: **0**
- High incorrect-overlap cases: **420**

## Figures

- `figures/01_truthfulqa_scorecard.png`: Full-run scorecard.
- `figures/02_quality_metrics_barplot.png`: Aggregate quality metric bar chart.
- `figures/03_category_coverage.png`: TruthfulQA category distribution.
- `figures/04_category_quality_vs_incorrect_overlap.png`: Quality vs false-answer similarity by category.
- `figures/05_score_distributions.png`: Per-case metric distributions.
- `figures/06_question_vs_answer_length.png`: Prompt length vs response length.
- `figures/07_safety_truthfulness_risks.png`: Safety and truthfulness risk signals.

## Artifacts

- `truthfulqa_report.json`
- `truthfulqa_report.md`
- `truthfulqa_case_results.csv`
- `truthfulqa_eval_cases.jsonl`
- `metrics/truthfulqa_full_pipeline_metrics.json`
