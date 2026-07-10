"""Collect papers from Semantic Scholar using the SemanticScholarClient.

Saves results to `dataset/semantic_scholar.csv` by default.
"""
from __future__ import annotations

import argparse
import time
import pandas as pd
from typing import List

from .semantic_scholar import SemanticScholarClient


def collect(query: str, limit: int = 100, offset: int = 0, max_pages: int | None = None, delay: float = 1.0) -> pd.DataFrame:
    """Collect pages of results from Semantic Scholar with pacing.

    - `limit` is the page size per request.
    - `offset` is the initial offset.
    - `max_pages` optionally limits the number of pages to fetch.
    - `delay` is seconds to wait between pages (in addition to client's internal pacing).
    """
    try:
        client = SemanticScholarClient()
    except RuntimeError as e:
        print(f"Skipping Semantic Scholar collector: {e}")
        return pd.DataFrame()
    papers: List[dict] = []
    page_count = 0

    while True:
        try:
            results = client.search(query, limit=limit, offset=offset)
        except Exception as e:
            print(f"Semantic Scholar request failed at offset {offset}: {e}")
            break

        if not results:
            break

        for item in results:
            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "year": item.get("year", ""),
                "paperId": item.get("paperId", ""),
                "source": "SemanticScholar",
            })
            if len(papers) >= limit:
                break

        offset += limit
        page_count += 1

        if len(papers) >= limit:
            print(f"Reached custom limit of {limit}; stopping.")
            break

        if max_pages is not None and page_count >= max_pages:
            print(f"Reached max_pages={max_pages}; stopping.")
            break

        # respect a client-side delay between pages to avoid rate issues
        time.sleep(delay)

    return pd.DataFrame(papers)


def main():
    parser = argparse.ArgumentParser(description="Collect papers from Semantic Scholar")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of pages to fetch")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between pages")
    parser.add_argument("--output", default="dataset/semantic_scholar.csv")
    args = parser.parse_args()

    df = collect(args.query, limit=args.limit, offset=args.offset, max_pages=args.max_pages, delay=args.delay)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
