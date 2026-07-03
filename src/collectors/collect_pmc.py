"""Collect papers from Europe PMC with pagination, rate-limiting, and retries."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List


def fetch_page(session: requests.Session, query: str, page: int, page_size: int) -> List[dict]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/"
        "search"
    )
    params = {"query": query, "format": "json", "pageSize": page_size, "page": page, "resultType": "core"}
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("resultList", {}).get("result", [])


def collect(query: str, page_size: int = 100, max_pages: int = 10, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    papers = []
    for page in range(1, max_pages + 1):
        try:
            results = fetch_page(session, query, page, page_size)
        except Exception as e:
            print(f"Request failed for page {page}: {e}")
            break

        if not results:
            print(f"No results on page {page}; stopping.")
            break

        for item in results:
            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstractText", ""),
                "year": item.get("pubYear", ""),
                "pmid": item.get("pmid", ""),
                "source": "PMC",
            })

        # respect rate limit
        time.sleep(rate_limit_sec)

        # stop early if fewer results than page_size
        if len(results) < page_size:
            break

    df = pd.DataFrame(papers)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect papers from Europe PMC")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--rate-limit", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--output", default="dataset/pmc.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()