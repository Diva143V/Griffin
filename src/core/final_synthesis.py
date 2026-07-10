"""Advanced biomedical research synthesis engine.

This script aggregates extracted claims, ranked papers, and pairwise contradiction
detection results to build a highly structured scientific synthesis report.
It includes weighting consensus by evidence scores and sample sizes, structuring
the final report, and outputting to clean text and markdown files.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Dict, Any, List
import pandas as pd
from ..shared.llm import chat as llm_chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("final_synthesis")

DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_CLAIMS = "dataset/claims.csv"
DEFAULT_RANKED = "dataset/ranked_papers.csv"
DEFAULT_CONTRADICTIONS = "dataset/contradictions.json"
DEFAULT_OUTPUT_TXT = "dataset/final_synthesis.txt"
DEFAULT_OUTPUT_MD = "dataset/final_synthesis.md"


def load_contradictions_summary(path: str) -> str:
    """Load and format contradiction detection results if available."""
    if not os.path.exists(path):
        return "No contradiction detection data available."
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        contradictions = data.get("contradictions", [])
        agreements = data.get("agreements", [])
        partial = data.get("partial_agreements", [])
        
        summary = (
            f"Contradiction Detector Summary:\n"
            f"- Identified {len(contradictions)} direct contradictions.\n"
            f"- Identified {len(agreements)} clean agreements.\n"
            f"- Identified {len(partial)} partial agreements.\n\n"
        )
        
        if contradictions:
            summary += "Key Contradictions Found:\n"
            for idx, c in enumerate(contradictions[:5], 1):
                summary += (
                    f"  {idx}. [{c['claim_a_title'][:50]}] vs [{c['claim_b_title'][:50]}]\n"
                    f"     Explanation: {c['explanation']}\n"
                )
        return summary
    except Exception as exc:
        logger.warning("Failed to parse contradiction JSON: %s", exc)
        return "Failed to parse contradiction data."


def run_synthesis(
    claims_path: str,
    ranked_path: str,
    contradictions_path: str,
    output_txt: str,
    output_md: str,
    model: str,
    topic: str = "the provided research topic",
) -> None:
    logger.info("Loading inputs...")
    
    # 1. Load Claims
    if not os.path.exists(claims_path):
        logger.error("Claims file not found: %s", claims_path)
        return
    claims_df = pd.read_csv(claims_path)
    
    # Extract claim column (support "claim", "claim_output", etc.)
    claim_col = None
    for col in ["claim", "claim_output"]:
        if col in claims_df.columns:
            claim_col = col
            break
    
    if claim_col:
        claims_text = "\n".join(
            f"- {row[claim_col]} (Stance: {row.get('stance', 'neutral')})"
            for _, row in claims_df.dropna(subset=[claim_col]).iterrows()
        )
    else:
        claims_text = "No claims successfully extracted."

    # 2. Load Ranked Papers
    if not os.path.exists(ranked_path):
        logger.error("Ranked papers file not found: %s", ranked_path)
        return
    ranked_df = pd.read_csv(ranked_path)
    
    # Sort and take top 12 papers for richer context
    top_papers = ranked_df.sort_values(by="evidence_score", ascending=False).head(12)
    paper_context = ""
    for i, row in top_papers.iterrows():
        sample_size_str = str(int(row['sample_size'])) if ('sample_size' in row and row['sample_size'] > 0) else "N/A"
        design_str = row.get('study_design', 'Undetermined')
        paper_context += (
            f"Title: {row['title']}\n"
            f"Evidence Score: {row['evidence_score']}/10 | Design: {design_str} | Sample Size: {sample_size_str}\n"
            f"Abstract: {row['abstract']}\n\n"
        )

    # 3. Load Contradictions JSON summary
    contradiction_summary = load_contradictions_summary(contradictions_path)

    # 4. Construct the synthesis prompt
    prompt = f"""You are an elite biomedical research analyst. Synthesize a clinical consensus report on: {topic}.

Below is the aggregated scientific data collected:

### 1. INDIVIDUAL EXTRACTED CLAIMS & STANCES
{claims_text}

### 2. PAIRWISE RELATIONSHIPS & CONTRADICTIONS
{contradiction_summary}

### 3. HIGH-QUALITY EVIDENCE PAPERS (Top 12 sorted by Oxford Evidence Level)
{paper_context}

Please generate a professional, structured synthesis report covering:
1. **Executive Summary**: A concise, 3-sentence summary of the scientific landscape.
2. **Clinical Consensus Analysis**: What does the high-quality evidence (Level 1/2, large sample sizes) consensus say?
3. **Key Disputes & Contradictions**: Highlight the main contradictions, referencing study designs (e.g. meta-analysis vs in vitro cell lines).
4. **Methodological & Population Discrepancies**: Analyze why discrepancies occur (dosage, patient cohorts, in vitro vs. in vivo, retrospective biases).
5. **Quality Assessment & Recommendations**: Future clinical and research recommendation.
6. **Overall Level of Evidence / Confidence**: Rate as High, Medium, or Low with explicit justification.

Return the report in standard Markdown formatting. Do not include introductory conversational text.
"""

    logger.info("Calling Ollama chat API using model '%s'...", model)
    try:
        response = llm_chat(
            model,
            messages=[{"role": "user", "content": prompt}],
            task="synthesis",
        )
        final_answer = response["message"]["content"]
    except Exception as exc:
        logger.error("Failed to generate synthesis with model: %s", exc)
        return

    # Write output files
    os.makedirs(os.path.dirname(output_txt) or ".", exist_ok=True)
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(final_answer)
        
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(final_answer)

    logger.info("Saved plain text report to %s", output_txt)
    logger.info("Saved Markdown report to %s", output_md)

    print("\n" + "=" * 75)
    print("  FINAL BIOMEDICAL SYNTHESIS COMPLETE")
    print("=" * 75)
    print(final_answer[:1000] + "\n... [Truncated for Console View] ...")
    print("=" * 75)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregates and synthesizes biomedical claims and evidence")
    parser.add_argument("--claims", default=DEFAULT_CLAIMS, help="Path to claims CSV")
    parser.add_argument("--ranked", default=DEFAULT_RANKED, help="Path to ranked papers CSV")
    parser.add_argument("--contradictions", default=DEFAULT_CONTRADICTIONS, help="Path to contradictions JSON")
    parser.add_argument("--output-txt", default=DEFAULT_OUTPUT_TXT, help="Path for TXT output")
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD, help="Path for Markdown output")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--topic", default="the provided research topic", help="Research topic for the synthesis")
    args = parser.parse_args()

    run_synthesis(
        claims_path=args.claims,
        ranked_path=args.ranked,
        contradictions_path=args.contradictions,
        output_txt=args.output_txt,
        output_md=args.output_md,
        model=args.model,
        topic=args.topic,
    )


if __name__ == "__main__":
    main()