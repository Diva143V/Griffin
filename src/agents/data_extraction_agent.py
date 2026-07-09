"""Scientific Data Extraction & Standardization Agent."""
from __future__ import annotations

import time
import json
from google import genai
from google.genai import types

def extract_paper_data(
    api_key: str,
    paper_text: str,
    model_name: str = "gemini-3.5-flash",
) -> dict:
    """Extract key clinical trial metadata and results from a paper in JSON format."""
    start_time = time.time()
    
    if not api_key:
        return {
            "extracted_data": {
                "title": "Error: Google API Key is required",
                "year": 0,
                "authors": [],
                "study_type": "Undetermined",
                "sample_size": 0,
                "population": "",
                "intervention": "",
                "primary_outcome": "",
                "effect_size": "",
                "confidence_interval": "",
                "p_value": "",
                "limitations": [],
                "conflicts_of_interest": "",
                "funding_source": ""
            },
            "execution_time_sec": 0.0
        }
        
    client = genai.Client(api_key=api_key)
    
    system_prompt = (
        "You are a Scientific Data Extraction specialist. Your job is to extract "
        "structured data from research papers in a standardized format (JSON)."
    )
    
    user_prompt = f"""PAPER: {paper_text}

EXTRACT (JSON only, no commentary):
{{
  "title": "",
  "year": 0,
  "authors": [],
  "study_type": "RCT / Cohort / Case Report / In-vitro / Animal",
  "sample_size": 0,
  "population": "",
  "intervention": "",
  "primary_outcome": "",
  "effect_size": "",
  "confidence_interval": "",
  "p_value": "",
  "limitations": [],
  "conflicts_of_interest": "",
  "funding_source": ""
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
        extracted = json.loads(response.text)
    except Exception as e:
        extracted = {
            "title": f"Failed extraction: {e}",
            "year": 0,
            "authors": [],
            "study_type": "Undetermined",
            "sample_size": 0,
            "population": "",
            "intervention": "",
            "primary_outcome": "",
            "effect_size": "",
            "confidence_interval": "",
            "p_value": "",
            "limitations": [],
            "conflicts_of_interest": "",
            "funding_source": ""
        }
        
    duration = time.time() - start_time
    
    return {
        "extracted_data": extracted,
        "execution_time_sec": round(duration, 2)
    }
