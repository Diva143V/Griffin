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

    prompt = f"""You are an Electronic Lab Notebook (ELN) Assistant. Your task is to generate a compliant, audit-ready lab record.

PROJECT: {project_name}
EXPERIMENT ID: {experiment_id}
PROTOCOL DRAFT: {protocol_draft}
RESEARCHER: {researcher_name}
DATE: {date_str}
USER NOTES: {user_notes}

GENERATE A STRUCTURED ELN ENTRY:

## 1. HEADER & METADATA
**Project Name**: {project_name}  
**Experiment ID**: {experiment_id}  
**Principal Investigator**: [Name]  
**Researcher**: {researcher_name}  
**Date/Time Initiated**: {date_str}  
**Protocol Version**: 1.0  
**Notebook Page**: [Auto-assigned]  

---

## 2. EXPERIMENTAL OBJECTIVE
[1-2 sentences describing scientific goal, therapeutic target, and primary readout]

Example:
"To determine whether Compound X (5–25 µM, 48h treatment) suppresses GLUT1 expression and reduces glucose uptake in HepG2 hepatocytes. Primary readout: % reduction in live-cell viability via MTT assay."

---

## 3. PROTOCOL SUMMARY & KEY PARAMETERS
**Cell Line & Culture**: HepG2 (ATCC #HB-8065), Passage 5, mycoplasma-negative  
**Incubation Conditions**: 37°C, 5% CO2, humidified  
**Treatment Groups**:
  - Vehicle (DMSO, 0.1% v/v)  
  - Positive Control: [Name], [Concentration]  
  - Test Compound: Compound X, [5 µM, 10 µM, 25 µM]  
  - Duration: 48 hours  

**Primary Readout**: MTT viability assay (Sigma M1235)  
**Expected Outcome**: Dose-dependent reduction in viability; positive control ≥60% inhibition  

---

## 4. OBSERVATIONS & RESULTS LOG
Create this table with REALISTIC mock data consistent with protocol:

| Timepoint | Sample Group | Well(s) | Treatment | OD570 (Raw) | OD630 (Blank) | Corrected OD | % Viability | Morphology | Notes |
|-----------|--------------|---------|-----------|------------|---------------|--------------|-------------|---------|-------|
| 0h | Vehicle | A1–A3 | DMSO 0.1% | 0.642 | 0.018 | 0.624 | 100% | Normal, confluent | Baseline |
| 24h | Vehicle | B1–B3 | DMSO 0.1% | 0.618 | 0.016 | 0.602 | 96.5% | Normal, confluent | On-track |
| 24h | Positive Control | C1–C3 | [Drug], 10 µM | 0.287 | 0.017 | 0.270 | 43.3% | Rounded, detached | Expected ≥50%; borderline |
| 24h | Test: Compound X | D1–D3 | 5 µM | 0.541 | 0.018 | 0.523 | 83.8% | Mostly normal | Dose-dependent |
| 24h | Test: Compound X | E1–E3 | 10 µM | 0.398 | 0.017 | 0.381 | 61.1% | Some rounding | Consistent |
| 24h | Test: Compound X | F1–F3 | 25 µM | 0.256 | 0.015 | 0.241 | 38.6% | Severe rounding, detached | Expected trend |
| 48h | [Repeat all groups] | ... | ... | ... | ... | ... | ... | ... | ... |

**Data Quality Notes**:
- CV (Vehicle replicates, 48h): ±3.2% (target: <5%)
- OD630 blanks consistent: 0.015–0.018 (acceptable background)
- Positive control at 48h: 68% inhibition (exceeds ≥50% threshold ✓)
- Compound X shows clear dose response (R² = 0.94 by linear regression)

---

## 5. DATA ANALYSIS & STATISTICS
**Method**: One-way ANOVA with Dunnett's post-hoc test (vehicle control)  
**Software**: GraphPad Prism v10  
**Results**:
- Vehicle vs. 5 µM: p = 0.062 (n.s.)  
- Vehicle vs. 10 µM: p = 0.008 (**)  
- Vehicle vs. 25 µM: p < 0.001 (***)  
- IC50 (estimated): ~9 µM  

**Graph**: [Placeholder: plot dose-response curve]

---

## 6. INTERPRETATION & NEXT STEPS
**Key Findings**:
1. Compound X reduces HepG2 viability in a dose-dependent manner (IC50 ≈ 9 µM)
2. Effect becomes statistically significant at ≥10 µM (48h)
3. Morphological changes (cell rounding, detachment) correlate with viability loss

**Validation Checks Passed**:
- ✓ Positive control met ≥50% threshold (68% inhibition)  
- ✓ Vehicle control <5% variation (CV 3.2%)  
- ✓ Data reproducible across technical replicates (n=3)  

**Limitations & Next Steps**:
1. Mechanism unknown: Recommend flow cytometry (apoptosis vs. necrosis) at 24/48h  
2. Cell-line specificity: Test on A549 (lung) and MCF7 (breast) to generalize  
3. Kinetics: Add 6h, 12h timepoints to map onset of effect  

---

## 7. AUDIT TRAIL & SIGN-OFF
**Recorded by**: {researcher_name}  
**Signature**: _________________ **Date**: {date_str}  

**Reviewed by**: [Supervisor Name]  
**Signature**: _________________ **Date**: [Date]  

**Approved for Final Use**: [PI or Lab Manager]  
**Signature**: _________________ **Date**: [Date]  

**Version History**:
- v1.0: Initial record (date)  
- v1.1: [If revisions made; track changes here]  

---

OUTPUT RULES:
- Mock data must be internally consistent (dose-response logic, control thresholds)
- All CV values must be realistic (±3–7% typical for cell viability)
- Positive control must exceed ≥50% effect; negative must be <10% of positive
- Include 2–3 realistic limitations and future experiments
- Do NOT invent data that contradicts protocol expectations"""

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
