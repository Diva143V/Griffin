"""Electronic Lab Notebook (ELN) agent to format and log laboratory records."""
from __future__ import annotations

import time
import random
from typing import Any, Dict
import ollama


def format_eln_entry(
    researcher_name: str,
    project_name: str,
    protocol_draft: str,
    user_notes: str = "",
    model_name: str = "gemma3:4b",
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Format and log an Electronic Lab Notebook entry matching the experimental protocol."""
    start_time = time.time()
    date_str = time.strftime("%Y-%m-%d %H:%M:%S")
    date_code = time.strftime("%Y%m%d")
    
    # Generate a unique Experiment ID
    exp_num = random.randint(100, 999)
    experiment_id = f"EXP-{date_code}-{exp_num}"

    prompt = f"""You are an Electronic Lab Notebook (ELN) Assistant. Your task is to format a formal ELN entry.

Project: {project_name}
Experiment ID: {experiment_id}
Researcher: {researcher_name}
Date/Time: {date_str}
Protocol Draft:
{protocol_draft}
Researcher Notes/Inputs:
{user_notes}

Task:
Generate a professional, structured ELN record in clean markdown. You must cover the following details:
1. **HEADER METADATA**: Standard notebook header listing Project Name, Lead Researcher Author, Entry Creation Date/Time, and Experiment ID ({experiment_id}).
2. **EXPERIMENTAL OBJECTIVE**: A concise summary describing the scientific purpose, therapeutic target, or pathway of interest.
3. **METHODOLOGICAL MATRIX**: Key parameters, including active cell lines, incubation temperatures (e.g. 37°C), media types, drug dosages (e.g. in uM), and treatment durations (e.g. 24h, 48h).
4. **MOCK OBSERVATIONS LOG**: Create a structured markdown table with standard tracking columns:
   | Day / Timepoint | Sample Group | Absorbance / Readout | Estimated Cell Viability (%) | Morphology Observations | Operator Initials |
   Populate this table with realistic, logical mock data representing negative control, positive control, and treatment test runs.
5. **CRITICAL ANALYSIS & NEXT STEPS**: Outline check points, standard deviations expected, statistical tests to run (e.g. ANOVA), and a validation checklist.
6. **SIGNATURE BLOCK**: A formal sign-off section with fields for:
   - "Recorded by [Researcher Name] on [Date]"
   - "Reviewed and Verified by [Witness Name] on [Date]"

Ensure the output is fully structured in clean markdown and behaves like a real certified laboratory log page.
"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options=options
        )
        eln_text = response["message"]["content"]
    except Exception as e:
        eln_text = f"Error calling ELN Agent: {e}"

    duration = time.time() - start_time
    
    return {
        "eln_entry": eln_text,
        "entry_metadata": {
            "author": researcher_name,
            "project": project_name,
            "timestamp": date_str,
            "experiment_id": experiment_id
        },
        "execution_time_sec": round(duration, 2)
    }
