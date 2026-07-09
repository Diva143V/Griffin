"""Overseer Report Agent to generate comprehensive, web-grounded research reports using the new google-genai SDK."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from google import genai
from google.genai import types

def generate_overseer_report(
    api_key: str,
    query: str,
    sources: List[Dict[str, Any]],
    claims: List[Dict[str, Any]],
    contradictions: Dict[str, Any],
    consensus_report: str = "",
    experiment_protocol: str = "",
    eln_entry: str = "",
    model_name: str = "gemini-3.5-flash",
) -> Dict[str, Any]:
    """Generate a comprehensive web-grounded scientific research report using Gemini."""
    start_time = time.time()
    
    if not api_key:
        return {
            "report_text": "Error: Google API Key is required to run the Overseer Report Agent.",
            "execution_time_sec": 0.0
        }
        
    # Configure Gemini Client
    client = genai.Client(api_key=api_key)
    
    # Format papers
    papers_desc = []
    for idx, s in enumerate(sources, 1):
        design = s.get("study_design", s.get("design", "Undetermined"))
        score = s.get("evidence_score", 5.0)
        sample = s.get("sample_size", "N/A")
        papers_desc.append(
            f"[{idx}] Title: '{s.get('title')}'\n"
            f"    Design: {design} | Sample Size: {sample} | Quality Score: {score}/10\n"
            f"    Abstract: {s.get('abstract', '')[:250]}..."
        )
    papers_str = "\n\n".join(papers_desc) if papers_desc else "None"
    
    # Format claims
    claims_desc = []
    for c in claims:
        claims_desc.append(
            f"- Paper: '{c.get('title')}'\n"
            f"  Claim: {c.get('claim')}\n"
            f"  Stance: {c.get('stance')} | Reason: {c.get('reason')}"
        )
    claims_str = "\n\n".join(claims_desc) if claims_desc else "None"
    
    # Format contradictions
    relations = []
    if contradictions:
        for r in contradictions.get("contradictions", []):
            relations.append(f"- [Contradiction] Claim A vs Claim B: '{r.get('claim_a_title')}' vs '{r.get('claim_b_title')}'\n  Detail: {r.get('explanation')}")
        for r in contradictions.get("agreements", []):
            relations.append(f"- [Agreement] Claim A vs Claim B: '{r.get('claim_a_title')}' vs '{r.get('claim_b_title')}'\n  Detail: {r.get('explanation')}")
        for r in contradictions.get("partial_agreements", []):
            relations.append(f"- [Partial Agreement] Claim A vs Claim B: '{r.get('claim_a_title')}' vs '{r.get('claim_b_title')}'\n  Detail: {r.get('explanation')}")
    relations_str = "\n".join(relations) if relations else "None"
    
    # Construct Prompt
    system_instruction = (
        "You are the Director of Scientific Research & Oversight Agent. Your mandate:\n"
        "1. Synthesize local database evidence with live web-grounded findings\n"
        "2. Resolve contradictions using publication date, sample size, and clinical vs. preclinical context\n"
        "3. Assign confidence scores to all recommendations (GRADE: High/Moderate/Low)\n"
        "4. Prioritize recent, high-tier evidence (RCT > cohort > case report)\n"
        "5. Generate a publication-ready report WITHOUT conversational preamble\n\n"
        "TOKEN BUDGET: Max 6000 tokens (enforce hard stop)\n"
        "OUTPUT: Markdown only; no preamble or meta-commentary"
    )
    
    user_prompt = f"""RESEARCH QUERY: {query}

LOCAL DATABASE EVIDENCE:
{papers_str}

LOCAL CONSENSUS FINDINGS:
{consensus_report or 'None'}

LOCAL EXPERIMENT PROTOCOL:
{experiment_protocol or 'None'}

---

TASK: Generate a comprehensive, publication-grade scientific overseer report.

## 1. EXECUTIVE SUMMARY
[Max 200 tokens; include: query, key finding, confidence grade, primary recommendation]

