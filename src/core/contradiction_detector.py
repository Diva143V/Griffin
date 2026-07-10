"""Multi-stage contradiction detection pipeline for biomedical claims.

Pipeline stages:
    1. Semantic pre-filtering  – embed claims & select the most relevant pairs
    2. Pairwise LLM analysis   – classify each pair as AGREEMENT / CONTRADICTION /
                                  PARTIAL_AGREEMENT / UNRELATED with structured JSON
    3. Evidence-weighted scoring – weight results by paper evidence quality
    4. Cluster & synthesise    – group findings and run a focused synthesis prompt
    5. Report generation       – produce JSON, Markdown, and plain-text reports

Upgrades over the original version:
    - granular pairwise analysis instead of monolithic prompt
    - embedding-based pair selection for efficiency
    - structured JSON exchange with the LLM (no fragile regex)
    - evidence-score integration from evidence_ranker
    - rich Markdown report with tables and summary dashboard
    - backward-compatible plain-text output
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import concurrent.futures
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import ollama
import pandas as pd
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen3.5:9b"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_INPUT = "dataset/claims.csv"
DEFAULT_EVIDENCE_FILE = "dataset/ranked_papers.csv"
DEFAULT_OUTPUT_TEXT = "dataset/contradictions.txt"
DEFAULT_OUTPUT_CSV = "dataset/contradictions.csv"
DEFAULT_OUTPUT_JSON = "dataset/contradictions.json"
DEFAULT_OUTPUT_REPORT = "dataset/contradictions_report.md"
DEFAULT_MAX_PAIRS = 50
DEFAULT_SIMILARITY_THRESHOLD = 0.3
MAX_LLM_RETRIES = 2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ClaimPairResult:
    """Result of analysing a single pair of claims."""

    claim_a_title: str
    claim_a_text: str
    claim_a_stance: str
    claim_b_title: str
    claim_b_text: str
    claim_b_stance: str
    cosine_similarity: float
    relationship: str  # AGREEMENT | CONTRADICTION | PARTIAL_AGREEMENT | UNRELATED
    confidence: float  # 0.0 – 1.0
    explanation: str
    evidence_weight: float = 0.0  # average evidence score of the two papers


@dataclass
class ContradictionReport:
    """Full pipeline output."""

    model: str
    embedding_model: str
    timestamp: str
    input_path: str
    total_claims: int
    pairs_analyzed: int
    agreements: List[ClaimPairResult] = field(default_factory=list)
    contradictions: List[ClaimPairResult] = field(default_factory=list)
    partial_agreements: List[ClaimPairResult] = field(default_factory=list)
    unrelated: List[ClaimPairResult] = field(default_factory=list)
    synthesis: str = ""
    overall_confidence: str = ""  # low / medium / high


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pick_claim_text(row: pd.Series) -> str:
    """Return the best available claim text from a row."""
    for column in ("claim_output", "llm_output", "claim"):
        if column in row.index:
            value = str(row.get(column, "") or "").strip()
            if value:
                return value
    return ""


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract a JSON object from *text*, tolerating markdown fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")

    # Try parsing directly
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Stage 1 – Semantic pre-filtering
# ---------------------------------------------------------------------------


def load_and_embed_claims(
    input_path: str,
    embedding_model_name: str,
    max_claims: Optional[int] = None,
) -> Tuple[pd.DataFrame, np.ndarray, SentenceTransformer]:
    """Load claims CSV, normalise columns, and compute embeddings."""
    df = pd.read_csv(input_path)
    logger.info("Loaded %d claims from %s", len(df), input_path)

    if max_claims is not None:
        df = df.head(max_claims)

    for col in ("title", "stance", "reason"):
        if col not in df.columns:
            df[col] = ""

    df["claim_text"] = df.apply(pick_claim_text, axis=1)
    df = df[df["claim_text"].astype(str).str.strip() != ""].reset_index(drop=True)

    if df.empty:
        raise RuntimeError("No usable claim texts found in the input file")

    model = SentenceTransformer(embedding_model_name)
    texts = df["claim_text"].tolist()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    embeddings = np.asarray(embeddings, dtype=np.float32)

    logger.info("Embedded %d claims with %s", len(df), embedding_model_name)
    return df, embeddings, model


def select_pairs(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    max_pairs: int,
    similarity_threshold: float,
) -> List[Tuple[int, int, float]]:
    """Return the most analytically-interesting (i, j, cosine_sim) pairs.

    Strategy: score each pair by how *likely* it is to reveal an agreement or
    contradiction.  Very high similarity → probable agreement; moderate
    similarity → potential contradiction; very low → probably unrelated.
    We rank by a heuristic interest score that favours the high-sim and
    moderate-sim bands, then take the top ``max_pairs``.
    """
    n = len(df)
    if n < 2:
        return []

    # Full cosine similarity matrix (embeddings are already L2-normalised)
    sim_matrix = embeddings @ embeddings.T

    candidates: List[Tuple[float, int, int, float]] = []
    for i, j in combinations(range(n), 2):
        sim = float(sim_matrix[i, j])
        if sim < similarity_threshold:
            continue
        # Interest score: high similarity is interesting (agreements /
        # contradictions on the same topic), moderate similarity is also
        # interesting.  We slightly prefer higher similarity.
        interest = sim
        candidates.append((interest, i, j, sim))

    # Sort descending by interest
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = [(i, j, sim) for _, i, j, sim in candidates[:max_pairs]]
    logger.info(
        "Selected %d pairs from %d candidates (threshold %.2f)",
        len(selected),
        len(candidates),
        similarity_threshold,
    )
    return selected


# ---------------------------------------------------------------------------
# Stage 2 – Pairwise LLM contradiction analysis
# ---------------------------------------------------------------------------

PAIRWISE_PROMPT_TEMPLATE = """\
You are a biomedical research analyst. Compare the two scientific claims below
and classify their relationship.

