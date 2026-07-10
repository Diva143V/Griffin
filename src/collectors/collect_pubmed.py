"""Collect papers from PubMed (Entrez) with pagination and basic error handling."""
from __future__ import annotations

import argparse
import os
import time
from typing import List

from Bio import Entrez
from Bio import Medline
import pandas as pd


def collect(query: str, email: str, batch_size: int = 100, rate_limit_sec: float = 0.5) -> pd.DataFrame:
    Entrez.email = email
    papers: List[dict] = []

    # initial search to get count
    handle = Entrez.esearch(db="pubmed", term=query, retmax=0)
    record = Entrez.read(handle)
    count = int(record.get("Count", 0))
    print(f"PubMed reported {count} results")

    for start in range(0, count, batch_size):
        try:
            handle = Entrez.esearch(db="pubmed", term=query, retstart=start, retmax=batch_size)
            rec = Entrez.read(handle)
            ids = rec.get("IdList", [])
            if not ids:
                break

            fetch_handle = Entrez.efetch(db="pubmed", id=ids, rettype="medline", retmode="text")
            records = Medline.parse(fetch_handle)
            for paper in records:
                papers.append({
                    "title": paper.get("TI", ""),
                    "abstract": paper.get("AB", ""),
                    "year": paper.get("DP", ""),
                    "pmid": paper.get("PMID", ""),
                    "source": "PubMed",
                })
                
                # Stop if we hit the batch size (which we use as the hard limit)
                if len(papers) >= batch_size:
                    break
            
            if len(papers) >= batch_size:
                break

            time.sleep(rate_limit_sec)
        except Exception as e:
            print(f"Error fetching PubMed batch starting at {start}: {e}")
            break

    df = pd.DataFrame(papers)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect papers from PubMed via Entrez")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--email", default=os.environ.get("ENTREZ_EMAIL", ""), help="Entrez email (or set ENTREZ_EMAIL env var)")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--rate-limit", type=float, default=0.5, help="seconds between requests")
    parser.add_argument("--output", default="dataset/pubmed.csv")
    args = parser.parse_args()

    if not args.email:
        raise RuntimeError("Entrez email not set. Provide --email or set ENTREZ_EMAIL env var.")

    df = collect(args.query, email=args.email, batch_size=args.batch_size, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()