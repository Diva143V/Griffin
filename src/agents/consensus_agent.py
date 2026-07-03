"""Consensus agent to resolve and explain scientific agreements and disagreements."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple
import ollama


def analyze_consensus(
    query: str,
    sources: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    model_name: str = "gemma3:4b"
) -> Dict[str, Any]:
    """Analyze the retrieved evidence and relations to find scientific consensus or divergence."""
    start_time = time.time()
    
    # 1. Format references, evidence and relationships
    evidence_desc = []
    for s in sources:
        design = s.get("design", "Undetermined")
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
Write a scientific consensus assessment report. Include:
1. CONSENSUS STATUS: State whether there is strong consensus, moderate consensus, or strong divergence in the literature.
2. AGREEMENT POINTS: What do the papers agree on? (Elaborate in detail)
3. KEY DISAGREEMENTS / DIVERGENCE: What are the main contradictions or differences in findings, and WHY do they occur (e.g., cell studies vs. human trials, sample size differences)?
4. CLINICAL RECOMMENDATION / CONCLUSION: Based on the highest-quality evidence (higher evidence scores), what is the current scientific consensus recommendation?

Do not make up any information."""

    # 3. Call LLM
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        consensus_text = response["message"]["content"]
    except Exception as e:
        consensus_text = f"Error calling Consensus Agent: {e}"

    duration = time.time() - start_time
    
    # 4. Formulate Result
    # Simple rule-based confidence estimator based on evidence scores of sources
    if sources:
        avg_score = sum(float(s.get("evidence_score", 5.0)) for s in sources) / len(sources)
        if avg_score >= 8.0:
            confidence = "High Confidence"
        elif avg_score >= 5.0:
            confidence = "Moderate Confidence"
        else:
            confidence = "Low Confidence"
    else:
        confidence = "Insufficient Evidence"

    return {
        "consensus_report": consensus_text,
        "confidence_level": confidence,
        "execution_time_sec": round(duration, 2)
    }
