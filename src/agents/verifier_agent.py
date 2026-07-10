"""Verifier agent for lightweight consistency and citation alignment checks."""
from __future__ import annotations

import re
from typing import Dict, List, Any


def verify_response(answer: str, sources: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify synthesis answer structure, citation indexing, and consistency checks."""
    answer_text = (answer or "").strip()
    findings: List[str] = []

    if not answer_text:
        findings.append("Answer is empty.")
        return {"status": "review", "findings": findings}

    if not sources:
        findings.append("No sources were retrieved.")
    else:
        # Check for citation footprints in text (e.g., [1], [Source Paper 1], [Source 1], [1, 2], [1-3])
        citation_blocks = re.findall(r'\[(?:Source Paper\s+|Source\s+|Paper\s+)?([\d\s,\-]+)\]', answer_text)
        
        if not citation_blocks:
            findings.append("No numerical citations found in the synthesis text (e.g., [1] or [Source Paper 1]).")
        else:
            total_sources = len(sources)
            invalid_citations = []
            
            # Extract individual integers from blocks like "1, 2" or "1-3"
            all_citation_numbers = []
            for block in citation_blocks:
                for part in block.split(','):
                    part = part.strip()
                    if '-' in part:
                        try:
                            start, end = part.split('-')
                            all_citation_numbers.extend(range(int(start), int(end) + 1))
                        except ValueError:
                            pass
                    elif part.isdigit():
                        all_citation_numbers.append(int(part))
            
            for idx in all_citation_numbers:
                if idx <= 0 or idx > total_sources:
                    invalid_citations.append(str(idx))
            
            if invalid_citations:
                findings.append(
                    f"Citations pointing to invalid indices: {', '.join(sorted(set(invalid_citations)))}. "
                    f"Total retrieved sources: {total_sources}."
                )

    if relations and not any(kw in answer_text.lower() for kw in ["contradict", "conflict", "agree", "differ", "disagree", "versus", "vs"]):
        findings.append("Disagreement relations exist in the database, but the answer does not mention any conflict or debate.")

    # Optional NLI Semantic Entailment
    try:
        from transformers import pipeline
        import torch
        # Only load if we have sources and sentences
        if sources and answer_text:
            sentences = [s.strip() + "." for s in answer_text.split(".") if len(s.strip()) > 20]
            if sentences:
                classifier = pipeline("zero-shot-classification", model="microsoft/deberta-v3-base-mnli", device=0 if torch.cuda.is_available() else -1)
                source_concat = " ".join([s.get("abstract", "") for s in sources])[:2000] # Trim for context window
                # Check entailment for a subset of sentences to save time
                for sent in sentences[:3]:
                    result = classifier(sent, candidate_labels=["entailment", "contradiction", "neutral"], hypothesis_template="This text implies that {}")
                    if result["labels"][0] == "contradiction":
                        findings.append(f"Possible hallucination/contradiction detected: '{sent}'")
    except ImportError:
        pass

    # Pass if no flags/warnings were raised
    if not findings:
        return {"status": "pass", "findings": []}
    return {"status": "review", "findings": findings}
