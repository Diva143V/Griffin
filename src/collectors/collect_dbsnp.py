"""Collect genetic variant data from NCBI dbSNP via E-utilities and format into paper structure."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def search_snp_ids(session: requests.Session, query: str, email: str = "", limit: int = 5) -> List[str]:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "snp",
        "term": query,
        "retmode": "json",
        "retmax": limit
    }
    if email:
        params["email"] = email
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_snp_summaries(session: requests.Session, snp_ids: List[str], email: str = "") -> Dict[str, Any]:
    if not snp_ids:
        return {}
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "snp",
        "id": ",".join(snp_ids),
        "retmode": "json"
    }
    if email:
        params["email"] = email
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 5, max_pages: int = 1, rate_limit_sec: float = 0.5, email: str = "") -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "GriffinBioAgent/1.0"})
    
    variants = []
    
    # Extract gene/mutation keywords
    keywords = [w.strip() for w in query.split() if len(w.strip()) > 3]
    search_term = keywords[0] if keywords else query
    
    try:
        snp_ids = search_snp_ids(session, search_term, email=email, limit=page_size)
        if snp_ids:
            time.sleep(rate_limit_sec)
            summary_data = fetch_snp_summaries(session, snp_ids, email=email)
            result_map = summary_data.get("result", {}) or {}
            
            for snp_id in snp_ids:
                snp_info = result_map.get(snp_id, {}) or {}
                rsid = snp_info.get("title", f"rs{snp_id}")
                genes = snp_info.get("genes", []) or []
                gene_names = [g.get("name", "") for g in genes if g.get("name")]
                gene_str = ", ".join(filter(None, gene_names))
                
                clin_sig = snp_info.get("clinical_significance", "N/A")
                maf = snp_info.get("global_maf", "N/A")
                chrom = snp_info.get("chr", "N/A")
                fxn = snp_info.get("fxn_class", "N/A")
                
                abstract = (
                    f"Genetic Variation Profile: Variant Identifier: {rsid} (dbSNP ID: {snp_id}). "
                    f"Chromosome mapping: Chr {chrom} | Functional Class: {fxn}. "
                    f"Clinical Significance Status: {clin_sig} | Global Minor Allele Frequency (MAF): {maf}. "
                    f"Associated Genes: {gene_str or 'N/A'}."
                )
                
                variants.append({
                    "title": f"Genetic Variant Profile: {rsid} (Gene: {gene_str or 'N/A'})",
                    "abstract": abstract,
                    "authors": "National Center for Biotechnology Information (NCBI)",
                    "journal": "NCBI dbSNP Database",
                    "year": "N/A",
                    "doi": f"dbSNP:{rsid}" if rsid else "",
                    "pmid": snp_id,
                    "pmcid": "",
                    "source": "dbSNP",
                })
                
    except Exception as e:
        print(f"dbSNP collection failed: {e}")
        
    df = pd.DataFrame(variants)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect genetic variants from dbSNP")
    parser.add_argument("--query", default="EGFR")
    parser.add_argument("--page-size", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--rate-limit", type=float, default=0.5)
    parser.add_argument("--email", default="")
    parser.add_argument("--output", default="dataset/dbsnp.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit, email=args.email)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
