"""Experiment Planning agent to design laboratory protocols and controls from literature synthesis."""
from __future__ import annotations

import time
from typing import Any, Dict
import ollama


def design_protocol(
    query: str,
    synthesis_report: str,
    model_name: str = "gemma3:4b",
    options: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Design a step-by-step laboratory protocol with negative/positive controls based on findings."""
    start_time = time.time()

    # Dynamic target assay classification based on query keywords
    query_lower = query.lower()
    assay_focus = "General Assay Analysis"
    suggested_steps = "treating cells and measuring viability/outcomes"
    suggested_controls = "DMSO/vehicle control vs. standard cell-killing reference"

    if any(k in query_lower for k in ["expression", "mrna", "gene", "transcription", "qpcr", "rna"]):
        assay_focus = "Gene Expression / qPCR Assay Protocol"
        suggested_steps = "RNA extraction, cDNA synthesis, and quantitative RT-PCR run parameters"
        suggested_controls = "Housekeeping gene (GAPDH/Actin) vs. positive transcript activator"
    elif any(k in query_lower for k in ["protein", "western", "blot", "translation", "antibody", "elisa"]):
        assay_focus = "Protein Expression / Western Blotting or ELISA Protocol"
        suggested_steps = "protein extraction, lysis, gel electrophoresis/transfer, and antibody staining steps"
        suggested_controls = "Loading control protein (Tubulin) vs. antibody positive control lysate"
    elif any(k in query_lower for k in ["viability", "apoptosis", "death", "mtt", "cck", "proliferation", "growth"]):
        assay_focus = "In-Vitro Cell Proliferation and Viability Assay Protocol"
        suggested_steps = "cell seeding, treatment dilution series, incubation timeline, and MTT/CCK-8 readout absorbance measurements"
        suggested_controls = "Untreated/vehicle media (negative) vs. 10% DMSO or Staurosporine (positive)"
    elif any(k in query_lower for k in ["synergy", "combination", "combine", "co-treatment"]):
        assay_focus = "Drug Combination Synergy Assay Protocol"
        suggested_steps = "checkerboard drug dilution layout, cell seeding, co-incubation, and synergy calculations (e.g., ZIP or Bliss score)"
        suggested_controls = "Single agents alone vs. combination wells and vehicle controls"

    system_prompt = (
        f"You are an expert Laboratory Protocol Planner specializing in {assay_focus}. "
        "Your goal is to translate scientific findings into a concrete, reproducible laboratory experiment protocol. "
        "Write your response in clean markdown format, being practical and scientifically rigorous."
    )
    
    user_prompt = f"""Research Query: {query}
Scientific Synthesis:
{synthesis_report}

Task:
Please design a structured, rigorous, and reproducible laboratory experiment protocol optimized for a {assay_focus}. Provide detailed, practical guidelines matching standard laboratory procedures:
1. **EXPERIMENTAL HYPOTHESIS**: Define a testable hypothesis linking treatments to measurable biochemical readouts.
2. **MATERIALS & REAGENTS**: Provide a comprehensive inventory table listing cell lines, chemical agents with exact concentration stocks (e.g., in mM/uM), assay detection kits, and analytical instrumentation.
3. **PREPARATION & RECONSTITUTION**: Detailed instructions on reconstitution (e.g. dissolving in DMSO/PBS) and final working dilutions.
4. **STEP-BY-STEP PROCEDURE**: Write a detailed, numbered laboratory protocol covering {suggested_steps}. Specify seeding densities (e.g., cells per well in 96-well format), exact incubation durations, temperature ranges (e.g. 37°C with 5% CO2), and detection parameters (e.g. PCR cycles, dye incubation limits).
5. **CONTROLS & SHAM TREATMENTS**:
   - **Negative Control**: Detailed setup for {suggested_controls.split(' vs. ')[0]}.
   - **Positive Control**: Detailed setup for {suggested_controls.split(' vs. ')[1]}.
6. **QUANTIFICATION & READOUT ANALYSIS**: Specify the instrumentation and exact readout values (e.g., absorbance wavelength at 570nm, fluorometric filter configurations, fold-change calculations using 2^-ddCt).
7. **SAFETY & BIOSAFETY COMPLIANCE**: Detail biosafety level requirements (BSL-1/BSL-2) and disposal protocols.

Ensure all instructions are biologically sound and directly support testing the research query. Do not make up any information."""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options=options
        )
        protocol_text = response["message"]["content"]
    except Exception as e:
        protocol_text = f"Error calling Experiment Agent: {e}"

    duration = time.time() - start_time
    
    return {
        "protocol_draft": protocol_text,
        "execution_time_sec": round(duration, 2)
    }
