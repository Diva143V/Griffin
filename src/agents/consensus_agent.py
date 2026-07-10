"""Consensus agent to resolve and explain scientific agreements and disagreements."""
from __future__ import annotations

import time
from typing import Any, Dict, List
import ollama

from ..shared.config import MODEL_ROUTING


def analyze_consensus(
    query: str,
    sources: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Analyze the retrieved evidence and relations to find scientific consensus or divergence."""
    start_time = time.time()
    
    # 1. Format references, evidence and relationships
    evidence_desc = []
    for s in sources:
        design = s.get("study_design", s.get("design", "Undetermined"))
        score = s.get("evidence_score", 5.0)
        sample = s.get("sample_size", "N/A")
        evidence_desc.append(
            f"- Paper: '{s.get('title')}'\n"
            f"  Evidence Quality: {score}/10 | Design: {design} | Sample Size: {sample}\n"
            f"  Abstract Excerpt: {s.get('abstract', '')[:300]}..."
        )
        
    relations_desc = []
    for r in relations:
        relations_desc.append(
            f"- Connection type: {r.get('type')}\n"
            f"  Paper A: '{r.get('claim_a_title')}' (Claim: {r.get('claim_a_text')})\n"
            f"  Paper B: '{r.get('claim_b_title')}' (Claim: {r.get('claim_b_text')})\n"
            f"  Explanation: {r.get('explanation')}"
        )
        
    evidence_str = "\n\n".join(evidence_desc) if evidence_desc else "None"
    relations_str = "\n\n".join(relations_desc) if relations_desc else "None"

    # 2. Build Prompt
    model_name = model_name or MODEL_ROUTING.get("consensus_analyst", "llama3.1:8b")

    system_prompt = (
        "You are a Senior Scientific Consensus Analyst. Your mandate:\n"
        "1. Synthesize multi-paper evidence into a rigorous consensus statement\n"
        "2. Quantify agreement/disagreement with explicit counts and percentages\n"
        "3. Classify disagreements by root cause: methodology, population, dose, study phase (in-vitro vs clinical)\n"
        "4. Assign confidence scores to every consensus claim (LOW/MEDIUM/HIGH)\n"
        "5. Output ONLY markdown; no preamble or meta-commentary\n\n"
        "DEPTH REQUIREMENTS:\n"
        "- CONSENSUS STATUS: Minimum 3 sentences justifying classification\n"
        "- AGREEMENT POINTS: For each point, state \u22653 papers and cite effect sizes (e.g., \"median 34% reduction\")\n"
        "- KEY DISAGREEMENTS: For each contradiction, provide 2-3 mechanistic explanations\n"
        "- EVIDENCE MATRIX: Include Publication Year, Sample Size, Study Phase (in-vitro/animal/clinical), Funding Source"
    )
    user_prompt = f"""QUERY: {query}
PAPERS: {evidence_str}
CONTRADICTIONS: {relations_str}

TASK: Write a rigorous consensus report with these mandatory sections:

## 1. CONSENSUS STATUS
Classify as: Strong Consensus (\u226575% papers agree) | Moderate Consensus (50-74%) | Weak/Conflicted (<50%)
- Report vote count explicitly: "7/10 papers show..." OR "findings are split: 5 pro, 4 con, 1 neutral"
- For each side, list 2 representative papers with effect sizes
- Assign confidence: [LOW | MEDIUM | HIGH] based on sample size and study quality

## 2. AGREEMENT DETAILS
List specific findings where papers agree:
- Biological mechanism: [Description]. Supporting papers: [X, Y, Z]
- Dosage/concentration: [Range]. Effect size: [median % change]. Papers: [List]
- Clinical context: [Population/condition]. Papers: [List]

## 3. CONTRADICTION ANALYSIS
For EACH conflicting paper pair:
| Paper A | Paper B | Root Cause | Mechanistic Explanation |
|---------|---------|-----------|------------------------|
| [Cite A] | [Cite B] | Methodology / Population / Dose | Explanation here |

## 4. EVIDENCE MATRIX TABLE
| Citation | Year | Design | n | Phase | Key Finding | Effect Size | Quality |
|----------|------|--------|---|-------|-------------|-------------|---------|
| [Paper] | [YYYY] | RCT/Cohort/In-vitro | [N] | Clinical/Animal | Finding | [+X% or effect size] | [HIGH/MED/LOW] |

## 5. CLINICAL RECOMMENDATION
**Consensus Statement**: [1-2 sentence definitive conclusion based on highest-tier evidence]
**Confidence**: [HIGH/MEDIUM/LOW]
**Critical Gaps**: List 2-3 future experiments needed to resolve remaining uncertainty

---

OUTPUT RULES:
- Do NOT exceed 3000 tokens
- If papers conflict fundamentally: Use subheadings (### Subgroup Analysis) to separate findings
- If <5 papers: Flag as "Limited Evidence Base"
- Cite papers ONLY by their identifiers; do NOT quote verbatim"""

    # 3. Call LLM
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options=options
        )
        consensus_text = response["message"]["content"]
    except Exception as e:
        consensus_text = f"Error calling Consensus Agent: {e}"

    duration = time.time() - start_time
    
    # 4. Formulate Result
    # Multidimensional confidence estimator
    if sources:
        # Calculate base evidence score average
        avg_score = sum(float(s.get("evidence_score", 5.0)) for s in sources) / len(sources)
        
        # Count randomized trials
        rct_count = sum(1 for s in sources if any(term in str(s.get("study_design", "")).lower() for term in ["random", "rct"]))
        
        # Count contradictions
        contradiction_count = sum(1 for r in relations if str(r.get("type", "")).lower() == "contradicts")
        
        # Multidimensional confidence score calculation
        score_component = avg_score
        rct_bonus = min(rct_count * 1.0, 2.0)  # Up to +2 bonus for multiple RCTs
        contradiction_penalty = min(contradiction_count * 1.5, 3.0)  # Up to -3 penalty for contradictions
        
        final_confidence_metric = score_component + rct_bonus - contradiction_penalty
        
        if final_confidence_metric >= 7.5:
            confidence = "High Confidence (Consistent High-Quality Evidence)"
        elif final_confidence_metric >= 5.0:
            if contradiction_count > 0:
                confidence = "Moderate Confidence (Evidence Present but Conflicting)"
            else:
                confidence = "Moderate Confidence (Consistent Mid-Quality Evidence)"
        else:
            if contradiction_count > 1:
                confidence = "Low Confidence (High Contradiction Rate / Divergent Evidence)"
            else:
                confidence = "Low Confidence (Limited/Low-Quality Evidence)"
    else:
        confidence = "Insufficient Evidence"

    return {
        "consensus_report": consensus_text,
        "confidence_level": confidence,
        "execution_time_sec": round(duration, 2)
    }
