"""Verifier agent for lightweight consistency checks."""
from __future__ import annotations

from typing import Dict, List


def verify_response(answer: str, sources: List[Dict[str, object]], relations: List[Dict[str, object]]) -> Dict[str, object]:
    answer_text = (answer or "").strip()
    findings: List[str] = []

    if not answer_text:
        findings.append("Answer is empty.")
    if not sources:
        findings.append("No sources were retrieved.")
    if relations and "contradict" not in answer_text.lower() and "conflict" not in answer_text.lower():
        findings.append("Relations exist but the answer does not mention disagreement or contradiction.")

    status = "pass" if not findings else "review"
    return {"status": status, "findings": findings}
