"""Collect papers from OpenAlex with pagination, rate-limiting, and abstract reconstruction."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def reconstruct_abstract(inverted_index: Dict[str, List[int]] | None) -> str:
    """Reconstruct abstract from OpenAlex's inverted index format."""
    if not inverted_index:
        return ""
    try:
        word_positions: Dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions[pos] = word
        sorted_keys = sorted(word_positions.keys())
        return " ".join(word_positions[k] for k in sorted_keys)
    except Exception:
        return ""


def fetch_page(session: requests.Session, query: str, page: int, per_page: int) -> List[Dict[str, Any]]:
    """Fetch a page of search results from OpenAlex works endpoint."""
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per_page": per_page,
        "page": page
    }
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def collect(query: str, per_page: int = 20, max_pages: int = 3, rate_limit_sec: float = 1.0, email: str | None = None) -> pd.DataFrame:
    """Collect pages of results from OpenAlex with pacing."""
    session = requests.Session()
    # Be friendly to OpenAlex by identifying ourselves
    import os
    if not email:
        email = os.getenv("ENTREZ_EMAIL") or "test@example.com"
    session.headers.update({"User-Agent": f"mailto:{email}"})
    papers = []
    
    for page in range(1, max_pages + 1):
        try:
            print(f"Fetching OpenAlex page {page}...")
            results = fetch_page(session, query, page, per_page)
        except Exception as e:
            print(f"Request failed for OpenAlex page {page}: {e}")
            break

        if not results:
            break

        for item in results:
            abstract_index = item.get("abstract_inverted_index")
            abstract = reconstruct_abstract(abstract_index)
            
            # Find a suitable ID
            doi = item.get("doi") or ""
            id_val = item.get("id") or ""
            pmid_url = item.get("ids", {}).get("pmid") or ""
            pmid = pmid_url.replace("https://pubmed.ncbi.nlm.nih.gov/", "") if pmid_url else ""
            
            paper_id = pmid or doi or id_val
            
            papers.append({
                "title": item.get("title", "") or "",
                "abstract": abstract,
                "year": item.get("publication_year", "") or "",
                "pmid": paper_id,
                "source": "OpenAlex",
            })

        time.sleep(rate_limit_sec)
        if len(results) < per_page:
            break

    df = pd.DataFrame(papers)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect papers from OpenAlex")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--per-page", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    import os
    parser.add_argument("--email", default=os.environ.get("ENTREZ_EMAIL", ""))
    parser.add_argument("--output", default="dataset/openalex.csv")
    args = parser.parse_args()

    df = collect(
        args.query,
        per_page=args.per_page,
        max_pages=args.max_pages,
        rate_limit_sec=args.rate_limit,
        email=args.email
    )
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
