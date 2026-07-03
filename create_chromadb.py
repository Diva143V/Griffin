"""Create and populate a Chroma DB vector database from the paper dataset.

Usage:
    python create_chromadb.py [--input dataset/clean_papers_with_embeddings.csv] [--db-path dataset/chroma_db]
"""
from __future__ import annotations

import argparse
import os
import json
import ast
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_INPUT = "dataset/clean_papers_with_embeddings.csv"
DEFAULT_DB_PATH = "dataset/chroma_db"
COLLECTION_NAME = "papers"


def parse_embedding(value: Any) -> List[float]:
    """Safely parse embedding vectors from CSV values into a list of floats."""
    if isinstance(value, list):
        return [float(x) for x in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, str):
        try:
            val = json.loads(value)
            if isinstance(val, list):
                return [float(x) for x in val]
        except Exception:
            try:
                val = ast.literal_eval(value)
                if isinstance(val, list):
                    return [float(x) for x in val]
            except Exception:
                pass
    raise ValueError(f"Could not parse embedding value: {value}")


def build_text(row: pd.Series) -> str:
    """Combine title and abstract for embedding and document representation."""
    title = str(row.get("title", "") or "").strip()
    abstract = str(row.get("abstract", "") or "").strip()
    parts = []
    if title:
        parts.append(title)
    if abstract:
        parts.append(abstract)
    return "\n".join(parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and populate Chroma DB vector database")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to the input CSV file")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Directory to store Chroma DB data")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to generate embeddings if missing")
    parser.add_argument("--query", default=None, help="Query the database after creating/populating it")
    args = parser.parse_args()

    # 1. Load the dataset
    if not os.path.exists(args.input):
        print(f"Warning: Input file '{args.input}' not found.")
        # Fall back to clean_papers.csv if with_embeddings doesn't exist
        fallback = "dataset/clean_papers.csv"
        if os.path.exists(fallback):
            print(f"Using fallback input file: '{fallback}'")
            args.input = fallback
        else:
            print("Error: No dataset files found. Please run 'build_dataset.py' and 'generate_embeddings.py' first.")
            return

    print(f"Loading data from {args.input}...")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} papers.")

    if len(df) == 0:
        print("Dataset is empty. Nothing to insert.")
        return

    # Ensure required columns
    df["title"] = df["title"].fillna("").astype(str)
    df["abstract"] = df["abstract"].fillna("").astype(str)

    # 2. Setup Chroma Client
    os.makedirs(args.db_path, exist_ok=True)
    print(f"Initializing Chroma DB client at '{args.db_path}'...")
    chroma_client = chromadb.PersistentClient(path=args.db_path)

    # Create or get collection
    # We use Cosine similarity space for distance metrics.
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # 3. Check for precomputed embeddings or generate them
    documents: List[str] = []
    embeddings: List[List[float]] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    model = None
    has_embeddings = "embedding" in df.columns

    if not has_embeddings:
        print(f"No embeddings found in dataset. Loading '{args.model}' to generate them...")
        model = SentenceTransformer(args.model)

    for idx, row in df.iterrows():
        doc_text = build_text(row)
        if not doc_text:
            continue

        # Extract metadata
        metadata = {}
        for col in df.columns:
            if col not in ["embedding", "embedding_key", "embedding_text", "embedding_model"]:
                val = row[col]
                # Chroma metadata supports string, int, float, bool
                if pd.isna(val):
                    continue
                if isinstance(val, (int, float, str, bool)):
                    metadata[col] = val
                else:
                    metadata[col] = str(val)

        # Use pmid, doi, or a index-based ID
        paper_id = str(row.get("pmid", "")) or str(row.get("doi", "")) or f"paper_{idx}"
        paper_id = str(paper_id).strip()
        if not paper_id or paper_id == "nan":
            paper_id = f"paper_{idx}"

        documents.append(doc_text)
        metadatas.append(metadata)
        ids.append(paper_id)

        if has_embeddings:
            try:
                embeddings.append(parse_embedding(row["embedding"]))
            except Exception as e:
                # If parsing fails, we'll need to generate embeddings
                print(f"Failed to parse embedding for row {idx}, will generate embeddings instead: {e}")
                has_embeddings = False
                break

    if not has_embeddings:
        print("Generating embeddings for documents...")
        generated_embeddings = model.encode(documents, show_progress_bar=True, normalize_embeddings=True)
        embeddings = [x.tolist() for x in generated_embeddings]

    # 4. Upsert into Chroma DB
    print(f"Adding/Updating {len(documents)} papers in Chroma DB...")
    
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents
    )
    print("Database populate completed successfully.")

    # 5. Query demonstration
    query_str = args.query or "How does metformin affect breast cancer cells?"
    print(f"\nRunning a sample query: '{query_str}'")
    
    # Query embedding
    if model is None:
        model = SentenceTransformer(args.model)
    
    query_emb = model.encode([query_str], normalize_embeddings=True)[0].tolist()
    
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=3
    )

    print("\nSearch Results:")
    for i in range(len(results["ids"][0])):
        print("-" * 60)
        print(f"Rank {i+1}: ID={results['ids'][0][i]} (Distance={round(results['distances'][0][i], 4)})")
        metadata = results["metadatas"][0][i]
        print(f"Title: {metadata.get('title', 'N/A')}")
        if "year" in metadata:
            print(f"Year: {metadata.get('year', 'N/A')}")
        if "source" in metadata:
            print(f"Source: {metadata.get('source', 'N/A')}")
        doc = results["documents"][0][i]
        print(f"Excerpt: {doc[:300]}...")


if __name__ == "__main__":
    main()