Example:
"This analysis examined 12 local papers on metformin use in breast cancer patients. **Key Finding**: Moderate evidence (4/12 papers) supports improved recurrence-free survival (median +18 months, HR 0.72–0.88). However, 3 papers showed no benefit, and mechanistic clarity remains limited. **Recommendation**: Prospective trials in hormone-receptor-positive populations. **Confidence**: MODERATE."

---

## 2. LOCAL EVIDENCE SYNTHESIS TABLE
| Finding | Supporting Papers | Contradicting Papers | Effect Size | Confidence (GRADE) |
|---------|------------------|----------------------|-------------|-------------------|
| [Main claim] | [n papers] | [n papers] | [median effect] | [HIGH/MOD/LOW] |

---

## 3. WEB GROUNDING & LIVE VALIDATION
[Use web search results to cross-reference local findings]

**Strategy**: 
- Search PubMed for [Query] + [recent 3 years]
- Search clinical trial registries (ClinicalTrials.gov) for active or completed trials
- Search FDA/EMA databases for regulatory guidance

**Live Findings**:
1. [Most recent publication, date, key result]
2. [Active clinical trial, recruitment status]
3. [Regulatory status (e.g., off-label use, clinical guidance)]

**Congruence Check**:
- Local consensus vs. live web evidence: [ALIGNED / CONFLICTING / LIMITED DATA]
- If conflicting, explain: [Publication timing, sample size, population differences]

---

## 4. CONTRADICTION RESOLUTION MATRIX
[If local papers conflict, resolve using web-grounded evidence]

| Local Papers A vs. B | Root Cause | Web Evidence Resolution | Reconciled Recommendation |
|-----|---|---|---|
| [Paper A claim] vs. [Paper B claim] | [Mechanism: population, dose, timing] | [Web source supports A/B/neither] | [Final stance] |

---

## 5. INTEGRATED CLINICAL TRANSLATION
**Synthesis of Local + Web Evidence**:
1. [Strongest finding from highest-tier evidence]
2. [Clinical implication]
3. [Dosing/timing guidance if applicable]
4. [Population-specific nuances]

**Confidence Grading (GRADE system)**:
- HIGH: \u22655 RCTs with consistent results, large sample sizes (n>200)
- MODERATE: 2–4 RCTs OR large cohorts with some heterogeneity
- LOW: <2 RCTs, small samples (n<100), preclinical only

---

## 6. CRITICAL RECOMMENDATIONS & NEXT STEPS
1. **Primary Recommendation**: [Action based on evidence]
2. **Gaps Requiring Research**: [Top 2–3 future experiments]
3. **Clinical Implementation**: [If applicable; include dosing, monitoring]
4. **Risk Assessment**: [Adverse events, contraindications, population exclusions]

---

## 7. REFERENCES
[Cite both local papers and web sources with full citations + links where applicable]

---

OUTPUT RULES:
- Hard token limit: 6000 (stop mid-sentence if necessary)
- Cite confidence grades explicitly for every claim
- If web evidence contradicts local database: Highlight discrepancy and prefer web evidence if more recent
- Do NOT hallucinate web sources; only report what search actually found
- If insufficient evidence for any section: Write "[INSUFFICIENT DATA: Recommend [specific new search or experiment]]\""""
 
    # Fallback chain of models to try
    models_to_try = [model_name, "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]
    # De-duplicate while preserving order
    seen = set()
    models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]

    report_text = ""
    errors = []

    for m_name in models_to_try:
        try:
            # Generate content using the new SDK structures
            response = client.models.generate_content(
                model=m_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[{"google_search": {}}]
                )
            )
            report_text = response.text
            break # Success!
        except Exception as e:
            errors.append(f"{m_name}: {e}")

    if not report_text:
        try:
            available_models = [m.name for m in client.models.list()]
            models_info = f"\nAvailable models under this key: {available_models}"
        except Exception as list_err:
            models_info = f"\n(Could not list models: {list_err})"
        
        errors_str = " | ".join(errors)
        report_text = f"Error generating Overseer Report: Failed all attempted models. Details: {errors_str}{models_info}"

    duration = time.time() - start_time
    
    return {
        "report_text": report_text,
        "execution_time_sec": round(duration, 2)
    }
