"""Bias Detector Agent to flag potential conflicts of interest or publication bias."""
from __future__ import annotations

import time
from typing import Any, Dict
from ..shared.llm import chat as llm_chat
from ..shared.config import MODEL_ROUTING


def detect_bias(
    context: str,
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Scan the context for potential biases and conflicts of interest."""
    start_time = time.time()
    
    model_name = model_name or MODEL_ROUTING.get("bias", "llama3.1:8b")

    prompt = f"""You are a scientific ethics and bias analyst.
Review the following text (which contains abstracts and metadata from scientific papers) and flag any potential biases.

CONTEXT:
{context}

Please provide a "Bias & Conflict of Interest Report" covering:
1. **Funding Sources:** Are corporate funding or pharmaceutical sponsorships mentioned? Do they correlate with positive results?
2. **Publication Bias:** Is there evidence that only positive results are being reported (e.g., lack of negative trials)?
3. **Author Affiliations:** Are there significant industry affiliations?
4. **Tone:** Is the language overly promotional or excessively definitive without enough caveats?
5. **Overall Bias Risk:** Give an overall rating (Low, Medium, High) for the risk of bias across these papers.

Format the output in clean, readable Markdown.
"""

    try:
        response = llm_chat(
            model_name,
            messages=[{"role": "user", "content": prompt}],
            task="bias",
            options=options,
        )
        bias_text = response["message"]["content"]
    except Exception as e:
        bias_text = f"Error generating bias report: {e}"

    duration = time.time() - start_time
    
    return {
        "bias_report": bias_text,
        "execution_time_sec": round(duration, 2)
    }
