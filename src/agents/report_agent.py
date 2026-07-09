import os
from google import genai

def generate_overseer_report(api_key: str, consensus_report: str, eln_logs: str, custom_instructions: str = "", model_name: str = "gemini-1.5-pro") -> str:
    """
    Generates a comprehensive Overseer Report using Gemini, synthesizing local findings 
    with live web-grounded research (if grounding is supported/enabled).
    """
    if not api_key:
        return "Error: Google API Key is required to generate the Overseer Report."
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are the Grounded Overseer Agent for Griffin Bio.
Synthesize the following local findings into a comprehensive Executive Overseer Report.

[CONSENSUS FINDINGS]
{consensus_report}

[LAB/ELN LOGS]
{eln_logs}

[CUSTOM INSTRUCTIONS]
{custom_instructions if custom_instructions else "None"}

Please output a well-structured markdown report."""
        
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    except Exception as e:
        return f"Error synthesizing report: {str(e)}"
