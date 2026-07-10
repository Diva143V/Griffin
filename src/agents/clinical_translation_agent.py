"""Clinical Translation Agent to analyze bench-to-bedside readiness."""
from __future__ import annotations

import time
from typing import Any, Dict
from ..shared.llm import chat as llm_chat
from ..shared.config import MODEL_ROUTING


def analyze_clinical_translation(
    consensus_text: str,
    model_name: str | None = None,
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Evaluate how close the findings are to clinical application."""
    start_time = time.time()
    
    model_name = model_name or MODEL_ROUTING.get("clinical", "llama3.1:8b")

    prompt = f"""You are a clinical translation expert (Translational Medicine Specialist).
Review the following consensus report of recent scientific literature and evaluate how close this research is to human clinical application.

CONSENSUS REPORT:
{consensus_text}

Please provide a "Clinical Readiness Report" covering:
1. **Current Phase:** Where does this research stand? (e.g., Basic Science, Preclinical/Animal, Phase I/II/III trials, or FDA Approved).
2. **Major Hurdles:** What are the biggest barriers preventing this from being used in humans (e.g., toxicity, delivery mechanisms, lack of clinical trials)?
3. **Timeline Estimate:** Given the current state, what is a realistic timeline for clinical use (if applicable)?
4. **Clinical Implications:** If successful, how would this change standard of care?

Format the output in clean, readable Markdown.
"""

    try:
        response = llm_chat(
            model_name,
            messages=[{"role": "user", "content": prompt}],
            task="clinical",
            options=options,
        )
        clinical_text = response["message"]["content"]
    except Exception as e:
        clinical_text = f"Error generating clinical translation report: {e}"

    duration = time.time() - start_time
    
    return {
        "clinical_report": clinical_text,
        "execution_time_sec": round(duration, 2)
    }
