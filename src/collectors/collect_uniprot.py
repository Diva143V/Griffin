"""Collect protein annotations from UniProt API and format into paper structure."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def fetch_proteins(session: requests.Session, query: str, limit: int = 5) -> Dict[str, Any]:
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": query,
        "size": limit,
        "format": "json"
    }
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 5, max_pages: int = 1, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "GriffinBioAgent/1.0"})
    
    proteins = []
    
    # Extract gene/protein keywords
    keywords = [w.strip() for w in query.split() if len(w.strip()) > 3]
    search_term = keywords[0] if keywords else query
    
    try:
        data = fetch_proteins(session, search_term, limit=page_size)
        results = data.get("results", [])
        
        for item in results:
            accession = item.get("primaryAccession", "")
            kb_id = item.get("uniProtkbId", "")
            
            # Extract names safely
            desc = item.get("proteinDescription", {}) or {}
            rec_name = desc.get("recommendedName", {}) or {}
            full_name = rec_name.get("fullName", {}).get("value", kb_id)
            
            organism = item.get("organism", {}).get("scientificName", "Unknown Organism")
            
            genes_list = item.get("genes", []) or []
            gene_names = [g.get("geneName", {}).get("value", "") for g in genes_list if g.get("geneName")]
            gene_str = ", ".join(filter(None, gene_names))
            
            # Find function comments
            comments = item.get("comments", []) or []
            func_desc = "No description available."
            for c in comments:
                if c.get("commentType") == "FUNCTION":
                    texts = c.get("texts", []) or []
                    func_desc = " ".join(t.get("value", "") for t in texts)
                    break
                    
            abstract = (
                f"Protein Annotation Profile: {full_name} (UniProt ID: {kb_id} | Accession: {accession}). "
                f"Organism: {organism} | Genes: {gene_str or 'N/A'}. "
                f"Function: {func_desc}"
            )
            
            proteins.append({
                "title": f"Protein Profile: {full_name} ({accession})",
                "abstract": abstract,
                "authors": "UniProt Consortium",
                "journal": "UniProtKB Database",
                "year": "N/A",
                "doi": f"UniProtKB:{accession}" if accession else "",
                "pmid": accession,
                "pmcid": "",
                "source": "UniProt",
            })
            
    except Exception as e:
        print(f"UniProt collection failed: {e}")
        
    df = pd.DataFrame(proteins)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect proteins from UniProt")
    parser.add_argument("--query", default="EGFR")
    parser.add_argument("--page-size", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--output", default="dataset/uniprot.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
