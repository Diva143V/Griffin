"""Collect bioRxiv preprints from the public date-based API and filter locally by keywords."""
from __future__ import annotations

import argparse
import time
import requests
import datetime
import pandas as pd
from typing import List, Dict, Any


def fetch_biorxiv_range(session: requests.Session, start_date: str, end_date: str, cursor: int = 0) -> Dict[str, Any]:
    url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/{cursor}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 100, max_pages: int = 2, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "GriffinBioAgent/1.0"})
    
    # Define date range: last 30 days
    today = datetime.date.today()
    thirty_days_ago = today - datetime.timedelta(days=30)
    start_str = thirty_days_ago.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")
    
    keywords = [w.strip().lower() for w in query.split() if len(w.strip()) > 3]
    
    preprints = []
    cursor = 0
    
    for page in range(1, max_pages + 1):
        try:
            print(f"Fetching bioRxiv page {page} (cursor: {cursor})...")
            data = fetch_biorxiv_range(session, start_str, end_str, cursor)
        except Exception as e:
            print(f"bioRxiv request failed: {e}")
            break
            
        collection = data.get("collection", [])
        if not collection:
            break
            
        for item in collection:
            title = item.get("title", "") or ""
            abstract = item.get("abstract", "") or ""
            
            # Local keyword filtering
            matches = True
            if keywords:
                text_block = (title + " " + abstract).lower()
                matches = any(kw in text_block for kw in keywords)
                
            if matches:
                authors = item.get("authors", "") or ""
                year = item.get("date", "")[:4]
                doi = item.get("doi", "") or ""
                
                preprints.append({
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "journal": "bioRxiv (Preprint)",
                    "year": year,
                    "doi": doi,
                    "pmid": "",
                    "pmcid": "",
                    "source": "bioRxiv",
                })
                
        # Advance pagination cursor
        cursor += len(collection)
        if len(collection) < 100:
            break
            
        time.sleep(rate_limit_sec)
        
    df = pd.DataFrame(preprints)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect preprints from bioRxiv")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--output", default="dataset/biorxiv.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
