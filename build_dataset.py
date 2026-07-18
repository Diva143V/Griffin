"""End-to-end dataset builder for the paper and biological annotation collection pipeline.

Pipeline:
  Active Ingestion Collectors (PubMed, PMC, Semantic Scholar, OpenAlex, ClinicalTrials, bioRxiv, ChEMBL, UniProt, PubChem, dbSNP)
      ↓
  Merge results
      ↓
  Remove duplicates according to collector priority
      ↓
  Save final dataset

Optionally runs `clean_dataset.py` afterward.
"""
from __future__ import annotations

from collections.abc import Iterable

import argparse
import os
import subprocess
import sys
import pandas as pd

# pyrefly: ignore [missing-import]
from src.collectors.collector_registry import get_collector_names, get_selected_collectors, source_paths


def ensure_dataset_dir() -> None:
    os.makedirs("dataset", exist_ok=True)


def run_collectors(query: str, args) -> None:
    ensure_dataset_dir()

    import json
    limits = {}
    if getattr(args, "collector_limits", None):
        try:
            limits = json.loads(args.collector_limits)
        except Exception:
            pass

    selected = get_selected_collectors(args.sources)
    for spec in selected:
        print(f"Running {spec.name} collector...")
        custom_limit = limits.get(spec.name, args.max_results)
        
        import copy
        runner_args = copy.copy(args)
        # Override values dynamically
        if spec.name == "PubMed":
            runner_args.pubmed_limit = custom_limit
        elif spec.name == "PMC":
            runner_args.pmc_limit = custom_limit
        elif spec.name == "SemanticScholar":
            runner_args.ss_limit = custom_limit
        elif spec.name == "OpenAlex":
            runner_args.openalex_limit = custom_limit
        else:
            setattr(runner_args, f"{spec.name.lower()}_limit", custom_limit)

        df = spec.runner(query, runner_args)
        df.to_csv(spec.output_path, index=False)
        print(f"Saved {spec.output_path} with {len(df)} records")


def merge_and_dedup(output: str, selected_sources: Iterable[str] | None = None, max_results: int | None = None) -> pd.DataFrame:
    frames = []

    for name, path in source_paths(selected_sources).items():
        if not os.path.exists(path):
            print(f"Source missing: {path} (skipping)")
            continue
        try:
            df = pd.read_csv(path)
            if "source" not in df.columns:
                df["source"] = name
            print(f"{name} papers: {len(df)} -- loaded from {path}")
            frames.append(df)
        except Exception as exc:
            print(f"Failed to read {path}: {exc}")

    if not frames:
        print("No source CSVs found to merge. Creating empty dataset.")
        empty_df = pd.DataFrame(columns=[
            "title", "abstract", "authors", "journal", "year", "doi", "pmid", "pmcid", 
            "source", "study_design", "sample_size", "evidence_score"
        ])
        empty_df.to_csv(output, index=False)
        return empty_df

    all_papers = pd.concat(frames, ignore_index=True)
    print("Before removing duplicates:", len(all_papers))

    if "title" in all_papers.columns:
        all_papers["title_norm"] = all_papers["title"].astype(str).str.strip().str.lower()
    else:
        all_papers["title_norm"] = all_papers.index.astype(str)

    priority = {
        "PubMed": 0,
        "PMC": 1,
        "SemanticScholar": 2,
        "OpenAlex": 3,
        "ClinicalTrials": 4,
        "bioRxiv": 5,
        "ChEMBL": 6,
        "UniProt": 7,
        "PubChem": 8,
        "dbSNP": 9,
        "DuckDuckGo": 10
    }
    all_papers["source_priority"] = all_papers.get("source", "").map(priority).fillna(99)
    all_papers = all_papers.sort_values(["source_priority"], ascending=True)

    before = len(all_papers)
    all_papers = all_papers.drop_duplicates(subset=["title_norm"], keep="first")
    print("After removing duplicates:", len(all_papers), f"(removed {before - len(all_papers)})")

    all_papers = all_papers.drop(columns=["title_norm", "source_priority"], errors="ignore")

    if "abstract" in all_papers.columns:
        all_papers = all_papers.dropna(subset=["abstract"])
        all_papers = all_papers[all_papers["abstract"].astype(str).str.strip() != ""]
    print("After removing empty abstracts:", len(all_papers))

    if max_results is not None:
        all_papers = all_papers.head(max_results)
        print(f"Trimmed to top {len(all_papers)} results (max-results={max_results})")

    os.makedirs(os.path.dirname(output), exist_ok=True)
    all_papers.to_csv(output, index=False)
    print(f"Saved {output} ({len(all_papers)} records)")
    return all_papers


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the paper dataset end-to-end")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument(
        "--sources",
        nargs="*",
        default=None,
        help=f"Collectors to run. Default is all: {', '.join(get_collector_names())}",
    )

    parser.add_argument("--email", default=os.environ.get("ENTREZ_EMAIL", ""), help="Entrez email (or set ENTREZ_EMAIL env var)")
    parser.add_argument("--pubmed-batch-size", type=int, default=100)
    parser.add_argument("--pubmed-rate-limit", type=float, default=0.5)

    parser.add_argument("--pmc-page-size", type=int, default=100)
    parser.add_argument("--pmc-max-pages", type=int, default=1)
    parser.add_argument("--pmc-rate-limit", type=float, default=1.0)

    parser.add_argument("--ss-limit", type=int, default=20)
    parser.add_argument("--ss-offset", type=int, default=0)
    parser.add_argument("--ss-max-pages", type=int, default=3)
    parser.add_argument("--ss-delay", type=float, default=1.5)

    parser.add_argument("--openalex-per-page", type=int, default=20)
    parser.add_argument("--openalex-max-pages", type=int, default=2)
    parser.add_argument("--openalex-rate-limit", type=float, default=1.0)
    parser.add_argument("--duckduckgo-limit", type=int, default=10)

    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--collector-limits", default="{}", help="JSON string mapping collector names to limits")
    parser.add_argument("--output", default=os.path.join(os.environ.get("GRIFFIN_RUN_DIR", "dataset"), "final_papers.csv"))
    parser.add_argument("--run-filter", action="store_true", help="Run clean_dataset.py after saving final_papers.csv")

    args = parser.parse_args()

    if not args.email:
        print("Error: Entrez email not set. Provide --email or set ENTREZ_EMAIL env var.")
        sys.exit(1)

    run_collectors(args.query, args)
    merge_and_dedup(args.output, selected_sources=args.sources, max_results=args.max_results)

    if args.run_filter:
        print("Running clean_dataset.py...")
        subprocess.run([sys.executable, "clean_dataset.py", "--query", args.query], check=True)


if __name__ == "__main__":
    main()
