"""Evidence ranker agent facade with DataFrame ranking helper."""
from __future__ import annotations

from typing import Tuple

import pandas as pd

from ..core.evidence_ranker import classify_and_score, extract_sample_size


def rank_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Classifies study design, extracts sample sizes, and scores rows in a Pandas DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["study_design", "base_score", "sample_size", "evidence_score"])
        
    study_designs = []
    base_scores = []
    sample_sizes = []
    final_scores = []

    for _, row in df.iterrows():
        title = str(row.get("title", "") or "").strip()
        abstract = str(row.get("abstract", "") or "").strip()
        
        try:
            base, label, n_size, score = classify_and_score(title, abstract)
        except Exception:
            # Safety fallback values
            base, label, n_size, score = 5.0, "Undetermined", -1, 5.0
            
        base_scores.append(base)
        study_designs.append(label)
        sample_sizes.append(n_size if (n_size is not None and isinstance(n_size, (int, float))) else -1)
        final_scores.append(score)

    ranked = df.copy()
    ranked["study_design"] = study_designs
    ranked["base_score"] = base_scores
    ranked["sample_size"] = sample_sizes
    ranked["evidence_score"] = final_scores
    return ranked


__all__ = ["classify_and_score", "extract_sample_size", "rank_dataframe"]
