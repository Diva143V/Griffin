import os
from google import genai

def run_peer_review(api_key: str, synthesis_text: str, focus_area: str = "General logic and methodology", model_name: str = "gemini-1.5-pro") -> str:
    """
    Runs a critical appraisal (Devil's Advocate) of the local findings/synthesis.
    """
    if not api_key:
        return "Error: Google API Key is required for Peer Review."
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are a ruthless but fair "Devil's Advocate" Peer Reviewer for Griffin Bio.
Critically appraise the following scientific synthesis report. Your goal is to identify weak assumptions, missing controls, potential biases, and alternative explanations.

FOCUS AREA: {focus_area}

SYNTHESIS REPORT:
{synthesis_text}

Provide a structured, rigorous critique. Do not rewrite the report, but clearly list the methodological flaws, unsupported claims, and recommendations for improvement. Use a professional, academic tone.
"""
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    except Exception as e:
        return f"Error during peer review with Gemini: {str(e)}"
