"""Contradiction agent facade."""
from __future__ import annotations

from ..core.contradiction_detector import (
    ContradictionReport,
    ClaimPairResult,
    apply_evidence_weights,
    build_report,
    load_and_embed_claims,
    load_evidence_scores,
    run_detector,
    run_pairwise_analysis,
    run_synthesis,
    select_pairs,
)

__all__ = [
    "ContradictionReport",
    "ClaimPairResult",
    "apply_evidence_weights",
    "build_report",
    "load_and_embed_claims",
    "load_evidence_scores",
    "run_detector",
    "run_pairwise_analysis",
    "run_synthesis",
    "select_pairs",
]
