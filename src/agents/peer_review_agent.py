"""Peer Review / Devil's Advocate Agent to critically appraise scientific claims and hypotheses."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from google import genai
from google.genai import types

def review_findings(
    api_key: str,
    query: str,
    findings: str,
    papers: List[Dict[str, Any]],
    model_name: str = "gemini-3.5-flash",
) -> dict:
    """Critically appraise scientific claims, identify study weaknesses, and outline confounding factors."""
    start_time = time.time()
    
    if not api_key:
        return {
            "peer_review": "Error: Google API Key is required to run the Peer Review Agent.",
            "execution_time_sec": 0.0
        }
        
    client = genai.Client(api_key=api_key)
    
    # Format papers list for prompt context
    papers_desc = []
    for idx, p in enumerate(papers, 1):
        papers_desc.append(
            f"Paper [{idx}]:\n"
            f"Title: {p.get('title')}\n"
            f"Abstract: {p.get('abstract', '')}"
        )
    papers_str = "\n\n".join(papers_desc) if papers_desc else "None"
    
    system_prompt = (
        "You are a Peer Reviewer / Devil's Advocate. Your job is to critically appraise "
        "scientific findings, identify methodological weaknesses, and propose alternative interpretations."
    )
    
    user_prompt = f"""RESEARCH QUESTION: {query}
PROPOSED FINDINGS: {findings}
EVIDENCE BASE:
{papers_str}

CRITICAL APPRAISAL:
1. **Methodological Limitations**: What study design weaknesses exist?
2. **Confounding Factors**: What unmeasured variables could explain findings?
3. **Alternative Interpretations**: What other mechanisms could explain the data?
4. **Publication Bias**: Are negative studies missing?
5. **Sample Size & Generalizability**: Can we trust these findings in other populations?

OUTPUT: Structured critique identifying 3–5 major weaknesses and alternative hypotheses."""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        critique = response.text
    except Exception as e:
        critique = f"Error during peer review: {e}"
        
    duration = time.time() - start_time
    
    return {
        "peer_review": critique,
        "execution_time_sec": round(duration, 2)
    }
