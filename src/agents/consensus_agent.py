"""Consensus agent to resolve and explain scientific agreements and disagreements."""
from __future__ import annotations

import time
from typing import Any, Dict, List
import ollama


def analyze_consensus(
    query: str,
    sources: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    model_name: str = "gemma3:4b",
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
    system_prompt = "You are a senior Scientific Consensus Analyst. Your job is to analyze retrieved research evidence and connections to determine scientific consensus. Provide a highly detailed, comprehensive, and exhaustive scientific consensus report in markdown format. Be objective, thorough, and direct."
    user_prompt = f"""User Research Query: {query}
 
Retrieved Paper Evidence:
{evidence_str}
 
Relationships Between Papers:
{relations_str}
 
Task:
Write a rigorous scientific consensus assessment report in markdown format. You must cover the following sections in detail:
1. **CONSENSUS STATUS**: Classify the status (Strong Consensus, Moderate Consensus, or Strong Divergence/Conflict). Provide an explicit rationale comparing the clinical quality (levels of evidence) and sample sizes of opposing vs. agreeing papers.
2. **AGREEMENT POINTS & STRENGTH**: Detail the specific biological mechanisms, treatments, or dosages where papers agree. Quantify how many papers support this view (e.g., '3 out of 5 papers observe...').
3. **KEY DISAGREEMENTS & CONTRADICTION ANALYSIS**: Analyze all contradiction pairs. Explain the technical or methodological divergence (e.g., does Paper A study in-vitro tumor cells at high concentrations while Paper B studies clinical outcomes in human populations?). Break down the discrepancies between in-vitro, in-vivo, and retrospective studies.
4. **EVIDENCE MATRIX TABLE**: Create a clean markdown table summarizing:
   | Paper Citation | Study Type / Design | Sample Size | Key Finding | Evidence Strength (high/moderate/low) |
5. **CLINICAL DIRECTIVE / RECOMMENDATION**: Conclude with a definitive scientific summary based on the highest-tier evidence. Highlight missing gaps that require future experimental runs.

Do not make up any information, and ensure all claims are directly linked to the provided paper excerpts."""

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
