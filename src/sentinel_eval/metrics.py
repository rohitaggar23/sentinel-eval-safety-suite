from __future__ import annotations
import math
import re
from collections import Counter
from typing import Iterable, List

_WORD = re.compile(r"[a-zA-Z0-9_]+")

def normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))

def tokenize(text: str) -> List[str]:
    return _WORD.findall(text.lower())

def exact_match(pred: str, gold: str) -> float:
    return float(normalize(pred) == normalize(gold)) if gold else 0.0

def token_f1(pred: str, gold: str) -> float:
    if not gold:
        return 0.0
    p = tokenize(pred)
    g = tokenize(gold)
    if not p or not g:
        return 0.0
    pc = Counter(p)
    gc = Counter(g)
    common = sum((pc & gc).values())
    if common == 0:
        return 0.0
    precision = common / len(p)
    recall = common / len(g)
    return 2 * precision * recall / (precision + recall)

def keyword_recall(pred: str, keywords: Iterable[str]) -> float:
    kws = [k.lower() for k in keywords if k]
    if not kws:
        return 1.0
    pred_l = pred.lower()
    return sum(1 for k in kws if k in pred_l) / len(kws)

def groundedness(answer: str, contexts: List[str]) -> float:
    """A lexical groundedness proxy: content words in answer also present in contexts."""
    answer_terms = [t for t in tokenize(answer) if len(t) > 3]
    if not answer_terms:
        return 1.0
    ctx = set(tokenize("\n".join(contexts)))
    supported = sum(1 for t in answer_terms if t in ctx)
    return supported / len(answer_terms)

def citation_coverage(answer: str, contexts: List[str], citations: List[str]) -> float:
    if not contexts:
        return 1.0
    if not citations:
        # If the answer contains bracket-style citations, count them too.
        bracketed = re.findall(r"\[[^\]]+\]", answer)
        citations = bracketed
    return min(1.0, len(citations) / max(1, min(3, len(contexts))))

def mean(values: Iterable[float]) -> float:
    xs = list(values)
    return sum(xs) / len(xs) if xs else 0.0
