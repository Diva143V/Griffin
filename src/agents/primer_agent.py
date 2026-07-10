"""Layperson Primer Agent to explain the query in simple terms."""
from __future__ import annotations

import time
from typing import Any, Dict
from ..shared.llm import chat as llm_chat
from ..shared.config import MODEL_ROUTING


def generate_primer(
    query: str,
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Generate a beginner-friendly explanation of the scientific query."""
    start_time = time.time()
    
    model_name = model_name or MODEL_ROUTING.get("primer", "llama3.1:8b")

    prompt = f"""You are an expert science communicator and educator. 
Your task is to explain the following scientific research question to a beginner (someone with a high-school level understanding of science).

RESEARCH QUESTION:
{query}

Please provide a "Beginner's Guide" that covers:
1. **The Core Question:** What is this research actually asking in simple terms?
2. **Background Context:** Why does this matter? What is the disease, biological process, or mechanism involved?
3. **Key Concepts:** Briefly introduce the main actors (genes, drugs, diseases) involved in this query.
4. **The Goal:** What would finding an answer to this query help achieve?

Keep the tone encouraging, accessible, and free of overly dense jargon. Use analogies if helpful.
Format the output in clean, readable Markdown.
"""

    try:
        response = llm_chat(
            model_name,
            messages=[{"role": "user", "content": prompt}],
            task="primer",
            options=options,
        )
        primer_text = response["message"]["content"]
    except Exception as e:
        primer_text = f"Error generating primer: {e}"

    duration = time.time() - start_time
    
    return {
        "primer_report": primer_text,
        "execution_time_sec": round(duration, 2)
    }
