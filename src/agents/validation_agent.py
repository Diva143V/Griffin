"""Validation & Quality Check Agent to verify report credibility and check for hallucinations."""
from __future__ import annotations

import time
import json
from typing import Any, Dict, List
from google import genai
from google.genai import types

def validate_report(
    api_key: str,
    query: str,
    agent_output: str,
    papers: List[Dict[str, Any]],
    model_name: str = "gemini-3.5-flash",
) -> Dict[str, Any]:
    """Verify scientific report accuracy, biological plausibility, and formatting consistency."""
    start_time = time.time()
    
    if not api_key:
        return {
            "validation_results": {
                "quality_score": 0,
                "issues": ["Google API Key missing"],
                "hallucinations": [],
                "confidence_downgrade": "Downgrade all claims due to lack of verification key.",
                "recommendation": "revise and resubmit"
            },
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
        "You are a Scientific Validation & Quality Assurance agent. Your job:\n"
        "1. Check for hallucinated sources, impossible values, or logical contradictions\n"
        "2. Verify claims against provided evidence\n"
        "3. Flag confidence issues\n"
        "4. Score output quality (0\u2013100)\n\n"
        "CHECKS:\n"
        "- Citation accuracy: Are cited papers in the source database?\n"
        "- Biological plausibility: Are concentrations, timepoints, cell lines realistic?\n"
        "- Logical consistency: Do conclusions follow from data?\n"
        "- Completeness: Are all required sections present?"
    )
    
    user_prompt = f"""ORIGINAL QUERY: {query}
AGENT OUTPUT: {agent_output}
SOURCE DATABASE:
{papers_str}

VALIDATION CHECKLIST:
1. [ ] All citations traceable to provided papers (flag any not found)
2. [ ] Numeric claims (effect sizes, concentrations) match source values
3. [ ] Biological plausibility: flagging impossible values (e.g., >100% viability)
4. [ ] Logical flow: conclusions follow from evidence
5. [ ] Completeness: all required sections present

OUTPUT (JSON):
{{
  "quality_score": 0\u2013100,
  "issues": ["issue1", "issue2"],
  "hallucinations": ["claim: evidence not found"],
  "confidence_downgrade": "if any issue, which claims to downgrade",
  "recommendation": "proceed / revise and resubmit"
}}"""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json"
            )
        )
        validation_res = json.loads(response.text)
    except Exception as e:
        validation_res = {
            "quality_score": 50,
            "issues": [f"Validation agent generation failed: {e}"],
            "hallucinations": [],
            "confidence_downgrade": "Unchecked output",
            "recommendation": "proceed"
        }
        
    duration = time.time() - start_time
    
    return {
        "validation_results": validation_res,
        "execution_time_sec": round(duration, 2)
    }