Claim A (from "{title_a}"):
  Stance: {stance_a}
  Text: {text_a}

Claim B (from "{title_b}"):
  Stance: {stance_b}
  Text: {text_b}

Classify the relationship as exactly one of:
  AGREEMENT – the claims support each other
  CONTRADICTION – the claims conflict with each other
  PARTIAL_AGREEMENT – the claims partially agree but have notable differences
  UNRELATED – the claims address different aspects and cannot be compared

Return ONLY valid JSON in this format (no extra text):
{{"relationship": "<one of the four labels>", "confidence": <0.0 to 1.0>, "explanation": "<one sentence>"}}"""

RETRY_PROMPT = """\
Your previous response was not valid JSON. Please return ONLY the JSON object
with keys "relationship", "confidence", and "explanation". No markdown, no
extra text."""


def analyse_pair(
    title_a: str,
    text_a: str,
    stance_a: str,
    title_b: str,
    text_b: str,
    stance_b: str,
    model: str,
) -> Dict[str, Any]:
    """Run the LLM on a single claim pair and return parsed JSON."""
    prompt = PAIRWISE_PROMPT_TEMPLATE.format(
        title_a=title_a,
        text_a=text_a,
        stance_a=stance_a,
        title_b=title_b,
        text_b=text_b,
        stance_b=stance_b,
    )

    messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]
    last_raw = ""

    for attempt in range(1 + MAX_LLM_RETRIES):
        try:
            response = ollama.chat(model=model, messages=messages)
            last_raw = response["message"]["content"]
            parsed = _safe_json_parse(last_raw)

            if parsed and "relationship" in parsed:
                # Normalise
                rel = str(parsed["relationship"]).upper().strip()
                valid = {"AGREEMENT", "CONTRADICTION", "PARTIAL_AGREEMENT", "UNRELATED"}
                if rel not in valid:
                    rel = "UNRELATED"
                conf = float(parsed.get("confidence", 0.5))
                conf = max(0.0, min(1.0, conf))
                return {
                    "relationship": rel,
                    "confidence": conf,
                    "explanation": str(parsed.get("explanation", "")),
                }

            # Retry with stricter prompt
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({"role": "user", "content": RETRY_PROMPT})

        except Exception as exc:
            logger.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(1)

    # Fallback: return conservative default
    logger.warning("Could not parse LLM output after retries: %s", last_raw[:200])
    return {
        "relationship": "UNRELATED",
        "confidence": 0.0,
        "explanation": f"Failed to parse LLM response: {last_raw[:100]}",
    }


def run_pairwise_analysis(
    df: pd.DataFrame,
    pairs: List[Tuple[int, int, float]],
    model: str,
) -> List[ClaimPairResult]:
    """Analyse all selected pairs and return structured results."""
    results: List[ClaimPairResult] = []
    total = len(pairs)

    def process_pair(idx, pair):
        i, j, sim = pair
        row_a = df.iloc[i]
        row_b = df.iloc[j]

        title_a = str(row_a.get("title", "")).strip()
        title_b = str(row_b.get("title", "")).strip()
        text_a = str(row_a.get("claim_text", "")).strip()
        text_b = str(row_b.get("claim_text", "")).strip()
        stance_a = str(row_a.get("stance", "")).strip()
        stance_b = str(row_b.get("stance", "")).strip()

        logger.info("[%d/%d] Analysing: '%s' vs '%s' (sim=%.3f)", idx, total, title_a[:40], title_b[:40], sim)
        print(f"  [{idx}/{total}] Analysing pair (similarity {sim:.3f})...")

        parsed = analyse_pair(title_a, text_a, stance_a, title_b, text_b, stance_b, model)

        return ClaimPairResult(
            claim_a_title=title_a,
            claim_a_text=text_a,
            claim_a_stance=stance_a,
            claim_b_title=title_b,
            claim_b_text=text_b,
            claim_b_stance=stance_b,
            cosine_similarity=round(sim, 4),
            relationship=parsed["relationship"],
            confidence=round(parsed["confidence"], 3),
            explanation=parsed["explanation"],
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(process_pair, idx, pair) for idx, pair in enumerate(pairs, 1)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    return results


# ---------------------------------------------------------------------------
# Stage 3 – Evidence-weighted scoring
# ---------------------------------------------------------------------------


def load_evidence_scores(evidence_path: str) -> Dict[str, float]:
    """Load title → evidence_score mapping from ranked_papers.csv."""
    if not os.path.exists(evidence_path):
        logger.info("Evidence file not found: %s — skipping evidence weighting", evidence_path)
        return {}

    try:
        edf = pd.read_csv(evidence_path)
    except Exception as exc:
        logger.warning("Failed to read evidence file: %s", exc)
        return {}

    if "evidence_score" not in edf.columns or "title" not in edf.columns:
        return {}

    scores: Dict[str, float] = {}
    for _, row in edf.iterrows():
        title = str(row["title"]).strip().lower()
        score = float(row["evidence_score"])
        if title:
            scores[title] = score

    logger.info("Loaded %d evidence scores from %s", len(scores), evidence_path)
    return scores


def apply_evidence_weights(
    results: List[ClaimPairResult],
    evidence_scores: Dict[str, float],
    default_score: float = 4.0,
) -> None:
    """Mutate results in-place to set evidence_weight."""
    for r in results:
        score_a = evidence_scores.get(r.claim_a_title.strip().lower(), default_score)
        score_b = evidence_scores.get(r.claim_b_title.strip().lower(), default_score)
        r.evidence_weight = round((score_a + score_b) / 2.0, 2)


# ---------------------------------------------------------------------------
# Stage 4 – Cluster & synthesise
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT_TEMPLATE = """\
You are an expert biomedical research analyst writing a synthesis report.

