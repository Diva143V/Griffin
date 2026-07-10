"""Methodology Critic Agent to analyze the experimental design."""
from __future__ import annotations

import time
from typing import Any, Dict
from ..shared.llm import chat as llm_chat
from ..shared.config import MODEL_ROUTING


def analyze_methodology(
    context: str,
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Critique the study designs and methodology from the context."""
    start_time = time.time()
    
    model_name = model_name or MODEL_ROUTING.get("methodology", "llama3.1:8b")

    prompt = f"""You are a harsh but fair scientific peer reviewer focusing exclusively on methodology and study design.
Review the following text (which contains abstracts from scientific papers) and provide a critique of the experimental methods.

CONTEXT:
{context}

Please provide a "Methodology Critique" covering:
1. **Model Systems:** What types of models are being used (e.g., in-vitro cell lines, animal models, human cohorts)? Are they appropriate?
2. **Sample Sizes & Power:** Are the studies adequately powered based on the descriptions? 
3. **Control Groups:** Are proper controls (positive, negative, vehicle) mentioned or likely missing?
4. **General Weaknesses:** What are the major methodological limitations across these papers?
5. **Robustness Score:** Give an overall rating (1-10) on the robustness of the methodology across these papers.

Format the output in clean, readable Markdown.
"""

    try:
        response = llm_chat(
            model_name,
            messages=[{"role": "user", "content": prompt}],
            task="methodology",
            options=options,
        )
        methodology_text = response["message"]["content"]
    except Exception as e:
        methodology_text = f"Error generating methodology critique: {e}"

    duration = time.time() - start_time
    
    return {
        "methodology_report": methodology_text,
        "execution_time_sec": round(duration, 2)
    }
