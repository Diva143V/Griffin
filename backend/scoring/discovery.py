def discovery_score(evidence: float, novelty: float, impact: float) -> float:
    # Weighted score calculation
    score = (
        evidence * 0.5 +
        novelty * 0.25 +
        impact * 0.25
    )
    return score
