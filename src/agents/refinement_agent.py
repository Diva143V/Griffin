import os
from google import genai

def refine_report_section(api_key: str, original_text: str, instructions: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Allows iterative refinement of specific report sections based on natural language instructions.
    """
    if not api_key:
        return "Error: Google API Key is required for refinement."
        
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""You are an expert scientific editor.
Refine and update the following text exactly according to the user's instructions.

ORIGINAL TEXT:
{original_text}

REFINEMENT INSTRUCTIONS:
{instructions}

Return the complete, refined text."""
        
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    except Exception as e:
        return f"Error refining text: {str(e)}"
