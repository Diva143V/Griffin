"""Collect web search results from DuckDuckGo."""
from __future__ import annotations

import argparse
import time
from typing import List

import pandas as pd
from duckduckgo_search import DDGS


def collect(query: str, limit: int = 10, rate_limit_sec: float = 0.5) -> pd.DataFrame:
    """Fetch search results from DuckDuckGo."""
    results: List[dict] = []
    
    print(f"Searching DuckDuckGo for: '{query}'")
    
    try:
        with DDGS() as ddgs:
            # text search
            search_results = ddgs.text(query, max_results=limit)
            
            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "abstract": r.get("body", ""),
                    "year": "",  # DDG doesn't always return year cleanly in text search
                    "url": r.get("href", ""),
                    "source": "DuckDuckGo",
                })
        
        time.sleep(rate_limit_sec)
    except Exception as e:
        print(f"Error fetching from DuckDuckGo: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        # Ensure standard columns exist
        for col in ["title", "abstract", "year", "source", "url"]:
            if col not in df.columns:
                df[col] = ""
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect search results from DuckDuckGo")
    parser.add_argument("--query", default="latest news on crispr")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--rate-limit", type=float, default=0.5)
    parser.add_argument("--output", default="dataset/duckduckgo.csv")
    args = parser.parse_args()

    df = collect(args.query, limit=args.limit, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
