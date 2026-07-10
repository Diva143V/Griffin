"""Shared disk-backed data helpers for V2 pages (dashboard / workspace).

Reads the real pipeline outputs under dataset/ so the shell UI is not mock-only.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATASET_DIR = os.path.join(ROOT_DIR, "dataset")


def _safe_len_csv(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        return len(pd.read_csv(path))
    except Exception:
        return 0


def _load_contradictions() -> Dict[str, Any]:
    path = os.path.join(DATASET_DIR, "contradictions.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_dashboard_metrics() -> Dict[str, str]:
    """Live metrics derived from dataset artifacts."""
    papers = _safe_len_csv(os.path.join(DATASET_DIR, "clean_papers.csv"))
    if papers == 0:
        papers = _safe_len_csv(os.path.join(DATASET_DIR, "ranked_papers.csv"))
    if papers == 0:
        papers = _safe_len_csv(os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv"))

    ranked_path = os.path.join(DATASET_DIR, "ranked_papers.csv")
    avg_score = "—"
    if os.path.exists(ranked_path):
        try:
            df = pd.read_csv(ranked_path)
            col = "evidence_score" if "evidence_score" in df.columns else None
            if col is None and "score" in df.columns:
                col = "score"
            if col:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(vals):
                    # Evidence scores are typically 1-10; show as percent of 10
                    avg_score = f"{(vals.mean() / 10.0) * 100:.0f}%"
        except Exception:
            pass

    contr = _load_contradictions()
    n_contr = len(contr.get("contradictions", []) or [])
    n_agree = len(contr.get("agreements", []) or [])
    n_partial = len(contr.get("partial_agreements", []) or [])

    claims = _safe_len_csv(os.path.join(DATASET_DIR, "claims.csv"))
    if claims == 0:
        claims = _safe_len_csv(os.path.join(DATASET_DIR, "claims_dataset.csv"))

    # Agents: count which stages appear in last execution trace
    agents = "—"
    trace_path = os.path.join(DATASET_DIR, "execution_trace.json")
    if os.path.exists(trace_path):
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                trace = json.load(f)
            executed = trace.get("executed_agents") or []
            agents = str(len(executed)) if executed else "—"
        except Exception:
            pass

    # Current research goal
    goal = "No active research run yet"
    goal_path = os.path.join(DATASET_DIR, "last_research_goal.txt")
    if os.path.exists(goal_path):
        try:
            with open(goal_path, "r", encoding="utf-8") as f:
                g = f.read().strip()
                if g:
                    goal = g
        except Exception:
            pass

    pipeline_status = "Idle — run a query from the Planner"
    if os.path.exists(os.path.join(DATASET_DIR, "consensus_report.md")) or os.path.exists(
        os.path.join(DATASET_DIR, "final_synthesis.md")
    ):
        pipeline_status = "Latest synthesis available"
    if os.path.exists(os.path.join(DATASET_DIR, "execution_trace.json")):
        pipeline_status = "Pipeline completed — open Planner for full trace"

    progress = 0
    if papers:
        progress = 25
    if claims:
        progress = 45
    if n_contr or n_agree:
        progress = 70
    if os.path.exists(os.path.join(DATASET_DIR, "consensus_report.md")) or os.path.exists(
        os.path.join(DATASET_DIR, "final_synthesis.md")
    ):
        progress = 100

    return {
        "papers": str(papers) if papers else "0",
        "evidence_score": avg_score,
        "contradictions": str(n_contr),
        "agreements": str(n_agree + n_partial),
        "claims": str(claims),
        "agents": agents if agents != "—" else "0",
        "goal": goal,
        "pipeline_status": pipeline_status,
        "progress": str(progress),
    }


def get_papers(limit: int = 24, search: str = "") -> List[Dict[str, str]]:
    """Paper cards for the workspace explorer from ranked / clean CSVs."""
    candidates = [
        os.path.join(DATASET_DIR, "ranked_papers.csv"),
        os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv"),
        os.path.join(DATASET_DIR, "clean_papers.csv"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return []

    try:
        df = pd.read_csv(path)
    except Exception:
        return []

    q = (search or "").strip().lower()
    rows: List[Dict[str, str]] = []
    for _, r in df.iterrows():
        title = str(r.get("title", "") or "")
        abstract = str(r.get("abstract", "") or "")
        if q and q not in title.lower() and q not in abstract.lower():
            continue
        score = r.get("evidence_score", r.get("score", ""))
        year = r.get("year", r.get("publication_year", ""))
        journal = r.get("journal", r.get("source", r.get("venue", "Unknown")))
        src = str(r.get("source", "") or journal or "")
        url = str(r.get("url", r.get("link", r.get("doi", ""))) or "#")
        if url and url != "#" and not url.startswith("http") and "doi" in (r.keys() if hasattr(r, "keys") else []):
            # leave raw doi as-is; Open Analysis link still works as "#"
            pass
        rows.append(
            {
                "title": title[:200] if title else "Untitled",
                "journal": str(journal)[:80],
                "year": str(year) if pd.notna(year) else "—",
                "score": str(score) if pd.notna(score) else "—",
                "abstract": abstract[:280] + ("…" if len(abstract) > 280 else ""),
                "source": src[:80] if src else str(journal)[:80],
                "url": url if url else "#",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def get_knowledge_graph() -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Nodes/edges derived from contradiction pairs (real claim titles)."""
    data = _load_contradictions()
    nodes: Dict[str, Dict[str, str]] = {}
    edges: List[Dict[str, str]] = []

    def _add_pair(items: list, rel: str, ntype: str):
        for it in (items or [])[:40]:
            a = str(it.get("claim_a_title") or it.get("claim_a") or "Claim A")[:60]
            b = str(it.get("claim_b_title") or it.get("claim_b") or "Claim B")[:60]
            if not a or not b:
                continue
            nodes[a] = {"id": a, "label": a, "type": ntype}
            nodes[b] = {"id": b, "label": b, "type": ntype}
            edges.append({"source": a, "target": b, "label": rel})

    _add_pair(data.get("contradictions", []), "contradicts", "Conflict")
    _add_pair(data.get("agreements", []), "agrees", "Agreement")
    _add_pair(data.get("partial_agreements", []), "partial", "Partial")

    if not nodes:
        # Fallback: sample paper titles as isolated nodes
        papers = get_papers(limit=8)
        for p in papers:
            t = p["title"][:50]
            nodes[t] = {"id": t, "label": t, "type": "Paper"}
        return list(nodes.values()), []

    return list(nodes.values())[:24], edges[:30]


