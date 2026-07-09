"""Refinement & Iteration Loop Agent to update and iterate on report content based on feedback."""
from __future__ import annotations

import time
from google import genai
from google.genai import types

def refine_report(
    api_key: str,
    original_report: str,
    feedback: str,
    examples: str = "",
    model_name: str = "gemini-3.5-flash",
) -> dict:
    """Iteratively refine the research report using targeted feedback."""
    start_time = time.time()
    
    if not api_key:
        return {
            "refined_report": "Error: Google API Key is required to run the Refinement Agent.",
            "execution_time_sec": 0.0
        }
        
    client = genai.Client(api_key=api_key)
    
    system_prompt = (
        "You are a Refinement Agent. Your job is to take user feedback and "
        "iteratively improve prior agent outputs WITHOUT regenerating the entire report from scratch."
    )
    
    user_prompt = f"""ORIGINAL REPORT: {original_report}
USER FEEDBACK: {feedback}
EXAMPLES: {examples or 'None provided'}

TASK:
1. Identify which section(s) need revision
2. Rewrite only those sections (preserve others exactly)
3. Output ONLY the revised report (same structure as original)
4. Highlight changes with [REVISED] markers

USER FEEDBACK TYPES:
- "Add more detail on [topic]"
- "Disagree with [claim]; evidence suggests [alternative]"
- "Too technical; simplify [section]"
- "Missing discussion of [topic]"
"""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        refined_text = response.text
    except Exception as e:
        refined_text = f"Error during report refinement: {e}"
        
    duration = time.time() - start_time
    
    return {
        "refined_report": refined_text,
        "execution_time_sec": round(duration, 2)
    }
