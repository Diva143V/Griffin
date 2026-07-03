"""Electronic Lab Notebook (ELN) agent to format and log laboratory records."""
from __future__ import annotations

import time
from typing import Any, Dict
import ollama


def format_eln_entry(
    researcher_name: str,
    project_name: str,
    protocol_draft: str,
    user_notes: str = "",
    model_name: str = "gemma3:4b"
) -> Dict[str, Any]:
    """Format and log an Electronic Lab Notebook entry matching the experimental protocol."""
    start_time = time.time()
    date_str = time.strftime("%Y-%m-%d %H:%M:%S")

    prompt = f"""You are an Electronic Lab Notebook (ELN) Assistant. Your task is to format a formal ELN entry.

Project: {project_name}
Researcher: {researcher_name}
Date/Time: {date_str}
Protocol Draft:
{protocol_draft}
Researcher Notes/Inputs:
{user_notes}

Task:
Generate a professional, structured ELN record. Include:
1. HEADER: Standard ELN metadata (Project, Author, Entry Date, Experiment ID).
2. OBJECTIVE: Short description of why this run is performed.
3. PROTOCOL SUMMARY: Key treatments, concentration levels, and assay points.
4. OBSERVATIONS LOG (MOCK): A table or list for recording observed cell morphology changes, cell viability rates, and other daily readouts.
5. DISCUSSION & NEXT STEPS: What to monitor during incubation/run.

Ensure the output is clean, formatted in markdown, and looks like a real laboratory notebook page.
"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
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
            "timestamp": date_str
        },
        "execution_time_sec": round(duration, 2)
    }