def get_timeline_events() -> List[Dict[str, str]]:
    """Year-bucketed research evolution from paper years + contradiction milestones."""
    events: List[Dict[str, str]] = []

    # From papers
    papers = get_papers(limit=200)
    by_year: Dict[str, int] = {}
    for p in papers:
        y = str(p.get("year") or "").strip()
        if y.isdigit() and 1900 < int(y) < 2100:
            by_year[y] = by_year.get(y, 0) + 1
    for y in sorted(by_year.keys())[-8:]:
        events.append(
            {
                "year": y,
                "text": f"{by_year[y]} paper(s) in dataset from {y}",
            }
        )

    # From contradictions file timestamps if present (use counts as milestones)
    contr = _load_contradictions()
    n_c = len(contr.get("contradictions", []) or [])
    n_a = len(contr.get("agreements", []) or [])
    if n_c or n_a:
        events.append(
            {
                "year": "Now",
                "text": f"Detected {n_c} contradiction(s) and {n_a} agreement(s) in claims",
            }
        )

    if not events:
        events = [
            {
                "year": "—",
                "text": "No dataset yet. Run the Planner to collect literature.",
            }
        ]
    return events


def save_research_goal(goal: str) -> None:
    os.makedirs(DATASET_DIR, exist_ok=True)
    with open(os.path.join(DATASET_DIR, "last_research_goal.txt"), "w", encoding="utf-8") as f:
        f.write((goal or "").strip())


def load_research_goal() -> str:
    path = os.path.join(DATASET_DIR, "last_research_goal.txt")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