Below are the results of pairwise comparisons between scientific claims about
the research topic. Each entry shows two claims, their relationship, the
analyst's confidence, and the evidence quality weight.

{pairwise_summary}

Based on these findings, write a structured synthesis covering:

1. **Overall consensus**: What do the majority of claims agree on?
2. **Key disputes**: What are the most significant contradictions? Which claims
   are involved and why do they disagree?
3. **Evidence quality assessment**: Do higher-evidence studies (meta-analyses,
   RCTs) tend to agree or disagree with lower-evidence studies?
4. **Possible reasons for disagreement**: Methodological differences, population
   differences, outcome measures, etc.
5. **Confidence level**: Overall confidence in the body of evidence (low / medium / high),
   with justification.

Write clearly and concisely. Use bullet points where appropriate."""


def _build_pairwise_summary(results: List[ClaimPairResult]) -> str:
    """Format the most important pairwise results for the synthesis prompt."""
    # Prioritise contradictions and high-confidence results
    sorted_results = sorted(
        results,
        key=lambda r: (
            r.relationship == "CONTRADICTION",
            r.confidence,
            r.evidence_weight,
        ),
        reverse=True,
    )

    # Cap at 30 to stay within context limits
    top = sorted_results[:30]
    lines = []
    for idx, r in enumerate(top, 1):
        lines.append(
            f"{idx}. [{r.relationship}] (confidence={r.confidence}, evidence_weight={r.evidence_weight})\n"
            f"   Claim A ({r.claim_a_title[:60]}): {r.claim_a_text[:150]}\n"
            f"   Claim B ({r.claim_b_title[:60]}): {r.claim_b_text[:150]}\n"
            f"   Explanation: {r.explanation}"
        )
    return "\n\n".join(lines)


def run_synthesis(
    results: List[ClaimPairResult],
    model: str,
) -> Tuple[str, str]:
    """Generate the final synthesis. Returns (synthesis_text, confidence_level)."""
    meaningful = [r for r in results if r.relationship != "UNRELATED"]
    if not meaningful:
        meaningful = results  # fall back to all

    pairwise_summary = _build_pairwise_summary(meaningful)
    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(pairwise_summary=pairwise_summary)

    logger.info("Running synthesis prompt (%d chars)", len(prompt))
    print("  Generating synthesis report...")

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        synthesis = response["message"]["content"]
    except Exception as exc:
        logger.error("Synthesis LLM call failed: %s", exc)
        synthesis = f"Synthesis generation failed: {exc}"

    # Try to extract confidence level
    confidence = "medium"
    conf_match = re.search(r"(?i)confidence\s*(?:level)?[:\s]*(low|medium|high)", synthesis)
    if conf_match:
        confidence = conf_match.group(1).lower()

    return synthesis, confidence


# ---------------------------------------------------------------------------
# Stage 5 – Report generation
# ---------------------------------------------------------------------------


def build_report(
    results: List[ClaimPairResult],
    synthesis: str,
    confidence: str,
    model: str,
    embedding_model: str,
    input_path: str,
    total_claims: int,
) -> ContradictionReport:
    """Assemble all results into a ContradictionReport."""
    report = ContradictionReport(
        model=model,
        embedding_model=embedding_model,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        input_path=input_path,
        total_claims=total_claims,
        pairs_analyzed=len(results),
        synthesis=synthesis,
        overall_confidence=confidence,
    )

    for r in results:
        if r.relationship == "AGREEMENT":
            report.agreements.append(r)
        elif r.relationship == "CONTRADICTION":
            report.contradictions.append(r)
        elif r.relationship == "PARTIAL_AGREEMENT":
            report.partial_agreements.append(r)
        else:
            report.unrelated.append(r)

    return report


def save_json(report: ContradictionReport, path: str) -> None:
    """Write structured JSON output."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    data = asdict(report)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved JSON report: %s", path)


