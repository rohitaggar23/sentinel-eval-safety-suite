from __future__ import annotations
import argparse, os
from .adapters import RuleBasedMockAdapter, ChatCompletionsAdapter
from .core import write_json
from .runner import EvalRunner
from .report import to_markdown

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sentinel LLM eval and safety suite")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--suite", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--markdown", default="")
    run.add_argument("--adapter", choices=["mock", "chat-completions"], default="mock")
    run.add_argument("--model", default=os.getenv("MODEL_NAME", "production-model"))
    run.add_argument("--base-url", default=os.getenv("REMOTE_BASE_URL", "https://api.example.com/v1"))
    return p

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "run":
        if args.adapter == "mock":
            adapter = RuleBasedMockAdapter()
        else:
            key = os.getenv("REMOTE_API_KEY")
            if not key:
                raise SystemExit("REMOTE_API_KEY is required for chat-completions adapter")
            adapter = ChatCompletionsAdapter(api_key=key, model=args.model, base_url=args.base_url)
        report = EvalRunner(adapter).run(args.suite)
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        write_json(args.output, report.to_dict())
        if args.markdown:
            os.makedirs(os.path.dirname(args.markdown) or ".", exist_ok=True)
            with open(args.markdown, "w", encoding="utf-8") as f:
                f.write(to_markdown(report))
        print(f"pass_rate={report.pass_rate:.2%} total_cases={report.total_cases}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
