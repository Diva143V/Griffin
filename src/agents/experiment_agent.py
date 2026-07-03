"""Experiment Planning agent to design laboratory protocols and controls from literature synthesis."""
from __future__ import annotations

import time
from typing import Any, Dict, List
import ollama


def design_protocol(
    query: str,
    synthesis_report: str,
    model_name: str = "gemma3:4b"
) -> Dict[str, Any]:
    """Design a step-by-step laboratory protocol with negative/positive controls based on findings."""
    start_time = time.time()

    system_prompt = "You are an expert Laboratory Protocol Planner. Your goal is to translate scientific findings into a concrete, reproducible laboratory experiment protocol. Write your response in clean markdown format, being practical and scientifically rigorous."
    user_prompt = f"""Research Query: {query}
Scientific Synthesis:
{synthesis_report}

Task:
Please design a structured laboratory experiment protocol. Include:
1. EXPERIMENTAL HYPOTHESIS: What is the primary hypothesis being tested?
2. MATERIALS & REAGENTS: List the primary cell lines, drugs, assay kits, and tools needed.
3. STEP-BY-STEP PROCEDURE: Write a detailed, numbered laboratory protocol for treating cells and measuring outcomes.
4. CONTROLS:
   - Negative Control (e.g., untreated cells or DMSO/vehicle control).
   - Positive Control (e.g., known chemotherapy agent or apoptosis inducer).
5. SAFETY & PRECAUTIONS: Describe any chemical/biological safety precautions."""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        protocol_text = response["message"]["content"]
    except Exception as e:
        protocol_text = f"Error calling Experiment Agent: {e}"

    duration = time.time() - start_time
    
    return {
        "protocol_draft": protocol_text,
        "execution_time_sec": round(duration, 2)
    }