def save_markdown(report: ContradictionReport, path: str) -> None:
    """Write a rich Markdown report."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def _pair_table(pairs: List[ClaimPairResult]) -> str:
        if not pairs:
            return "_None found._\n"
        lines = [
            "| # | Paper A | Paper B | Similarity | Confidence | Evidence Wt | Explanation |",
            "|---|---------|---------|:----------:|:----------:|:-----------:|-------------|",
        ]
        for idx, p in enumerate(
            sorted(pairs, key=lambda x: x.confidence, reverse=True), 1
        ):
            lines.append(
                f"| {idx} "
                f"| {p.claim_a_title[:50]} "
                f"| {p.claim_b_title[:50]} "
                f"| {p.cosine_similarity:.3f} "
                f"| {p.confidence:.2f} "
                f"| {p.evidence_weight:.1f} "
                f"| {p.explanation[:80]} |"
            )
        return "\n".join(lines) + "\n"

    md = []
    md.append("# 🔬 Contradiction Detection Report\n")
    md.append(f"**Generated**: {report.timestamp}  ")
    md.append(f"**LLM**: `{report.model}` | **Embeddings**: `{report.embedding_model}`  ")
    md.append(f"**Input**: `{report.input_path}`  ")
    md.append(f"**Claims analysed**: {report.total_claims} | **Pairs analysed**: {report.pairs_analyzed}\n")

    # Dashboard
    md.append("## 📊 Summary Dashboard\n")
    md.append(f"| Metric | Count |")
    md.append(f"|--------|:-----:|")
    md.append(f"| Agreements | {len(report.agreements)} |")
    md.append(f"| Contradictions | {len(report.contradictions)} |")
    md.append(f"| Partial Agreements | {len(report.partial_agreements)} |")
    md.append(f"| Unrelated | {len(report.unrelated)} |")
    md.append(f"| **Overall Confidence** | **{report.overall_confidence.upper()}** |")
    md.append("")

    # Contradictions (most important section)
    md.append("## ⚡ Contradictions\n")
    md.append(_pair_table(report.contradictions))

    # Agreements
    md.append("## ✅ Agreements\n")
    md.append(_pair_table(report.agreements))

    # Partial agreements
    md.append("## 🔀 Partial Agreements\n")
    md.append(_pair_table(report.partial_agreements))

    # Synthesis
    md.append("## 📝 Synthesis\n")
    md.append(report.synthesis)
    md.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    logger.info("Saved Markdown report: %s", path)


def save_text(report: ContradictionReport, path: str) -> None:
    """Write backward-compatible plain-text output."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    lines = []
    lines.append("=" * 70)
    lines.append("CONTRADICTION DETECTION REPORT")
    lines.append(f"Generated: {report.timestamp}")
    lines.append(f"Model: {report.model} | Embeddings: {report.embedding_model}")
    lines.append(f"Claims: {report.total_claims} | Pairs analysed: {report.pairs_analyzed}")
    lines.append("=" * 70)
    lines.append("")

    lines.append(f"CONTRADICTIONS ({len(report.contradictions)})")
    lines.append("-" * 40)
    for r in sorted(report.contradictions, key=lambda x: x.confidence, reverse=True):
        lines.append(f"  [{r.confidence:.2f}] {r.claim_a_title[:50]} vs {r.claim_b_title[:50]}")
        lines.append(f"         {r.explanation}")
    lines.append("")

    lines.append(f"AGREEMENTS ({len(report.agreements)})")
    lines.append("-" * 40)
    for r in sorted(report.agreements, key=lambda x: x.confidence, reverse=True):
        lines.append(f"  [{r.confidence:.2f}] {r.claim_a_title[:50]} vs {r.claim_b_title[:50]}")
        lines.append(f"         {r.explanation}")
    lines.append("")

    lines.append(f"PARTIAL AGREEMENTS ({len(report.partial_agreements)})")
    lines.append("-" * 40)
    for r in sorted(report.partial_agreements, key=lambda x: x.confidence, reverse=True):
        lines.append(f"  [{r.confidence:.2f}] {r.claim_a_title[:50]} vs {r.claim_b_title[:50]}")
        lines.append(f"         {r.explanation}")
    lines.append("")

    lines.append("SYNTHESIS")
    lines.append("-" * 40)
    lines.append(report.synthesis)
    lines.append("")
    lines.append(f"Overall confidence: {report.overall_confidence.upper()}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Saved text report: %s", path)


