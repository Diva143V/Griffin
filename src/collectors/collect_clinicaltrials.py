"""Collect clinical trials from ClinicalTrials.gov API v2 with pagination and rate-limiting."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def fetch_page(session: requests.Session, query: str, page_size: int, page_token: str | None = None) -> Dict[str, Any]:
    url = "https://clinicaltrials.gov/api/v2/studies"
    params: Dict[str, Any] = {
        "query.term": query,
        "pageSize": page_size,
    }
    if page_token:
        params["pageToken"] = page_token
        
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 50, max_pages: int = 3, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    trials = []
    page_token = None
    
    print(f"Prominent Notification: Please check the terms of use at https://clinicaltrials.gov/ before using this data.")

    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(session, query, page_size, page_token)
        except Exception as e:
            print(f"Request failed for page {page}: {e}")
            break

        studies = data.get("studies", [])
        if not studies:
            print(f"No studies found on page {page}; stopping.")
            break

        for item in studies:
            protocol = item.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            desc = protocol.get("descriptionModule", {})
            status_mod = protocol.get("statusModule", {})
            sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
            
            nct_id = ident.get("nctId", "")
            title = ident.get("briefTitle", "")
            abstract = desc.get("briefSummary", "")
            sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "")
            
            start_date = status_mod.get("startDateStruct", {}).get("date", "")
            year = start_date[:4] if start_date else ""
            
            # Map into unified paper format
            trials.append({
                "title": title,
                "abstract": abstract,
                "authors": sponsor,
                "journal": "ClinicalTrials.gov",
                "year": year,
                "doi": f"NCTId:{nct_id}" if nct_id else "",
                "pmid": nct_id,
                "pmcid": "",
                "source": "ClinicalTrials",
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break
            
        time.sleep(rate_limit_sec)

    df = pd.DataFrame(trials)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect clinical trials from ClinicalTrials.gov")
    parser.add_argument("--query", default="metformin breast cancer")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--rate-limit", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--output", default="dataset/clinicaltrials.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
