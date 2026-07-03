"""Evidence ranker agent facade with DataFrame ranking helper."""
from __future__ import annotations

from typing import Tuple

import pandas as pd

from ..core.evidence_ranker import classify_and_score, extract_sample_size


def rank_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    study_designs = []
    base_scores = []
    sample_sizes = []
    final_scores = []

    for _, row in df.iterrows():
        title = str(row.get("title", ""))
        abstract = str(row.get("abstract", ""))
        base, label, n_size, score = classify_and_score(title, abstract)
        base_scores.append(base)
        study_designs.append(label)
        sample_sizes.append(n_size if n_size is not None else -1)
        final_scores.append(score)

    ranked = df.copy()
    ranked["study_design"] = study_designs
    ranked["base_score"] = base_scores
    ranked["sample_size"] = sample_sizes
    ranked["evidence_score"] = final_scores
    return ranked


__all__ = ["classify_and_score", "extract_sample_size", "rank_dataframe"]