def save_csv(report: ContradictionReport, path: str) -> None:
    """Write backward-compatible CSV with all pair results."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    all_pairs = report.agreements + report.contradictions + report.partial_agreements + report.unrelated
    if all_pairs:
        rows = [asdict(p) for p in all_pairs]
        pd.DataFrame(rows).to_csv(path, index=False)
    else:
        pd.DataFrame().to_csv(path, index=False)

    logger.info("Saved CSV: %s", path)


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------


def run_detector(
    input_path: str,
    output_text: str,
    output_csv: str,
    output_json: str,
    output_report: str,
    model: str,
    embedding_model: str,
    evidence_file: str,
    max_claims: Optional[int] = None,
    max_pairs: int = DEFAULT_MAX_PAIRS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    skip_embeddings: bool = False,
) -> ContradictionReport:
    """Execute the full 5-stage pipeline."""

    print("\n" + "=" * 70)
    print("  CONTRADICTION DETECTOR - Multi-Stage Pipeline")
    print("=" * 70)

    # -- Stage 1: Load & embed -------------------------------------------
    print("\n[Stage 1] Loading claims and computing embeddings...")
    df, embeddings, _emb_model = load_and_embed_claims(input_path, embedding_model, max_claims)
    total_claims = len(df)
    print(f"  * {total_claims} claims embedded with {embedding_model}")

    # -- Pair selection --------------------------------------------------
    if skip_embeddings:
        # Analyse sequential pairs up to max_pairs
        n = len(df)
        pairs = [(i, j, 0.0) for i, j in combinations(range(n), 2)][:max_pairs]
        print(f"  * Skipped embedding filter - using first {len(pairs)} sequential pairs")
    else:
        pairs = select_pairs(df, embeddings, max_pairs, similarity_threshold)
        print(f"  * Selected {len(pairs)} pairs for analysis")

    if not pairs:
        print("  ! No pairs met the similarity threshold - try lowering --similarity-threshold")
        # Create empty report
        report = ContradictionReport(
            model=model,
            embedding_model=embedding_model,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            input_path=input_path,
            total_claims=total_claims,
            pairs_analyzed=0,
            synthesis="No claim pairs were similar enough to analyse.",
            overall_confidence="low",
        )
        save_json(report, output_json)
        save_markdown(report, output_report)
        save_text(report, output_text)
        save_csv(report, output_csv)
        return report

    # -- Stage 2: Pairwise LLM analysis ---------------------------------
    print(f"\n[Stage 2] Pairwise LLM analysis ({len(pairs)} pairs, model={model})...")
    results = run_pairwise_analysis(df, pairs, model)
    counts = {}
    for r in results:
        counts[r.relationship] = counts.get(r.relationship, 0) + 1
    print(f"  * Results: {counts}")

    # -- Stage 3: Evidence weighting -------------------------------------
    print(f"\n[Stage 3] Evidence-weighted scoring...")
    evidence_scores = load_evidence_scores(evidence_file)
    if evidence_scores:
        apply_evidence_weights(results, evidence_scores)
        print(f"  * Applied evidence weights from {len(evidence_scores)} papers")
    else:
        print("  ! No evidence scores available - using default weights")

    # -- Stage 4: Synthesis ----------------------------------------------
    print(f"\n[Stage 4] Generating synthesis...")
    synthesis, confidence = run_synthesis(results, model)
    print(f"  * Synthesis complete (confidence: {confidence})")

    # -- Stage 5: Report generation --------------------------------------
    print(f"\n[Stage 5] Generating reports...")
    report = build_report(results, synthesis, confidence, model, embedding_model, input_path, total_claims)

    save_json(report, output_json)
    save_markdown(report, output_report)
    save_text(report, output_text)
    save_csv(report, output_csv)

    print(f"\n  * JSON   -> {output_json}")
    print(f"  * Report -> {output_report}")
    print(f"  * Text   -> {output_text}")
    print(f"  * CSV    -> {output_csv}")

    # -- Print synthesis to console --------------------------------------
    print("\n" + "=" * 70)
    print("  SYNTHESIS")
    print("=" * 70)
    print(synthesis)
    print("=" * 70)
    print(f"  Overall confidence: {confidence.upper()}")
    print(f"  Agreements: {len(report.agreements)} | Contradictions: {len(report.contradictions)} "
          f"| Partial: {len(report.partial_agreements)} | Unrelated: {len(report.unrelated)}")
    print("=" * 70)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-stage contradiction detection pipeline for biomedical claims",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python contradiction_detector.py
  python contradiction_detector.py --max-pairs 10 --similarity-threshold 0.4
  python contradiction_detector.py --model llama3.1:8b --evidence-file dataset/ranked_papers.csv
  python contradiction_detector.py --no-embeddings --max-pairs 20
""",
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to claims CSV")
    parser.add_argument("--output-text", default=DEFAULT_OUTPUT_TEXT, help="Plain-text report output")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV, help="CSV output with all pair results")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON, help="Structured JSON report")
    parser.add_argument("--output-report", default=DEFAULT_OUTPUT_REPORT, help="Markdown report")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model for analysis")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Sentence-transformer model")
    parser.add_argument("--evidence-file", default=DEFAULT_EVIDENCE_FILE, help="Path to ranked_papers.csv")
    parser.add_argument("--max-claims", type=int, default=None, help="Limit claims loaded from input")
    parser.add_argument("--max-pairs", type=int, default=DEFAULT_MAX_PAIRS, help="Max claim pairs to analyse")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Min cosine similarity for pair selection",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding-based pre-filtering",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_detector(
        input_path=args.input,
        output_text=args.output_text,
        output_csv=args.output_csv,
        output_json=args.output_json,
        output_report=args.output_report,
        model=args.model,
        embedding_model=args.embedding_model,
        evidence_file=args.evidence_file,
        max_claims=args.max_claims,
        max_pairs=args.max_pairs,
        similarity_threshold=args.similarity_threshold,
        skip_embeddings=args.no_embeddings,
    )


if __name__ == "__main__":
    main()