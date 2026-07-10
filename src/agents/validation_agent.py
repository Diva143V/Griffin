import os
import json
from google import genai

def run_qa_audit(api_key: str, report_text: str, model_name: str = "gemini-2.5-flash") -> dict:
    """
    Acts as a Hallucination QA Auditor to output a credibility score (0-100) 
    and highlight logical inconsistencies or untraceable citations.
    """
    if not api_key:
        return {"score": 0, "feedback": "Error: Google API Key is required for QA Audit.", "issues": []}
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are the Griffin Bio Validation QA Auditor.
Review the following scientific report for logical inconsistencies, hallucinations, and untraceable citations.

REPORT TEXT:
{report_text}

Analyze the text and provide your output strictly as a JSON object with the following schema:
{{
    "score": <int 0-100 representing credibility/reliability>,
    "feedback": "<string summarizing overall quality>",
    "issues": ["<string issue 1>", "<string issue 2>"]
}}
"""
        response = client.models.generate_content(model=model_name, contents=prompt)
        
        # Parse JSON output
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"score": 0, "feedback": "Failed to parse validation JSON.", "issues": [result_text]}
            
    except Exception as e:
        return {"score": 0, "feedback": f"Error running validation with Gemini: {str(e)}", "issues": []}
