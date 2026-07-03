"""Advanced evidence ranking pipeline for biomedical papers.

This script processes cleaned research papers and ranks them according to a
rigorous hierarchy of clinical evidence (adapted from Oxford Centre for Evidence-Based Medicine).
It integrates regular expression patterns, trial phase extraction, study design classification,
sample size estimation, and produces detailed scoring and reports.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, Any, Tuple
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("evidence_ranker")

# ---------------------------------------------------------------------------
# Constants & Evidence Hierarchy Definitions
# ---------------------------------------------------------------------------
# Oxford Centre for Evidence-Based Medicine (CEBM) Levels:
# Level 1: Systematic reviews, Meta-analyses, Randomized Controlled Trials (RCTs)
# Level 2: Cohort studies, Prospective studies, low-quality RCTs
# Level 3: Case-control studies, Retrospective cohort studies
# Level 4: Case series, Case reports, Cross-sectional studies
# Level 5: In vitro (cell lines) / In vivo (animal models) / Expert opinion / Review papers

STUDY_TYPES = {
    "LEVEL_1_META": {
        "label": "Systematic Review / Meta-Analysis",
        "base_score": 10.0,
        "patterns": [
            r"systematic\s+review",
            r"meta[- ]analys(is|es)",
            r"pooled\s+analysis",
        ],
    },
    "LEVEL_1_RCT": {
        "label": "Randomized Controlled Trial (Phase III/IV)",
        "base_score": 9.0,
        "patterns": [
            r"randomi[zs]ed\s+controlled\s+trial",
            r"randomi[zs]ed\s+clinical\s+trial",
            r"\brct\b",
            r"double[- ]blind",
            r"placebo[- ]controlled",
            r"phase\s+3\b",
            r"phase\s+iii\b",
            r"phase\s+4\b",
            r"phase\s+iv\b",
        ],
    },
    "LEVEL_2_CLINICAL_TRIAL": {
        "label": "Clinical Trial (Phase I/II) / Prospective Cohort",
        "base_score": 8.0,
        "patterns": [
            r"clinical\s+trial",
            r"phase\s+1\b",
            r"phase\s+i\b",
            r"phase\s+2\b",
            r"phase\s+ii\b",
            r"prospective\s+cohort",
            r"prospective\s+study",
            r"longitudinal\s+study",
        ],
    },
    "LEVEL_3_RETROSPECTIVE": {
        "label": "Retrospective Cohort / Case-Control",
        "base_score": 6.5,
        "patterns": [
            r"cohort\s+study",
            r"cohort\s+analysis",
            r"retrospective\s+cohort",
            r"retrospective\s+study",
            r"case[- ]control",
            r"observational\s+study",
        ],
    },
    "LEVEL_4_DESCRIPTIVE": {
        "label": "Cross-Sectional Study / Case Series",
        "base_score": 5.0,
        "patterns": [
            r"cross[- ]sectional",
            r"case\s+series",
            r"survey",
            r"epidemiologic(al)?\s+study",
        ],
    },
    "LEVEL_5_CASE_REPORT": {
        "label": "Case Report / Case Study",
        "base_score": 3.0,
        "patterns": [
            r"case\s+report",
            r"case\s+study",
            r"single\s+case",
        ],
    },
    "LEVEL_5_REVIEW": {
        "label": "Narrative Review / Editorial / Commentary",
        "base_score": 4.0,
        "patterns": [
            r"\breview\b",
            r"editorial",
            r"commentary",
            r"perspective",
        ],
    },
    "LEVEL_5_PRECLINICAL": {
        "label": "Preclinical Study (In Vitro / In Vivo Animal)",
        "base_score": 2.0,
        "patterns": [
            r"in\s+vitro",
            r"cell\s+line",
            r"xenograft",
            r"mouse\s+model",
            r"murine",
            r"in\s+vivo",
            r"\brat\b",
            r"\brats\b",
            r"\bmice\b",
            r"animal\s+model",
        ],
    },
}


# ---------------------------------------------------------------------------
# Advanced Extractors & Scoring Logics
# ---------------------------------------------------------------------------

def extract_sample_size(text: str) -> int | None:
    """Attempt to extract sample size (number of patients/participants/subjects) from text.

    Examples matched:
        - "n = 154"
        - "1,245 patients"
        - "cohort of 300 women"
    """
    text_lower = text.lower()
    
    # 1. Look for explicit sample size notations like n = 123
    n_matches = re.findall(r"\bn\s*=\s*([0-9,]+)\b", text_lower)
    if n_matches:
        try:
            return int(n_matches[0].replace(",", ""))
        except ValueError:
            pass

    # 2. Look for patterns like "1,234 patients" or "300 participants"
    patient_patterns = [
        r"([0-9,]+)\s+(?:patients|subjects|participants|women|enrolled|cases|participants|individuals)\b"
    ]
    for pattern in patient_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            try:
                # Get the largest sample size candidate to be safe or use first
                val = int(matches[0].replace(",", ""))
                if 5 <= val <= 10_000_000:  # Ignore extreme small/large anomalies
                    return val
            except ValueError:
                pass
                
    return None


def classify_and_score(title: str, abstract: str) -> Tuple[float, str, int | None, float]:
    """Classify the paper study design and compute a nuanced evidence score.

    Returns:
        Tuple of (base_score, study_type_label, sample_size, final_score)
    """
    combined = (str(title) + " " + str(abstract)).lower()
    
    matched_type = "UNKNOWN"
    matched_label = "Undetermined / Default"
    base_score = 4.0  # default score for basic biomedical papers
    
    # Evaluate study types from strongest (Level 1) to weakest (Level 5)
    for study_key, config in STUDY_TYPES.items():
        matched = False
        for pattern in config["patterns"]:
            if re.search(pattern, combined):
                matched = True
                break
        if matched:
            matched_type = study_key
            matched_label = config["label"]
            base_score = config["base_score"]
            break  # Stop at the highest evidence class matching

    # Extract sample size and calculate bonus/penalty adjustments
    sample_size = extract_sample_size(combined)
    final_score = base_score
    
    if sample_size:
        # Scale score slightly based on log of sample size for human studies
        if matched_type not in ["LEVEL_5_PRECLINICAL", "LEVEL_5_REVIEW"]:
            if sample_size > 1000:
                final_score += 1.0  # Large scale study bonus
            elif sample_size > 100:
                final_score += 0.5
            elif sample_size < 20:
                final_score -= 1.0  # Very small human study penalty
    else:
        # Slight penalty for human studies where sample size is not stated
        if matched_type in ["LEVEL_1_RCT", "LEVEL_2_CLINICAL_TRIAL", "LEVEL_3_RETROSPECTIVE"]:
            final_score -= 0.5

    # Clamp the final evidence score between 1.0 and 10.0
    final_score = max(1.0, min(10.0, round(final_score, 2)))
    return base_score, matched_label, sample_size, final_score


# ---------------------------------------------------------------------------
# Run Pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    input_file = "dataset/clean_papers.csv"
    output_file = "dataset/ranked_papers.csv"

    if not os.path.exists(input_file):
        logger.error("Input file not found: %s. Run clean_dataset.py first.", input_file)
        return

    logger.info("Loading cleaned papers from %s...", input_file)
    df = pd.read_csv(input_file)
    total_papers = len(df)
    logger.info("Loaded %d papers for evidence ranking.", total_papers)

    # Initialize lists to hold extracted features and scores
    study_designs = []
    base_scores = []
    sample_sizes = []
    final_scores = []

    for idx, row in df.iterrows():
        title = str(row.get("title", ""))
        abstract = str(row.get("abstract", ""))
        
        base, label, n_size, score = classify_and_score(title, abstract)
        
        base_scores.append(base)
        study_designs.append(label)
        sample_sizes.append(n_size if n_size is not None else -1) # Use -1 for missing sample size
        final_scores.append(score)

    # Attach results to the dataframe
    df["study_design"] = study_designs
    df["base_score"] = base_scores
    df["sample_size"] = sample_sizes
    df["evidence_score"] = final_scores

    # Save to output file
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    df.to_csv(output_file, index=False)
    logger.info("Saved ranked papers with metadata to %s.", output_file)

    # Display Top Ranked Studies
    print("\n" + "=" * 75)
    print("  TOP RANKED PAPERS BY EVIDENCE STRENGTH")
    print("=" * 75)
    
    top_df = df.sort_values(by="evidence_score", ascending=False).head(10)
    for idx, (_, row) in enumerate(top_df.iterrows(), 1):
        n_str = str(int(row['sample_size'])) if row['sample_size'] > 0 else "N/A"
        print(f"{idx}. [{row['evidence_score']}/10] - {row['study_design']} (Sample Size: {n_str})")
        print(f"   Title: {row['title'][:110]}...")
        print(f"   Source: {row.get('source', 'Unknown')} | Year: {row.get('year', 'N/A')}\n")
    print("=" * 75)


if __name__ == "__main__":
    main()