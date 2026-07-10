"""Glossary Agent to define complex scientific terminology."""
from __future__ import annotations

import time
from typing import Any, Dict
from ..shared.llm import chat as llm_chat
from ..shared.config import MODEL_ROUTING


def generate_glossary(
    context: str,
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Extract complex terms from the context and generate a glossary."""
    start_time = time.time()
    
    model_name = model_name or MODEL_ROUTING.get("glossary", "llama3.1:8b")

    prompt = f"""You are a scientific glossary generator.
Review the following text (which contains abstracts from scientific papers) and identify the 10-15 most complex, domain-specific, or difficult scientific terms, acronyms, or concepts.

CONTEXT:
{context[:6000]}  # limit context to save tokens

For each term you identify, provide a clear, concise definition (1-2 sentences) that a layperson can understand.
Format the output as a Markdown table with two columns: "Term" and "Definition".
Do not include any introductory or concluding text outside the table.
"""

    try:
        response = llm_chat(
            model_name,
            messages=[{"role": "user", "content": prompt}],
            task="glossary",
            options=options,
        )
        glossary_text = response["message"]["content"]
    except Exception as e:
        glossary_text = f"Error generating glossary: {e}"

    duration = time.time() - start_time
    
    return {
        "glossary_report": glossary_text,
        "execution_time_sec": round(duration, 2)
    }
