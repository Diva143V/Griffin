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
        f"You are an expert Laboratory Protocol Planner specializing in {assay_focus}. Your standards:\n"
        "1. ONLY include reagents and procedures that exist and are commercially available\n"
        "2. VALIDATE all concentrations against published references (e.g., IC50 values, published dosing)\n"
        "3. Flag any speculative steps with [REQUIRES OPTIMIZATION]\n"
        "4. Enforce reproducibility: every step must be quantified (no \"incubate until done\")\n"
        "5. Include inter-assay variability expectations (CV \u00b1 X%)\n\n"
        "BIOLOGICAL GUARDRAILS:\n"
        "- Cell viability readouts: Must use validated assays (MTT, LDH, live/dead staining) \u2014 no guesses\n"
        "- Incubation times: Cite literature for all durations (e.g., \"24h incubation per Jones et al. 2020\")\n"
        "- Controls: Positive control MUST show \u226550% effect; negative must show <10% background\n"
        "- Concentrations: Flag if dose exceeds known toxic range (e.g., >10\u00b5M for most small molecules in cells)"
    )
    
    user_prompt = f"""RESEARCH QUERY: {query}
SCIENTIFIC SYNTHESIS: {synthesis_report}
ASSAY TYPE: {assay_focus}

DESIGN PROTOCOL: {suggested_steps}
POSITIVE CONTROL: {suggested_controls.split(' vs. ')[1]}
NEGATIVE CONTROL: {suggested_controls.split(' vs. ')[0]}

TASK: Design a reproducible, validated laboratory protocol in markdown.

## 1. EXPERIMENTAL HYPOTHESIS
State as: "We hypothesize that [TREATMENT] will [MECHANISM \u2192 READOUT]"
Example: "We hypothesize that metformin (5\u201325 \u00b5M, 48h) will suppress GLUT1 expression and reduce glucose uptake \u226530% in HepG2 cells"

## 2. REAGENTS & MATERIALS TABLE
| Item | Catalog # | Vendor | Stock Concentration | Final Working Concentration | Validation/Notes |
|------|-----------|--------|-------|--------|---------|
| [Drug/Reagent] | [ID] | [Vendor] | [X mM stock] | [Y \u00b5M final] | [e.g., "Validated in Jones et al. 2020; IC50 = 8 \u00b5M"] |
| [Cell line] | [ATCC ID] | ATCC | N/A | Passage 3\u20138 | [e.g., "HepG2 hepatocytes; validated mycoplasma-free"] |

## 3. STEP-BY-STEP PROCEDURE
Write 10\u201315 numbered steps. EVERY step must include:
- Exact quantities (cell count, incubation temp, duration in minutes/hours)
- Validation reference: "Per [published method]"
- Expected outcome: "Expect 90\u201395% viability post-treatment"
- [REQUIRES OPTIMIZATION] if step is speculative

Example:
> 7. Treat cells with drug or control (45-min pre-incubation at 37\u00b0C, 5% CO2)
>    - Add [Vehicle] or Metformin (5, 10, 25 \u00b5M final) to each well
>    - Incubation: 48 hours at 37\u00b0C, 5% CO2 (standard per HepG2 culture guidelines)
>    - Expected: Dose-dependent reduction in viability; positive control \u226560% reduction

## 4. POSITIVE & NEGATIVE CONTROLS
**Negative Control**: {suggested_controls.split(' vs. ')[0]}
- Setup: [Exact procedure, including blanks and vehicle-only wells]
- Expected outcome: <10% background signal (or cite literature CV%)
- Validation: [Citation supporting this expectation]

**Positive Control**: {suggested_controls.split(' vs. ')[1]}
- Setup: [Exact procedure]
- Expected outcome: \u226550% effect compared to vehicle
- Validation: [Citation]

## 5. READOUT & QUANTIFICATION
- Assay: [Name] (validated kit or protocol)
- Instrument: [Plate reader model, filters]
- Raw data: [Wavelength, gain, integration time]
- Calculations: [e.g., "% viability = (Treated OD570 \u2013 Blank) / (Vehicle OD570 \u2013 Blank) \u00d7 100"]
- Statistical test: [ANOVA, n-fold, t-test with Benjamini\u2013Hochberg FDR correction]

## 6. REPRODUCIBILITY & QUALITY CHECKLIST
- [ ] All concentrations validated against IC50/published literature
- [ ] Positive control expects \u226550% effect
- [ ] Negative control expects <10% background
- [ ] Incubation times justified by citation
- [ ] Cell passage number constrained (e.g., P3\u2013P8)
- [ ] Mycoplasma status verified
- [ ] Replicate design specified (n=3 technical, m=3 biological)
- [ ] Expected inter-assay CV: \u00b1X%

## 7. SAFETY & DISPOSAL
- Biosafety Level: [BSL-1/BSL-2]
- Chemical hazards: [List]
- Disposal protocol: [Cite institutional SOP]

---

OUTPUT RULES:
- Do NOT invent reagent catalog numbers; use real vendors or flag as [REQUIRES SOURCING]
- Do NOT propose concentrations outside published safe ranges without [REQUIRES OPTIMIZATION]
- If literature is scarce: Flag entire protocol as [PRELIMINARY; REQUIRES LITERATURE SEARCH]
- Max 4000 tokens; prioritize feasibility over exhaustive detail"""

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
