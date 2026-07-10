"""Interactive retrieval over the embedded paper dataset."""
from __future__ import annotations

import argparse
import ast
from typing import Any, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_INPUT = "dataset/clean_papers_with_embeddings.csv"


def parse_embedding(value: Any) -> np.ndarray:
    if isinstance(value, list):
        return np.asarray(value, dtype=np.float32)
    if isinstance(value, str):
        return np.asarray(ast.literal_eval(value), dtype=np.float32)
    return np.asarray(value, dtype=np.float32)


def apply_filters(df: pd.DataFrame, source: Optional[str], year_min: Optional[int], year_max: Optional[int]) -> pd.DataFrame:
    filtered = df

    if source:
        if "source" in filtered.columns:
            source_mask = filtered["source"].astype(str).str.lower() == source.lower()
            filtered = filtered[source_mask]

    if year_min is not None and "year" in filtered.columns:
        year_series = pd.to_numeric(filtered["year"], errors="coerce")
        filtered = filtered[year_series >= year_min]

    if year_max is not None and "year" in filtered.columns:
        year_series = pd.to_numeric(filtered["year"], errors="coerce")
        filtered = filtered[year_series <= year_max]

    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Search embedded papers by semantic similarity")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--query", default=None, help="Optional query string; if omitted you'll be prompted")
    parser.add_argument("--source", default=None, help="Filter by source (PubMed, PMC, SemanticScholar)")
    parser.add_argument("--year-min", type=int, default=None)
    parser.add_argument("--year-max", type=int, default=None)
    args = parser.parse_args()

    model = SentenceTransformer(args.model)
    df = pd.read_csv(args.input)
    print(f"Loaded papers: {len(df)} from {args.input}")

    if "embedding" not in df.columns:
        raise ValueError("Input file must contain an 'embedding' column")

    df = apply_filters(df, args.source, args.year_min, args.year_max)
    print(f"Filtered papers: {len(df)}")

    embeddings = np.vstack(df["embedding"].apply(parse_embedding).to_list())

    query = args.query or input("Ask a question: ").strip()
    if not query:
        raise ValueError("Query cannot be empty")

    query_embedding = model.encode([query], normalize_embeddings=True)
    similarities = (embeddings @ query_embedding[0]).astype(float)
    df = df.copy()
    df["similarity"] = similarities

    top_papers = df.sort_values(by="similarity", ascending=False).head(args.top_k)

    print("\nTop Relevant Papers:\n")
    for _, row in top_papers.iterrows():
        print("=" * 80)
        print(f"Title: {row.get('title', '')}")
        if "year" in row:
            print(f"Year: {row.get('year', '')}")
        if "source" in row:
            print(f"Source: {row.get('source', '')}")
        print(f"Score: {round(float(row['similarity']), 3)}")
        print("Abstract:")
        print(str(row.get("abstract", ""))[:400])
        print()


if __name__ == "__main__":
    main()