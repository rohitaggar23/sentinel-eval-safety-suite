from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class EvalCase:
    id: str
    prompt: str
    expected: str = ""
    contexts: List[str] = field(default_factory=list)
    expected_keywords: List[str] = field(default_factory=list)
    must_refuse: bool = False
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelResponse:
    text: str
    citations: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CaseResult:
    case_id: str
    category: str
    prompt: str
    response: str
    scores: Dict[str, float]
    safety: Dict[str, Any]
    passed: bool
    notes: List[str] = field(default_factory=list)

@dataclass
class EvalReport:
    suite_path: str
    total_cases: int
    pass_rate: float
    aggregate_scores: Dict[str, float]
    safety_summary: Dict[str, int]
    results: List[CaseResult]
    gates: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_path": self.suite_path,
            "total_cases": self.total_cases,
            "pass_rate": self.pass_rate,
            "aggregate_scores": self.aggregate_scores,
            "safety_summary": self.safety_summary,
            "results": [asdict(r) for r in self.results],
            "gates": self.gates,
        }

def load_cases(path: str) -> List[EvalCase]:
    cases: List[EvalCase] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                cases.append(EvalCase(**data))
            except Exception as exc:
                raise ValueError(f"Invalid JSONL case at {path}:{line_no}: {exc}") from exc
    return cases

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
